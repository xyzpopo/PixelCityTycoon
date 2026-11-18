@echo off
setlocal
cd /d "%~dp0"
title Pixel City Tycoon - Run

where py >nul 2>nul
if errorlevel 1 goto no_launcher

py -3 --version
if errorlevel 1 goto no_python

if exist ".venv\Scripts\python.exe" goto venv_ready

echo Creating an isolated Python environment...
py -3 -m venv .venv
if errorlevel 1 goto failed

:venv_ready
if not exist "assets\fonts\NotoSansKR[wght].ttf" (
    echo Downloading Korean font...
    if not exist "assets\fonts" mkdir "assets\fonts"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/google/fonts/main/ofl/notosanskr/NotoSansKR%%5Bwght%%5D.ttf' -OutFile 'assets\fonts\NotoSansKR[wght].ttf'"
    if errorlevel 1 goto failed
)

echo Installing or checking pygame-ce...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --only-binary=pygame-ce "pygame-ce>=2.5.8"
if errorlevel 1 goto failed

".venv\Scripts\python.exe" main.py
if errorlevel 1 goto failed
exit /b 0

:no_launcher
echo ERROR: Python launcher was not found. Install Python 3.10 or newer.
goto failed

:no_python
echo ERROR: No Python installation was found.
goto failed

:failed
echo.
echo The game could not start. Copy the error text above and send it for troubleshooting.
pause
exit /b 1
