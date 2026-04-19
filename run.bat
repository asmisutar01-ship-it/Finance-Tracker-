@echo off
REM FinanceTracker – start script that always uses the venv Python
REM Run from project root: run.bat
cd /d "%~dp0"
.\venv\Scripts\python.exe app\app.py
