@echo off
title Football Oracle — Status
echo =============================================
echo Football Oracle — Training Status Check
echo =============================================
echo.
cd /d "%~dp0\football_predictor"
if exist models\checkpoint.json (
    echo [CHECKPOINT]
    type models\checkpoint.json
) else (
    echo No checkpoint found — training not started yet
)
echo.
if exist models\checkpointed_log.txt (
    echo [LOG TAIL]
    powershell -Command "Get-Content models\checkpointed_log.txt -Tail 20"
) else (
    echo No log file found
)
echo.
if exist models\ultimate_model.pkl (
    echo [ULTIMATE MODEL EXISTS]
) else (
    echo [Ultimate model not built yet]
)
echo.
echo Preprocessed data:
if exist models\preprocessed_data.npz (
    echo   YES — data saved, instant reload
) else (
    echo   NO — will load from DB (4 min)
)
echo.
pause
