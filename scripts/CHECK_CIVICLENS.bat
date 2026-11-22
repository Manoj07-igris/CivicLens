@echo off
setlocal
title CivicLens AI - Status Inspector
cd /d "%~dp0"

if exist "check_civiclens.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0check_civiclens.ps1"
) else if exist "..\scripts\check_civiclens.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\check_civiclens.ps1"
) else (
    echo [ERROR] check_civiclens.ps1 could not be found.
)

echo.
pause
