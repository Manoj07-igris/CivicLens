<#
.SYNOPSIS
    Starts the full CivicLens application (Backend + Frontend).
.DESCRIPTION
    Launches FastAPI on port 8000 and Vite dev server on port 5173.
    Supports -SingleOrigin flag to serve pre-built SPA directly from FastAPI.
.PARAMETER SingleOrigin
    Run in single-origin mode: FastAPI serves both API and production frontend on port 8000.
#>
param(
    [switch]$SingleOrigin
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectDir "backend\.venv\Scripts\python.exe"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "Starting CivicLens AI System" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

if ($SingleOrigin) {
    Write-Host "Mode: SINGLE-ORIGIN (Serving pre-built frontend from FastAPI)" -ForegroundColor Yellow
    $env:SERVE_FRONTEND = "true"
    
    # Ensure frontend is built
    $DistDir = Join-Path $ProjectDir "frontend\dist"
    if (-not (Test-Path $DistDir)) {
        Write-Host "Building frontend distribution..." -ForegroundColor Gray
        npm run build --prefix (Join-Path $ProjectDir "frontend")
    }

    Write-Host "Starting FastAPI server on http://127.0.0.1:8000..." -ForegroundColor Green
    Set-Location (Join-Path $ProjectDir "backend")
    & $PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} else {
    Write-Host "Mode: DUAL-SERVER (FastAPI API on 8000 + Vite Dev Server on 5173)" -ForegroundColor Green

    # Preflight: check for existing port listeners
    $Existing8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($Existing8000) {
        Write-Host "  Port 8000 is currently occupied (PID: $($Existing8000[0].OwningProcess)). Cleaning up..." -ForegroundColor Yellow
        & (Join-Path $PSScriptRoot "stop_all.ps1")
        Start-Sleep -Seconds 1
    }

    # Start Backend in background process
    Write-Host "1. Launching Backend API (port 8000)..." -ForegroundColor Gray
    $BackendJob = Start-Process -FilePath $PythonExe -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory (Join-Path $ProjectDir "backend") -PassThru

    # Wait-for-health polling loop (up to 20 seconds)
    Write-Host "   Waiting for Backend API to become ready..." -ForegroundColor Gray
    $MaxWaitSec = 20
    $StartTime = Get-Date
    $BackendHealthy = $false

    while (((Get-Date) - $StartTime).TotalSeconds -lt $MaxWaitSec) {
        if ($BackendJob.HasExited) {
            Write-Host "  [ERROR] Backend process terminated unexpectedly with code $($BackendJob.ExitCode)." -ForegroundColor Red
            break
        }
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
            if ($resp.status -eq "ok" -or $resp.status -eq "degraded") {
                $BackendHealthy = $true
                $Elapsed = [math]::Round(((Get-Date) - $StartTime).TotalSeconds, 1)
                Write-Host "   Backend API is healthy! (status: $($resp.status), database: $($resp.database), took ${Elapsed}s)" -ForegroundColor Green
                break
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }

    if (-not $BackendHealthy -and -not $BackendJob.HasExited) {
        Write-Host "   [WARN] Health endpoint did not respond within ${MaxWaitSec}s, continuing startup..." -ForegroundColor Yellow
    }

    # Start Frontend in background process
    Write-Host "2. Launching Frontend Dev Server (port 5173)..." -ForegroundColor Gray
    $FrontendJob = Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory (Join-Path $ProjectDir "frontend") -PassThru

    Start-Sleep -Seconds 2

    Write-Host ""
    Write-Host "CivicLens is now active!" -ForegroundColor Cyan
    Write-Host "-------------------------------------------------------" -ForegroundColor Gray
    Write-Host "  Frontend Web UI:   http://localhost:5173" -ForegroundColor Green
    Write-Host "  Backend API Docs:  http://127.0.0.1:8000/docs" -ForegroundColor Green
    Write-Host "  Demo Portal:       http://127.0.0.1:8000/demo-portal" -ForegroundColor Green
    Write-Host "-------------------------------------------------------" -ForegroundColor Gray
    Write-Host "To stop all processes, execute: .\scripts\stop_all.ps1" -ForegroundColor Yellow

    # Keep script open to track processes
    try {
        Wait-Process -Id $BackendJob.Id, $FrontendJob.Id
    } finally {
        Write-Host "Shutting down servers..." -ForegroundColor Gray
        Stop-Process -Id $BackendJob.Id -Force -ErrorAction SilentlyContinue
        Stop-Process -Id $FrontendJob.Id -Force -ErrorAction SilentlyContinue
    }
}
