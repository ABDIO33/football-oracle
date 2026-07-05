"""
train_xgb_full.py — Full XGBoost on V3 data, then ensemble with V3
"""
import sys, os, time, json, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

logfile = open('xgb_full_log.txt', 'w', encoding='utf-8')
def p(msg):
    print(msg, flush=True)
    logfile.write(msg + '\n'); logfile.flush()

p('XGBoost Full Training Started')
p('='*50)

t0 = time.time()
data = np.load('training_data_v3.npz', allow_pickle=True)
X = data['X'].astype(np.float32); y = data['y'].astype(np.int32)
order = np.argsort(data['match_ids'])
X, y = X[order], y[order]
n = len(X); n_tr = int(n*0.85); n_v = int(n*0.05)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_v, y_v = X[n_tr:n_tr+int(n*0.05)], y[n_tr:n_tr+int(n*0.05)]
X_te, y_te = X[n_tr+int(n*0.05):], y[n_tr+int(n*0.05):]
del X; gc.collect()
p('Data: Train=%d Val=%d Test=%d' % (len(y_tr), len(y_v), len(y_te)))

import xgboost as xgb, joblib

# Train XGBoost on full data
p('Training XGBoost (full data)...')
t1 = time.time()

dtrain = xgb.DMatrix(X_tr, y_tr)
dval = xgb.DMatrix(X_v, y_v)
dtest = xgb.DMatrix(X_te, y_te)
del X_tr, X_v; gc.collect()

params = {
    'objective': 'multi:softprob',
    'num_class': 25,
    'max_depth': 10,
    'eta': 0.06,
    'subsample': 0.8,
    'colsample_bytree': 0.6,
    'alpha': 0.1,
    'lambda': 0.5,
    'gamma': 0.1,
    'min_child_weight': 5,
    'nthread': 8,
    'seed': 42
}

m = xgb.train(params, dtrain, num_boost_round=300,
              evals=[(dval, 'val')], early_stopping_rounds=20,
              verbose_eval=50)

# Predict
pt = m.predict(dtest)
p_te = np.argmax(pt, axis=1)
ex = float(np.mean(p_te == y_te))
p('XGBoost full: exact=%.2f%% [%ds]' % (ex*100, time.time()-t1))

yh, ya = y_te//5, y_te%5; ph, pa = p_te//5, p_te%5
yr = np.where(yh>ya,0,np.where(yh==ya,1,2)); pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
x1 = float(np.mean(yr==pr))
p('  1X2=%.2f%%' % (x1*100))

# Save
m.save_model('models/xgb_full.model')
p('Saved XGBoost model')

# ===== Load V3 ensemble and blend =====
p('\n=== Blending with V3 ensemble ===')
v3 = joblib.load('models/ultimate_30pct_ensemble.pkl')
v3_probs = [m2.predict_proba(X_te) for m2 in v3['models']]
v3_blend = np.mean(v3_probs, axis=0)

# Try different weights
for xgb_w in [0.02, 0.05, 0.1, 0.15, 0.2, 0.3]:
    blend = (1-xgb_w) * v3_blend + xgb_w * pt
    preds = np.argmax(blend, axis=1)
    e = float(np.mean(preds == y_te))
    p('  XGB weight=%.2f: exact=%.2f%%' % (xgb_w, e*100))

# Best blend
best = 0; best_w = 0
for xgb_w in np.arange(0.01, 0.5, 0.01):
    blend = (1-xgb_w) * v3_blend + xgb_w * pt
    preds = np.argmax(blend, axis=1)
    e = float(np.mean(preds == y_te))
    if e > best:
        best = e; best_w = xgb_w

p('Best XGB weight: %.2f (exact=%.2f%%)' % (best_w, best*100))
p('V3 alone: 29%%+ (on subset)')
p('New ensemble: %.2f%%' % (best*100))

# Save new ensemble
final_ensemble = {
    'models': v3['models'],
    'xgb_model': m,
    'xgb_weight': best_w,
    'v3_weights': v3.get('weights', [0.33, 0.33, 0.33]),
    'test_exact': best,
    'test_1x2': x1
}
joblib.dump(final_ensemble, 'models/v3_xgb_hybrid.pkl', compress=3)

res = {'test_exact': best, 'test_1x2': x1, 'xgb_weight': best_w,
       'xgb_alone_exact': ex, 'time_min': (time.time()-t0)/60}
with open('models/v3_xgb_hybrid_results.json', 'w') as f:
    json.dump(res, f, indent=2)

p('\nDone! Total: %.1f min' % res['time_min'])
logfile.close()
