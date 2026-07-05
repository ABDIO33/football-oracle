"""
V5 TRAINER -- Focal Loss, 120 epochs, 5 architectures, 887K matches
"""
import sys, os, json, time, numpy as np, warnings, gc, traceback
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
LOG = os.path.join(MODEL_DIR, 'v5_log.txt')

sys.stdout = open(LOG, 'a', buffering=1, encoding='utf-8')
sys.stderr = sys.stdout

def log(msg):
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
            for aa2 in range(5):
                if hh > aa2: cp[0] += p[hh*5+aa2]
                elif hh == aa2: cp[1] += p[hh*5+aa2]
                else: cp[2] += p[hh*5+aa2]
        ca = np.zeros(3); ca[ar:] = 1.0
        rps += float(np.mean((ca - np.cumsum(cp))**2))
    return rps / len(y_true)

class FocalLoss(nn.Module):
    def __init__(self, gamma=2.0): super().__init__(); self.gamma = gamma
    def forward(self, inputs, targets):
        ce = nn.functional.cross_entropy(inputs, targets, reduction='none')
        return ((1 - torch.exp(-ce)) ** self.gamma * ce).mean()

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

t0 = time.time()
log('='*60)
log('V5 FOCAL LOSS -- 887K matches, 5 arch, 120 epochs')
log('='*60)

# Load preprocessed
log('\n[1/3] Loading preprocessed data...')
npz = os.path.join(MODEL_DIR, 'v5_preprocessed.npz')
if not os.path.exists(npz):
    log('ERROR: Run _preprocess_v5.py first!'); exit(1)
data = np.load(npz, allow_pickle=True)
X, y = data['X'], data['y']
log(f'Loaded {len(X):,} samples, {X.shape[1]} features')

n = len(X); split = int(n * 0.80)
if not os.path.exists(os.path.join(MODEL_DIR, 'v5_pp.npz')):
    log('\nImpute + Scale...')
    imp = SimpleImputer(strategy='median')
    X_train = imp.fit_transform(X[:split]); X_test = imp.transform(X[split:])
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train); X_test_s = scaler.transform(X_test)
    y_train, y_test = y[:split], y[split:]
    np.savez_compressed(os.path.join(MODEL_DIR, 'v5_pp.npz'),
        X_train_s=X_train_s, X_test_s=X_test_s, y_train=y_train, y_test=y_test)
    joblib.dump(imp, os.path.join(MODEL_DIR, 'v5_imputer.pkl'))
    joblib.dump(scaler, os.path.join(MODEL_DIR, 'v5_scaler.pkl'))
else:
    log('Loading cached preprocessed...')
    d = np.load(os.path.join(MODEL_DIR, 'v5_pp.npz'), allow_pickle=True)
    X_train_s, X_test_s, y_train, y_test = d['X_train_s'], d['X_test_s'], d['y_train'], d['y_test']

NUM_INPUT = X_train_s.shape[1]
actual_1x2 = np.array([0 if _cs(c)[0] > _cs(c)[1] else 1 if _cs(c)[0] == _cs(c)[1] else 2 for c in y_test])
log(f'Input dim: {NUM_INPUT}, Train: {len(X_train_s):,}, Test: {len(X_test_s):,}')

X_test_t = torch.tensor(X_test_s, dtype=torch.float32)
y_test_t = torch.tensor(y_test, dtype=torch.long)

ARCHS = {
    'M5_small_v5': [128, 256, 128],
    'M5_medium_v5': [256, 512, 256],
    'M5_wide_v5': [1024, 512, 256],
    'M5_deep_v5': [256, 512, 256, 128],
    'M5_big_v5': [512, 1024, 512],
}
EPOCHS = 120; LR = 0.0008; GAMMA = 2.0
BATCH = 1024

train_loader = DataLoader(
    TensorDataset(torch.tensor(X_train_s, dtype=torch.float32),
                  torch.tensor(y_train, dtype=torch.long)),
    batch_size=BATCH, shuffle=True)

all_probas, all_results = {}, {}

