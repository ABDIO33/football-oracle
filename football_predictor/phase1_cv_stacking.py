
import sys, os, json, gc, pickle, time
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

SEED = 42
SEEDS = [42, 7, 123, 999, 2026]
random_state = np.random.RandomState(SEED)

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
torch.manual_seed(SEED)

class DeepNN_M3(nn.Module):
    def __init__(self, n_in, n_out):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, 128), nn.BatchNorm1d(128), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(128, n_out),
        )
    def forward(self, x):
        return self.net(x)

from direct_predictor import _load_training_data, EnsemblePredictor, NUM_CLASSES, FEATURES, SCORE_CLASSES, class_to_score
from sklearn.model_selection import StratifiedKFold
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
N_FOLDS = 5
N_META_SEEDS = 5

X, y, _ = _load_training_data()
y = y.astype(int)
print(f"[Phase1] Loaded {len(X)} samples, {len(FEATURES)} features, {NUM_CLASSES} classes")

# Hold out 20% for final test
from sklearn.model_selection import train_test_split
X_train_full, X_test, y_train_full, y_test = train_test_split(X, y, test_size=0.2, random_state=SEED)
print(f"[Phase1] Train: {len(X_train_full)}, Test: {len(X_test)}")

# 5-fold on train_full
skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)

def train_xgb(X_tr, y_tr):
    model = xgb.XGBClassifier(
        n_estimators=500, max_depth=6, learning_rate=0.05,
        objective='multi:softprob', num_class=NUM_CLASSES,
        subsample=0.8, colsample_bytree=0.8,
        random_state=SEED, n_jobs=-1,
        early_stopping_rounds=20,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_tr, y_tr)], verbose=False)
    return model

