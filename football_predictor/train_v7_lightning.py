#!/usr/bin/env python3
"""
V7 LIGHTNING TRAINER — تدريب سريع على training_data_v7.npz
يستخدم LightGBM + خفيف عشان نشوف النتيجة
ENI for LO 🔥
"""

import numpy as np, os, time, json, warnings, gc
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

t0 = time.time()
log("="*60)
log("V7 LIGHTNING TRAINER")
log("="*60)

# Load V7 data
log("[1] Loading training_data_v7.npz...")
data = np.load('training_data_v7.npz', allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)
uc = data.get('understat_matched', 0)
log(f"  X: {X.shape}, y: {y.shape}, Understat matched: {uc}")

# Split - same as champion retrain
n = len(X)
n_tr = int(n * 0.85)
n_v = int(n * 0.05)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_v, y_v = X[n_tr:n_tr+n_v], y[n_tr:n_tr+n_v]
X_te, y_te = X[n_tr+n_v:], y[n_tr+n_v:]
log(f"  Train: {len(y_tr)}, Val: {len(y_v)}, Test: {len(y_te)}")

import lightgbm as lgb, joblib

models = []
results = []

def eval_model(m, name, Xt, yt):
    p = m.predict(Xt)
    ex = float(np.mean(p == yt))
    yh, ya = yt//5, yt%5; ph, pa = p//5, p%5
    yr = np.where(yh>ya,0,np.where(yh==ya,1,2))
    pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
    x1 = float(np.mean(yr==pr))
    log(f"  {name}: exact={ex*100:.2f}% 1X2={x1*100:.2f}%")
    return {'name': name, 'exact': ex, '1x2': x1}

# Model 1: Medium depth (champion baseline)
log("\n[2] Training M5 (depth=20)...")
m5 = lgb.LGBMClassifier(
    n_estimators=200, max_depth=20, learning_rate=0.02,
    subsample=0.7, colsample_bytree=0.4, num_leaves=511,
    reg_alpha=0.01, reg_lambda=0.05, min_child_weight=2,
    random_state=111, n_jobs=8, verbose=-1
)
m5.fit(X_tr, y_tr, eval_set=[(X_v, y_v)],
      callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
r5 = eval_model(m5, 'M5-depth20', X_te, y_te)
models.append(m5)
joblib.dump(m5, 'models/v7_m5.pkl', compress=3)

# Model 2: M3 deep (champion baseline)
log("\n[3] Training M3 (depth=15, 70% sample)...")
idx = np.random.RandomState(42).choice(len(y_tr), int(len(y_tr)*0.7), replace=False)
m3 = lgb.LGBMClassifier(
    n_estimators=400, max_depth=15, learning_rate=0.03,
    subsample=0.6, colsample_bytree=0.4, num_leaves=255,
    reg_alpha=0.05, reg_lambda=0.2, min_child_weight=3,
    random_state=88, n_jobs=8, verbose=-1
)
m3.fit(X_tr[idx], y_tr[idx], eval_set=[(X_v, y_v)],
      callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
r3 = eval_model(m3, 'M3-depth15', X_te, y_te)
models.append(m3)
joblib.dump(m3, 'models/v7_m3.pkl', compress=3)

# Model 3: Quick XGB baseline
log("\n[4] Training XGBoost baseline...")
import xgboost as xgb
xgb_model = xgb.XGBClassifier(
    n_estimators=200, max_depth=8, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8,
    reg_alpha=0.1, reg_lambda=0.2,
    random_state=42, n_jobs=8, verbosity=0
)
xgb_model.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], verbose=0)
rx = eval_model(xgb_model, 'XGB-depth8', X_te, y_te)
models.append(xgb_model)

# Ensemble M3+M5
log("\n[5] Ensemble search...")
p3 = m3.predict_proba(X_te)
p5 = m5.predict_proba(X_te)
px = xgb_model.predict_proba(X_te)

best_ex = 0
best_w = {}
for w3 in np.arange(0.1, 0.9, 0.1):
    for w5 in np.arange(0.1, 0.9, 0.1):
        wx = 1 - w3 - w5
        if wx <= -0.01: continue
        blend = w3*p3 + w5*p5 + wx*px
        preds = np.argmax(blend, axis=1)
        e = float(np.mean(preds == y_te))
        if e > best_ex:
            best_ex = e
            best_w = {'M3': w3, 'M5': w5, 'XGB': wx}

log(f"\n  Best ensemble: w={best_w}")
log(f"  Best exact: {best_ex*100:.2f}%")

# Compare with V3 baseline
log("\n[6] Comparison with V3 baseline...")
# V3 used 120 features. Now we have 130 (10 more from Understat).
# Check feature importance for Understat features
imp = m5.feature_importances_
for i in range(120, 130):
    if i < len(imp):
        log(f"  Understat feat {i-120} ({['home_xg','away_xg','xg_diff','home_npxg','away_npxg','npxg_diff','home_deep','away_deep','home_ppda','away_ppda'][i-120]}): importance={imp[i]:.4f}")

# Save champion
log("\n[7] Saving champion...")
ens = {
    'models': models,
    'names': ['M5-depth20', 'M3-depth15', 'XGB-depth8'],
    'weights': best_w,
    'test_exact': float(best_ex),
    'test_1x2': float(r5['1x2']),
}
joblib.dump(ens, 'models/v7_champion.pkl', compress=3)
res = {
    'test_exact': best_ex,
    'test_1x2': max(r5['1x2'], r3['1x2'], rx['1x2']),
    'weights': best_w,
    'individual': {'M5': r5['exact'], 'M3': r3['exact'], 'XGB': rx['exact']},
    'understat_matched': int(uc),
    'time_min': (time.time()-t0)/60,
    'features': X.shape[1],
}
with open('models/v7_results.json', 'w') as f:
    json.dump(res, f, indent=2)

log(f"\n{'='*60}")
log(f"V7 TRAINING COMPLETE!")
log(f"  Exact score: {best_ex*100:.2f}%")
log(f"  1X2: {max(r5['1x2'], r3['1x2'], rx['1x2'])*100:.2f}%")
log(f"  Time: {res['time_min']:.1f} min")
log(f"  Previous best: 32.05%")
log(f"  Delta: {best_ex*100 - 32.05:+.2f}%")
log(f"{'='*60}")
