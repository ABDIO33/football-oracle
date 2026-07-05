"""
ultimate_train_fast.py — تدريب سريع مع progress
"""
import sys, os, time, json, gc, warnings
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import xgboost as xgb

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
MODEL_DIR = BASE + "/models"

t0 = time.time()
print("LOADING DATA...", flush=True)
data = np.load(BASE + "/training_data_v3.npz", allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)
print(f"Loaded: {X.shape}, {len(np.unique(y))} classes ({time.time()-t0:.1f}s)", flush=True)

# Chronological split
order = np.argsort(data['match_ids'])
X = X[order]; y = y[order]
n = len(X); n_train = int(n * 0.8); n_val = int(n * 0.1)
X_tr, y_tr = X[:n_train], y[:n_train]
X_v, y_v = X[n_train:n_train+n_val], y[n_train:n_train+n_val]
X_te, y_te = X[n_train+n_val:], y[n_train+n_val:]
print(f"Split: train={len(y_tr):,} val={len(y_v):,} test={len(y_te):,}", flush=True)

def acc_exact(y, p): return float(np.mean(y == p))
def acc_1x2(y, p):
    yh, ya = y//5, y%5; ph, pa = p//5, p%5
    yr = np.where(yh>ya,0,np.where(yh==ya,1,2))
    pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
    return float(np.mean(yr==pr))

models, names = [], []
test_probas = []  # Store test set predictions for blending

# === MODEL 1: XGBoost medium (fastest) ===
print("\n[M1] XGB-v1 (depth=6, lr=0.05, 500 trees)...", flush=True)
t1 = time.time()
m1 = xgb.XGBClassifier(n_estimators=500, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.6, reg_alpha=0.01, reg_lambda=0.1,
    tree_method='hist', random_state=42, n_jobs=8,
    eval_metric='mlogloss', early_stopping_rounds=30, verbose=1)
m1.fit(X_tr, y_tr, eval_set=[(X_v, y_v)])
p = m1.predict(X_v)
print(f"  Val: Exact={acc_exact(y_v,p):.4f} 1X2={acc_1x2(y_v,p):.4f} ({time.time()-t1:.1f}s)", flush=True)
models.append(m1); names.append('XGB-v1'); test_probas.append(m1.predict_proba(X_te))

# === MODEL 2: XGBoost shallower, more trees ===
print("\n[M2] XGB-v2 (depth=4, lr=0.08, 1000 trees)...", flush=True)
t1 = time.time()
m2 = xgb.XGBClassifier(n_estimators=1000, max_depth=4, learning_rate=0.08,
    subsample=0.9, colsample_bytree=0.8, reg_alpha=0, reg_lambda=0.05,
    tree_method='hist', random_state=43, n_jobs=8,
    eval_metric='mlogloss', early_stopping_rounds=30, verbose=1)
m2.fit(X_tr, y_tr, eval_set=[(X_v, y_v)])
p = m2.predict(X_v)
print(f"  Val: Exact={acc_exact(y_v,p):.4f} 1X2={acc_1x2(y_v,p):.4f} ({time.time()-t1:.1f}s)", flush=True)
models.append(m2); names.append('XGB-v2'); test_probas.append(m2.predict_proba(X_te))

# === MODEL 3: XGBoost deep but low lr ===
print("\n[M3] XGB-v3 (depth=8, lr=0.03, 500 trees)...", flush=True)
t1 = time.time()
m3 = xgb.XGBClassifier(n_estimators=500, max_depth=8, learning_rate=0.03,
    subsample=0.7, colsample_bytree=0.5, reg_alpha=0.05, reg_lambda=0.2, gamma=0.05,
    tree_method='hist', random_state=44, n_jobs=8,
    eval_metric='mlogloss', early_stopping_rounds=30, verbose=1)
m3.fit(X_tr, y_tr, eval_set=[(X_v, y_v)])
p = m3.predict(X_v)
print(f"  Val: Exact={acc_exact(y_v,p):.4f} 1X2={acc_1x2(y_v,p):.4f} ({time.time()-t1:.1f}s)", flush=True)
models.append(m3); names.append('XGB-v3'); test_probas.append(m3.predict_proba(X_te))

