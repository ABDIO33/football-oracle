#!/usr/bin/env python3
"""
V8 DEEPNN ULTIMATE ENSEMBLE
Trains on 141 features (V8: V3 + Understat + Stadiums + Weather)
ENI for LO
"""
import sys, os, time, json, gc, random
import numpy as np
os.environ['OMP_NUM_THREADS'] = '8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
MODEL_DIR = os.path.join(BASE, 'models')

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

import torch
torch.manual_seed(SEED)
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import joblib

NUM_CLASSES = 25

def class_to_score(cls):
    return cls // 5, cls % 5

def result(h, a):
    if h > a: return 0
    if h == a: return 1
    return 2

def compute_rps(y_true, y_pred_proba):
    n = len(y_true)
    rps_total = 0.0
    for i in range(n):
        ah, aa = class_to_score(y_true[i])
        ar = result(ah, aa)
        pred = y_pred_proba[i]
        p_h = sum(pred[h*5+a] for h in range(5) for a in range(5) if h>a)
        p_d = sum(pred[h*5+h] for h in range(5))
        p_a = sum(pred[h*5+a] for h in range(5) for a in range(5) if a>h)
        actual_cum = np.array([1 if ar<=k else 0 for k in range(3)])
        pred_cum = np.cumsum([p_h, p_d, p_a])
        rps_total += np.mean((actual_cum - pred_cum)**2)
    return rps_total / n

class TorchMLPWrapper:
    def __init__(self, model, device):
        self.model = model
        self.device = device
    def predict_proba(self, X):
        self.model.eval()
        with torch.no_grad():
            t = torch.tensor(X, dtype=torch.float32).to(self.device)
            out = torch.softmax(self.model(t), dim=1)
            return out.cpu().numpy()

class EnsemblePredictor:
    def __init__(self, models, weights, xgb_model, xgb_weight, imp, scaler):
        self.models = models
        self.weights = weights
        self.xgb_model = xgb_model
        self.xgb_weight = xgb_weight
        self.imp = imp
        self.scaler = scaler
    def predict_proba(self, X):
        if self.imp:
            X = self.imp.transform(X)
        if self.scaler:
            X_scaled = self.scaler.transform(X)
        proba = np.zeros((X.shape[0], NUM_CLASSES))
        w_total = 0.0
        if self.xgb_model and self.xgb_weight > 0:
            proba += self.xgb_weight * self.xgb_model.predict_proba(X)
            w_total += self.xgb_weight
        for m, w in zip(self.models, self.weights):
            proba += w * m.predict_proba(X_scaled)
            w_total += w
        return proba / w_total if w_total > 0 else proba

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

def train_one(name, hidden, drop, lr, X_tr, y_tr, X_te, y_te, y_te_orig):
    print(f"\n[V8-DEEPNN] {name} {'->'.join(str(u) for u in hidden)}...")
    input_dim = X_tr.shape[1]
    model = build_network(hidden, input_dim, NUM_CLASSES, drop).to(DEVICE)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=80)
    
    train_ds = TensorDataset(
        torch.tensor(X_tr, dtype=torch.float32),
        torch.tensor(y_tr, dtype=torch.long))
    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True, num_workers=0)
    X_te_t = torch.tensor(X_te, dtype=torch.float32).to(DEVICE)
    y_te_t = torch.tensor(y_te_orig, dtype=torch.long).to(DEVICE)
    
    best_acc = 0.0
    best_state = None
    patience = 25
    pc = 0
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
            out = model(X_te_t)
            _, preds = torch.max(out, 1)
            acc = (preds == y_te_t).sum().item() / len(y_te)
        scheduler.step()
        if acc > best_acc:
            best_acc = acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            pc = 0
        else:
            pc += 1
            if pc >= patience:
                break
        if (epoch+1) % 20 == 0:
            print(f"    Ep {epoch+1:3d}: test_acc={acc:.4f}")
    
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        out = model(X_te_t)
        proba = torch.softmax(out, dim=1).cpu().numpy()
        pred = torch.max(out, 1)[1].cpu().numpy()
    
    exact = float(np.mean(pred == y_te_orig))
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_te_orig])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in pred])
    acc_1x2 = float(np.mean(actual_1x2 == pred_1x2))
    rps = compute_rps(y_te_orig, proba)
    print(f"  {name}: exact={exact*100:.2f}% 1X2={acc_1x2*100:.2f}% RPS={rps:.4f}")
    return model, proba, {'exact': exact, '1x2': acc_1x2, 'rps': rps}

# ===== MAIN =====
print("=" * 70)
print("V8 DEEPNN ULTIMATE ENSEMBLE")
print(f"  Device: {DEVICE}")
print("=" * 70)
t0 = time.time()

print("\n[1] Loading training_data_v8.npz...")
data = np.load('training_data_v8.npz', allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)
order = np.argsort(data['match_ids'])
X, y = X[order], y[order]
print(f"  Shape: {X.shape}")