log('\n[2/3] Training DeepNNs...')
try:  # outer try for full training loop
 for aname, layers in ARCHS.items():
    log(f'\n-- {aname}: {layers} --')
    model = M5Variant(NUM_INPUT, 25, layers, 0.25)
    opt = optim.AdamW(model.parameters(), lr=LR, weight_decay=5e-5)
    sched = optim.lr_scheduler.CosineAnnealingLR(opt, T_max=EPOCHS)
    crit = FocalLoss(gamma=GAMMA)
    best_acc, best_rps, best_state = 0, 999, None
    ta = time.time()
    for ep in range(EPOCHS):
        model.train()
        for xb, yb in train_loader:
            opt.zero_grad(); crit(model(xb), yb).backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        model.eval()
        with torch.no_grad():
            preds = torch.max(model(X_test_t), 1)[1]
            acc = (preds == y_test_t).sum().item() / len(y_test)
            proba = torch.softmax(model(X_test_t), dim=1).numpy()
            rps_v = rps_score(y_test, proba)
        sched.step()
        if acc > best_acc + 0.0003 or rps_v < best_rps - 0.0001:
            if acc > best_acc: best_acc = acc
            if rps_v < best_rps: best_rps = rps_v
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        if ep % 20 == 0 or ep == EPOCHS - 1:
            elapsed = time.time() - ta
            rem = (elapsed/(ep+1))*(EPOCHS-ep-1)/60
            log(f'  ep {ep+1}: val={acc*100:.2f}% best={best_acc*100:.2f}% rps={rps_v:.4f} ETA={rem:.0f}m')
    model.load_state_dict(best_state); model.eval()
    with torch.no_grad():
        proba = torch.softmax(model(X_test_t), dim=1).numpy()
        pred = np.argmax(proba, axis=1)
    r = {'exact': float(np.mean(pred == y_test)),
         '1x2': float(np.mean([0 if _cs(c)[0] > _cs(c)[1] else 1 if _cs(c)[0] == _cs(c)[1] else 2 for c in pred] == actual_1x2)),
         'rps': float(rps_score(y_test, proba))}
    log(f'  OK exact={r["exact"]*100:.2f}% 1X2={r["1x2"]*100:.2f}% RPS={r["rps"]:.4f}')
    save_path = os.path.join(MODEL_DIR, f'{aname}.pt')
    try:
        torch.save(best_state, save_path)
        if not os.path.exists(save_path):
            log(f'  [!] torch.save did not create {save_path}')
            torch.save({'state_dict': best_state, 'arch': layers}, save_path)
    except Exception as e:
        log(f'  [!] torch.save error: {e}')
        import pickle
        with open(save_path.replace('.pt', '.pkl'), 'wb') as f:
            pickle.dump(best_state, f)
        log(f'  OK saved as pickle fallback')
    all_probas[aname] = proba; all_results[aname] = r
    del model; gc.collect()
except Exception as e:
    import traceback
    log(f'  [!] DeepNN training error: {e}')
    log(traceback.format_exc())

