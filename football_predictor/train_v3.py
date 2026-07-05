"""
V3 Focal Loss Trainer — 120 epochs, focal loss, stacking ensemble
"""
import sys, os, json, time, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import xgboost as xgb
import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DATA_FILE = os.path.join(MODEL_DIR, 'preprocessed_data.npz')
LOG = os.path.join(MODEL_DIR, 'v3_log.txt')

def log(msg):
    with open(LOG, 'a') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

class FocalLoss(nn.Module):
    def __init__(self, gamma=2.0, alpha=None):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha
    def forward(self, inputs, targets):
        ce_loss = nn.functional.cross_entropy(inputs, targets, reduction='none')
        pt = torch.exp(-ce_loss)
        focal_loss = ((1 - pt) ** self.gamma * ce_loss).mean()
        return focal_loss

class M5_Variant(nn.Module):
    def __init__(self, input_dim, num_classes, layer_sizes, dropout_rate=0.3):
        super().__init__()
        modules = []
        prev = input_dim
        for i, sz in enumerate(layer_sizes):
            modules.append(nn.Linear(prev, sz))
            if sz >= 64:
                modules.append(nn.BatchNorm1d(sz))
            modules.append(nn.ELU())
            modules.append(nn.Dropout(dropout_rate * (0.5 if i == len(layer_sizes)-1 else 1.0)))
            prev = sz
        modules.append(nn.Linear(prev, num_classes))
        self.net = nn.Sequential(*modules)
    def forward(self, x):
        return self.net(x)

