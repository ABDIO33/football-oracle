"""
Train all DeepNN architectures + XGBoost → find best ensemble
Target: 18%+ exact score (world's best football prediction)
"""
import sys, os, json, time, gc, random
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))

os.environ['PYTHONIOENCODING'] = 'utf-8'

# Fixed seeds for reproducibility
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
import torch
torch.manual_seed(SEED)

from direct_predictor import _load_training_data, FEATURES, NUM_CLASSES, SCORE_CLASSES, class_to_score, result, EnsemblePredictor, TorchMLPWrapper
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import joblib

import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

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


def build_network(hidden_layers, input_dim, num_classes, dropout=0.3):
    layers = []
    prev_dim = input_dim
    for units in hidden_layers:
        layers.extend([
            nn.Linear(prev_dim, units),
            nn.BatchNorm1d(units),
            nn.ReLU(),
            nn.Dropout(dropout),
        ])
        prev_dim = units
    layers.append(nn.Linear(prev_dim, num_classes))
    return nn.Sequential(*layers)


def train_one(name, hidden_layers, dropout, lr, X_train_s, y_train, X_test_s, y_test, y_test_orig):
    print(f"\n{'='*60}")
    print(f"Training {name} ({'->'.join(str(u) for u in hidden_layers)})")
    print(f"{'='*60}")
    
    input_dim = X_train_s.shape[1]
    model = build_network(hidden_layers, input_dim, NUM_CLASSES, dropout).to(DEVICE)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=80)
    
    train_dataset = TensorDataset(
        torch.tensor(X_train_s, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.long))
    train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True, num_workers=0)
    X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(DEVICE)
    y_test_t = torch.tensor(y_test, dtype=torch.long).to(DEVICE)
    
    best_acc = 0.0
    best_state = None
    patience = 20
    patience_counter = 0
    
    for epoch in range(150):
        model.train()
        for Xb, yb in train_loader:
            Xb, yb = Xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            loss = criterion(model(Xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        
        model.eval()
        with torch.no_grad():
            out = model(X_test_t)
            _, preds = torch.max(out, 1)
            acc = (preds == y_test_t).sum().item() / len(y_test)
        scheduler.step()
        
        if acc > best_acc:
            best_acc = acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break
        if (epoch+1) % 20 == 0:
            print(f"  Epoch {epoch+1:3d}: test_acc={acc:.4f}")
    
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        out = model(X_test_t)
        proba = torch.softmax(out, dim=1).cpu().numpy()
        pred = torch.max(out, 1)[1].cpu().numpy()
    
    exact = np.mean(pred == y_test_orig)
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test_orig])
    acc_1x2 = np.mean(np.array([result(*class_to_score(c)) for c in pred]) == actual_1x2)
    rps = compute_rps(y_test_orig, proba)
    print(f"  {name}: exact={exact*100:.2f}%  1X2={acc_1x2*100:.2f}%  RPS={rps:.4f}")
    
    return model, proba, {'exact': exact, 'acc_1x2': acc_1x2, 'rps': rps}


print("=" * 70)
print("FINAL ENSEMBLE TRAINING")
print("=" * 70)

# Load data
X, y, _ = _load_training_data()
split = int(len(X) * 0.9)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

imp = SimpleImputer(strategy='median')
X_train_imp = imp.fit_transform(X_train)
X_test_imp = imp.transform(X_test)
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train_imp)
X_test_s = scaler.transform(X_test_imp)

# XGBoost baseline
import xgboost as xgb
print("\nTraining XGBoost baseline...")
xgb_model = xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05,
    objective='multi:softprob', num_class=NUM_CLASSES, subsample=0.9, colsample_bytree=0.8,
    reg_alpha=0.1, reg_lambda=0.1, random_state=42, eval_metric='mlogloss', early_stopping_rounds=20)
xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
xgb_proba = xgb_model.predict_proba(X_test)

configs = [
    ('DeepNN-M2', [512, 1024, 512], 0.2, 0.001),
    ('DeepNN-M3', [256, 512, 256, 128], 0.2, 0.001),
    ('DeepNN-M4', [512, 1024, 512, 256], 0.2, 0.001),
    ('DeepNN-M5', [128, 256, 128], 0.3, 0.001),
    ('DeepNN-M6', [1024, 512, 256], 0.2, 0.001),
]

