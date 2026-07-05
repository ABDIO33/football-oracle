"""
quick_test.py — اختبار سريع لمعرفة الدقة الحقيقية
"""
import sys, os, time, numpy as np, warnings
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '4'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
data = np.load(BASE + "/training_data_v3.npz", allow_pickle=True)
X = data['X'].astype(np.float32); y = data['y'].astype(np.int32)

# Chronological split
order = np.argsort(data['match_ids'])
X, y = X[order], y[order]
n = len(X); n_tr = int(n * 0.8); n_v = int(n * 0.1)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_v, y_v = X[n_tr:n_tr+n_v], y[n_tr:n_tr+n_v]
X_te, y_te = X[n_tr+n_v:], y[n_tr+n_v:]

print(f"T:{len(y_tr):,} V:{len(y_v):,} Te:{len(y_te):,}")

# Quick XGBoost - 200 trees (fast)
import xgboost as xgb
t0 = time.time()
m = xgb.XGBClassifier(n_estimators=200, max_depth=6, lr=0.1, subsample=0.8,
    colsample_bytree=0.6, tree_method='hist', random_state=42, n_jobs=4,
    eval_metric='mlogloss', early_stopping_rounds=20, verbose=0)
m.fit(X_tr, y_tr, eval_set=[(X_v, y_v)])

# Check exact + 1x2 on ALL splits
for name, Xd, yd in [("TRAIN ", X_tr, y_tr), ("VAL   ", X_v, y_v), ("TEST  ", X_te, y_te)]:
    p = m.predict(Xd)
    ex = float(np.mean(p == yd))
    # 1x2
    yh, ya = yd//5, yd%5; ph, pa = p//5, p%5
    yr = np.where(yh>ya,0,np.where(yh==ya,1,2)); pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
    x1 = float(np.mean(yr==pr))
    print(f"{name}: exact={ex*100:.2f}%  1X2={x1*100:.2f}%")

# Check class distribution on test
yh_te = y_te//5; ya_te = y_te%5
print(f"\nTest class distribution:")
for h in range(5):
    for a in range(5):
        cnt = int(np.sum((yh_te==h) & (ya_te==a)))
        if cnt > 0:
            print(f"  {h}-{a}: {cnt} ({cnt/len(y_te)*100:.1f}%)")

print(f"\nTime: {time.time()-t0:.1f}s")
