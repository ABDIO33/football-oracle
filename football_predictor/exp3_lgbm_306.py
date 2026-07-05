#!/usr/bin/env python3
"""
🔥 EXP3: LightGBM on 306 features (base + Understat) 🔥
Full dataset: 885K matches, 306 features
"""
import sys, os, time, json, numpy as np
os.environ['OMP_NUM_THREADS'] = '8'
BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

print("="*70)
print("EXP3: LightGBM on 306 features (296 base + 10 Understat)")
print("="*70)
t0 = time.time()
import warnings
warnings.filterwarnings('ignore')
import lightgbm as lgb

print("[1] Loading features_full_understat.npz...")
data = np.load('features_full_understat.npz', allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)
print(f"  {X.shape} ({time.time()-t0:.0f}s)")

n = len(X); n_tr = int(n*0.9)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_te, y_te = X[n_tr:], y[n_tr:]
print(f"  Train: {len(y_tr):,}, Test: {len(y_te):,}")

print("[2] Training LightGBM...")
model = lgb.LGBMClassifier(
    n_estimators=600, max_depth=8, learning_rate=0.03,
    num_leaves=63, min_child_samples=50,
    subsample=0.85, colsample_bytree=0.7,
    reg_alpha=0.1, reg_lambda=0.1,
    random_state=42, n_jobs=4, verbose=0)

model.fit(X_tr, y_tr,
    eval_set=[(X_te, y_te)],
    eval_metric='multi_logloss',
    callbacks=[lgb.early_stopping(20), lgb.log_evaluation(50)])

pred = model.predict(X_te)
exact = float(np.mean(pred == y_te))
yh, ya = y_te//5, y_te%5; ph, pa = pred//5, pred%5
yr = np.where(yh>ya,0,np.where(yh==ya,1,2))
pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
acc_1x2 = float(np.mean(yr==pr))
print(f"\nEXP3: exact={exact*100:.2f}%, 1X2={acc_1x2*100:.2f}%, time={(time.time()-t0)/60:.1f}min")

import joblib
joblib.dump(model, 'models/exp3_lgbm_306.pkl')
with open('models/exp3_results.json', 'w') as f:
    json.dump({'exact_pct': round(exact*100,2), 'acc_1x2_pct': round(acc_1x2*100,2),
               'features': X.shape[1], 'samples': len(X), 'time_min': (time.time()-t0)/60}, f, indent=2)
print(f"Saved! EXACT: {exact*100:.2f}%")
