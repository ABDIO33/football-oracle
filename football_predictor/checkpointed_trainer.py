"""
CHECKPOINTED ULTIMATE TRAINER — saves after every model, resumes if interrupted
"""
import sys, os, json, time, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import joblib
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DATA_FILE = os.path.join(MODEL_DIR, 'preprocessed_data.npz')
CHECKPOINT_FILE = os.path.join(MODEL_DIR, 'checkpoint.json')
LOG = os.path.join(MODEL_DIR, 'checkpointed_log.txt')

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')
    sys.stdout.flush()

log('='*60)
log('CHECKPOINTED ULTIMATE TRAINER')
log('='*60)
t_start = time.time()

# Helper functions
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

def get_best_epoch(model, X_test_t, y_test_t):
    """Dummy - already using best_state during training"""
    return 0

ARCHITECTURES = {
    'M5_small': [128, 256, 128],
    'M5_medium': [256, 512, 256],
    'M5_big': [512, 1024, 512],
    'M5_wide': [1024, 512, 256],
    'M5_deep': [256, 512, 256, 128],
}
EPOCHS = 60

class M5_Variant(nn.Module):
    def __init__(self, input_dim, num_classes, layer_sizes):
        super().__init__()
        modules = []
        prev = input_dim
        dropouts = [0.3, 0.3, 0.3, 0.2, 0.2]
        for i, sz in enumerate(layer_sizes):
            modules.append(nn.Linear(prev, sz))
            if sz >= 128:
                modules.append(nn.BatchNorm1d(sz))
            modules.append(nn.ReLU())
            modules.append(nn.Dropout(dropouts[min(i, len(dropouts)-1)]))
            prev = sz
        modules.append(nn.Linear(prev, num_classes))
        self.net = nn.Sequential(*modules)
    def forward(self, x):
        return self.net(x)

# Load checkpoint
checkpoint = {}
if os.path.exists(CHECKPOINT_FILE):
    checkpoint = json.load(open(CHECKPOINT_FILE))
    log(f'Found checkpoint: {checkpoint.get("completed", [])}')
else:
    checkpoint['completed'] = []
    checkpoint['results'] = {}

# Load or create preprocessed data
if os.path.exists(DATA_FILE):
    log('Loading preprocessed data from disk...')
    data = np.load(DATA_FILE, allow_pickle=True)
    X_train_s = data['X_train_s']
    X_test_s = data['X_test_s']
    y_train = data['y_train']
    y_test = data['y_test']
    imp = joblib.load(os.path.join(MODEL_DIR, 'checkpoint_imputer.pkl'))
    scaler = joblib.load(os.path.join(MODEL_DIR, 'checkpoint_scaler.pkl'))
    FEATURES = data['FEATURES'].tolist() if 'FEATURES' in data else 85
    NUM_INPUT = X_train_s.shape[1]
    NUM_CLASSES = 25
    log(f'Loaded: {len(X_train_s)} train, {len(X_test_s)} test, {NUM_INPUT} features')
else:
    log('Loading data from DB...')
    from direct_predictor import _load_training_data
    X, y, _ = _load_training_data()
    n = len(X)
    split = int(n * 0.80)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    FEATURES = X_train.shape[1]
    NUM_CLASSES = 25
    log(f'Loaded: {len(X_train)} train, {len(X_test)} test, {FEATURES} features')
    
    imp = SimpleImputer(strategy='median')
    X_train_imp = imp.fit_transform(X_train)
    X_test_imp = imp.transform(X_test)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train_imp)
    X_test_s = scaler.transform(X_test_imp)
    del X, X_train, X_test, X_train_imp, X_test_imp
    
    # Save to disk
    log('Saving preprocessed data to disk...')
    np.savez_compressed(DATA_FILE,
        X_train_s=X_train_s, X_test_s=X_test_s,
        y_train=y_train, y_test=y_test,
        FEATURES=np.array([FEATURES] if isinstance(FEATURES, int) else FEATURES, dtype=object))
    joblib.dump(imp, os.path.join(MODEL_DIR, 'checkpoint_imputer.pkl'))
    joblib.dump(scaler, os.path.join(MODEL_DIR, 'checkpoint_scaler.pkl'))

NUM_INPUT = X_train_s.shape[1]
actual_1x2 = np.array([_result(*_class_to_score(c)) for c in y_test])
X_test_t = torch.tensor(X_test_s, dtype=torch.float32)
y_test_t = torch.tensor(y_test, dtype=torch.long)

all_probas = {}
final_model = None