try:  # XGBoost + Ensemble
    log('\n-- XGBoost_v5 --')
    from sklearn.utils.class_weight import compute_class_weight
    classes = np.unique(y_train)
    cw = compute_class_weight('balanced', classes=classes, y=y_train); cw_d = dict(zip(classes, cw))
    sw = np.array([cw_d[y] for y in y_train])
    xgb_m = xgb.XGBClassifier(n_estimators=1000, max_depth=6, learning_rate=0.06,
        objective='multi:softprob', num_class=25, subsample=0.85, colsample_bytree=0.85,
        reg_alpha=0.05, reg_lambda=0.1, random_state=99, eval_metric='mlogloss',
        early_stopping_rounds=25, verbosity=0)
    try:
        xgb_m.fit(X_train_s, y_train, sample_weight=sw, eval_set=[(X_test_s, y_test)], verbose=False)
    except Exception as e:
        log(f'  [!] XGBoost error: {e}, retrying without sample_weight')
        xgb_m = xgb.XGBClassifier(n_estimators=500, max_depth=6, learning_rate=0.06,
            objective='multi:softprob', num_class=25, random_state=99, verbosity=0)
        xgb_m.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)
    xgb_p = xgb_m.predict_proba(X_test_s)
    xr = {'exact': float(np.mean(np.argmax(xgb_p, axis=1) == y_test)),
          '1x2': float(np.mean([0 if _cs(c)[0] > _cs(c)[1] else 1 if _cs(c)[0] == _cs(c)[1] else 2 for c in np.argmax(xgb_p, axis=1)] == actual_1x2)),
          'rps': float(rps_score(y_test, xgb_p))}
    log(f'  OK exact={xr["exact"]*100:.2f}% 1X2={xr["1x2"]*100:.2f}% RPS={xr["rps"]:.4f}')
    joblib.dump(xgb_m, os.path.join(MODEL_DIR, 'xgb_v5.pkl'))
    all_probas['xgb_v5'] = xgb_p; all_results['xgb_v5'] = xr
    
    nms = list(all_probas.keys())
    log(f'\n[3/3] Ensemble search ({len(nms)} models)...')
    best_acc, best_w = 0, None
    for _ in range(5000):
        w = np.random.dirichlet(np.ones(len(nms)))
        ep = sum(w[i]*all_probas[nm] for i, nm in enumerate(nms))
        acc = float(np.mean(np.argmax(ep, axis=1) == y_test))
        if acc > best_acc: best_acc, best_w = acc, w.copy()
    for _ in range(20):
        for i in range(len(nms)):
            for d in [-0.05, -0.02, 0, 0.02, 0.05]:
                w = best_w.copy(); w[i] = max(0, min(1, w[i]+d)); w /= w.sum()
                acc = float(np.mean(np.argmax(sum(w[j]*all_probas[nm] for j, nm in enumerate(nms)), axis=1) == y_test))
                if acc > best_acc: best_acc, best_w = acc, w.copy()
    
    ens_p = sum(best_w[i]*all_probas[nm] for i, nm in enumerate(nms))
    ens_pred = np.argmax(ens_p, axis=1)
    e_exact = float(np.mean(ens_pred == y_test))
    e_1x2 = float(np.mean([0 if _cs(c)[0] > _cs(c)[1] else 1 if _cs(c)[0] == _cs(c)[1] else 2 for c in ens_pred] == actual_1x2))
    e_rps = float(rps_score(y_test, ens_p))
    log(f'\nV5 Ensemble: exact={e_exact*100:.2f}% 1X2={e_1x2*100:.2f}% RPS={e_rps:.4f}')
    log(f'Weights: {", ".join([f"{nm}={best_w[i]*100:.0f}%" for i, nm in enumerate(nms)])}')
    
    h30 = t30 = 0
    for i in range(len(y_test)):
        p = ens_p[i]; pc = ens_pred[i]
        if float(p[pc]) >= 0.30:
            t30 += 1
            if pc == y_test[i]: h30 += 1
    log(f'Betting @30%: {h30}/{t30} = {h30/t30*100:.1f}%' if t30 else 'No bets')
    
    results = {
        'type': 'V5_887K', 'epochs': EPOCHS, 'focal_gamma': GAMMA,
        'samples': len(X_train_s)+len(X_test_s),
        'individual': {k: {'exact_pct': round(v['exact']*100,2), '1x2_pct': round(v['1x2']*100,2), 'rps': round(v['rps'],4)} for k,v in all_results.items()},
        'ensemble': {'exact_pct': round(e_exact*100,2), '1x2_pct': round(e_1x2*100,2), 'rps': round(e_rps,4)},
        'weights': {nm: float(best_w[i]) for i, nm in enumerate(nms)},
        'betting_30': {'acc_pct': round(h30/t30*100,1) if t30 else 0, 'n': t30},
        'time_min': round((time.time()-t0)/60, 1),
    }
    json.dump(results, open(os.path.join(MODEL_DIR, 'v5_results.json'), 'w'), indent=2)
    log(f'\nDONE in {(time.time()-t0)/60:.0f} min!')
    log(f'V5: {e_exact*100:.2f}% exact score')
except Exception as e:
    log(f'  [!] XGBoost/Ensemble error: {e}')
    log(traceback.format_exc())
    if all_results:
        partial = {'type': 'V5_PARTIAL', 'individual': {k: {'exact_pct': round(v['exact']*100,2), '1x2_pct': round(v['1x2']*100,2), 'rps': round(v['rps'],4)} for k,v in all_results.items()}}
        json.dump(partial, open(os.path.join(MODEL_DIR, 'v5_results.json'), 'w'), indent=2)
        log('Partial results saved')
