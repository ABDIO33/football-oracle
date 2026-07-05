#!/usr/bin/env python3
"""
🔥 EXP2: XGBoost on 296 features 🔥
Different architecture to complement LightGBM
"""
import sys, os, time, json, numpy as np
os.environ['OMP_NUM_THREADS'] = '8'
BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

print("="*70)
print("EXP2: XGBoost on 296 features, 885K matches")
print("="*70)
t0 = time.time()
import warnings
warnings.filterwarnings('ignore')
import xgboost as xgb

print("[1] Loading features_selected.npz...")
data = np.load('features_selected.npz', allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)
print(f"  {X.shape} ({time.time()-t0:.0f}s)")

n = len(X); n_tr = int(n*0.9)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_te, y_te = X[n_tr:], y[n_tr:]
print(f"  Train: {len(y_tr):,}, Test: {len(y_te):,}")

print("[2] Training XGBoost...")
model = xgb.XGBClassifier(
    n_estimators=500, max_depth=7, learning_rate=0.04,
    objective='multi:softprob', num_class=25,
    subsample=0.85, colsample_bytree=0.7,
    reg_alpha=0.2, reg_lambda=0.2,
    random_state=42, n_jobs=4,
    eval_metric='mlogloss', early_stopping_rounds=25)
model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)

pred = model.predict(X_te)
exact = float(np.mean(pred == y_te))
yh, ya = y_te//5, y_te%5; ph, pa = pred//5, pred%5
yr = np.where(yh>ya,0,np.where(yh==ya,1,2))
pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
acc_1x2 = float(np.mean(yr==pr))
print(f"\nEXP2: exact={exact*100:.2f}%, 1X2={acc_1x2*100:.2f}%, time={(time.time()-t0)/60:.1f}min")

# Feature importance
imp = model.feature_importances_
fnames = data['feature_names']
top_idx = np.argsort(imp)[-20:]
print(f"\nTop 20 features:")
for i in range(20):
    idx = top_idx[i]
    print(f"  {fnames[idx]:40s}: {imp[idx]/imp.sum()*100:.2f}%")

import joblib
joblib.dump(model, 'models/exp2_xgb_296.pkl')
with open('models/exp2_results.json', 'w') as f:
    json.dump({
        'experiment': 'exp2_xgb_296',
        'exact_pct': round(exact*100, 2),
        'acc_1x2_pct': round(acc_1x2*100, 2),
        'time_min': (time.time()-t0)/60
    }, f, indent=2)
print(f"Saved: models/exp2_xgb_296.pkl")
print(f"EXP2 DONE: {exact*100:.2f}% exact")
