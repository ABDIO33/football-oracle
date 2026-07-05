@echo off
cd /d "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
echo [%date% %time%] Starting V4 Training...
python train_v4.py
echo [%date% %time%] V4 Exited with code %errorlevel%
pause
