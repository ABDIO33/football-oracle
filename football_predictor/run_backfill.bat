@echo off
set PYTHONIOENCODING=utf-8
cd /d "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
python -u lineup_backfill_parallel.py > "C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\backfill_log.txt" 2>&1
