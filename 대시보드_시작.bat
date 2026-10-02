@echo off
setlocal
cd /d "%~dp0"
title KTB RTD Dashboard
".venv32\Scripts\python.exe" ".\dashboard.py"
pause
