@echo off
chcp 65001 >nul
cd /d "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
echo ========================================
echo  V4 MONITOR — %date% %time%
echo ========================================

:: Check V4
if exist models\v4_log.txt (
    for /f "skip=1" %%a in (models\v4_log.txt) do set last=%%a
    echo.
    echo [V4 Training] Tail:
    powershell -Command "Get-Content models\v4_log.txt -Tail 3"
) else (
    echo [V4] Not started yet
)

:: Check FD integration
if exist models\fd_integrate_log.txt (
    echo.
    echo [FD History Integration] Tail:
    powershell -Command "Get-Content models\fd_integrate_log.txt -Tail 2"
) else (
    echo [FD] Not started
)

:: DB stats
echo.
python -c "
import sqlite3
conn = sqlite3.connect('scrape_cache.db')
t = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
c = conn.execute('SELECT MIN(date), MAX(date) FROM sofa_historical_results').fetchone()
wf = conn.execute('SELECT COUNT(*) FROM walkforward_state').fetchone()[0]
wt = conn.execute('SELECT COUNT(DISTINCT team_name) FROM walkforward_state').fetchone()[0]
print(f'Matches: {t:,}')
print(f'Date range: {c[0]} to {c[1]}')
print(f'Walkforward: {wf:,} states, {wt:,} teams')
conn.close()
"

:: Check V4 results
if exist models\v4_results.json (
    echo.
    python -c "import json; r=json.load(open('models/v4_results.json')); print(f\"V4 Ensemble: {r['ensemble']['exact_pct']}%% exact, {r['ensemble']['1x2_pct']}%% 1X2, RPS={r['ensemble']['rps']}\")"
) else (
    echo.
    echo [V4] Training in progress...
)

echo ========================================
