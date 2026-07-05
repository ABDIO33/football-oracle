@echo off
title Football Oracle — 48h Autonomous Pipeline
cd /d "%~dp0\football_predictor"

set LOG=models\pipeline_log.txt
set STATUS=models\pipeline_status.txt
set START=%date% %time%

echo ============================================= > %LOG%
echo FOOTBALL ORACLE - 48 HOUR PIPELINE >> %LOG%
echo Started: %START% >> %LOG%
echo ============================================= >> %LOG%

echo =============================================
echo FOOTBALL ORACLE - 48 HOUR PIPELINE
echo Started: %START%
echo =============================================
echo For status: type %STATUS%
echo For log: type %LOG%
echo.

echo PHASE 0: STARTED > %STATUS%

REM ============ PHASE 1: DATA EXPANSION ============
echo.
echo [PHASE 1/3] Data Expansion - Scanning all tournaments...
echo [%date% %time%] PHASE 1: Data Expansion Starting >> %LOG%
echo PHASE 1: RUNNING (Smart Scanner) > %STATUS%
python smart_scanner.py >> %LOG% 2>&1
echo [%date% %time%] PHASE 1: Done (%%ERRORLEVEL%%%) >> %LOG%

REM Count matches after expansion
python -c "import sqlite3; c=sqlite3.connect('scrape_cache.db'); print(f'Total matches: {c.execute(\"SELECT COUNT(*) FROM sofa_historical_results\").fetchone()[0]}'); c.close()" >> %LOG%

REM ============ PHASE 2: FORCE FRESH TRAINING ============
echo.
echo [PHASE 2/3] Fresh Training with Expanded Data...
echo [%date% %time%] PHASE 2: Deleting old checkpoints >> %LOG%
echo PHASE 2: CLEANING > %STATUS%

REM Delete old checkpoint files to force fresh training
if exist models\checkpoint.json del /f /q models\checkpoint.json
if exist models\preprocessed_data.npz del /f /q models\preprocessed_data.npz
if exist models\checkpoint_imputer.pkl del /f /q models\checkpoint_imputer.pkl
if exist models\checkpoint_scaler.pkl del /f /q models\checkpoint_scaler.pkl
if exist models\checkpoint_xgb.pkl del /f /q models\checkpoint_xgb.pkl
if exist models\checkpoint_M5_small.pt del /f /q models\checkpoint_M5_small.pt
if exist models\checkpoint_M5_medium.pt del /f /q models\checkpoint_M5_medium.pt
if exist models\checkpoint_M5_big.pt del /f /q models\checkpoint_M5_big.pt
if exist models\checkpoint_M5_wide.pt del /f /q models\checkpoint_M5_wide.pt
if exist models\checkpoint_M5_deep.pt del /f /q models\checkpoint_M5_deep.pt
if exist models\checkpointed_log.txt del /f /q models\checkpointed_log.txt
if exist models\checkpointed_stdout.txt del /f /q models\checkpointed_stdout.txt

echo [%date% %time%] PHASE 2: Starting Ultimate Training >> %LOG%
echo PHASE 2: RUNNING (Ultimate Training - %date% %time%) > %STATUS%
python checkpointed_trainer.py >> %LOG% 2>&1
echo [%date% %time%] PHASE 2: Done (%%ERRORLEVEL%%%) >> %LOG%

REM ============ PHASE 3: FINAL EVALUATION ============
echo.
echo [PHASE 3/3] Final Evaluation...
echo [%date% %time%] PHASE 3: Evaluation Starting >> %LOG%
echo PHASE 3: RUNNING (Evaluation) > %STATUS%

if exist models\ultimate_results.json (
    echo ============ FINAL RESULTS ============ >> %LOG%
    type models\ultimate_results.json >> %LOG%
    echo ====================================== >> %LOG%
) else (
    if exist models\checkpoint.json (
        type models\checkpoint.json >> %LOG%
    ) else (
        echo No results found >> %LOG%
    )
)

REM Comprehensive final report
echo. >> %LOG%
echo ============================================= >> %LOG%
echo FINAL PIPELINE SUMMARY >> %LOG%
echo ============================================= >> %LOG%
echo Started: %START% >> %LOG%
echo Completed: %date% %time% >> %LOG%

python -c "
import sqlite3, json, os
pn = os.path.dirname(__file__) or '.'
conn = sqlite3.connect(os.path.join(pn, 'scrape_cache.db'))
count = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
conn.close()
print(f'Final match count: {count}')
" >> %LOG% 2>&1

if exist models\ultimate_results.json (
    python -c "
import json
r = json.load(open(r'models/ultimate_results.json'))
e = r.get('ensemble', {})
bt = r.get('betting_30', {})
print(f'Ensemble exact: {e.get(\"exact_pct\",\"?\")}%%')
print(f'Ensemble 1X2: {e.get(\"1x2\",\"?\")}%%')
print(f'Betting @30%%: {bt.get(\"accuracy_pct\",\"?\")}%% ({bt.get(\"hits\",0)}/{bt.get(\"total\",0)})')
" >> %LOG% 2>&1
)

echo PHASE 3: COMPLETE > %STATUS%
echo. >> %LOG%
echo ============================================= >> %LOG%
echo PIPELINE COMPLETE >> %LOG%
echo ============================================= >> %LOG%

echo.
echo =============================================
echo PIPELINE COMPLETE
echo Check %LOG% for full log
echo Check models\ultimate_results.json for results
echo =============================================
