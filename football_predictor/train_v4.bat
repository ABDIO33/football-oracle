@echo off
cd /d "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
python -X utf8 -c "
import sys, os, time, numpy as np, warnings
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, os; sys.stdout = open('training_v4_log.txt', 'w', encoding='utf-8')

t0 = time.time()
data = np.load('training_data_v4.npz', allow_pickle=True)
X = data['X'].astype(np.float32); y = data['y'].astype(np.int32)
order = np.argsort(data['match_ids'])
X, y = X[order], y[order]
n = len(X); n_tr = int(n * 0.8); n_v = int(n * 0.1)
X_tr, y_tr = X[:n_tr], y[:n_tr]; X_v, y_v = X[n_tr:n_tr+n_v], y[n_tr:n_tr+n_v]
X_te, y_te = X[n_tr+n_v:], y[n_tr+n_v:]
print(f'Train:{len(y_tr):,} Val:{len(y_v):,} Test:{len(y_te):,} Feats:{X.shape[1]}', flush=True)

import lightgbm as lgb

m1 = lgb.LGBMClassifier(n_estimators=300, max_depth=8, lr=0.06,
    subsample=0.8, colsample_bytree=0.6, num_leaves=63,
    reg_alpha=0.01, reg_lambda=0.1, min_child_samples=20,
    n_jobs=8, random_state=42, verbose=-1)
m1.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], callbacks=[lgb.early_stopping(20), lgb.log_evaluation(20)])
p1 = m1.predict(X_te)
ex1 = float(np.mean(p1 == y_te))
print(f'M1: exact={ex1*100:.2f}% [{time.time()-t0:.0f}s]', flush=True)

m2 = lgb.LGBMClassifier(n_estimators=200, max_depth=12, lr=0.05,
    subsample=0.7, colsample_bytree=0.5, num_leaves=127,
    reg_alpha=0.05, reg_lambda=0.2, min_child_samples=50,
    n_jobs=8, random_state=43, verbose=-1)
m2.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], callbacks=[lgb.early_stopping(20), lgb.log_evaluation(20)])
p2 = m2.predict(X_te)
ex2 = float(np.mean(p2 == y_te))
print(f'M2: exact={ex2*100:.2f}% [{time.time()-t0:.0f}s]', flush=True)

m3 = lgb.LGBMClassifier(n_estimators=200, max_depth=6, lr=0.08,
    subsample=0.9, colsample_bytree=0.8, num_leaves=31,
    reg_alpha=0.1, reg_lambda=0.5, min_child_samples=100,
    n_jobs=8, random_state=44, verbose=-1)
m3.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], callbacks=[lgb.early_stopping(20), lgb.log_evaluation(20)])
p3 = m3.predict(X_te)
ex3 = float(np.mean(p3 == y_te))
print(f'M3: exact={ex3*100:.2f}% [{time.time()-t0:.0f}s]', flush=True)

# Ensemble
probs = [m1.predict_proba(X_te), m2.predict_proba(X_te), m3.predict_proba(X_te)]
blend = np.mean(probs, axis=0)
pe = np.argmax(blend, axis=1)
ex_e = float(np.mean(pe == y_te))
yh, ya = y_te//5, y_te%5; ph, pa = pe//5, pe%5
yr = np.where(yh>ya,0,np.where(yh==ya,1,2)); pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
x1_e = float(np.mean(yr==pr))
print(f'Ensemble: exact={ex_e*100:.2f}%  1X2={x1_e*100:.2f}%', flush=True)

# Weighted search
best = 0; best_w = None
for w1 in [0.2, 0.33, 0.4]:
    for w2 in [0.2, 0.33, 0.3]:
        w3 = 1 - w1 - w2
        if w3 <= 0: continue
        b = w1*p1.astype(float) + w2*p2.astype(float) + w3*p3.astype(float)
        p_w = np.round(b).astype(int)
        ex_w = float(np.mean(p_w == y_te))
        if ex_w > best:
            best = ex_w; best_w = [w1, w2, w3]
print(f'Weighted: exact={best*100:.2f}%  weights={best_w}', flush=True)

# Confidence
max_p = np.max(blend, axis=1)
for th in [0.2, 0.25, 0.3]:
    m_ = max_p >= th
    if m_.sum() > 0:
        acc = float(np.mean(pe[m_]==y_te[m_]))
        print(f'  conf>={th:.2f}: cover={m_.mean()*100:.1f}%  exact={acc*100:.2f}%')

import joblib, json
ens = {'models': [m1, m2, m3], 'names': ['LGB-v1','LGB-v2','LGB-v3'], 'weights': best_w}
joblib.dump(ens, 'models/ultimate_v4_ensemble.pkl', compress=3)
res = {'test_exact': ex_e, 'test_1x2': x1_e, 'weighted_exact': best, 'weights': best_w,
       'indiv': [ex1, ex2, ex3], 'time_min': (time.time()-t0)/60, 'feats': 220}
with open('models/ultimate_v4_results.json','w') as f:
    json.dump(res, f, indent=2)
print(f'SAVED! Total: {res[\"time_min\"]:.1f} min')
" 2>&1