# === MODEL 4: XGBoost high regularization ===
print("\n[M4] XGB-v4 (depth=6, lr=0.02, high reg, 500 trees)...", flush=True)
t1 = time.time()
m4 = xgb.XGBClassifier(n_estimators=500, max_depth=6, learning_rate=0.02,
    subsample=0.6, colsample_bytree=0.4, reg_alpha=0.1, reg_lambda=0.5, gamma=0.1,
    tree_method='hist', random_state=45, n_jobs=8,
    eval_metric='mlogloss', early_stopping_rounds=30, verbose=1)
m4.fit(X_tr, y_tr, eval_set=[(X_v, y_v)])
p = m4.predict(X_v)
print(f"  Val: Exact={acc_exact(y_v,p):.4f} 1X2={acc_1x2(y_v,p):.4f} ({time.time()-t1:.1f}s)", flush=True)
models.append(m4); names.append('XGB-v4'); test_probas.append(m4.predict_proba(X_te))

# === MODEL 5: XGBoost class_weighted ===
print("\n[M5] XGB-v5 (class_weight=balanced, 500 trees)...", flush=True)
t1 = time.time()
classes, counts = np.unique(y_tr, return_counts=True)
weight = {int(c): float(len(y_tr))/(len(classes)*float(counts[i])) for i,c in enumerate(classes)}
sw = np.array([weight.get(int(yi),1.0) for yi in y_tr])
m5 = xgb.XGBClassifier(n_estimators=500, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.6, reg_alpha=0.01, reg_lambda=0.1,
    tree_method='hist', random_state=46, n_jobs=8,
    eval_metric='mlogloss', early_stopping_rounds=30, verbose=1)
m5.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], sample_weight=sw)
p = m5.predict(X_v)
print(f"  Val: Exact={acc_exact(y_v,p):.4f} 1X2={acc_1x2(y_v,p):.4f} ({time.time()-t1:.1f}s)", flush=True)
models.append(m5); names.append('XGB-v5'); test_probas.append(m5.predict_proba(X_te))

# === ENSEMBLE: simple grid search ===
print("\n=== ENSEMBLE BLENDING ===", flush=True)
val_probas = [m.predict_proba(X_v) for m in models]

best_ex = 0; best_w = None; best_vp = None
for w1 in np.arange(0, 1.1, 0.1):
    for w2 in np.arange(0, 1.1, 0.1):
        w3 = max(0, 1-w1-w2)
        if w3 <= 0: continue
        r = w3
        ws = [w1, w2, r*0.33, r*0.33, r*0.34]
        bl = sum(w * vp for w, vp in zip(ws, val_probas))
        pr = np.argmax(bl, axis=1)
        ex = acc_exact(y_v, pr)
        if ex > best_ex:
            best_ex = ex; best_w = ws

print(f"Best weights: {[f'{w:.2f}' for w in best_w]}", flush=True)
print(f"Val Exact: {best_ex:.4f}", flush=True)

# Test
bl_te = sum(w * tp for w, tp in zip(best_w, test_probas))
pr_te = np.argmax(bl_te, axis=1)
te_ex = acc_exact(y_te, pr_te)
te_1x2 = acc_1x2(y_te, pr_te)

print(f"\n=== TEST SET ===", flush=True)
print(f"Exact: {te_ex*100:.2f}%", flush=True)
print(f"1X2:   {te_1x2*100:.2f}%", flush=True)

# Individual performance
print(f"\n=== INDIVIDUAL ===", flush=True)
for i, n in enumerate(names):
    pr_i = np.argmax(test_probas[i], axis=1)
    print(f"  {n}: Exact={acc_exact(y_te, pr_i)*100:.2f}% 1X2={acc_1x2(y_te, pr_i)*100:.2f}%", flush=True)

# Save
import joblib
ens = {'models': models, 'names': names, 'weights': best_w}
joblib.dump(ens, MODEL_DIR + "/ultimate_30pct.pkl", compress=3)
print(f"\nSaved: {MODEL_DIR}/ultimate_30pct.pkl", flush=True)

res = {
    'test_exact': te_ex, 'test_1x2': te_1x2,
    'val_exact': best_ex, 'weights': best_w,
    'n': len(y_te), 'total_time_min': (time.time()-t0)/60
}
with open(MODEL_DIR + "/ultimate_results.json", 'w') as f:
    json.dump(res, f, indent=2)
print(f"Total: {(time.time()-t0)/60:.1f} min", flush=True)
print("DONE!", flush=True)
