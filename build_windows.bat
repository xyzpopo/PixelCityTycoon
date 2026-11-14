@echo off
setlocal
cd /d "%~dp0"
title Pixel City Tycoon - Windows EXE Build

echo ========================================
echo   Pixel City Tycoon - Windows EXE Build
echo ========================================
echo.

where py >nul 2>nul
if errorlevel 1 goto no_launcher

py -3 --version
if errorlevel 1 goto no_python

if exist ".venv\Scripts\python.exe" goto venv_ready

echo [0/3] Creating an isolated Python environment...
py -3 -m venv .venv
if errorlevel 1 goto failed

:venv_ready
echo.
echo [1/3] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed

echo.
echo [2/3] Installing pygame-ce and PyInstaller...
".venv\Scripts\python.exe" -m pip install --only-binary=pygame-ce -r requirements.txt
if errorlevel 1 goto failed

echo.
echo [3/3] Building EXE...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name PixelCityTycoon main.py
if errorlevel 1 goto failed

if not exist "dist\PixelCityTycoon.exe" goto missing_exe

echo.
echo ========================================
echo Build successful!
echo EXE: %CD%\dist\PixelCityTycoon.exe
echo ========================================
echo.
pause
exit /b 0

:no_launcher
echo ERROR: Python launcher was not found.
echo Reinstall Python and enable the Python launcher option.
goto failed

:no_python
echo ERROR: Python was found, but no Python 3 installation is available.
echo Install Python 3.10 or newer, then try again.
goto failed

:missing_exe
echo ERROR: PyInstaller finished, but the EXE file was not found in dist.
goto failed

:failed
echo.
echo Build failed. Read the error messages above.
echo Copy this CMD window text and send it for troubleshooting.
pause
exit /b 1