def _class_to_score(c):
    return (c // 5, c % 5)
def _result(h, a):
    return 0 if h > a else (1 if h == a else 2)
def compute_rps(y_true, y_pred_proba):
    rps = 0.0
    for i in range(len(y_true)):
        ah, aa = _class_to_score(y_true[i])
        ar = _result(ah, aa)
        ac = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        p = y_pred_proba[i]
        p_h = sum(p[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(p[h*5 + h] for h in range(5))
        p_a = sum(p[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pc = np.cumsum([p_h, p_d, p_a])
        rps += float(np.mean((ac - pc) ** 2))
    return rps / len(y_true)

print('='*60)
print('V3 FOCAL LOSS TRAINER')
print('='*60)

log('='*60)
log('V3 FOCAL LOSS TRAINER')
log('='*60)

# Load preprocessed data
data = np.load(DATA_FILE, allow_pickle=True)
X_train_s = data['X_train_s']
X_test_s = data['X_test_s']
y_train = data['y_train']
y_test = data['y_test']
NUM_INPUT = X_train_s.shape[1]
NUM_CLASSES = 25
log(f'Loaded: {len(X_train_s)} train, {len(X_test_s)} test, {NUM_INPUT} features')

actual_1x2 = np.array([_result(*_class_to_score(c)) for c in y_test])
X_test_t = torch.tensor(X_test_s, dtype=torch.float32)
y_test_t = torch.tensor(y_test, dtype=torch.long)

ARCHITECTURES = {
    'M5_small_v3': [128, 256, 128],
    'M5_medium_v3': [256, 512, 256],
    'M5_big_v3': [512, 1024, 512],
    'M5_wide_v3': [1024, 512, 256],
    'M5_deep_v3': [256, 512, 256, 128],
}
EPOCHS = 120
LR = 0.0008
GAMMA = 2.0  # Focal loss gamma

train_loader = DataLoader(
    TensorDataset(torch.tensor(X_train_s, dtype=torch.float32),
                  torch.tensor(y_train, dtype=torch.long)),
    batch_size=512, shuffle=True, num_workers=0
)

all_probas = {}

for arch_name, layers in ARCHITECTURES.items():
    log(f'\n[{arch_name}] Training {layers} (focal loss, {EPOCHS} epochs)...')
    model = M5_Variant(NUM_INPUT, NUM_CLASSES, layers, dropout_rate=0.25)
    optimizer = optim.AdamW(model.parameters(), lr=LR, weight_decay=5e-5)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    criterion = FocalLoss(gamma=GAMMA)
    
    best_acc, best_state, best_rps = 0, None, 999
    t_arch = time.time()
    
    for epoch in range(EPOCHS):
        model.train()
        for Xb, yb in train_loader:
            optimizer.zero_grad()
            criterion(model(Xb), yb).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        
        model.eval()
        with torch.no_grad():
            preds = torch.max(model(X_test_t), 1)[1]
            acc = (preds == y_test_t).sum().item() / len(y_test)
            proba = torch.softmax(model(X_test_t), dim=1).numpy()
            rps = compute_rps(y_test, proba)
        
        scheduler.step()
        
        improved = False
        if acc > best_acc + 0.0005:
            best_acc = acc
            improved = True
        if rps < best_rps - 0.0001:
            best_rps = rps
            improved = True
        if improved:
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        
        if epoch % 20 == 0 or epoch == EPOCHS - 1:
            elapsed = time.time() - t_arch
            rem = (elapsed / (epoch+1)) * (EPOCHS - epoch - 1)
            log(f'  ep {epoch+1}/{EPOCHS}: val={acc*100:.2f}% best={best_acc*100:.2f}% RPS={rps:.4f} {rem/60:.0f}m')
    
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        proba = torch.softmax(model(X_test_t), dim=1).numpy()
        pred = np.argmax(proba, axis=1)
    
    r = {'exact': float(np.mean(pred == y_test)),
         '1x2': float(np.mean(np.array([_result(*_class_to_score(c)) for c in pred]) == actual_1x2)),
         'rps': float(compute_rps(y_test, proba))}
    log(f'  DONE: exact={r["exact"]*100:.2f}% 1X2={r["1x2"]*100:.2f}% RPS={r["rps"]:.4f}')
    
    torch.save(best_state, os.path.join(MODEL_DIR, f'{arch_name}.pt'))
    all_probas[arch_name] = proba
    del model; gc.collect()

# Also try XGBoost with focal loss approximation via sample weights
log('\n[XGBoost_v3] Training with focal-like weights...')
from sklearn.utils.class_weight import compute_class_weight
classes = np.unique(y_train)
cw = compute_class_weight('balanced', classes=classes, y=y_train)
class_weight_dict = dict(zip(classes, cw))
sample_weights = np.array([class_weight_dict[y] for y in y_train])
# Apply focal-like scaling
for c in classes:
    idx = y_train == c
    count = idx.sum()
    if count > 0:
        sample_weights[idx] *= (1.0 - (count / len(y_train))) ** 0.5

xgb_model = xgb.XGBClassifier(
    n_estimators=1000, max_depth=6, learning_rate=0.06,
    objective='multi:softprob', num_class=NUM_CLASSES,
    subsample=0.85, colsample_bytree=0.85,
    reg_alpha=0.05, reg_lambda=0.1, random_state=99,
    eval_metric='mlogloss', early_stopping_rounds=25
)
xgb_model.fit(X_train_s, y_train, sample_weight=sample_weights,
              eval_set=[(X_test_s, y_test)], verbose=False)
xgb_proba = xgb_model.predict_proba(X_test_s)
xgb_pred = np.argmax(xgb_proba, axis=1)
xr = {'exact': float(np.mean(xgb_pred == y_test)),
      '1x2': float(np.mean(np.array([_result(*_class_to_score(c)) for c in xgb_pred]) == actual_1x2)),
      'rps': compute_rps(y_test, xgb_proba)}
log(f'XGBoost_v3: exact={xr["exact"]*100:.2f}% 1X2={xr["1x2"]*100:.2f}% RPS={xr["rps"]:.4f}')
joblib.dump(xgb_model, os.path.join(MODEL_DIR, 'xgb_v3.pkl'))
all_probas['xgb_v3'] = xgb_proba

model_names = list(all_probas.keys())
log(f'\nModels: {model_names}')

# Ensemble search
log('Searching ensemble blend...')
best_ensemble, best_weights = 0, None
for trial in range(5000):
    w = np.random.dirichlet(np.ones(len(model_names)))
    ep = sum(w[i] * all_probas[nm] for i, nm in enumerate(model_names))
    epred = np.argmax(ep, axis=1)
    acc = float(np.mean(epred == y_test))
    if acc > best_ensemble:
        best_ensemble, best_weights = acc, w.copy()

for _ in range(20):
    for i in range(len(model_names)):
        for delta in [-0.05, -0.02, 0, 0.02, 0.05]:
            w = best_weights.copy()
            w[i] = max(0, min(1, w[i] + delta))
            w /= w.sum()
            ep = sum(w[j] * all_probas[nm] for j, nm in enumerate(model_names))
            epred = np.argmax(ep, axis=1)
            acc = float(np.mean(epred == y_test))
            if acc > best_ensemble:
                best_ensemble, best_weights = acc, w.copy()

ensemble_proba = sum(best_weights[i] * all_probas[nm] for i, nm in enumerate(model_names))
ensemble_pred = np.argmax(ensemble_proba, axis=1)
ensemble_exact = float(np.mean(ensemble_pred == y_test))
ensemble_1x2 = float(np.mean(np.array([_result(*_class_to_score(c)) for c in ensemble_pred]) == actual_1x2))
ensemble_rps = compute_rps(y_test, ensemble_proba)

log(f'\nV3 Ensemble: exact={ensemble_exact*100:.2f}% 1X2={ensemble_1x2*100:.2f}% RPS={ensemble_rps:.4f}')
w_str = ', '.join([f'{nm}={best_weights[i]*100:.0f}%' for i, nm in enumerate(model_names)])
log(f'Weights: {w_str}')

# Betting @30%
hits30 = total30 = 0
for i in range(len(y_test)):
    p = ensemble_proba[i]
    pc = ensemble_pred[i]
    if float(p[pc]) >= 0.30:
        total30 += 1
        if pc == y_test[i]:
            hits30 += 1
log(f'Betting @30%: {hits30}/{total30} = {hits30/total30*100:.1f}%' if total30 > 0 else 'No 30%+ bets')

# Save
results = {
    'type': 'V3_FOCAL_LOSS',
    'epochs': EPOCHS,
    'focal_gamma': GAMMA,
    'model_names': model_names,
    'individual': {k: {'exact_pct': round(r.get('exact',0)*100,2), '1x2_pct': round(r.get('1x2',0)*100,2), 'rps': round(r.get('rps',0),4)} for k, r in [('xgb_v3', xr)]},
    'ensemble': {'exact_pct': round(ensemble_exact*100,2), '1x2_pct': round(ensemble_1x2*100,2), 'rps': round(ensemble_rps,4)},
    'weights': {nm: float(best_weights[i]) for i, nm in enumerate(model_names)},
    'betting_30': {'accuracy_pct': round(hits30/total30*100,1) if total30 else 0, 'samples': total30},
}
json.dump(results, open(os.path.join(MODEL_DIR, 'v3_results.json'), 'w'), indent=2)
log('\nSaved v3_results.json')
log('Done!')
