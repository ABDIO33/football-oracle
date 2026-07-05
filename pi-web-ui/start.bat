@echo off
title Pi Web UI
echo ============================================================
echo    Pi Web UI — Beautiful Chat Interface
echo    https://pi.dev
echo ============================================================
echo.
cd /d "%~dp0"
node server.js
pause
