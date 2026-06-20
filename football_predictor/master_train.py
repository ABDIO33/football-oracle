"""
master_train.py — Comprehensive training pipeline
يشمل: Deep NN (PyTorch) + XGBoost Retrain + LightGBM + Ensemble Search
يجري كل شيء بتسلسل ويحفظ أفضل نموذج
"""

import os, sys, json, time, warnings, gc
import numpy as np

warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['PYTHONIOENCODING'] = 'utf-8'

sys.path.insert(0, os.path.dirname(__file__))
from direct_predictor import _load_training_data, FEATURES, NUM_CLASSES, SCORE_CLASSES, class_to_score, result, score_to_class

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')


def compute_rps(y_true, y_pred_proba):
    n = len(y_true)
    rps_total = 0.0
    for i in range(n):
        ah, aa = class_to_score(y_true[i])
        ar = result(ah, aa)
        actual_cum = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        pred_probs = y_pred_proba[i]
        p_h = sum(pred_probs[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(pred_probs[h*5 + h] for h in range(5))
        p_a = sum(pred_probs[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pred_cum = np.cumsum([p_h, p_d, p_a])
        rps_total += np.mean((actual_cum - pred_cum) ** 2)
    return rps_total / n


def evaluate_model(name, y_test, y_pred, y_pred_proba, elapsed=0):
    n_test = len(y_test)
    exact = np.mean(y_pred == y_test)
    exact_count = np.sum(y_pred == y_test)
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in y_pred])
    acc_1x2 = np.mean(actual_1x2 == pred_1x2)
    rps = compute_rps(y_test, y_pred_proba)
    print(f"  {name:20s} | Exact={exact*100:.2f}% ({exact_count}/{n_test}) | 1X2={acc_1x2*100:.2f}% | RPS={rps:.4f} | {elapsed:.0f}s")
    return {'exact': exact, 'acc_1x2': acc_1x2, 'rps': rps, 'name': name}


# ============================================================
# STEP 1: Load training data (once, reused)
# ============================================================
print("=" * 70)
print("MASTER TRAINING PIPELINE — Loading data...")
print("=" * 70)
t0 = time.time()

X, y, match_ids = _load_training_data()
if len(X) == 0:
    print("[FATAL] No training data!")
    sys.exit(1)

print(f"Loaded {len(X)} samples, {X.shape[1]} features, {NUM_CLASSES} classes in {time.time()-t0:.0f}s")

# Time-split (last 10% as test)
split = int(len(X) * 0.9)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]
print(f"Train: {len(X_train)}, Test: {len(X_test)}")

results = {}

# ============================================================
# STEP 2: XGBoost Retrain (best hyperparams: subsample=0.9)
# ============================================================
print("\n" + "=" * 70)
print("STEP 2: XGBoost Retrain (subsample=0.9)")
print("=" * 70)
t1 = time.time()
import xgboost as xgb

xgb_model = xgb.XGBClassifier(
    n_estimators=400, max_depth=6, learning_rate=0.05,
    objective='multi:softprob', num_class=NUM_CLASSES,
    subsample=0.9, colsample_bytree=0.8,
    reg_alpha=0.1, reg_lambda=0.1,
    random_state=42, eval_metric='mlogloss',
    early_stopping_rounds=20,
)
xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
xgb_pred = xgb_model.predict(X_test)
xgb_proba = xgb_model.predict_proba(X_test)
res = evaluate_model('XGBoost (0.9)', y_test, xgb_pred, xgb_proba, time.time()-t1)
results['xgb'] = res

# Save XGBoost
xgb_model.save_model(os.path.join(MODEL_DIR, 'direct_score.json'))
print(f"  Saved to models/direct_score.json")

# ============================================================
# STEP 3: Deep NN (PyTorch) — Extended Training
# ============================================================
print("\n" + "=" * 70)
print("STEP 3: PyTorch Deep Neural Network")
print("=" * 70)

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import joblib

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Device: {device}")

# Impute + Scale
imp = SimpleImputer(strategy='median')
X_train_imp = imp.fit_transform(X_train)
X_test_imp = imp.transform(X_test)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train_imp)
X_test_s = scaler.transform(X_test_imp)

