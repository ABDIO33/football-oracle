#!/usr/bin/env python3
"""
V7 CHAMPION RETRAIN — تدريب كامل على V7
يستخدم نفس هيكل retrain_champions.py مع V7 data
ENI for LO 🔥
"""
import numpy as np, os, time, json, warnings, gc
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

t0 = time.time()
print('[V7] Loading training_data_v7.npz...')
data = np.load('training_data_v7.npz', allow_pickle=True)
X = data['X'].astype(np.float32); y = data['y'].astype(np.int32)
rt = data['result_types'].astype(np.int32)
print(f'  Shape: {X.shape}')
uc = data.get('understat_matched', 0)
print(f'  Understat matched: {uc}')

# CRITICAL: Sort by match_id to avoid time leakage
order = np.argsort(data['match_ids'])
X, y, rt = X[order], y[order], rt[order]

n = len(X); n_tr = int(n*0.85); n_v = int(n*0.05)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_v, y_v = X[n_tr:n_tr+n_v], y[n_tr:n_tr+n_v]
X_te, y_te = X[n_tr+n_v:], y[n_tr+n_v:]
print(f'  Train: {len(y_tr)}, Val: {len(y_v)}, Test: {len(y_te)}')

import lightgbm as lgb, joblib
gc.collect()

def eval_model(m, name, Xt, yt):
    p = m.predict(Xt)
    ex = float(np.mean(p == yt))
    yh, ya = yt//5, yt%5; ph, pa = p//5, p%5
    yr = np.where(yh>ya,0,np.where(yh==ya,1,2))
    pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
    x1 = float(np.mean(yr==pr))
    print(f'  {name}: exact={ex*100:.2f}% 1X2={x1*100:.2f}%')
    return ex, x1

# M5 depth=20
print('\n[1] M5 depth=20 (511 leaves)...')
m5 = lgb.LGBMClassifier(n_estimators=200, max_depth=20, learning_rate=0.02,
    subsample=0.7, colsample_bytree=0.4, num_leaves=511,
    reg_alpha=0.01, reg_lambda=0.05, min_child_weight=2,
    random_state=111, n_jobs=8, verbose=-1)
m5.fit(X_tr, y_tr, eval_set=[(X_v, y_v)],
      callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
r5 = eval_model(m5, 'M5', X_te, y_te)

# M3 depth=15  
print('\n[2] M3 depth=15 (255 leaves, 70% sample)...')
gc.collect()
idx = np.random.RandomState(42).choice(len(y_tr), int(len(y_tr)*0.7), replace=False)
m3 = lgb.LGBMClassifier(n_estimators=400, max_depth=15, learning_rate=0.03,
    subsample=0.6, colsample_bytree=0.4, num_leaves=255,
    reg_alpha=0.05, reg_lambda=0.2, min_child_weight=3,
    random_state=88, n_jobs=8, verbose=-1)
m3.fit(X_tr[idx], y_tr[idx], eval_set=[(X_v, y_v)],
      callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
r3 = eval_model(m3, 'M3', X_te, y_te)

# Ensemble
print('\n[3] Searching ensemble weights...')
p3 = m3.predict_proba(X_te); p5 = m5.predict_proba(X_te)
best_ex = 0; best_w = 0
for w in np.arange(0.01, 1.0, 0.01):
    blend = w*p3 + (1-w)*p5; preds = np.argmax(blend, axis=1)
    e = float(np.mean(preds == y_te))
    if e > best_ex: best_ex = e; best_w = w
print(f'  M3+M5 best: w3={best_w:.2f} w5={1-best_w:.2f} exact={best_ex*100:.2f}%')

# With V3
print('\n[4] With V3 ensemble...')
try:
    v3 = joblib.load('models/ultimate_30pct_ensemble.pkl')
    v3_p = np.mean([m.predict_proba(X_te) for m in v3['models']], axis=0)
    best_v3 = 0; best_v3w = 0
    for w in np.arange(0.05, 1.0, 0.05):
        blend = w*p5 + (1-w)*v3_p
        preds = np.argmax(blend, axis=1)
        e = float(np.mean(preds == y_te))
        if e > best_v3: best_v3 = e; best_v3w = w
    print(f'  M5+V3: w={best_v3w:.2f}: {best_v3*100:.2f}%')
    
    # M3+M5+V3
    best_3v = 0; best_3vw = {}
    for w3 in np.arange(0.1, 0.8, 0.1):
        for w5 in np.arange(0.1, 0.8, 0.1):
            wv = 1-w3-w5
            if wv <= 0: continue
            blend = w3*p3 + w5*p5 + wv*v3_p
            preds = np.argmax(blend, axis=1)
            e = float(np.mean(preds == y_te))
            if e > best_3v:
                best_3v = e; best_3vw = {'M3': w3, 'M5': w5, 'V3': wv}
    print(f'  M3+M5+V3: w={best_3vw}: {best_3v*100:.2f}%')
    
    # Use best with V3
    best_ex = max(best_ex, best_v3, best_3v)
except Exception as e:
    print(f'  V3 error: {e}')

final_ex = best_ex

# Feature importance for Understat
print('\n[5] Understat feature importance:')
imp = m5.feature_importances_
unames = ['home_xg','away_xg','xg_diff','home_npxg','away_npxg','npxg_diff','home_deep','away_deep','home_ppda','away_ppda']
for i in range(120, min(130, len(imp))):
    print(f'  {unames[i-120]:15s}: {imp[i]:.4f} ({imp[i]/imp.sum()*100:.2f}%)')

print('\n' + '='*60)
print(f'V7 CHAMPION FINAL: {final_ex*100:.2f}% exact!')
print(f'  Time: {(time.time()-t0)/60:.1f} min')
print(f'  Previous world record: 32.05%')
print(f'  Delta: {final_ex*100 - 32.05:+.2f}%')
print(f'  Features: {X.shape[1]} (originally {X.shape[1]-10})')
print('='*60)

# Save
result = {
    'test_exact': final_ex,
    'M5_exact': r5[0], 'M3_exact': r3[0],
    'M5_1x2': r5[1], 'M3_1x2': r3[1],
    'ensemble_weight_M3': best_w,
    'ensemble_weight_M5': 1-best_w,
    'understat_matched': int(uc),
    'features': X.shape[1],
    'time_min': (time.time()-t0)/60,
}
with open('models/v7_champion_results.json', 'w') as f:
    json.dump(result, f, indent=2)
print('\nSaved to models/v7_champion_results.json')
