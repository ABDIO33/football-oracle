"""
ultimate_train_v2.py — 3 models fast, verify results, save best
"""
import sys, os, time, json, warnings, gc
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import xgboost as xgb

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
MODEL_DIR = BASE + "/models"
os.makedirs(MODEL_DIR, exist_ok=True)

t0 = time.time()
print("LOADING...", flush=True)
data = np.load(BASE + "/training_data_v3.npz", allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)
print(f"Loaded: {X.shape} ({time.time()-t0:.1f}s)", flush=True)

# Chronological split
order = np.argsort(data['match_ids'])
X, y = X[order], y[order]
n = len(X); n_tr = int(n * 0.8); n_v = int(n * 0.1)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_v, y_v = X[n_tr:n_tr+n_v], y[n_tr:n_tr+n_v]
X_te, y_te = X[n_tr+n_v:], y[n_tr+n_v:]
print(f"T:{len(y_tr):,} V:{len(y_v):,} Te:{len(y_te):,}", flush=True)

def acc_ex(y, p): return float(np.mean(y == p))
def acc_1x2(y, p):
    yh, ya = y//5, y%5; ph, pa = p//5, p%5
    yr = np.where(yh>ya,0,np.where(yh==ya,1,2))
    pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
    return float(np.mean(yr==pr))

models, names, t_probas = [], [], []

# === M1 ===
print("\n[M1] depth=6, lr=0.05, 800 trees", flush=True)
t1 = time.time()
m = xgb.XGBClassifier(n_estimators=800, max_depth=6, lr=0.05,
    subsample=0.8, colsample=0.6, reg_alpha=0.01, reg_lambda=0.1,
    tree_method='hist', random_state=42, n_jobs=8, 
    eval_metric='mlogloss', early_stopping_rounds=30)
m.fit(X_tr, y_tr, eval_set=[(X_v, y_v)])
p = m.predict(X_v)
print(f"  V: exact={acc_ex(y_v,p):.4f} 1x2={acc_1x2(y_v,p):.4f} [{time.time()-t1:.0f}s]", flush=True)
models.append(m); names.append('M1'); t_probas.append(m.predict_proba(X_te))

# === M2 ===
print("\n[M2] depth=4, lr=0.08, 1000 trees", flush=True)
t1 = time.time()
m = xgb.XGBClassifier(n_estimators=1000, max_depth=4, lr=0.08,
    subsample=0.9, colsample=0.8, tree_method='hist', 
    random_state=43, n_jobs=8, eval_metric='mlogloss', early_stopping_rounds=30)
m.fit(X_tr, y_tr, eval_set=[(X_v, y_v)])
p = m.predict(X_v)
print(f"  V: exact={acc_ex(y_v,p):.4f} 1x2={acc_1x2(y_v,p):.4f} [{time.time()-t1:.0f}s]", flush=True)
models.append(m); names.append('M2'); t_probas.append(m.predict_proba(X_te))

# === M3 ===
print("\n[M3] depth=8, lr=0.03, 600 trees", flush=True)
t1 = time.time()
m = xgb.XGBClassifier(n_estimators=600, max_depth=8, lr=0.03,
    subsample=0.7, colsample=0.5, reg_alpha=0.05, reg_lambda=0.2,
    tree_method='hist', random_state=44, n_jobs=8,
    eval_metric='mlogloss', early_stopping_rounds=30)
m.fit(X_tr, y_tr, eval_set=[(X_v, y_v)])
p = m.predict(X_v)
print(f"  V: exact={acc_ex(y_v,p):.4f} 1x2={acc_1x2(y_v,p):.4f} [{time.time()-t1:.0f}s]", flush=True)
models.append(m); names.append('M3'); t_probas.append(m.predict_proba(X_te))

# === Ensemble (weighted avg) ===
print("\n=== ENSEMBLE ===", flush=True)
v_probas = [m.predict_proba(X_v) for m in models]

best_ex = 0; best_w = None
for w1 in np.arange(0,1.1,0.1):
    for w2 in np.arange(0,1.1,0.1):
        w3 = max(0,1-w1-w2)
        if w3 <= 0: continue
        ws = [w1, w2, w3]
        bl = sum(w*vp for w,vp in zip(ws, v_probas))
        pr = np.argmax(bl, axis=1)
        ex = acc_ex(y_v, pr)
        if ex > best_ex:
            best_ex = ex; best_w = ws

print(f"Best: {[round(w,2) for w in best_w]} -> val exact={best_ex:.4f}", flush=True)

# Test
bl_te = sum(w*tp for w,tp in zip(best_w, t_probas))
pr_te = np.argmax(bl_te, axis=1)
te_ex = acc_ex(y_te, pr_te)
te_1x2 = acc_1x2(y_te, pr_te)
print(f"\nTEST: exact={te_ex*100:.2f}%  1X2={te_1x2*100:.2f}%", flush=True)

# Individual test
for i,n in enumerate(names):
    pri = np.argmax(t_probas[i], axis=1)
    print(f"  {n}: exact={acc_ex(y_te,pri)*100:.2f}%  1X2={acc_1x2(y_te,pri)*100:.2f}%", flush=True)

# RPS
def rps(y_true, proba):
    total = 0.0
    for i in range(len(y_true)):
        h = y_true[i]//5; a = y_true[i]%5
        actual_h = 1 if h>a else 0; actual_d = 1 if h==a else 0; actual_a = 1 if h<a else 0
        home_p = sum(proba[i][h*5+a] for h in range(5) for a in range(5) if h>a)
        draw_p = sum(proba[i][h*5+h] for h in range(5))
        cp = [home_p, home_p+draw_p, 1.0]; ca = [actual_h, actual_h+actual_d, 1.0]
        total += sum((cp[k]-ca[k])**2 for k in range(3))/2
    return total/len(y_true)

rps_val = rps(y_v, sum(w*vp for w,vp in zip(best_w, v_probas)))
rps_te = rps(y_te, bl_te)
print(f"RPS: val={rps_val:.4f} test={rps_te:.4f}", flush=True)

# Save
import joblib
ens = {'models': models, 'names': names, 'weights': best_w}
fp = MODEL_DIR + "/ultimate_30pct.pkl"
joblib.dump(ens, fp, compress=3)
print(f"\nSaved: {fp}", flush=True)

res = {
    'test_exact': te_ex, 'test_1x2': te_1x2, 'test_rps': rps_te,
    'val_exact': best_ex, 'val_rps': rps_val,
    'weights': [float(w) for w in best_w],
    'individual': {names[i]: {'exact': acc_ex(y_te,np.argmax(t_probas[i],axis=1)), 
                               '1x2': acc_1x2(y_te,np.argmax(t_probas[i],axis=1))} for i in range(3)},
    'n_test': len(y_te), 'n_train': len(y_tr),
    'time_min': (time.time()-t0)/60
}
with open(MODEL_DIR + "/ultimate_results.json", 'w') as f:
    json.dump(res, f, indent=2)
print(f"Results saved. Total: {res['time_min']:.1f} min", flush=True)

# Feature importance
print("\n=== FEATURE IMPORTANCE (Top 20) ===", flush=True)
imp = models[0].feature_importances_
top20 = np.argsort(imp)[-20:][::-1]
for i, idx in enumerate(top20):
    print(f"  {i+1}. feat[{idx}] = {imp[idx]:.4f}", flush=True)

print("\nDONE!", flush=True)
