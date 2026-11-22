@echo off
setlocal enabledelayedexpansion
title CivicLens AI - Launcher
cd /d "%~dp0"

echo ======================================================================
echo                  CivicLens AI System Launcher
echo           "Understand. Verify. Act." - Local Civic Intelligence
echo ======================================================================
echo.

:: 1. Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not found in your system PATH.
    echo Please download and install Python 3.10 or 3.11 from:
    echo    https://www.python.org/downloads/
    echo (Make sure to check "Add Python to PATH" during installation!)
    echo.
    pause
    exit /b 1
)

:: 2. Check Node.js installation
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not found in your system PATH.
    echo Please download and install Node.js (LTS version) from:
    echo    https://nodejs.org/
    echo.
    pause
    exit /b 1
)

:: 3. Verify Virtual Environment
if not exist "backend\.venv\Scripts\python.exe" (
    echo [INFO] Setting up backend Python virtual environment...
    python -m venv backend\.venv
    if not exist "backend\.venv\Scripts\python.exe" (
        echo [ERROR] Failed to create virtual environment in backend\.venv
        pause
        exit /b 1
    )
    echo [INFO] Installing backend dependencies (this may take a minute)...
    backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
)

:: 4. Verify Frontend node_modules
if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies (this may take a minute)...
    cd frontend && call npm install && cd ..
)

:: 5. Create backend server.log if not exists
if not exist "backend" mkdir backend
if exist "backend\server.log" del /f /q "backend\server.log"

:: 6. Launch Backend in its own window
echo [1/3] Starting CivicLens Backend server on port 8000...
start "CivicLens Backend (keep this open)" cmd /k "title CivicLens Backend (keep this open) && cd /d ""%~dp0"" && .\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend 2>&1 | powershell -NoProfile -Command ""$input | Tee-Object -FilePath '%~dp0backend\server.log'"""

:: 7. Launch Frontend in its own window
echo [2/3] Starting CivicLens Frontend dev server on port 5173...
start "CivicLens Frontend (keep this open)" cmd /k "title CivicLens Frontend (keep this open) && cd /d ""%~dp0frontend"" && npm run dev"

:: 8. Polling health check (up to 60 seconds)
echo [3/3] Waiting for CivicLens Backend to initialize and become ready...
echo (Checking http://127.0.0.1:8000/api/v1/health...)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ready = $false;" ^
    "for ($i = 1; $i -le 30; $i++) {" ^
    "    try {" ^
    "        $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 2 -ErrorAction Stop;" ^
    "        if ($resp.status -eq 'ok' -or $resp.status -eq 'degraded') {" ^
    "            $ready = $true;" ^
    "            break;" ^
    "        }" ^
    "    } catch {}" ^
    "    Start-Sleep -Seconds 2;" ^
    "    Write-Host -NoNewline '.';" ^
    "}" ^
    "Write-Host '';" ^
    "if ($ready) { exit 0 } else { exit 1 }"

if %errorlevel% equ 0 (
    echo.
    echo ======================================================================
    echo [SUCCESS] CivicLens is online and healthy!
    echo.
    echo Opening CivicLens in your browser:
    echo    http://localhost:5173
    echo.
    echo Keep the Backend and Frontend windows OPEN while using CivicLens.
    echo To stop CivicLens, double-click: STOP_CIVICLENS.bat
    echo ======================================================================
    start http://localhost:5173
    timeout /t 5 >nul
    exit /b 0
) else (
    echo.
    echo ======================================================================
    echo [ERROR] The backend did not become healthy within 60 seconds.
    echo ======================================================================
    echo.
    echo Recent output from the backend:
    echo ----------------------------------------------------------------------
    if exist "backend\server.log" (
        powershell -NoProfile -Command "Get-Content 'backend\server.log' -Tail 20"
    ) else (
        echo (No log file was created. Please check the 'CivicLens Backend' window.)
    )
    echo ----------------------------------------------------------------------
    echo.
    echo HINT: Look at the window titled 'CivicLens Backend (keep this open)'.
    echo If you see an error, copy the last lines above and share them with
    echo your assistant for quick resolution.
    echo.
    pause
    exit /b 1
)