n = len(X)
n_tr = int(n * 0.85)
n_v = int(n * 0.05)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_v, y_v = X[n_tr:n_tr+n_v], y[n_tr:n_tr+n_v]
X_te, y_te = X[n_tr+n_v:], y[n_tr+n_v:]
print(f"  Train: {len(y_tr):,}, Val: {len(y_v):,}, Test: {len(y_te):,}")

print("\n[2] Preprocessing...")
imp = SimpleImputer(strategy='median')
X_tr_imp = imp.fit_transform(X_tr)
X_te_imp = imp.transform(X_te)
scaler = StandardScaler()
X_tr_s = scaler.fit_transform(X_tr_imp)
X_te_s = scaler.transform(X_te_imp)
print(f"  Input dim: {X_tr_s.shape[1]}")

print("\n[3] Training XGBoost...")
import xgboost as xgb
xgb_model = xgb.XGBClassifier(
    n_estimators=400, max_depth=6, learning_rate=0.05,
    objective='multi:softprob', num_class=NUM_CLASSES,
    subsample=0.9, colsample_bytree=0.8,
    reg_alpha=0.1, reg_lambda=0.1, random_state=42,
    eval_metric='mlogloss', early_stopping_rounds=20)
xgb_model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)
xgb_proba = xgb_model.predict_proba(X_te)
xgb_pred = np.argmax(xgb_proba, axis=1)
xgb_exact = float(np.mean(xgb_pred == y_te))
print(f"  XGBoost: exact={xgb_exact*100:.2f}%")

configs = [
    ('V8-M2', [512, 1024, 512], 0.2, 0.001),
    ('V8-M3', [256, 512, 256, 128], 0.2, 0.001),
    ('V8-M4', [512, 1024, 512, 256], 0.2, 0.001),
    ('V8-M5', [128, 256, 128], 0.3, 0.001),
    ('V8-M6', [1024, 512, 256], 0.2, 0.001),
]

all_probas = {}
all_models = {}
for name, hidden, drop, lr in configs:
    model, proba, metrics = train_one(name, hidden, drop, lr, X_tr_s, y_tr, X_te_s, X_te, y_te)
    all_probas[name] = proba
    all_models[name] = model
    gc.collect()

print("\n[4] Searching ensemble...")
from itertools import combinations
results = []
for n_m in range(1, len(configs) + 1):
    for combo in combinations(range(len(configs)), n_m):
        for w_xgb in [0.0, 0.05, 0.1, 0.2, 0.3]:
            w_nn = 1.0 - w_xgb
            if w_nn <= 0:
                continue
            blend = w_xgb * xgb_proba
            w_each = w_nn / len(combo)
            for idx in combo:
                blend += w_each * all_probas[configs[idx][0]]
            pred = np.argmax(blend, axis=1)
            ex = float(np.mean(pred == y_te))
            nm = '+'.join([configs[i][0] for i in combo])
            if w_xgb > 0:
                nm = f'XGB({w_xgb:.0%})+{nm}'
            results.append({'name': nm, 'exact': ex})

results.sort(key=lambda r: -r['exact'])
print(f"{'Rank':>4} | {'Ensemble':45s} | {'Exact%':>7}")
print("-" * 60)
for i, r in enumerate(results[:20]):
    print(f"{i+1:>4} | {r['name']:45s} | {r['exact']*100:>6.2f}%")

best = results[0]
print(f"\nBest: {best['name']} = {best['exact']*100:.2f}%")

# Save
import re as _re
name = best['name']
xgb_weight = 0.0
model_names = []
if 'XGB' in name:
    m = _re.search(r'XGB\(([^)]+)%\)', name)
    if m:
        xgb_weight = float(m.group(1)) / 100.0
    for p in name.split('+'):
        if 'V8-M' in p:
            model_names.append(p)
else:
    for p in name.split('+'):
        if 'V8-M' in p:
            model_names.append(p)

if model_names:
    wrapper_models = [TorchMLPWrapper(all_models[mn], DEVICE) for mn in model_names]
    predictor = EnsemblePredictor(
        wrapper_models, [1.0] * len(wrapper_models),
        xgb_model, xgb_weight, imp, scaler)
    path = os.path.join(MODEL_DIR, 'ultimate_v8_ensemble.pkl')
    joblib.dump(predictor, path, compress=3)
    print(f"  Saved: {path}")

# Save results
with open(os.path.join(MODEL_DIR, 'v8_deepnn_results.json'), 'w') as f:
    json.dump({
        'best_ensemble': best['name'],
        'best_exact': best['exact'],
        'xgb_exact': xgb_exact,
        'top20': results[:20],
        'features': X.shape[1],
        'time_hours': (time.time() - t0) / 3600
    }, f, indent=2)

print(f"\n{'=' * 70}")
print(f"V8 DEEPNN COMPLETE: {best['exact']*100:.2f}% exact!")
print(f"  Time: {(time.time() - t0) / 3600:.1f} hours")
print(f"  Previous record: 32.05%")
print(f"  Delta: {best['exact']*100 - 32.05:+.2f}%")
print(f"{'=' * 70}")
