@echo off
title Football Oracle — Ultimate Trainer
echo =============================================
echo Football Oracle — Checkpointed Ultimate Trainer
echo =============================================
echo.
echo Safe to restart — resumes from last checkpoint
echo See football_predictor/models/checkpoint.json for progress
echo.
cd /d "%~dp0\football_predictor"
echo Started: %date% %time%
echo.
python checkpointed_trainer.py
echo.
echo =============================================
echo Training finished! Check models/ultimate_results.json
pause
