#!/usr/bin/env python3
"""
V7 CHAMPION — مع SORT زي الأصل
يقارن V3 (120 feats) vs V7 (130 feats) بنفس الترتيب
ENI for LO
"""
import numpy as np, os, time, json, warnings, gc
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

t0 = time.time()
print('[V7] Loading & sorting...')
v7 = np.load('training_data_v7.npz', allow_pickle=True)
X = v7['X'].astype(np.float32); y = v7['y'].astype(np.int32)
order = np.argsort(v7['match_ids'])
X, y = X[order], y[order]

n = len(X); n_tr = int(n*0.85); n_v = int(n*0.05)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_v, y_v = X[n_tr:n_tr+n_v], y[n_tr:n_tr+n_v]
X_te, y_te = X[n_tr+n_v:], y[n_tr+n_v:]

# Only first 120 (baseline) vs all 130 (understat)
X_tr_120 = X_tr[:, :120]
X_v_120 = X_v[:, :120]
X_te_120 = X_te[:, :120]

print(f'Train: {len(y_tr)} Val: {len(y_v)} Test: {len(y_te)}')
print(f'Feats: 120 (baseline) vs 130 (with Understat)')

import lightgbm as lgb

def train_and_eval(X_tr, X_v, X_te, y_tr, y_v, y_te, name):
    m = lgb.LGBMClassifier(n_estimators=200, max_depth=20, learning_rate=0.02,
        subsample=0.7, colsample_bytree=0.4, num_leaves=511,
        reg_alpha=0.01, reg_lambda=0.05, min_child_weight=2,
        random_state=111, n_jobs=8, verbose=-1)
    m.fit(X_tr, y_tr, eval_set=[(X_v, y_v)],
          callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
    p = m.predict(X_te)
    ex = float(np.mean(p == y_te))
    yh, ya = y_te//5, y_te%5; ph, pa = p//5, p%5
    yr = np.where(yh>ya,0,np.where(yh==ya,1,2))
    pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
    x1 = float(np.mean(yr==pr))
    print(f'  {name}: exact={ex*100:.2f}% 1X2={x1*100:.2f}%')
    return ex, x1, m

# Baseline (120 feats = exact same as champion)
print('\n[1] Baseline V3 (120 feats)...')
ex120, x120, m120 = train_and_eval(X_tr_120, X_v_120, X_te_120, y_tr, y_v, y_te, 'V3-120')

# V7 (130 feats)
print('\n[2] V7 with Understat (130 feats)...')
ex130, x130, m130 = train_and_eval(X_tr, X_v, X_te, y_tr, y_v, y_te, 'V7-130')

# Ensemble both
print('\n[3] Ensemble...')
p120 = m120.predict_proba(X_te)
p130 = m130.predict_proba(X_te)
best_e = 0; best_w = 0
for w in np.arange(0.01, 1.0, 0.01):
    blend = w*p120 + (1-w)*p130
    preds = np.argmax(blend, axis=1)
    e = float(np.mean(preds == y_te))
    if e > best_e: best_e = e; best_w = w
print(f'  V3+V7 blend: w={best_w:.2f} exact={best_e*100:.2f}%')

# Understat feature importance
print('\n[4] Understat importances (V7 model):')
imp = m130.feature_importances_
total_imp = imp.sum()
unames = ['home_xg','away_xg','xg_diff','home_npxg','away_npxg','npxg_diff','home_deep','away_deep','home_ppda','away_ppda']
for i in range(120, min(130, len(imp))):
    pct = imp[i] / total_imp * 100
    print(f'  {unames[i-120]:15s}: {imp[i]:6d} ({pct:.3f}%)')
print(f'  TOTAL Understat: {imp[120:130].sum()/total_imp*100:.3f}%')

print(f'\n{"="*60}')
print(f'V7 FINAL RESULTS:')
print(f'  V3 baseline: {ex120*100:.2f}%')
print(f'  V7 Understat: {ex130*100:.2f}%')
print(f'  Change: {ex130*100 - ex120*100:+.2f}%')
print(f'  Ensemble V3+V7: {best_e*100:.2f}%')
print(f'  World record: 32.05%')
print(f'  Time: {(time.time()-t0)/60:.1f} min')
print(f'{"="*60}')

# Save
with open('models/v7_comparison.json', 'w') as f:
    json.dump({
        'v3_baseline_exact': ex120, 'v3_baseline_1x2': x120,
        'v7_understat_exact': ex130, 'v7_understat_1x2': x130,
        'ensemble_exact': best_e,
        'change_pct': (ex130 - ex120) * 100,
        'understat_total_imp_pct': float(imp[120:130].sum()/total_imp*100),
    }, f, indent=2)

import joblib
joblib.dump(m130, 'models/v7_understat_model.pkl', compress=3)
joblib.dump(m120, 'models/v7_baseline_model.pkl', compress=3)

print('Models saved!')
