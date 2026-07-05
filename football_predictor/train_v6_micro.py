"""
V6 Micro Train — Minimal test: 20K matches, 1 arch, 30 epochs
Goal: Get first V6 result within 30 min
"""
import sys, os, json, time, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
LOG = os.path.join(MODEL_DIR, 'v6_micro_log.txt')

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(msg)

def _cs(c): return (c // 5, c % 5)

def rps(y_true, y_pred_proba):
    rps_val = 0.0
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
        rps_val += float(np.mean((ca - np.cumsum(cp))**2))
    return rps_val / len(y_true)

class LabelSmoothingLoss(nn.Module):
    def __init__(self, smoothing=0.1, gamma=2.0):
        super().__init__()
        self.smoothing = smoothing
        self.gamma = gamma
    def forward(self, inputs, targets):
        n_cls = inputs.size(1)
        with torch.no_grad():
            sm = torch.full_like(inputs, self.smoothing / (n_cls - 1))
            sm.scatter_(1, targets.unsqueeze(1), 1.0 - self.smoothing)
        loss = -(sm * nn.functional.log_softmax(inputs, dim=1)).sum(dim=1)
        if self.gamma > 0:
            p_t = torch.softmax(inputs, dim=1).gather(1, targets.unsqueeze(1)).squeeze()
            loss = loss * ((1 - p_t) ** self.gamma)
        return loss.mean()

class M5Variant(nn.Module):
    def __init__(self, input_dim, n_classes, layers, dr=0.25):
        super().__init__()
        modules = []; prev = input_dim
        for i, sz in enumerate(layers):
            modules += [nn.Linear(prev, sz)]
            if sz >= 64: modules += [nn.BatchNorm1d(sz)]
            modules += [nn.ELU(), nn.Dropout(dr * (0.5 if i == len(layers)-1 else 1.0))]
            prev = sz
        modules += [nn.Linear(prev, n_classes)]
        self.net = nn.Sequential(*modules)
    def forward(self, x): return self.net(x)

log('V6 MICRO TRAIN - 20K matches, 1 arch, 30 epochs')
log('='*50)

t0 = time.time()

# Load data
from direct_predictor import _load_training_data
X, y, mids = _load_training_data()
X, y = X[-20000:], y[-20000:]
log(f'Loaded: {len(X)} samples')

# Split
n = len(X); split = int(n * 0.80)
imp = SimpleImputer(strategy='median')
scaler = StandardScaler()
X_tr = imp.fit_transform(X[:split]); X_te = imp.transform(X[split:])
X_trs = scaler.fit_transform(X_tr); X_tes = scaler.transform(X_te)

# DataLoaders
tds = TensorDataset(torch.tensor(X_trs, dtype=torch.float32), torch.tensor(y[:split], dtype=torch.long))
vds = TensorDataset(torch.tensor(X_tes, dtype=torch.float32), torch.tensor(y[split:], dtype=torch.long))
tl = DataLoader(tds, batch_size=256, shuffle=True)
vl = DataLoader(vds, batch_size=512, shuffle=False)

# Model: M5_deep (proven best in V5)
model = M5Variant(X_trs.shape[1], 25, [256, 512, 256, 128])
criterion = LabelSmoothingLoss(smoothing=0.1, gamma=2.0)
optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-5)
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=30, eta_min=1e-5)

log('Training M5_deep [256,512,256,128] 30 epochs...')
best_val = 0.0
best_ep = 0

for ep in range(30):
    model.train()
    for xb, yb in tl:
        optimizer.zero_grad()
        criterion(model(xb), yb).backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
    
    model.eval()
    ap, at = [], []
    with torch.no_grad():
        for xb, yb in vl:
            ap.append(torch.softmax(model(xb), dim=1).numpy())
            at.append(yb.numpy())
    ap = np.concatenate(ap); at_ = np.concatenate(at)
    ve = float(np.mean(np.argmax(ap, axis=1) == at_)) * 100
    vr = rps(at_, ap)
    scheduler.step()
    
    if ve > best_val:
        best_val = ve
        best_ep = ep
    
    if (ep+1) % 5 == 0:
        log(f'  ep {ep+1}: val={ve:.2f}% best={best_val:.2f}% rps={vr:.4f}')

# Final test
model.eval()
with torch.no_grad():
    tp = torch.softmax(model(torch.tensor(X_tes, dtype=torch.float32)), dim=1).numpy()
tc = np.argmax(tp, axis=1)
te = float(np.mean(tc == y[split:])) * 100
t1x2 = float(np.mean(
    np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in tc]]) ==
    np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in y[split:]]])
)) * 100
tr = rps(y[split:], tp)

elapsed = time.time() - t0

log(f'')
log(f'=== V6 MICRO RESULTS ===')
log(f'Samples: {len(X)} | Train: {len(X_trs)} | Test: {len(X_tes)}')
log(f'Exact: {te:.2f}%')
log(f'1X2: {t1x2:.2f}%')
log(f'RPS: {tr:.4f}')
log(f'Best val epoch: {best_ep+1}')
log(f'Time: {elapsed:.0f}s ({elapsed/60:.1f}min)')
log(f'')
log(f'V5 reference: 18.51% (887K, 120ep)')
log(f'V3 reference: 25.89% (128K, 120ep)')

# Save
torch.save(model.state_dict(), os.path.join(MODEL_DIR, 'v6_micro.pt'))
np.save(os.path.join(MODEL_DIR, 'v6_micro_probas.npy'), tp)
results = {
    'type': 'V6_MICRO',
    'samples': len(X), 'train': len(X_trs), 'test': len(X_tes),
    'epochs': 30, 'exact': round(te,2), '1x2': round(t1x2,2), 'rps': round(tr,4),
    'time_sec': round(elapsed, 1),
}
with open(os.path.join(MODEL_DIR, 'v6_micro_results.json'), 'w') as f:
    json.dump(results, f, indent=2)

log('Saved to models/v6_micro*')
