@echo off
setlocal

set "ROOT=%~dp0"
set /p PORT=Server port [8000]: 
if "%PORT%"=="" set "PORT=8000"

cd /d "%ROOT%"
python -m uvicorn server_main:app --host 0.0.0.0 --port %PORT%
