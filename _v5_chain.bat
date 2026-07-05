@echo off
chcp 65001 >nul
cd /d "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
echo ===========================================================================
echo  48h AUTONOMOUS PIPELINE — V5 Production Chain
echo  Started: %date% %time%
echo ===========================================================================

:wait_loop
echo [%date% %time%] Checking V5 status...
if exist models\v5_results.json (
    echo [%date% %time%] V5 COMPLETE! Building production model...
    python build_production_v5.py >> models\v5_chain_log.txt 2>&1
    echo [%date% %time%] Production model built! Running betting pipeline...
    python betting_pipeline.py >> models\betting_log.txt 2>&1
    echo [%date% %time%] Betting predictions complete!
    
    :: Show results
    echo.
    echo ===========================================================================
    type models\v5_chain_log.txt | find "World Best" /i
    type models\v5_chain_log.txt | find "BEAT V3" /i
    echo.
    echo FINAL RESULTS:
    python -c "import json; r=json.load(open('models/v5_results.json')); print(f'V5 Ensemble Exact: {r[\"ensemble\"][\"exact_pct\"]}%%'); print(f'V5 1X2: {r[\"ensemble\"][\"1x2_pct\"]}%%'); print(f'Models: {len(r[\"individual\"])}'); [print(f'''  {k}: {v[\"exact_pct\"]}%%''') for k,v in r['individual'].items()]"
    echo.
    echo ===========================================================================
    echo 48h PIPELINE COMPLETE
    echo ===========================================================================
    pause
    exit /b 0
) else (
    echo [%date% %time%] V5 still running... checking again in 5 minutes
)

:: Check V5 process
powershell -Command "if (Get-Process python* 2>$null) { echo 'Python process active' } else { echo 'WARNING: No Python process running!' }"

:: Show V5 log tail
powershell -Command "Get-Content models\v5_log.txt -Tail 2"

timeout /t 300 /nobreak >nul
goto wait_loop
