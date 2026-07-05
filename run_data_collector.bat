@echo off
title Football Oracle — Data Collector
echo =============================================
echo Football Oracle — Bulk Data Collector
echo =============================================
echo Collects more matches from SofaScore + football-data.org
echo.
cd /d "%~dp0\football_predictor"
echo Started: %date% %time%
echo.
python smart_scanner.py
echo.
echo Done!
pause
