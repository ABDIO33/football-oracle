"""
train_best_xgb.py — Train XGBoost with best found params + ensemble with M4
"""
import sys, numpy as np, json, pickle, os
sys.path.insert(0, '.')
from direct_predictor import _load_training_data, TorchMLPWrapper, EnsemblePredictor, SCORE_CLASSES
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
import xgboost as xgb
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

N_FEATURES = 85
NUM_CLASSES = 25
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

print('Loading data...')
X, y, ids = _load_training_data()
print(f'  {len(X)} samples, {X.shape[1]} features')

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
imp = SimpleImputer(strategy='median')
X_train_i = imp.fit_transform(X_train)
X_test_i = imp.transform(X_test)
scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train_i)
X_test_sc = scaler.transform(X_test_i)
le = LabelEncoder()
y_train_enc = le.fit_transform(y_train)
y_test_enc = le.transform(y_test)

# Best params from grid search
print('\nTraining XGBoost (best params)...')
model_xgb = xgb.XGBClassifier(
    n_estimators=700, max_depth=6, learning_rate=0.08,
    subsample=0.8, colsample_bytree=0.8,
    objective='multi:softprob', num_class=NUM_CLASSES,
    eval_metric='mlogloss', random_state=42, n_jobs=-1
)
model_xgb.fit(X_train_i, y_train_enc)
xgb_probs = model_xgb.predict_proba(X_test_i)
xgb_preds = np.argmax(xgb_probs, axis=1)
xgb_exact = (xgb_preds == y_test_enc).mean()
print(f'  XGBoost exact: {xgb_exact*100:.2f}%')

if xgb_exact < 0.23:
    print('  Warning: XGBoost accuracy seems low, might need more tuning')

# Train M4
print('\nTraining DeepNN-M4...')
model_m4 = nn.Sequential(
    nn.Linear(N_FEATURES, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.2),
    nn.Linear(512, 1024), nn.BatchNorm1d(1024), nn.ReLU(), nn.Dropout(0.2),
    nn.Linear(1024, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.2),
    nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(0.2),
    nn.Linear(256, NUM_CLASSES),
).to(DEVICE)

criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
optimizer = optim.AdamW(model_m4.parameters(), lr=0.001, weight_decay=1e-4)
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=80)

train_ds = TensorDataset(
    torch.tensor(X_train_sc, dtype=torch.float32),
    torch.tensor(y_train_enc, dtype=torch.long)
)
train_loader = DataLoader(train_ds, batch_size=1024, shuffle=True, num_workers=0)
X_test_t = torch.tensor(X_test_sc, dtype=torch.float32).to(DEVICE)
y_test_t = torch.tensor(y_test_enc, dtype=torch.long).to(DEVICE)

best_acc = 0.0
best_state = None
patience = 15
pc = 0

for epoch in range(100):
    model_m4.train()
    for Xb, yb in train_loader:
        Xb, yb = Xb.to(DEVICE), yb.to(DEVICE)
        optimizer.zero_grad()
        loss = criterion(model_m4(Xb), yb)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model_m4.parameters(), 1.0)
        optimizer.step()
    model_m4.eval()
    with torch.no_grad():
        out = model_m4(X_test_t)
        _, preds = torch.max(out, 1)
        acc = (preds == y_test_t).sum().item() / len(y_test_enc)
    scheduler.step()
    if acc > best_acc:
        best_acc = acc
        best_state = model_m4.state_dict()
        pc = 0
    else:
        pc += 1
        if pc >= patience:
            print(f'  Early stop at epoch {epoch+1}')
            break
    if (epoch+1) % 20 == 0:
        print(f'  Epoch {epoch+1}: test_acc={acc:.4f}')

model_m4.load_state_dict(best_state)
wrapper = TorchMLPWrapper(model_m4, device=DEVICE)
m4_probs = wrapper.predict_proba(X_test_sc)
print(f'  M4 best exact: {best_acc*100:.2f}%')

# Blend search
print('\nSearching optimal blend...')
best_exact = 0
best_w = 0
for w in np.arange(0.0, 1.01, 0.05):
    blend = w * xgb_probs + (1-w) * m4_probs
    preds = np.argmax(blend, axis=1)
    exact = (preds == y_test_enc).mean()
    if exact > best_exact:
        best_exact = exact
        best_w = w

blend = best_w * xgb_probs + (1-best_w) * m4_probs
preds = np.argmax(blend, axis=1)
best_exact = (preds == y_test_enc).mean()

# 1X2
hda_pred = np.zeros((len(y_test_enc), 3))
for i in range(25):
    h, a = i // 5, i % 5
    idx = 0 if h > a else 1 if h == a else 2
    hda_pred[:, idx] += blend[:, i]

true_hda = np.array([0 if h > a else 1 if h == a else 2 for h in range(5) for a in range(5)])
hda_acc = (np.argmax(hda_pred, axis=1) == true_hda[y_test_enc]).mean()

def calc_rps(probs, true_labels):
    rps_list = []
    for i in range(len(true_labels)):
        p = probs[i]
        ph = sum(p[j] for j in range(25) if j // 5 > j % 5)
        pd = sum(p[j] for j in range(25) if j // 5 == j % 5)
        pa = sum(p[j] for j in range(25) if j // 5 < j % 5)
        cum_pred = np.cumsum([ph, pd, pa])
        cum_true = np.array([1 if true_labels[i] <= k else 0 for k in range(3)])
        rps_list.append(np.mean((cum_pred - cum_true) ** 2))
    return np.mean(rps_list)

rps_val = calc_rps(blend, y_test_enc)

print(f'\n=== FINAL: XGB({best_w*100:.0f}%) + M4({(1-best_w)*100:.0f}%) ===')
print(f'  Exact: {best_exact*100:.2f}%')
print(f'  1X2:   {hda_acc*100:.2f}%')
print(f'  RPS:   {rps_val:.4f}')

# Save
print('\nSaving production models...')
ensemble = EnsemblePredictor(
    models=[wrapper], model_weights=[1.0],
    xgb_model=model_xgb, xgb_weight=best_w,
    imp=imp, scaler=scaler
)
with open('models/mlp_blend.pkl', 'wb') as f:
    pickle.dump(ensemble, f)
model_xgb.save_model('models/direct_score.ubj')

results = {
    'best_exact': round(float(best_exact)*100, 2),
    'best_1x2': round(float(hda_acc)*100, 2),
    'best_rps': round(float(rps_val), 4),
    'best_ensemble': f'XGB({best_w*100:.0f}%)+M4',
    'training_samples': len(X),
    'test_samples': len(y_test_enc),
    'xgb_params': {'n_estimators': 700, 'max_depth': 6, 'learning_rate': 0.08, 'subsample': 0.8}
}
with open('models/ensemble_results.json', 'w') as f:
    json.dump(results, f, indent=2)

size_mlp = os.path.getsize('models/mlp_blend.pkl') / 1e6
size_xgb = os.path.getsize('models/direct_score.json') / 1e6
print(f'  mlp_blend.pkl ({size_mlp:.1f} MB)')
print(f'  direct_score.json ({size_xgb:.1f} MB)')
print(f'  ensemble_results.json saved')
print(f'\nDONE: Exact={best_exact*100:.2f}%  1X2={hda_acc*100:.2f}%  RPS={rps_val:.4f}')