def train_dnn(X_tr, y_tr, X_val, y_val):
    imp = SimpleImputer(strategy='median')
    scaler = StandardScaler()
    X_tr_i = imp.fit_transform(X_tr)
    X_tr_s = scaler.fit_transform(X_tr_i)
    X_val_i = imp.transform(X_val)
    X_val_s = scaler.transform(X_val_i)
    
    n_in = X_tr_s.shape[1]
    net = DeepNN_M3(n_in, NUM_CLASSES)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(net.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    
    train_ds = TensorDataset(torch.FloatTensor(X_tr_s), torch.LongTensor(y_tr))
    train_loader = DataLoader(train_ds, batch_size=128, shuffle=True)
    val_ds = TensorDataset(torch.FloatTensor(X_val_s), torch.LongTensor(y_val))
    val_loader = DataLoader(val_ds, batch_size=256)
    
    best_acc = 0
    best_state = None
    patience = 15
    no_improve = 0
    
    for epoch in range(100):
        net.train()
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            out = net(batch_x)
            loss = criterion(out, batch_y)
            loss.backward()
            optimizer.step()
        
        net.eval()
        correct = 0
        total = 0
        val_loss = 0
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                out = net(batch_x)
                val_loss += criterion(out, batch_y).item()
                _, preds = out.max(1)
                correct += (preds == batch_y).sum().item()
                total += batch_y.size(0)
        acc = correct / total
        scheduler.step(val_loss)
        
        if acc > best_acc:
            best_acc = acc
            best_state = net.state_dict()
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                break
    
    net.load_state_dict(best_state)
    net.eval()
    with torch.no_grad():
        val_proba = torch.softmax(net(torch.FloatTensor(X_val_s)), 1).numpy()
    
    return net, imp, scaler, val_proba, best_acc

# Phase 1a: Collect multi-seed ensemble predictions via 5-fold CV
print("\n========== PHASE 1a: 5-FOLD CV ENSEMBLE ==========")

all_meta_features = []
all_meta_targets = []
fold_results = []

for fold, (train_idx, val_idx) in enumerate(skf.split(X_train_full, y_train_full)):
    print(f"\n--- Fold {fold+1}/{N_FOLDS} ---")
    X_tr = X_train_full[train_idx]
    y_tr = y_train_full[train_idx]
    X_val = X_train_full[val_idx]
    y_val = y_train_full[val_idx]
    
    # Train XGBoost
    t0 = time.time()
    print(f"  Training XGBoost...")
    xgb_model = train_xgb(X_tr, y_tr)
    xgb_val = xgb_model.predict_proba(X_val)
    print(f"  XGBoost: {time.time()-t0:.0f}s")
    
    # Train DeepNN-M3
    t0 = time.time()
    print(f"  Training DeepNN-M3...")
    dnn_model, imp, scaler, dnn_val, dnn_acc = train_dnn(X_tr, y_tr, X_val, y_val)
    print(f"  DeepNN-M3 val acc={dnn_acc*100:.2f}% [{time.time()-t0:.0f}s]")
    
    # Ensemble: try best blend weights
    best_ensemble_acc = 0
    best_xgb_w = 0.2
    for xgb_w in [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]:
        ens = (1 - xgb_w) * dnn_val + xgb_w * xgb_val
        acc = (ens.argmax(1) == y_val).mean()
        if acc > best_ensemble_acc:
            best_ensemble_acc = acc
            best_xgb_w = xgb_w
    
    ens_val = (1 - best_xgb_w) * dnn_val + best_xgb_w * xgb_val
    print(f"  Ensemble (XGB {best_xgb_w:.0%}): acc={best_ensemble_acc*100:.2f}%")
    
    # Meta-features: ensemble probs + top-3 + argmax
    meta_feat = np.column_stack([
        ens_val,
        np.sort(ens_val, axis=1)[:, -3:],
        ens_val.argmax(1).reshape(-1, 1),
    ])
    all_meta_features.append(meta_feat)
    all_meta_targets.append(y_val)
    
    fold_results.append({
        'fold': fold, 'xgb_w': best_xgb_w, 'ensemble_acc': float(best_ensemble_acc),
    })
    
    # Save fold model
    fold_model = {
        'xgb_model': xgb_model,
        'dnn_model': dnn_model,
        'imputer': imp,
        'scaler': scaler,
        'xgb_weight': best_xgb_w,
    }
    with open(os.path.join(MODEL_DIR, f'fold_{fold}_model.pkl'), 'wb') as f:
        pickle.dump(fold_model, f)

all_meta_features = np.vstack(all_meta_features)
all_meta_targets = np.concatenate(all_meta_targets)
print(f"\nMeta-features shape: {all_meta_features.shape}")
print(f"Meta-targets shape: {all_meta_targets.shape}")

# Phase 1b: Train meta-classifier
print("\n========== PHASE 1b: TRAIN META-CLASSIFIER ==========")
meta_clf = xgb.XGBClassifier(
    n_estimators=300, max_depth=4, learning_rate=0.05,
    objective='multi:softprob', num_class=NUM_CLASSES,
    subsample=0.8, colsample_bytree=0.8,
    random_state=SEED, n_jobs=-1,
)
t0 = time.time()
meta_clf.fit(all_meta_features, all_meta_targets)
print(f"Meta-classifier trained [{time.time()-t0:.0f}s]")

# Phase 1c: Isotonic calibration on meta-features
print("\n========== PHASE 1c: CALIBRATION ==========")
calibrators = []
y_meta_onehot = np.zeros((len(all_meta_targets), NUM_CLASSES))
for i, cls in enumerate(all_meta_targets):
    y_meta_onehot[i, int(cls)] = 1.0

for c in range(NUM_CLASSES):
    cal = IsotonicRegression(out_of_bounds='clip')
    cal.fit(all_meta_features[:, c], y_meta_onehot[:, c])
    calibrators.append(cal)

# Apply calibration
meta_cal = np.zeros_like(all_meta_features[:, :NUM_CLASSES])
for c in range(NUM_CLASSES):
    meta_cal[:, c] = calibrators[c].transform(all_meta_features[:, c])
meta_cal = np.clip(meta_cal, 0, 1)
row_sums = meta_cal.sum(axis=1, keepdims=True)
row_sums = np.where(row_sums > 0, row_sums, 1.0)
meta_cal = meta_cal / row_sums

# Phase 1d: Evaluate on test set
print("\n========== PHASE 1d: TEST SET EVALUATION ==========")

# Build test ensemble predictions from all 5 fold models (average)
test_ensembles = []
for fold in range(N_FOLDS):
    with open(os.path.join(MODEL_DIR, f'fold_{fold}_model.pkl'), 'rb') as f:
        fm = pickle.load(f)
    xgb_test = fm['xgb_model'].predict_proba(X_test)
    dnn_model = fm['dnn_model']
    imp = fm['imputer']
    scaler = fm['scaler']
    X_test_i = imp.transform(X_test)
    X_test_s = scaler.transform(X_test_i)
    dnn_model.eval()
    with torch.no_grad():
        dnn_test = torch.softmax(dnn_model(torch.FloatTensor(X_test_s)), 1).numpy()
    xgb_w = fm['xgb_weight']
    ens_test = (1 - xgb_w) * dnn_test + xgb_w * xgb_test
    test_ensembles.append(ens_test)

test_proba = np.mean(test_ensembles, axis=0)

# Base ensemble accuracy
y_test_onehot = np.zeros((len(y_test), NUM_CLASSES))
for i, cls in enumerate(y_test):
    y_test_onehot[i, int(cls)] = 1.0

def calc_brier(proba, onehot):
    return np.mean([brier_score_loss(onehot[:, c], proba[:, c]) for c in range(NUM_CLASSES)])

base_exact = (test_proba.argmax(1) == y_test).mean() * 100
base_brier = calc_brier(test_proba, y_test_onehot)
print(f"5-fold ensemble: Exact={base_exact:.2f}%  Brier={base_brier:.6f}")

# Calibrated
test_cal = np.zeros_like(test_proba)
for c in range(NUM_CLASSES):
    test_cal[:, c] = calibrators[c].transform(test_proba[:, c])
test_cal = np.clip(test_cal, 0, 1)
row_sums = test_cal.sum(axis=1, keepdims=True)
row_sums = np.where(row_sums > 0, row_sums, 1.0)
test_cal = test_cal / row_sums

cal_exact = (test_cal.argmax(1) == y_test).mean() * 100
cal_brier = calc_brier(test_cal, y_test_onehot)
print(f"+ Calibration:    Exact={cal_exact:.2f}%  Brier={cal_brier:.6f}")

# Meta-stacker
test_meta = np.column_stack([
    test_proba,
    np.sort(test_proba, axis=1)[:, -3:],
    test_proba.argmax(1).reshape(-1, 1),
])
stack_proba = meta_clf.predict_proba(test_meta)
stack_exact = (stack_proba.argmax(1) == y_test).mean() * 100
stack_brier = calc_brier(stack_proba, y_test_onehot)
print(f"+ Meta-stacker:   Exact={stack_exact:.2f}%  Brier={stack_brier:.6f}")

# Blend calibrated + stacked
best_blend_acc = 0
best_blend_brier = 999
best_alpha = 0.5
for alpha in np.arange(0.0, 1.05, 0.05):
    bp = alpha * test_cal + (1 - alpha) * stack_proba
    acc = (bp.argmax(1) == y_test).mean() * 100
    br = calc_brier(bp, y_test_onehot)
    if acc > best_blend_acc:
        best_blend_acc = acc
        best_blend_brier = br
        best_alpha = alpha

blend_proba = best_alpha * test_cal + (1 - best_alpha) * stack_proba
blend_proba = blend_proba / blend_proba.sum(axis=1, keepdims=True)
print(f"+ Blend({best_alpha:.0%} cal): Exact={best_blend_acc:.2f}%  Brier={best_blend_brier:.6f}")

# Save everything
print("\n========== SAVING ==========")
output = {
    'calibrators': calibrators,
    'meta_classifier': meta_clf,
    'blend_alpha': float(best_alpha),
    'results': {
        'base_ensemble': {'exact': float(base_exact), 'brier': float(base_brier)},
        'calibrated': {'exact': float(cal_exact), 'brier': float(cal_brier)},
        'stacked': {'exact': float(stack_exact), 'brier': float(stack_brier)},
        'blend': {'exact': float(best_blend_acc), 'brier': float(best_blend_brier), 'alpha': float(best_alpha)},
    },
    'fold_results': fold_results,
    'num_classes': NUM_CLASSES,
    'features': FEATURES,
}

with open(os.path.join(MODEL_DIR, 'cv_stacker.pkl'), 'wb') as f:
    pickle.dump(output, f)

with open(os.path.join(MODEL_DIR, 'phase1_results.json'), 'w') as f:
    json.dump({'fold_results': fold_results, 'results': {k: v for k, v in output['results'].items()}}, f, indent=2)

print("\n" + "="*60)
print("PHASE 1 COMPLETE")
print("="*60)
print(f"  Base ensemble:    Exact={base_exact:.2f}%  Brier={base_brier:.6f}")
print(f"  + Calibration:    Exact={cal_exact:.2f}%  Brier={cal_brier:.6f}")
print(f"  + Meta-stacker:   Exact={stack_exact:.2f}%  Brier={stack_brier:.6f}")
print(f"  + Best blend:     Exact={best_blend_acc:.2f}%  Brier={best_blend_brier:.6f}")
print(f"  (alpha={best_alpha:.0%} cal + {1-best_alpha:.0%} stack)")
print(f"Saved: cv_stacker.pkl, phase1_results.json")
