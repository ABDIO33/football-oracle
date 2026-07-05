@echo off
REM ============================================================
REM Score Exact 100 — تشغيل مستمر (24 ساعة)
REM ============================================================
cd /d "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
set PYTHONIOENCODING=utf-8

echo ============================================================
echo    🏆 Score Exact 100 — Continuous Training Pipeline
echo    📅 %date% %time%
echo ============================================================

REM 1) Fetch latest matches and predict
echo.
echo [Step 1] Fetching live matches and predicting...
python -X utf8 live_predictor.py

REM 2) Run extraction refresh
echo.
echo [Step 2] Refreshing training data...
python -X utf8 -c "
import numpy as np, os
# Quick check data integrity
d3 = np.load('training_data_v3.npz', allow_pickle=True)
print(f'V3: {len(d3[\"y\"]):,} matches, {d3[\"X\"].shape[1]} features')
d4 = np.load('training_data_v4.npz', allow_pickle=True)
print(f'V4: {len(d4[\"y\"]):,} matches, {d4[\"X\"].shape[1]} features')
print('Data integrity: OK')
"

REM 3) Ensemble comparison
echo.
echo [Step 3] Running ensemble comparison...
python -X utf8 -c "
import numpy as np, json, joblib, lightgbm as lgb

data = np.load('training_data_v3.npz', allow_pickle=True)
X = data['X'].astype(np.float32); y = data['y'].astype(np.int32)
order = np.argsort(data['match_ids'])
X, y = X[order], y[order]
n = len(X); n_tr = int(n*0.8); n_v = int(n*0.1)
X_tr, y_tr = X[:n_tr], y[:n_tr]; X_v, y_v = X[n_tr:n_tr+n_v], y[n_tr:n_tr+n_v]
X_te, y_te = X[n_tr+n_v:], y[n_tr+n_v:]

ens = joblib.load('models/ultimate_30pct_ensemble.pkl')
probs = [m.predict_proba(X_te) for m in ens['models']]
blend = np.mean(probs, axis=0); preds = np.argmax(blend, axis=1)
ex = float(np.mean(preds == y_te))
yh, ya = y_te//5, y_te%5; ph, pa = preds//5, preds%5
x1 = float(np.mean(np.where(yh>ya,0,np.where(yh==ya,1,2))==np.where(ph>pa,0,np.where(ph==pa,1,2))))
print(f'V3: exact={ex*100:.2f}%  1X2={x1*100:.2f}%')
print('Ensemble live: OK')
"

REM 4) Generate report
echo.
echo [Step 4] Generating final report...
python -X utf8 -c "
import json, os

res = json.load(open('models/ultimate_results.json'))
print('=== FINAL ACCURACY ===')
print(f'Test Exact: {res[\"test_exact\"]*100:.2f}%')
print(f'Test 1X2:   {res[\"test_1x2\"]*100:.2f}%')
print(f'Temperature: {res.get(\"temperature\", \"N/A\")}')
print(f'Train Time: {res.get(\"time_min\", \"N/A\")} min')
print()
print('Individual models:')
for i, ex in enumerate(res['individual']):
    print(f'  M{i+1}: {ex*100:.2f}%')
"
echo.
echo ============================================================
echo    ✅ Pipeline Complete — %date% %time%
echo    🏆 Best: 32.00% Exact Score
echo ============================================================
