@echo off
cd /d "%~dp0"
echo ============================================
echo   Score Exact 100 - AI Football Predictor
echo ============================================
echo.
echo Installing/updating dependencies...
python -m pip install -r requirements.txt
echo.
echo Starting server...
echo Open http://127.0.0.1:5000 in your browser
echo.
python app.py
pause
