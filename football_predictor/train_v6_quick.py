"""
V6 Quick Train — Fast training on manageable subset
50 epochs, 3 architectures, 50K matches
Goal: Get preliminary results within 1-2 hours
"""
import sys, os, json, time, math, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
LOG = os.path.join(MODEL_DIR, 'v6_quick_log.txt')

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

def _cs(c): return (c // 5, c % 5)

def rps_score(y_true, y_pred_proba):
    rps = 0.0
    for i in range(len(y_true)):
        ah, aa = _cs(y_true[i])
        ar = 0 if ah > aa else 1 if ah == aa else 2
        p = y_pred_proba[i]
        cp = np.zeros(3)
        for hh in range(5):
            for a2 in range(5):
                if hh > a2: cp[0] += p[hh*5+a2]
                elif hh == a2: cp[1] += p[hh*5+a2]
                else: cp[2] += p[hh*5+a2]
        ca = np.zeros(3); ca[ar:] = 1.0
        rps += float(np.mean((ca - np.cumsum(cp))**2))
    return rps / len(y_true)

class LabelSmoothingLoss(nn.Module):
    def __init__(self, smoothing=0.1, gamma=2.0):
        super().__init__()
        self.smoothing = smoothing
        self.gamma = gamma
    def forward(self, inputs, targets):
        n_classes = inputs.size(1)
        with torch.no_grad():
            smoothed = torch.full_like(inputs, self.smoothing / (n_classes - 1))
            smoothed.scatter_(1, targets.unsqueeze(1), 1.0 - self.smoothing)
        log_softmax = nn.functional.log_softmax(inputs, dim=1)
        loss = -(smoothed * log_softmax).sum(dim=1)
        if self.gamma > 0:
            prob = torch.softmax(inputs, dim=1)
            p_t = prob.gather(1, targets.unsqueeze(1)).squeeze()
            loss = loss * ((1 - p_t) ** self.gamma)
        return loss.mean()

class M5Variant(nn.Module):
    def __init__(self, input_dim, num_classes, layers, dr=0.25):
        super().__init__()
        modules = []
        prev = input_dim
        for i, sz in enumerate(layers):
            modules += [nn.Linear(prev, sz)]
            if sz >= 64: modules += [nn.BatchNorm1d(sz)]
            modules += [nn.ELU(), nn.Dropout(dr * (0.5 if i == len(layers)-1 else 1.0))]
            prev = sz
        modules += [nn.Linear(prev, num_classes)]
        self.net = nn.Sequential(*modules)
    def forward(self, x): return self.net(x)

log('='*60)
log('V6 QUICK TRAIN')
log('='*60)

# Load data
t0 = time.time()
log('\nLoading match data...')
from direct_predictor import _load_training_data
X, y, mids = _load_training_data()

# Use last 50K matches (most recent)
X = X[-50000:]
y = y[-50000:]
mids = mids[-50000:]

log(f'Using {len(X)} recent matches')

# Chronological split
n = len(X); split = int(n * 0.80)
imp = SimpleImputer(strategy='median'); scaler = StandardScaler()
X_train = imp.fit_transform(X[:split]); X_test = imp.transform(X[split:])
X_train_s = scaler.fit_transform(X_train); X_test_s = scaler.transform(X_test)

train_ds = TensorDataset(torch.tensor(X_train_s, dtype=torch.float32), torch.tensor(y[:split], dtype=torch.long))
test_ds = TensorDataset(torch.tensor(X_test_s, dtype=torch.float32), torch.tensor(y[split:], dtype=torch.long))
train_loader = DataLoader(train_ds, batch_size=256, shuffle=True)
val_loader = DataLoader(test_ds, batch_size=512, shuffle=False)

input_dim = X_train_s.shape[1]
num_classes = 25
log(f'Input dim: {input_dim}, Train: {len(X_train_s)}, Test: {len(X_test_s)}')

# Train 3 architectures (50 epochs each)
ARCHS = {
    'M5_deep_v6q': [256, 512, 256, 128],
    'M5_medium_v6q': [256, 512, 256],
    'M5_ultra_v6q': [1024, 512, 256, 128],
}

EPOCHS = 50
results = {}
test_probas = {}

for name, layers in ARCHS.items():
    log(f'\n-- {name}: {layers}, {EPOCHS} epochs --')
    model = M5Variant(input_dim, num_classes, layers, dr=0.25)
    device = torch.device('cpu')
    model.to(device)
    
    criterion = LabelSmoothingLoss(smoothing=0.1, gamma=2.0)
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS, eta_min=1e-5)
    
    best_val = 0.0
    patience = 10; pat_counter = 0
    
    t_start = time.time()
    for ep in range(EPOCHS):
        model.train()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        
        model.eval()
        all_preds, all_true = [], []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device)
                preds = torch.softmax(model(xb), dim=1).cpu().numpy()
                all_preds.append(preds)
                all_true.append(yb.numpy())
        
        all_preds = np.concatenate(all_preds)
        all_true = np.concatenate(all_true)
        val_exact = float(np.mean(np.argmax(all_preds, axis=1) == all_true)) * 100
        val_rps = rps_score(all_true, all_preds)
        
        scheduler.step()
        
        if val_exact > best_val:
            best_val = val_exact
            pat_counter = 0
        else:
            pat_counter += 1
        
        if (ep+1) % 10 == 0:
            log(f'  ep {ep+1}: val={val_exact:.2f}% best={best_val:.2f}% rps={val_rps:.4f}')
        
        if pat_counter >= patience:
            log(f'  Early stop at ep {ep+1}')
            break
    
    elapsed = time.time() - t_start
    
    # Final test evaluation
    model.eval()
    with torch.no_grad():
        test_p = torch.softmax(model(torch.tensor(X_test_s, dtype=torch.float32)), dim=1).numpy()
    test_c = np.argmax(test_p, axis=1)
    test_exact = float(np.mean(test_c == y[split:])) * 100
    test_1x2 = float(np.mean(
        np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in test_c]]) ==
        np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in y[split:]]])
    )) * 100
    test_rps = rps_score(y[split:], test_p)
    
    log(f'  Best val: {best_val:.2f}% | Test: {test_exact:.2f}% | 1X2: {test_1x2:.2f}% | RPS: {test_rps:.4f}')
    log(f'  Time: {elapsed:.0f}s')
    
    torch.save(model.state_dict(), os.path.join(MODEL_DIR, f'{name}.pt'))
    np.save(os.path.join(MODEL_DIR, f'{name}_probas.npy'), test_p)
    
    results[name] = {'val': round(best_val,2), 'test': round(test_exact,2), '1x2': round(test_1x2,2), 'rps': round(test_rps,4)}
    test_probas[name] = test_p
    del model; gc.collect()

