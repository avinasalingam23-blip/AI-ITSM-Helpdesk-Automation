
@echo off
title AI Helpdesk Launcher

cd /d "%~dp0"

echo Starting AI Helpdesk Backend...
start "Helpdesk Backend" cmd /k "cd /d ""%~dp0"" && ""%~dp0backend\.venv\Scripts\python.exe"" -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000"

echo Starting AI Helpdesk Frontend...
start "Helpdesk Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort"

echo Waiting for frontend...
timeout /t 8 /nobreak >nul

start "" "http://127.0.0.1:5173"

echo Helpdesk launch commands completed.
