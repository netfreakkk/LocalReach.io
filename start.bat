@echo off
cd /d "%~dp0"
title ScaleReach.ai Local Studio
echo ========================================================
echo  ScaleReach.ai Local Studio - RTX 4050 Accelerated
echo ========================================================
echo.
.venv\Scripts\python.exe server.py
pause
