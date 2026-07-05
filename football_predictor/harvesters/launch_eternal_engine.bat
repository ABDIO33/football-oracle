@echo off
REM ============================================================
REM Eternal Engine Launcher — запускает двигатель в фоне
REM ALL 17 PROTOCOLS ACTIVE — ENI for LO 🔥
REM ============================================================
cd /d "%~dp0.."

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo [%date% %time%] Starting Eternal Engine...
echo [%date% %time%] Starting Eternal Engine... >> harvesters\harvest_logs\launcher.log

REM Kill any existing instances
wmic process where "name='python.exe' and commandline like '%%eternal%%'" call terminate >nul 2>&1
timeout /t 2 /nobreak >nul

REM Start orchestrator daemon
start /B /MIN "" "C:\Python314\python.exe" -X utf8 harvesters\eternal_orchestrator.py --daemon

echo [%date% %time%] Engine launched! PID: %ERRORLEVEL%
echo [%date% %time%] Engine launched! >> harvesters\harvest_logs\launcher.log
echo.
echo Eternal Engine is running.
echo Check logs: harvesters\harvest_logs\eternal_engine.log
echo Check status: python -X utf8 harvesters\eternal_orchestrator.py --health