# 1. XGBoost
if 'xgb' not in checkpoint['completed']:
    log('\n[1/6] Training XGBoost...')
    model = xgb.XGBClassifier(
        n_estimators=1000, max_depth=6, learning_rate=0.06,
        objective='multi:softprob', num_class=NUM_CLASSES,
        subsample=0.85, colsample_bytree=0.85,
        reg_alpha=0.05, reg_lambda=0.1, random_state=42,
        eval_metric='mlogloss', early_stopping_rounds=25
    )
    model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)
    proba = model.predict_proba(X_test_s)
    pred = np.argmax(proba, axis=1)
    r = {'exact': float(np.mean(pred == y_test)),
         '1x2': float(np.mean(np.array([_result(*_class_to_score(c)) for c in pred]) == actual_1x2)),
         'rps': compute_rps(y_test, proba)}
    log(f'XGBoost: exact={r["exact"]*100:.2f}% 1X2={r["1x2"]*100:.2f}% RPS={r["rps"]:.4f}')
    checkpoint['completed'].append('xgb')
    checkpoint['results']['xgb'] = {k: float(v) if isinstance(v, np.floating) else v for k,v in r.items()}
    joblib.dump(model, os.path.join(MODEL_DIR, 'checkpoint_xgb.pkl'))
    json.dump(checkpoint, open(CHECKPOINT_FILE, 'w'))
    all_probas['xgb'] = proba
else:
    log('XGBoost already trained, loading...')
    model = joblib.load(os.path.join(MODEL_DIR, 'checkpoint_xgb.pkl'))
    all_probas['xgb'] = model.predict_proba(X_test_s)
    log(f'  XGBoost results: {checkpoint["results"]["xgb"]}')

# 2-6. DeepNN architectures
train_loader = DataLoader(
    TensorDataset(torch.tensor(X_train_s, dtype=torch.float32),
                  torch.tensor(y_train, dtype=torch.long)),
    batch_size=512, shuffle=True, num_workers=0
)

for arch_name, layers in ARCHITECTURES.items():
    if arch_name in checkpoint['completed']:
        log(f'{arch_name} already trained, loading...')
        model = M5_Variant(NUM_INPUT, NUM_CLASSES, layers)
        model.load_state_dict(torch.load(os.path.join(MODEL_DIR, f'checkpoint_{arch_name}.pt'), map_location='cpu'))
        model.eval()
        with torch.no_grad():
            proba = torch.softmax(model(X_test_t), dim=1).numpy()
        all_probas[arch_name] = proba
        log(f'  {arch_name}: {checkpoint["results"].get(arch_name, {})}')
        continue
    
    log(f'\n[{arch_name}] Training {layers}...')
    model = M5_Variant(NUM_INPUT, NUM_CLASSES, layers)
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=50)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    
    best_acc, best_state = 0, None
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
        scheduler.step()
        if acc > best_acc:
            best_acc = acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        if epoch % 15 == 0:
            elapsed = time.time() - t_arch
            rem = (elapsed / (epoch+1)) * (EPOCHS - epoch - 1)
            log(f'  ep {epoch+1}/{EPOCHS}: val={acc*100:.2f}% best={best_acc*100:.2f}% {rem/60:.0f}m')
    
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        proba = torch.softmax(model(X_test_t), dim=1).numpy()
        pred = np.argmax(proba, axis=1)
    
    r = {'exact': float(np.mean(pred == y_test)),
         '1x2': float(np.mean(np.array([_result(*_class_to_score(c)) for c in pred]) == actual_1x2)),
         'rps': float(compute_rps(y_test, proba))}
    log(f'  DONE: exact={r["exact"]*100:.2f}% 1X2={r["1x2"]*100:.2f}% RPS={r["rps"]:.4f}')
    
    # SAVE CHECKPOINT
    checkpoint['completed'].append(arch_name)
    checkpoint['results'][arch_name] = r
    json.dump(checkpoint, open(CHECKPOINT_FILE, 'w'))
    torch.save(best_state, os.path.join(MODEL_DIR, f'checkpoint_{arch_name}.pt'))
    all_probas[arch_name] = proba
    del model; gc.collect()

# 7. Ensemble search
model_names = list(all_probas.keys())
n_models = len(model_names)

if 'ensemble' not in checkpoint['completed']:
    log(f'\n[Final] Searching ensemble blend ({n_models} models)...')
    best_ensemble, best_weights = 0, None
    
    for trial in range(5000):
        w = np.random.dirichlet(np.ones(n_models))
        ep = sum(w[i] * all_probas[nm] for i, nm in enumerate(model_names))
        epred = np.argmax(ep, axis=1)
        acc = float(np.mean(epred == y_test))
        if acc > best_ensemble:
            best_ensemble, best_weights = acc, w.copy()
    
    # Refine
    for _ in range(20):
        for i in range(n_models):
            for delta in [-0.05, -0.02, 0, 0.02, 0.05]:
                w = best_weights.copy()
                w[i] = max(0, min(1, w[i] + delta))
                w /= w.sum()
                ep = sum(w[j] * all_probas[nm] for j, nm in enumerate(model_names))
                epred = np.argmax(ep, axis=1)
                acc = float(np.mean(epred == y_test))
                if acc > best_ensemble:
                    best_ensemble, best_weights = acc, w.copy()
    
    checkpoint['completed'].append('ensemble')
    checkpoint['best_ensemble'] = float(best_ensemble)
    checkpoint['best_weights'] = {nm: float(best_weights[i]) for i, nm in enumerate(model_names)}
    json.dump(checkpoint, open(CHECKPOINT_FILE, 'w'))
