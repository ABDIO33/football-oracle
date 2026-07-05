@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
python ultimate_train.py 2>&1
