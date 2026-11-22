@echo off
setlocal enabledelayedexpansion
title CivicLens AI - Stopper
cd /d "%~dp0"

echo ======================================================================
echo                  CivicLens AI System Stopper
echo ======================================================================
echo.

echo [1/3] Stopping CivicLens Backend and Frontend windows...
taskkill /FI "WINDOWTITLE eq CivicLens Backend (keep this open)*" /T /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq CivicLens Frontend (keep this open)*" /T /F >nul 2>nul

echo [2/3] Releasing ports 8000 and 5173...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ports = @(8000, 5173);" ^
    "foreach ($port in $ports) {" ^
    "    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue;" ^
    "    if ($conns) {" ^
    "        foreach ($c in $conns) {" ^
    "            if ($c.OwningProcess -gt 4) {" ^
    "                Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue;" ^
    "                Write-Host ('  Released port ' + $port + ' (PID: ' + $c.OwningProcess + ')');" ^
    "            }" ^
    "        }" ^
    "    } else {" ^
    "        Write-Host ('  Port ' + $port + ' is free.');" ^
    "    }" ^
    "}"

echo [3/3] Sweeping for leftover demo browser processes...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$chromes = Get-Process chrome -ErrorAction SilentlyContinue;" ^
    "if ($chromes) {" ^
    "    foreach ($p in $chromes) {" ^
    "        try {" ^
    "            $cmd = (Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $p.Id) -ErrorAction SilentlyContinue).CommandLine;" ^
    "            if ($cmd -match 'playwright' -or $cmd -match '--remote-debugging-pipe' -or $cmd -match 'civiclens') {" ^
    "                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue;" ^
    "                Write-Host ('  Stopped orphan demo browser PID ' + $p.Id);" ^
    "            }" ^
    "        } catch {}" ^
    "    }" ^
    "}"

echo.
echo ======================================================================
echo [SUCCESS] CivicLens servers and browser workers have been stopped.
echo Ports 8000 and 5173 are clean and ready for next launch.
echo ======================================================================
echo.
pause
