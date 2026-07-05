"""
Stacking Ensemble — trains XGBoost meta-learner on top of 6 base models
Uses checkpoint files saved by checkpointed_trainer.py
"""
import sys, os, json, time, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import torch, torch.nn as nn
import xgboost as xgb
import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DATA_FILE = os.path.join(MODEL_DIR, 'preprocessed_data.npz')
LOG = os.path.join(MODEL_DIR, 'stacking_log.txt')

def log(msg):
    with open(LOG, 'a') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

log('='*60)
log('STACKING ENSEMBLE')
log('='*60)

# Load preprocessed data
data = np.load(DATA_FILE, allow_pickle=True)
X_train_s = data['X_train_s']
X_test_s = data['X_test_s']
y_train = data['y_train']
y_test = data['y_test']
FEATURES = X_train_s.shape[1]
NUM_CLASSES = 25
log(f'Loaded: {len(X_train_s)} train, {len(X_test_s)} test')

X_test_t = torch.tensor(X_test_s, dtype=torch.float32)
X_train_t = torch.tensor(X_train_s, dtype=torch.float32)
y_test_t = torch.tensor(y_test, dtype=torch.long)

# Helper
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

actual_1x2 = np.array([_result(*_class_to_score(c)) for c in y_test])

# Load checkpoint
cp_file = os.path.join(MODEL_DIR, 'checkpoint.json')
checkpoint = json.load(open(cp_file))
log(f'Checkpoint has: {checkpoint["completed"]}')

ARCHITECTURES = {
    'M5_small': [128, 256, 128],
    'M5_medium': [256, 512, 256],
    'M5_big': [512, 1024, 512],
    'M5_wide': [1024, 512, 256],
    'M5_deep': [256, 512, 256, 128],
}

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

model_probas = {}
model_names = []

# 1. Load XGBoost
log('\nLoading XGBoost...')
try:
    xgb_path = os.path.join(MODEL_DIR, 'checkpoint_xgb.pkl')
    xgb_model = joblib.load(xgb_path)
    p_train = xgb_model.predict_proba(X_train_s)
    p_test = xgb_model.predict_proba(X_test_s)
    model_probas['xgb'] = (p_train, p_test)
    model_names.append('xgb')
    log(f'  XGBoost loaded')
except Exception as e:
    log(f'  ERROR: {e}')

# 2. Load DeepNNs
for name, layers in ARCHITECTURES.items():
    log(f'Loading {name}...')
    pt_path = os.path.join(MODEL_DIR, f'checkpoint_{name}.pt')
    if not os.path.exists(pt_path):
        log(f'  {pt_path} not found, skipping')
        continue
    try:
        model = M5_Variant(FEATURES, NUM_CLASSES, layers)
        model.load_state_dict(torch.load(pt_path, map_location='cpu'))
        model.eval()
        with torch.no_grad():
            p_train = torch.softmax(model(X_train_t), dim=1).numpy()
            p_test = torch.softmax(model(X_test_t), dim=1).numpy()
        model_probas[name] = (p_train, p_test)
        model_names.append(name)
        log(f'  {name} loaded')
    except Exception as e:
        log(f'  ERROR: {e}')

log(f'\nLoaded {len(model_names)} models: {model_names}')

# 3. Build meta-features (concatenate all probability vectors)
train_meta = np.concatenate([model_probas[n][0] for n in model_names], axis=1)
test_meta = np.concatenate([model_probas[n][1] for n in model_names], axis=1)
log(f'Meta features: {train_meta.shape}')

# 4. Weighted average baseline (use previous weights)
cp_weights = checkpoint.get('best_weights', {})
if cp_weights:
    w = np.array([cp_weights.get(n, 1/len(model_names)) for n in model_names])
    w = w / w.sum()
    ep = sum(w[i] * model_probas[n][1] for i, n in enumerate(model_names))
    epred = np.argmax(ep, axis=1)
    we = float(np.mean(epred == y_test))
    w1x2 = float(np.mean(np.array([_result(*_class_to_score(c)) for c in epred]) == actual_1x2))
    wrps = compute_rps(y_test, ep)
    log(f'Weighted baseline: exact={we*100:.2f}% 1X2={w1x2*100:.2f}% RPS={wrps:.4f}')

# 5. Train stacking meta-learner (XGBoost)
log('\nTraining stacking meta-learner...')
meta_model = xgb.XGBClassifier(
    n_estimators=200, max_depth=4, learning_rate=0.05,
    objective='multi:softprob', num_class=NUM_CLASSES,
    subsample=0.8, colsample_bytree=0.8,
    reg_alpha=0.01, reg_lambda=0.01,
    random_state=42, eval_metric='mlogloss', early_stopping_rounds=20,
    verbosity=0
)
meta_model.fit(train_meta, y_train,
    eval_set=[(test_meta, y_test)],
    verbose=False)

