@echo off
title SOFIA Market Analyst - Localhost Launcher
color 0A

echo =====================================================================
echo           SOFIA MARKET ANALYST v3.8 PRO - LOCALHOST RUNNER
echo =====================================================================
echo.
echo [1/2] Menjalankan Backend API (FastAPI) di http://localhost:8000 ...
start "SOFIA Backend (Port 8000)" cmd /k "cd /d %~dp0services\api && python -m uvicorn app.main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

echo [2/2] Menjalankan Frontend Web (Next.js) di http://localhost:3000 ...
start "SOFIA Frontend (Port 3000)" cmd /k "cd /d %~dp0apps\web && npm run dev"

echo.
echo =====================================================================
echo  Server sedang berjalan!
echo  - Frontend Web : http://localhost:3000
echo  - Backend API  : http://localhost:8000
echo  - API Docs     : http://localhost:8000/docs
echo =====================================================================
echo.
echo Browser akan otomatis terbuka dalam 5 detik...
timeout /t 5 /nobreak >nul
start http://localhost:3000
exit
