#!/usr/bin/env python3
"""
V7 FAST EVAL — تقييم سريع للتأثير
يدرب XGBoost فقط على subset عشان نشوف الفرق
ENI for LO 🔥
"""

import numpy as np, os, time, json, warnings
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

t0 = time.time()
log("="*60)
log("V7 FAST EVAL — XGBoost")
log("="*60)

# Load V7 data
log("[1] Loading training_data_v7.npz...")
data = np.load('training_data_v7.npz', allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)
log(f"  X: {X.shape}, y: {y.shape}")

# Use LAST 150K matches as test set (most recent matches)
n = len(X)
n_te = 200000
n_tr = n - n_te
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_te, y_te = X[n_tr:], y[n_tr:]
log(f"  Train: {len(y_tr)}, Test: {len(y_te)}")

# Train just 1 fast XGBoost model
log("\n[2] Training XGBoost (depth=8, 150 trees)...")
import xgboost as xgb

# Use 30% of training data for speed
sample_size = 150000
rs = np.random.RandomState(42)
idx = rs.choice(len(y_tr), sample_size, replace=False)
X_sub = X_tr[idx]
y_sub = y_tr[idx]
log(f"  Training on {len(y_sub)} samples...")

model = xgb.XGBClassifier(
    n_estimators=150, max_depth=8, learning_rate=0.08,
    subsample=0.8, colsample_bytree=0.8,
    reg_alpha=0.1, reg_lambda=0.2,
    random_state=42, n_jobs=8, verbosity=0,
    tree_method='hist',  # Fast!
)
model.fit(X_sub, y_sub, eval_set=[(X_te[:50000], y_te[:50000])], verbose=50)

# Evaluate
log("\n[3] Evaluation...")
p = model.predict(X_te)
exact = float(np.mean(p == y_te))
yh, ya = y_te//5, y_te%5; ph, pa = p//5, p%5
yr = np.where(yh>ya,0,np.where(yh==ya,1,2))
pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
x1 = float(np.mean(yr==pr))
log(f"  Exact: {exact*100:.2f}%")
log(f"  1X2: {x1*100:.2f}%")

# Feature importance for Understat
log("\n[4] Understat feature importance:")
imp = model.feature_importances_
names = ['home_xg','away_xg','xg_diff','home_npxg','away_npxg','npxg_diff','home_deep','away_deep','home_ppda','away_ppda']
for i in range(120, 130):
    if i < len(imp):
        log(f"  {names[i-120]:15s}: {imp[i]:.6f} ({imp[i]/imp.sum()*100:.3f}%)")

# Top 20 overall features
log("\n[5] Top 20 features overall:")
top_idx = np.argsort(imp)[::-1][:20]
for idx_in in top_idx:
    name = f'understat_{names[idx_in-120]}' if idx_in >= 120 else f'orig_{idx_in}'
    log(f"  #{idx_in:4d} {name:25s}: {imp[idx_in]:.6f}")

log(f"\n{'='*60}")
log(f"V7 FAST EVAL RESULT: {exact*100:.2f}% exact")
log(f"  (Note: trained on subset only)")
log(f"  Time: {(time.time()-t0)/60:.1f} min")
log(f"{'='*60}")

# Save
res = {
    'test_exact': exact,
    'test_1x2': x1,
    'understat_imp': {names[i]: float(imp[120+i]) for i in range(10) if 120+i < len(imp)},
    'time_min': (time.time()-t0)/60,
}
with open('models/v7_fast_eval.json', 'w') as f:
    json.dump(res, f, indent=2)
joblib.dump(model, 'models/v7_fast_xgb.pkl', compress=3)