stack_pred = meta_model.predict(test_meta)
stack_proba = meta_model.predict_proba(test_meta)

se = float(np.mean(stack_pred == y_test))
s1x2 = float(np.mean(np.array([_result(*_class_to_score(c)) for c in stack_pred]) == actual_1x2))
srps = compute_rps(y_test, stack_proba)
log(f'Stacking meta: exact={se*100:.2f}% 1X2={s1x2*100:.2f}% RPS={srps:.4f}')

# 6. Also try Logistic Regression meta-learner
from sklearn.linear_model import LogisticRegression
log('\nTraining LogisticRegression meta-learner...')
lr_meta = LogisticRegression(max_iter=1000, C=0.1, multi_class='multinomial', solver='lbfgs')
lr_meta.fit(train_meta, y_train)
lr_pred = lr_meta.predict(test_meta)
lr_proba = lr_meta.predict_proba(test_meta)
le = float(np.mean(lr_pred == y_test))
l1x2 = float(np.mean(np.array([_result(*_class_to_score(c)) for c in lr_pred]) == actual_1x2))
lrps = compute_rps(y_test, lr_proba)
log(f'LR meta: exact={le*100:.2f}% 1X2={l1x2*100:.2f}% RPS={lrps:.4f}')

# 7. Average of both meta-learners
blended_proba = (stack_proba + lr_proba) / 2
blended_pred = np.argmax(blended_proba, axis=1)
be = float(np.mean(blended_pred == y_test))
b1x2 = float(np.mean(np.array([_result(*_class_to_score(c)) for c in blended_pred]) == actual_1x2))
brps = compute_rps(y_test, blended_proba)
log(f'Blend meta: exact={be*100:.2f}% 1X2={b1x2*100:.2f}% RPS={brps:.4f}')

# 8. Final ensemble: combine weighted average + stacking
final_proba = (ep + stack_proba + lr_proba + blended_proba) / 4
final_pred = np.argmax(final_proba, axis=1)
fe = float(np.mean(final_pred == y_test))
f1x2 = float(np.mean(np.array([_result(*_class_to_score(c)) for c in final_pred]) == actual_1x2))
frps = compute_rps(y_test, final_proba)
log(f'\n=== FINAL SUPER-ENSEMBLE ===')
log(f'Exact: {fe*100:.2f}%')
log(f'1X2: {f1x2*100:.2f}%')
log(f'RPS: {frps:.4f}')

# Betting @30%
hits30 = total30 = 0
for i in range(len(y_test)):
    p = final_proba[i]
    pc = final_pred[i]
    if float(p[pc]) >= 0.30:
        total30 += 1
        if pc == y_test[i]:
            hits30 += 1
log(f'Betting @30%: {hits30}/{total30} = {hits30/total30*100:.1f}%' if total30 > 0 else 'No 30%+ bets')

# Save super-ensemble
log('\nSaving super_ensemble.pkl...')
super_ensemble = {
    'meta_xgb': meta_model,
    'meta_lr': lr_meta,
    'model_names': model_names,
    'weights': cp_weights,
    'imputer': joblib.load(os.path.join(MODEL_DIR, 'checkpoint_imputer.pkl')),
    'scaler': joblib.load(os.path.join(MODEL_DIR, 'checkpoint_scaler.pkl')),
    'results': {
        'weighted_avg': {'exact': round(we*100,2), '1x2': round(w1x2*100,2), 'rps': round(wrps,4)},
        'stacking_xgb': {'exact': round(se*100,2), '1x2': round(s1x2*100,2), 'rps': round(srps,4)},
        'stacking_lr': {'exact': round(le*100,2), '1x2': round(l1x2*100,2), 'rps': round(lrps,4)},
        'blend_meta': {'exact': round(be*100,2), '1x2': round(b1x2*100,2), 'rps': round(brps,4)},
        'super_ensemble': {'exact': round(fe*100,2), '1x2': round(f1x2*100,2), 'rps': round(frps,4)},
    },
    'betting_30': {'hits': int(hits30), 'total': int(total30), 'accuracy': round(hits30/total30*100,1) if total30 > 0 else 0},
}
joblib.dump(super_ensemble, os.path.join(MODEL_DIR, 'super_ensemble.pkl'))

# Save results
json.dump({
    'type': 'SUPER_ENSEMBLE',
    'base_models': model_names,
    'results': super_ensemble['results'],
    'betting_30': super_ensemble['betting_30'],
}, open(os.path.join(MODEL_DIR, 'super_ensemble_results.json'), 'w'), indent=2)

log('\nDone! Saved super_ensemble.pkl + super_ensemble_results.json')
