#!/usr/bin/env python3
"""
🔥 EXPERIMENT 1: LightGBM on 296 features (features_full selected) 🔥
Fast, tests if more features + more data helps
"""
import sys, os, time, json, numpy as np
os.environ['OMP_NUM_THREADS'] = '8'
BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

print("="*70)
print("EXP1: LightGBM on 296 features, 885K matches")
print("="*70)
t0 = time.time()

import warnings
warnings.filterwarnings('ignore')
import lightgbm as lgb

# Load
print("[1] Loading features_selected.npz...")
data = np.load('features_selected.npz', allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)
match_ids = data['match_ids']
print(f"  {X.shape} ({time.time()-t0:.0f}s)")

# Sorted split
n = len(X)
n_tr = int(n * 0.9)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_te, y_te = X[n_tr:], y[n_tr:]
print(f"  Train: {len(y_tr):,}, Test: {len(y_te):,}")

# LightGBM
print(f"[2] Training LightGBM...")
model = lgb.LGBMClassifier(
    n_estimators=600, max_depth=8, learning_rate=0.03,
    num_leaves=63, min_child_samples=50,
    subsample=0.85, colsample_bytree=0.7,
    reg_alpha=0.1, reg_lambda=0.1,
    random_state=42, n_jobs=4, verbose=-1)

model.fit(X_tr, y_tr,
    eval_set=[(X_te, y_te)],
    eval_metric='multi_logloss',
    callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])

pred = model.predict(X_te)
exact = float(np.mean(pred == y_te))
yh, ya = y_te//5, y_te%5; ph, pa = pred//5, pred%5
yr = np.where(yh>ya, 0, np.where(yh==ya, 1, 2))
pr = np.where(ph>pa, 0, np.where(ph==pa, 1, 2))
acc_1x2 = float(np.mean(yr == pr))

print(f"\n{'='*50}")
print(f"EXP1 RESULTS:")
print(f"  Exact: {exact*100:.2f}%")
print(f"  1X2:   {acc_1x2*100:.2f}%")
print(f"  Time:  {(time.time()-t0)/60:.1f} min")
print(f"{'='*50}")

# Top features
imp = model.feature_importances_
top_n = 20
top_idx = np.argsort(imp)[-top_n:]
fnames = data['feature_names']
print(f"\nTop {top_n} features:")
for i in range(top_n):
    idx = top_idx[i]
    print(f"  {fnames[idx]:40s}: {imp[idx]/imp.sum()*100:.2f}%")

# Save
import joblib
joblib.dump(model, 'models/exp1_lgbm_296.pkl')
with open('models/exp1_results.json', 'w') as f:
    json.dump({
        'experiment': 'exp1_lgbm_296',
        'exact_pct': round(exact*100, 2),
        'acc_1x2_pct': round(acc_1x2*100, 2),
        'features': X.shape[1],
        'samples': len(X),
        'train_samples': len(y_tr),
        'test_samples': len(y_te),
        'time_min': (time.time()-t0)/60
    }, f, indent=2)

print(f"\nSaved: models/exp1_lgbm_296.pkl")
print(f"EXP1 COMPLETE: {exact*100:.2f}% exact")