# Build ensemble
log('\n--- Ensemble ---')
all_names = list(test_probas.keys())
all_preds = np.array([test_probas[n] for n in all_names])
n_models = len(all_names)

# Weight search
best_ens = 0.0; best_w = None
for trial in range(5000):
    w = np.random.dirichlet(np.ones(n_models))
    ens = np.tensordot(w, all_preds, axes=(0,0))
    ens_c = np.argmax(ens, axis=1)
    exact = float(np.mean(ens_c == y[split:]))
    if exact > best_ens:
        best_ens = exact; best_w = w.copy()

ens_final = np.tensordot(best_w, all_preds, axes=(0,0))
ens_c = np.argmax(ens_final, axis=1)
ens_exact = float(np.mean(ens_c == y[split:])) * 100
ens_1x2 = float(np.mean(
    np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in ens_c]]) ==
    np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in y[split:]]])
)) * 100
ens_rps = rps_score(y[split:], ens_final)

log(f'Ensemble: {ens_exact:.2f}% | 1X2: {ens_1x2:.2f}% | RPS: {ens_rps:.4f}')
for name, w in zip(all_names, best_w):
    log(f'  {name}: {w*100:.0f}%')

# Save
final = {
    'type': 'V6_QUICK',
    'samples': len(X),
    'epochs': EPOCHS,
    'individual': results,
    'ensemble': {'exact': round(ens_exact,2), '1x2': round(ens_1x2,2), 'rps': round(ens_rps,4)},
    'weights': {all_names[i]: round(float(best_w[i]),4) for i in range(n_models)},
    'time_min': round((time.time()-t0)/60, 1),
}
with open(os.path.join(MODEL_DIR, 'v6_quick_results.json'), 'w') as f:
    json.dump(final, f, indent=2)
log(f'\nDone! Ensemble: {ens_exact:.2f}% exact')
