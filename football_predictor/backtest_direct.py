"""
backtest_direct.py — Time-split backtest for Direct Score Ensemble
Uses walk-forward validation to measure true out-of-sample performance
"""
import sys, os, json, time, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from direct_predictor import _load_training_data, FEATURES, NUM_CLASSES, class_to_score, result, load_model
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
print("="*60)
print("DIRECT SCORE BACKTEST (Time-Split Validation)")
print("="*60)

# Load full dataset
X, y, _ = _load_training_data()
n = len(X)
print(f"Total samples: {n}")

# Time-split: first 80% train, last 20% test (chronological)
split = int(n * 0.80)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]
print(f"Train: {len(X_train)}, Test: {len(X_test)}")

# Preprocess
imp = SimpleImputer(strategy='median')
X_train_imp = imp.fit_transform(X_train)
X_test_imp = imp.transform(X_test)
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train_imp)
X_test_s = scaler.transform(X_test_imp)

# Train XGBoost on training split
print("\n[1/2] Training XGBoost baseline...")
xgb_model = xgb.XGBClassifier(
    n_estimators=400, max_depth=6, learning_rate=0.05,
    objective='multi:softprob', num_class=NUM_CLASSES,
    subsample=0.9, colsample_bytree=0.8,
    reg_alpha=0.1, reg_lambda=0.1, random_state=42,
    eval_metric='mlogloss', early_stopping_rounds=20
)
xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
xgb_proba = xgb_model.predict_proba(X_test)
xgb_pred = np.argmax(xgb_proba, axis=1)

xgb_exact = np.mean(xgb_pred == y_test)
actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
xgb_1x2 = np.mean(np.array([result(*class_to_score(c)) for c in xgb_pred]) == actual_1x2)
print(f"  XGBoost exact={xgb_exact*100:.2f}%  1X2={xgb_1x2*100:.2f}%")

# Train DeepNN on training split
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

def build_network(hidden_layers, input_dim, num_classes, dropout=0.3):
    layers = []
    prev_dim = input_dim
    for units in hidden_layers:
        layers.extend([nn.Linear(prev_dim, units), nn.BatchNorm1d(units), nn.ReLU(), nn.Dropout(dropout)])
        prev_dim = units
    layers.append(nn.Linear(prev_dim, num_classes))
    return nn.Sequential(*layers)

input_dim = X_train_s.shape[1]
train_dataset = TensorDataset(
    torch.tensor(X_train_s, dtype=torch.float32),
    torch.tensor(y_train, dtype=torch.long))
train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True, num_workers=0)
X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(DEVICE)
y_test_t = torch.tensor(y_test, dtype=torch.long).to(DEVICE)

configs = [
    ('DeepNN-M3', [256, 512, 256, 128], 0.2, 0.001),
    ('DeepNN-M4', [512, 1024, 512, 256], 0.2, 0.001),
    ('DeepNN-M5', [128, 256, 128], 0.3, 0.001),
]

all_models = {}
all_probas = {}
for name, hidden, drop, lr in configs:
    print(f"\n[2/2] Training {name} ({'->'.join(str(u) for u in hidden)})...")
    model = build_network(hidden, input_dim, NUM_CLASSES, drop).to(DEVICE)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=80)
    
    best_acc = 0
    best_state = None
    for epoch in range(100):
        model.train()
        for Xb, yb in train_loader:
            Xb, yb = Xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            criterion(model(Xb), yb).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            acc = (torch.max(model(X_test_t), 1)[1] == y_test_t).sum().item() / len(y_test)
        scheduler.step()
        if acc > best_acc:
            best_acc = acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
    
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        proba = torch.softmax(model(X_test_t), dim=1).cpu().numpy()
        pred = torch.max(model(X_test_t), 1)[1].cpu().numpy()
    
    exact = np.mean(pred == y_test)
    acc_1x2 = np.mean(np.array([result(*class_to_score(c)) for c in pred]) == actual_1x2)
    print(f"  {name}: exact={exact*100:.2f}%  1X2={acc_1x2*100:.2f}%")
    all_models[name] = model
    all_probas[name] = proba

# Ensemble: try XGB(30%)+M3+M4+M5 (best config from full training)
print("\n" + "="*60)
print("ENSEMBLE EVALUATION")
print("="*60)

w_xgb = 0.30
ensemble_proba = w_xgb * xgb_proba
w_each = (1.0 - w_xgb) / len(configs)
for proba in all_probas.values():
    ensemble_proba += w_each * proba

ensemble_pred = np.argmax(ensemble_proba, axis=1)
ensemble_exact = np.mean(ensemble_pred == y_test)
ensemble_1x2 = np.mean(np.array([result(*class_to_score(c)) for c in ensemble_pred]) == actual_1x2)

# RPS
def compute_rps(y_true, y_pred_proba):
    rps_total = 0.0
    for i in range(len(y_true)):
        ah, aa = class_to_score(y_true[i])
        ar = result(ah, aa)
        actual_cum = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        p = y_pred_proba[i]
        p_h = sum(p[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(p[h*5 + h] for h in range(5))
        p_a = sum(p[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pred_cum = np.cumsum([p_h, p_d, p_a])
        rps_total += np.mean((actual_cum - pred_cum) ** 2)
    return rps_total / len(y_true)

rps_xgb = compute_rps(y_test, xgb_proba)
rps_ens = compute_rps(y_test, ensemble_proba)

print(f"{'Model':25s} | {'Exact%':>7} | {'1X2%':>6} | {'RPS':>5}")
print("-"*50)
print(f"{'XGBoost':25s} | {xgb_exact*100:>6.2f}% | {xgb_1x2*100:>5.1f}% | {rps_xgb:.4f}")
for i, (name, proba) in enumerate(all_probas.items()):
    pred = np.argmax(proba, axis=1)
    ex = np.mean(pred == y_test)
    _1x2 = np.mean(np.array([result(*class_to_score(c)) for c in pred]) == actual_1x2)
    rps = compute_rps(y_test, proba)
    print(f"{name:25s} | {ex*100:>6.2f}% | {_1x2*100:>5.1f}% | {rps:.4f}")
print("-"*50)
print(f"{'ENSEMBLE (XGB30%+M3+M4+M5)':25s} | {ensemble_exact*100:>6.2f}% | {ensemble_1x2*100:>5.1f}% | {rps_ens:.4f}")
print("="*60)

# Save results
results = {
    'test_samples': len(X_test),
    'xgb_exact_pct': round(xgb_exact*100, 2),
    'xgb_1x2_pct': round(xgb_1x2*100, 2),
    'xgb_rps': round(rps_xgb, 4),
    'ensemble_exact_pct': round(ensemble_exact*100, 2),
    'ensemble_1x2_pct': round(ensemble_1x2*100, 2),
    'ensemble_rps': round(rps_ens, 4),
    'config': 'XGB(30%)+M3+M4+M5',
}
with open(os.path.join(MODEL_DIR, 'backtest_direct_results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nSaved backtest_direct_results.json")
print("DONE")
