@echo off
REM ============================================================
REM  ONE-TIME SETUP for the HD daily updater. Run this once.
REM ============================================================
cd /d "%~dp0"
echo.
echo Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo   Python is not installed or not on PATH.
  echo   Install it from https://www.python.org/downloads/ and be sure to
  echo   tick "Add python.exe to PATH" during install, then run setup.cmd again.
  echo.
  pause
  exit /b 1
)

echo Installing Python packages (playwright, pymupdf)...
python -m pip install --upgrade pip
python -m pip install playwright pymupdf
if errorlevel 1 ( echo Package install failed. & pause & exit /b 1 )

echo Downloading the headless browser (one-time, ~150 MB)...
python -m playwright install chromium
if errorlevel 1 ( echo Browser download failed. & pause & exit /b 1 )

echo.
echo ============================================================
echo  Setup complete.  Double-click  run_update.cmd  to update.
echo ============================================================
echo.
pause
