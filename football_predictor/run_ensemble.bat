@echo off
set PYTHONIOENCODING=utf-8
cd /d "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
python -u ensemble_trainer.py > "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\ensemble_train.log" 2>&1
