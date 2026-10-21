@echo off
setlocal
set "NIGHTREIGN_PYTHON=%~dp0.venv\Scripts\pythonw.exe"
if exist "%NIGHTREIGN_PYTHON%" (
  start "" /b /d "%~dp0" "%NIGHTREIGN_PYTHON%" "%~dp0app.py"
  exit /b 0
)
where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" /b /d "%~dp0" pythonw "%~dp0app.py"
  exit /b 0
)
where pyw >nul 2>nul
if not errorlevel 1 (
  start "" /b /d "%~dp0" pyw -3 "%~dp0app.py"
  exit /b 0
)
echo Python was not found. Follow the setup instructions in README.md.
pause
exit /b 1
