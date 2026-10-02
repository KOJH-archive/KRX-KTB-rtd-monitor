@echo off
setlocal
cd /d "%~dp0"
title KTB RTD Monitor

if not exist ".venv32\Scripts\python.exe" (
    echo Python environment not found:
    echo %cd%\.venv32\Scripts\python.exe
    echo.
    echo Create .venv32 and install requirements first.
    pause
    exit /b 1
)

if not exist "???? ???.xlsx" (
    echo Workbook was not found in this folder.
    pause
    exit /b 1
)

echo Open the workbook in Excel and confirm that RTD values are visible.
echo Press Ctrl+C in this window to stop.
echo.
echo Log: data\launcher.log
".venv32\Scripts\python.exe" ".\ktb_rtd_monitor.py" --interval-ms 250 --output-dir ".\data" --log both --no-clear >> ".\data\launcher.log" 2>&1
echo.
echo Monitor stopped. Check data\launcher.log if there was an error.
pause
