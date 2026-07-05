@echo off
title Football Oracle — Phase 4 Super-Ensemble
cd /d "%~dp0\football_predictor"

echo =============================================
echo PHASE 4: Super-Ensemble + V3 Training
echo =============================================
echo Started: %date% %time%
echo.

REM Wait for Phase 2 to finish (check every 5 min)
echo Waiting for Phase 2 training to finish...
:WAIT
if exist models\ultimate_results.json (
    echo Phase 2 complete! Starting super-ensemble...
    goto RUN
)
REM Check if pipeline log shows Phase 3
findstr /i "PIPELINE COMPLETE" models\pipeline_log.txt >nul 2>&1
if %errorlevel%==0 (
    echo Pipeline complete! Starting super-ensemble...
    goto RUN
)
echo %date% %time% - Still waiting...
timeout /t 300 /nobreak >nul
goto WAIT

:RUN
echo.
echo =============================================
echo STEP 1: Stacking Ensemble
echo =============================================
echo [%date% %time%] Starting stacking_ensemble.py >> models\phase4_log.txt
python stacking_ensemble.py >> models\phase4_log.txt 2>&1
echo [%date% %time%] Stacking done >> models\phase4_log.txt

echo.
echo =============================================
echo STEP 2: V3 Focal Loss Training
echo =============================================
echo [%date% %time%] Starting train_v3.py >> models\phase4_log.txt
python train_v3.py >> models\phase4_log.txt 2>&1
echo [%date% %time%] V3 done >> models\phase4_log.txt

echo.
echo =============================================
echo ALL PHASES COMPLETE
echo =============================================
echo Results:
if exist models\super_ensemble_results.json type models\super_ensemble_results.json
if exist models\v3_results.json type models\v3_results.json
echo.
echo Done!
