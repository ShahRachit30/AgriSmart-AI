@echo off
REM AgriSmart AI - double-click launcher for Windows.
REM
REM   run.bat            start the app on http://localhost:8000
REM   run.bat 8010       start it on another port
REM   run.bat --doctor   environment check only
REM   run.bat --test     run the test suite
REM
REM Everything else (venv, pip, uvicorn) is handled by run.ps1 next to this file.
setlocal
cd /d "%~dp0"

set PORT=8000
set EXTRA=
if not "%~1"=="" (
  if "%~1"=="--doctor" ( set EXTRA=-Doctor ) else ( if "%~1"=="--test" ( set EXTRA=-Test ) else ( set PORT=%~1 ) )
)

where powershell >nul 2>&1
if errorlevel 1 (
  echo !!  PowerShell was not found. Install Python from https://www.python.org/downloads/
  echo     and run these two commands by hand:
  echo         python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  echo         python -m pip install -r requirements.txt
  echo         python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" -Port %PORT% %EXTRA%
if errorlevel 1 (
  echo.
  echo !!  the app exited with an error. Run "run.bat --doctor" for a diagnosis.
  pause
)
endlocal
