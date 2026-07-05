@echo off
title Football Oracle — FD Collector
cd /d "%~dp0\football_predictor"
python fd_bulk_collector.py
pause