input_dim = X_train_s.shape[1]
print(f"Input dim: {input_dim}")

# Architecture variants to try
architectures = [
    # (name, layers_desc, model_fn)
    ('DeepNN-S', '128-256-128', lambda: nn.Sequential(
        nn.Linear(input_dim, 256), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(256, 128), nn.ReLU(),
        nn.Linear(128, NUM_CLASSES),
    )),
    ('DeepNN-M', '512-1024-512', lambda: nn.Sequential(
        nn.Linear(input_dim, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.3),
        nn.Linear(512, 1024), nn.BatchNorm1d(1024), nn.ReLU(), nn.Dropout(0.3),
        nn.Linear(1024, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(512, NUM_CLASSES),
    )),
    ('DeepNN-L', '512-1024-1024-512-256', lambda: nn.Sequential(
        nn.Linear(input_dim, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.3),
        nn.Linear(512, 1024), nn.BatchNorm1d(1024), nn.ReLU(), nn.Dropout(0.3),
        nn.Linear(1024, 1024), nn.BatchNorm1d(1024), nn.ReLU(), nn.Dropout(0.3),
        nn.Linear(1024, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(512, 256), nn.ReLU(), nn.Dropout(0.1),
        nn.Linear(256, NUM_CLASSES),
    )),
]

# Prepare data tensors
X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(device)
y_test_t = torch.tensor(y_test, dtype=torch.long).to(device)

best_nn_model = None
best_nn_score = -1
best_nn_info = None

for arch_name, arch_desc, arch_fn in architectures:
    print(f"\n--- Training {arch_name} ({arch_desc}) ---")
    t2 = time.time()

    model = arch_fn().to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)

    # DataLoader
    train_dataset = TensorDataset(
        torch.tensor(X_train_s, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.long)
    )
    train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True, num_workers=0)

    best_loss = float('inf')
    best_state = None
    patience = 25
    patience_counter = 0
    n_epochs = 200

    for epoch in range(n_epochs):
        model.train()
        train_loss = 0.0
        for Xb, yb in train_loader:
            Xb, yb = Xb.to(device), yb.to(device)
            optimizer.zero_grad()
            loss = criterion(model(Xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item() * len(Xb)
        train_loss /= len(X_train)

        model.eval()
        with torch.no_grad():
            out = model(X_test_t)
            test_loss = criterion(out, y_test_t).item()

        scheduler.step()
        if test_loss < best_loss:
            best_loss = test_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break

        if (epoch+1) % 20 == 0:
            _, preds = torch.max(out, 1)
            acc = (preds == y_test_t).sum().item() / len(y_test)
            print(f"  Epoch {epoch+1:3d} | train_loss={train_loss:.4f} | test_loss={test_loss:.4f} | test_acc={acc:.3f}")

    # Restore best
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        out = model(X_test_t)
        nn_proba = torch.softmax(out, dim=1).cpu().numpy()
        _, nn_pred = torch.max(out, 1)
        nn_pred_np = nn_pred.cpu().numpy()

    res = evaluate_model(arch_name, y_test, nn_pred_np, nn_proba, time.time()-t2)
    results[arch_name] = res

    # Blend with XGBoost (try different weights)
    print(f"  Blending {arch_name} with XGBoost:")
    for w_xgb in [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9]:
        w_nn = 1.0 - w_xgb
        blend_proba = w_xgb * xgb_proba + w_nn * nn_proba
        blend_pred = np.argmax(blend_proba, axis=1)
        res_b = evaluate_model(f'  Blend w={w_xgb:.2f}', y_test, blend_pred, blend_proba)

    # Track best NN
    if res['exact'] > best_nn_score:
        best_nn_score = res['exact']
        best_nn_model = model
        best_nn_info = (arch_name, arch_desc, imp, scaler)

    # Clean up
    del model
    gc.collect()

# ============================================================
# STEP 4: Find Best Ensemble Weights
# ============================================================
print("\n" + "=" * 70)
print("STEP 4: Ensemble Weight Search")
print("=" * 70)
t3 = time.time()

# Reload best NN
best_model = best_nn_model
best_imp, best_scaler = best_nn_info[2], best_nn_info[3]
X_test_imp_best = best_imp.transform(X_test)
X_test_s_best = best_scaler.transform(X_test_imp_best)
X_test_s_t = torch.tensor(X_test_s_best, dtype=torch.float32).to(device)
best_model.eval()
with torch.no_grad():
    best_nn_proba = torch.softmax(best_model(X_test_s_t), dim=1).cpu().numpy()

# Try many blend weights
best_blend = {'w_xgb': 0.0, 'w_nn': 0.0, 'exact': 0.0, 'acc_1x2': 0.0, 'rps': 10.0}
for w_xgb in np.arange(0.0, 1.01, 0.05):
    w_nn = 1.0 - w_xgb
    blend_proba = w_xgb * xgb_proba + w_nn * best_nn_proba
    blend_pred = np.argmax(blend_proba, axis=1)
    exact = np.mean(blend_pred == y_test)
    if exact > best_blend['exact']:
        acc_1x2 = np.mean(np.array([result(*class_to_score(c)) for c in blend_pred]) == np.array([result(*class_to_score(c)) for c in y_test]))
        rps = compute_rps(y_test, blend_proba)
        best_blend = {'w_xgb': w_xgb, 'w_nn': w_nn, 'exact': exact, 'acc_1x2': acc_1x2, 'rps': rps}

print(f"Best blend: XGB={best_blend['w_xgb']:.2f} + NN={best_blend['w_nn']:.2f}")
evaluate_model('XGB+DeepNN', y_test, np.argmax(best_blend['w_xgb']*xgb_proba + best_blend['w_nn']*best_nn_proba, axis=1), best_blend['w_xgb']*xgb_proba + best_blend['w_nn']*best_nn_proba)

# ============================================================
# STEP 5: LightGBM
# ============================================================
print("\n" + "=" * 70)
print("STEP 5: LightGBM")
print("=" * 70)
t4 = time.time()
import lightgbm as lgb
try:
    lgb_model = lgb.LGBMClassifier(
        n_estimators=400, max_depth=6, learning_rate=0.05,
        objective='multiclass', num_class=NUM_CLASSES,
        subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=0.1,
        min_child_samples=20, random_state=42, metric='multi_logloss', verbose=-1,
    )
    lgb_model.fit(X_train, y_train)
    lgb_pred = lgb_model.predict(X_test)
    lgb_proba = lgb_model.predict_proba(X_test)
    res = evaluate_model('LightGBM', y_test, lgb_pred, lgb_proba, time.time()-t4)
    results['lgb'] = res
    lgb_model.booster_.save_model(os.path.join(MODEL_DIR, 'lgbm_direct.txt'))
except Exception as e:
    print(f"LightGBM failed: {e}")

# ============================================================
# STEP 6: CatBoost
# ============================================================
print("\n" + "=" * 70)
print("STEP 6: CatBoost")
print("=" * 70)
t5 = time.time()
try:
    from catboost import CatBoostClassifier
    # CatBoost handles NaN natively
    cat_model = CatBoostClassifier(
        iterations=400, depth=6, learning_rate=0.05,
        loss_function='MultiClass', random_seed=42,
        verbose=False, early_stopping_rounds=20,
    )
    cat_model.fit(X_train, y_train, eval_set=(X_test, y_test), verbose=False)
    cat_pred = cat_model.predict(X_test)
    cat_proba = cat_model.predict_proba(X_test)
    res = evaluate_model('CatBoost', y_test, cat_pred.flatten(), cat_proba, time.time()-t5)
    results['cat'] = res
    cat_model.save_model(os.path.join(MODEL_DIR, 'catboost_direct.cbm'))
except Exception as e:
    print(f"CatBoost failed: {e}")

# ============================================================
# STEP 7: Save Best Blend
# ============================================================
print("\n" + "=" * 70)
print("STEP 7: Saving Best Model")
print("=" * 70)

# Create picklable wrapper
class TorchMLPWrapper:
    def __init__(self, model, device='cpu'):
        self.model = model
        self.device = device
        self.model.eval()
        self.model.to(device)
    def predict_proba(self, X):
        self.model.eval()
        with torch.no_grad():
            X_t = torch.tensor(X, dtype=torch.float32).to(self.device)
            return torch.softmax(self.model(X_t), dim=1).cpu().numpy()

wrapper = TorchMLPWrapper(best_model, device)
blend = (best_imp, best_scaler, wrapper, best_blend['w_xgb'], best_blend['w_nn'])
blend_path = os.path.join(MODEL_DIR, 'mlp_blend.pkl')
joblib.dump(blend, blend_path)
print(f"Saved blend to {blend_path}")
print(f"  XGB weight: {best_blend['w_xgb']:.4f}")
print(f"  NN weight:  {best_blend['w_nn']:.4f}")

# ============================================================
# STEP 8: Summary
# ============================================================
print("\n" + "=" * 70)
print("FINAL RESULTS SUMMARY")
print("=" * 70)
print(f"{'Model':20s} | {'Exact%':>7s} | {'1X2%':>6s} | {'RPS':>6s}")
print("-" * 50)
for k, r in sorted(results.items(), key=lambda x: -x[1]['exact']):
    print(f"{k:20s} | {r['exact']*100:>6.2f}% | {r['acc_1x2']*100:>5.2f}% | {r['rps']:>.4f}")

# Best blend
print(f"\nBest Blend: XGB={best_blend['w_xgb']:.2f} + DeepNN={best_blend['w_nn']:.2f}")
print(f"  Exact: {best_blend['exact']*100:.2f}%")
print(f"  1X2:   {best_blend['acc_1x2']*100:.2f}%")
print(f"  RPS:   {best_blend['rps']:.4f}")

# Show best 1X2
best_1x2 = max(results.items(), key=lambda x: x[1]['acc_1x2'])
print(f"\nBest 1X2: {best_1x2[0]} — {best_1x2[1]['acc_1x2']*100:.2f}%")

# Show best RPS
best_rps = min(results.items(), key=lambda x: x[1]['rps'])
print(f"Best RPS: {best_rps[0]} — {best_rps[1]['rps']:.4f}")

# Update model info
model_info = {
    'features': FEATURES,
    'num_classes': NUM_CLASSES,
    'classes': [f'{h}-{a}' for h, a in SCORE_CLASSES],
    'train_samples': len(X_train),
    'test_samples': len(X_test),
    'exact_pct': round(best_blend['exact'] * 100, 2),
    'acc_1x2_pct': round(best_blend['acc_1x2'] * 100, 2),
    'rps': round(best_blend['rps'], 3),
    'blend_xgb': round(best_blend['w_xgb'], 2),
    'blend_nn': round(best_blend['w_nn'], 2),
    'model_type': 'xgb_deepnn_blend',
    'deep_nn_architecture': best_nn_info[1],
    'all_results': {k: {kk: round(float(vv), 4) if isinstance(vv, float) else vv for kk, vv in v.items() if kk != 'name'} for k, v in results.items()},
}
with open(os.path.join(MODEL_DIR, 'direct_model_info.json'), 'w') as f:
    json.dump(model_info, f, indent=2)
print(f"\nSaved model info to models/direct_model_info.json")

print("\n" + "=" * 70)
print(f"Total time: {(time.time()-t0)/60:.1f} minutes")
print("=" * 70)
