@echo off
REM run this in background: start /B /NORMAL cmd /c run_bg.bat
cd /d "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
set PYTHONIOENCODING=utf-8
python -X utf8 ultimate_train_v2.py > training_log.txt 2>&1
