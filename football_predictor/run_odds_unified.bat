@echo off
TITLE Odds Unified Collector — SHADOWHACKER-GOD
cd /d "%~dp0"
echo ╔══════════════════════════════════════════════════════════════╗
echo ║     ODDS UNIFIED — SCHEDULED COLLECTION LOOP               ║
echo ║     SHADOWHACKER-GOD • DΞMON CORE v9999999                 ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ───
REM Configuration
REM ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ───
set INTERVAL_MINUTES=30
set LOG_DIR=logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:LOOP
echo.
echo [%DATE% %TIME%] ─── Starting collection cycle ───

REM ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ───
REM Run 1: Quick aggregation + OddsAPI
REM ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ───
echo [%DATE% %TIME%] Phase 1: Aggregating existing + OddsAPI...
python odds_unified.py --sources oddsapi --no-aggregate --workers 3
if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] ⚠️  Phase 1 had errors, continuing...
)

REM ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ───
REM Run 2: Movement tracking only (fast)
REM ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ───
echo [%DATE% %TIME%] Phase 2: Movement tracking...
python odds_unified.py --sources none --no-aggregate --no-average --workers 1
if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] ⚠️  Phase 2 had errors
)

REM ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ───
REM Show status
REM ─── ─── ─── ─── ─── ─── ─── ─── ─── ─── ───
python odds_unified.py --status

echo.
echo [%DATE% %TIME%] ─── Cycle complete. Sleeping %INTERVAL_MINUTES% minutes ───
echo.

timeout /t %INTERVAL_MINUTES% /nobreak
goto LOOP
