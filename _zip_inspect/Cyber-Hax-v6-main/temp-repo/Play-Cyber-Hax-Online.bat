@echo off
setlocal

set "ROOT=%~dp0"
echo.
echo ============================================
echo          CYBER HAX ONLINE LAUNCHER
echo ============================================
echo.

set /p PLAYER=Callsign [Operator]: 
if "%PLAYER%"=="" set "PLAYER=Operator"

set /p SESSION=Session [session1]: 
if "%SESSION%"=="" set "SESSION=session1"

set /p SERVER=Server websocket URL [ws://127.0.0.1:8000]: 
if "%SERVER%"=="" set "SERVER=ws://127.0.0.1:8000"

if exist "%ROOT%cyber_hax_online.exe" (
    start "" "%ROOT%cyber_hax_online.exe" --session "%SESSION%" --player "%PLAYER%" --server "%SERVER%"
) else if exist "%ROOT%dist\cyber_hax_online.exe" (
    start "" "%ROOT%dist\cyber_hax_online.exe" --session "%SESSION%" --player "%PLAYER%" --server "%SERVER%"
) else if exist "%ROOT%cyber_hax.py" (
    start "" py -3 "%ROOT%cyber_hax.py" --session "%SESSION%" --player "%PLAYER%" --server "%SERVER%"
) else (
    echo Could not find a runnable Cyber Hax client in:
    echo %ROOT%
    pause
)