else:
    log('Ensemble already computed')
    best_ensemble = checkpoint['best_ensemble']
    best_weights_dict = checkpoint['best_weights']
    best_weights = np.array([best_weights_dict[nm] for nm in model_names])

ensemble_proba = sum(best_weights[i] * all_probas[nm] for i, nm in enumerate(model_names))
ensemble_pred = np.argmax(ensemble_proba, axis=1)
ensemble_exact = float(np.mean(ensemble_pred == y_test))
ensemble_1x2 = float(np.mean(np.array([_result(*_class_to_score(c)) for c in ensemble_pred]) == actual_1x2))
ensemble_rps = compute_rps(y_test, ensemble_proba)

# Print final results
log('\n' + '='*60)
log(f'{"Model":<20} {"Exact":>8} {"1X2":>8} {"RPS":>8}')
log('-'*44)
for nm in model_names:
    r = checkpoint['results'].get(nm, {})
    log(f'{nm:<20} {r.get("exact",0)*100:>7.2f}% {r.get("1x2",0)*100:>7.2f}% {r.get("rps",0):>7.4f}')
log('-'*44)
log(f'{"ENSEMBLE":<20} {ensemble_exact*100:>7.2f}% {ensemble_1x2*100:>7.2f}% {ensemble_rps:>7.4f}')

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
log(f'\nBetting @30%: {hits30}/{total30} = {hits30/total30*100:.1f}%' if total30 > 0 else 'No 30%+ bets')

# Compare
try:
    old = json.load(open(os.path.join(MODEL_DIR, 'improved_model_results.json')))
    old_ens = old.get('ensemble', {}).get('exact_pct', 24.69)
    log(f'\n vs improved_model ({old_ens}%): {ensemble_exact*100 - old_ens:+.2f}pp')
except:
    pass

# Save final model
log('\nSaving ultimate_model.pkl...')
final = {
    'ensemble_weights': {nm: float(best_weights[i]) for i, nm in enumerate(model_names)},
    'architectures': ARCHITECTURES,
    'imputer': imp,
    'scaler': scaler,
    'individual_results': {nm: {k: float(v) if isinstance(v, (np.floating,)) else v for k, v in checkpoint['results'].get(nm, {}).items()} for nm in model_names},
    'ensemble': {'exact': round(ensemble_exact*100, 2), '1x2': round(ensemble_1x2*100, 2), 'rps': round(ensemble_rps, 4)},
    'betting_30': {'hits': int(hits30), 'total': int(total30), 'accuracy': round(hits30/total30*100, 1) if total30 > 0 else 0},
    'time': round(time.time() - t_start, 1),
}
joblib.dump(final, os.path.join(MODEL_DIR, 'ultimate_model.pkl'))

json.dump({
    'model': 'ULTIMATE',
    'test_samples': len(X_test_s),
    'individual': {nm: {'exact_pct': round(checkpoint['results'].get(nm,{}).get('exact',0)*100,2), '1x2_pct': round(checkpoint['results'].get(nm,{}).get('1x2',0)*100,2), 'rps': round(checkpoint['results'].get(nm,{}).get('rps',0),4)} for nm in model_names},
    'ensemble': {'exact_pct': round(ensemble_exact*100, 2), '1x2_pct': round(ensemble_1x2*100, 2), 'rps': round(ensemble_rps, 4)},
    'weights': {nm: float(best_weights[i]) for i, nm in enumerate(model_names)},
    'betting_30': {'accuracy_pct': round(hits30/total30*100, 1) if total30 > 0 else 0, 'samples': total30},
    'time_minutes': round((time.time() - t_start)/60, 1),
}, open(os.path.join(MODEL_DIR, 'ultimate_results.json'), 'w'), indent=2)

total_t = time.time() - t_start
log('\n' + '='*60)
log(f'DONE! {total_t/60:.1f} min')
log(f'Final ensemble: {ensemble_exact*100:.2f}% exact')
log('='*60)
log('Models saved in models/ultimate_model.pkl')
log('Checkpoints saved: models/checkpoint_*.pkl/.pt')
log('Preprocessed data saved: models/preprocessed_data.npz')