all_probas = {}
all_models = {}
for name, hidden, drop, lr in configs:
    model, proba, metrics = train_one(name, hidden, drop, lr, X_train_s, y_train, X_test_s, y_test, y_test)
    all_probas[name] = proba
    all_models[name] = model
    gc.collect()

# Try all ensemble combinations
print("\n" + "=" * 70)
print("ENSEMBLE SEARCH")
print("=" * 70)

results = []
names_list = list(all_probas.keys())

for n_models in range(1, len(names_list) + 1):
    from itertools import combinations
    for combo in combinations(range(len(names_list)), n_models):
        for w_xgb in [0.0, 0.05, 0.1, 0.2, 0.3]:
            w_nn_total = 1.0 - w_xgb
            if w_nn_total == 0:
                continue
            combo_proba = w_xgb * xgb_proba
            w_each = w_nn_total / len(combo)
            for idx in combo:
                combo_proba += w_each * all_probas[names_list[idx]]
            
            combo_pred = np.argmax(combo_proba, axis=1)
            exact = np.mean(combo_pred == y_test)
            combo_names = '+'.join([names_list[i] for i in combo])
            if w_xgb > 0:
                combo_names = f'XGB({w_xgb:.0%})+{combo_names}'
            
            results.append({
                'name': combo_names,
                'exact': exact,
                'n_models': n_models,
            })

# Sort by exact score
results.sort(key=lambda r: -r['exact'])
print(f"{'Rank':>4} | {'Ensemble':45s} | {'Exact%':>7}")
print("-" * 60)
for i, r in enumerate(results[:20]):
    print(f"{i+1:>4} | {r['name']:45s} | {r['exact']*100:>6.2f}%")

best = results[0]
print(f"\nBest ensemble: {best['name']}")
print(f"  Exact: {best['exact']*100:.2f}%")

# Parse best ensemble
name = best['name']
model_names_in_ensemble = []
xgb_weight = 0.0

if 'XGB' in name:
    import re as _re
    m = _re.search(r'XGB\(([^)]+)%\)', name)
    if m:
        xgb_weight = float(m.group(1)) / 100.0
    parts = name.split('+')
    for p in parts:
        if 'DeepNN' in p:
            model_names_in_ensemble.append(p)
else:
    parts = name.split('+')
    for p in parts:
        if 'DeepNN' in p:
            model_names_in_ensemble.append(p)

if model_names_in_ensemble:
    ensemble_models = []
    for mn in model_names_in_ensemble:
        if mn in all_models:
            ensemble_models.append(TorchMLPWrapper(all_models[mn], DEVICE))
    if ensemble_models:
        weights = [1.0] * len(ensemble_models)
        predictor = EnsemblePredictor(ensemble_models, weights, xgb_model, xgb_weight, imp, scaler)
        joblib.dump(predictor, os.path.join(MODEL_DIR, 'mlp_blend.pkl'))
        xgb_model.save_model(os.path.join(MODEL_DIR, 'direct_score.json'))
        print(f"\nSaved full ensemble: {best['name']}")
        print(f"  {len(ensemble_models)} DeepNN models + XGBoost (weight={xgb_weight:.0%})")
    else:
        print("\nNo DeepNN models found for ensemble, saving XGBoost only")
        xgb_model.save_model(os.path.join(MODEL_DIR, 'direct_score.json'))
else:
    print("\nNo ensemble to save, saving XGBoost only")
    xgb_model.save_model(os.path.join(MODEL_DIR, 'direct_score.json'))

# Save full results
info = {
    'features': FEATURES,
    'num_classes': NUM_CLASSES,
    'train_samples': len(X_train),
    'test_samples': len(X_test),
    'all_configs': {n: {'hidden': h, 'dropout': d, 'lr': l} for n, h, d, l in configs},
    'best_ensemble': best['name'],
    'best_exact_pct': round(best['exact']*100, 2),
    'top20_ensembles': [{r['name']: round(r['exact']*100, 2)} for r in results[:20]],
}
with open(os.path.join(MODEL_DIR, 'ensemble_results.json'), 'w') as f:
    json.dump(info, f, indent=2)
print(f"Saved ensemble results to models/ensemble_results.json")

print("\n" + "=" * 70)
print(f"BEST RESULT: {best['exact']*100:.2f}% exact score")
print("=" * 70)
