"""
train_xgb_background.py — تدريب XGBoost في الخلفية لتنوع ensemble
يستخدم subset 100K لتسريع التدريب
"""
import sys, os, time, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

logfile = open('training_xgb_log.txt', 'w', encoding='utf-8')
def p(msg):
    print(msg, flush=True)
    logfile.write(msg + '\n'); logfile.flush()

p('XGBoost Background Training Started')
p('='*50)

# Load data
data = np.load('training_data_v3.npz', allow_pickle=True)
X = data['X'].astype(np.float32); y = data['y'].astype(np.int32)
order = np.argsort(data['match_ids'])
X, y = X[order], y[order]
n = len(X); n_tr = int(n * 0.8); n_v = int(n * 0.1)
X_tr, y_tr = X[:n_tr], y[:n_tr]; X_v, y_v = X[n_tr:n_tr+n_v], y[n_tr:n_tr+n_v]
X_te, y_te = X[n_tr+n_v:], y[n_tr+n_v:]

# Use subset (100K) for speed
idx = np.random.RandomState(42).choice(len(y_tr), 100000, replace=False)
Xs, ys = X_tr[idx], y_tr[idx]
p(f'Train: {len(ys):,} Val: {len(y_v):,} Test: {len(y_te):,} Feats: {X.shape[1]}')

import xgboost as xgb
t0 = time.time()

p('Training XGBoost M1 (depth=6, 300 trees)...')
m1 = xgb.XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.08,
    subsample=0.8, colsample_bytree=0.6, reg_alpha=0.01, reg_lambda=0.1,
    tree_method='hist', random_state=42, n_jobs=8,
    eval_metric='mlogloss', early_stopping_rounds=30, verbose=0)
m1.fit(Xs, ys, eval_set=[(X_v, y_v)])
p1 = m1.predict(X_te)
ex1 = float(np.mean(p1 == y_te))
p(f'  XGB-M1: exact={ex1*100:.2f}% [{time.time()-t0:.0f}s]')

p('Training XGBoost M2 (depth=8, 200 trees)...')
m2 = xgb.XGBClassifier(n_estimators=200, max_depth=8, learning_rate=0.06,
    subsample=0.7, colsample_bytree=0.5, reg_alpha=0.05, reg_lambda=0.2,
    tree_method='hist', random_state=43, n_jobs=8,
    eval_metric='mlogloss', early_stopping_rounds=30, verbose=0)
m2.fit(Xs, ys, eval_set=[(X_v, y_v)])
p2 = m2.predict(X_te)
ex2 = float(np.mean(p2 == y_te))
p(f'  XGB-M2: exact={ex2*100:.2f}% [{time.time()-t0:.0f}s]')

p('Training XGBoost M3 (depth=4, 400 trees)...')
m3 = xgb.XGBClassifier(n_estimators=400, max_depth=4, learning_rate=0.1,
    subsample=0.9, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=0.3,
    tree_method='hist', random_state=44, n_jobs=8,
    eval_metric='mlogloss', early_stopping_rounds=30, verbose=0)
m3.fit(Xs, ys, eval_set=[(X_v, y_v)])
p3 = m3.predict(X_te)
ex3 = float(np.mean(p3 == y_te))
p(f'  XGB-M3: exact={ex3*100:.2f}% [{time.time()-t0:.0f}s]')

# Ensemble with LightGBM
import joblib, json

# Load V3 LightGBM ensemble and get its predictions
p('Loading V3 ensemble for blending...')
v3 = joblib.load('models/ultimate_30pct_ensemble.pkl')
v3_probs = [m.predict_proba(X_te) for m in v3['models']]
v3_blend = np.mean(v3_probs, axis=0)
v3_preds = np.argmax(v3_blend, axis=1)

# XGBoost predictions
xgb_probs = [m1.predict_proba(X_te), m2.predict_proba(X_te), m3.predict_proba(X_te)]
xgb_blend = np.mean(xgb_probs, axis=0)
xgb_preds = np.argmax(xgb_blend, axis=1)

# V3 + XGB combined
final = (v3_blend + xgb_blend) / 2
final_preds = np.argmax(final, axis=1)
ex_final = float(np.mean(final_preds == y_te))

# V3 only
ex_v3_only = float(np.mean(v3_preds == y_te))

p(f'')
p(f'V3 LightGBM only: exact={ex_v3_only*100:.2f}%')
p(f'XGBoost only:     exact={float(np.mean(xgb_preds==y_te))*100:.2f}%')
p(f'V3+XGB Hybrid:    exact={ex_final*100:.2f}%')
p(f'---')
p(f'Improvement: {ex_final*100 - ex_v3_only*100:+.2f}pp')

# 1X2
yh, ya = y_te//5, y_te%5
ph, pa = final_preds//5, final_preds%5
yr = np.where(yh>ya,0,np.where(yh==ya,1,2))
pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
x1_final = float(np.mean(yr==pr))
p(f'V3+XGB 1X2: {x1_final*100:.2f}%')

# Save
ens = {
    'models': v3['models'] + [m1, m2, m3],
    'names': v3['names'] + ['XGB-M1', 'XGB-M2', 'XGB-M3'],
    'weights': None  # equal weight by default
}
joblib.dump(ens, 'models/ultimate_hybrid.pkl', compress=3)

res = {
    'test_exact': float(ex_final),
    'test_1x2': float(x1_final),
    'v3_exact': float(ex_v3_only),
    'xgb_exact': [ex1, ex2, ex3],
    'time_min': (time.time()-t0)/60
}
with open('models/hybrid_results.json', 'w') as f:
    json.dump(res, f, indent=2)

p(f'')
p(f'SAVED! Total time: {(time.time()-t0)/60:.1f} min')
p(f'Final exact: {ex_final*100:.2f}%')
p(f'Final 1X2: {x1_final*100:.2f}%')

logfile.close()
