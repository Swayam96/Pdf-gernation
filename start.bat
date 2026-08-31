@echo off
echo Stopping any existing PDF Report server...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
timeout /t 1 /nobreak >nul

echo Starting PDF Report Dashboard...
start "PDF Report Dashboard" cmd /k "cd /d %~dp0 && python api.py"
timeout /t 1 /nobreak >nul

echo.
echo  Dashboard: http://localhost:8001
echo.
echo  Open that URL in your browser.
pause
