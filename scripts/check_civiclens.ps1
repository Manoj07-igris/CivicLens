<#
.SYNOPSIS
    CivicLens AI System Status Inspector (Beginner-Friendly).
.DESCRIPTION
    Checks Backend health, Frontend reachability, .env configuration (never printing secrets),
    SQLite database integrity, core Python virtual environment packages, and port statuses.
#>

$ErrorActionPreference = "Continue"
$ProjectDir = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $ProjectDir "backend"))) {
    $ProjectDir = (Get-Location).Path
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "                 CivicLens AI System Status Inspector                 " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# Helper function to test port availability quickly without WMI delays
function Test-PortOpen($port) {
    $client = New-Object System.Net.Sockets.TcpClient
    $open = $false
    try {
        $async = $client.BeginConnect("127.0.0.1", $port, $null, $null)
        if ($async.AsyncWaitHandle.WaitOne(300, $false)) {
            $client.EndConnect($async)
            $open = $client.Connected
        }
    } catch {
        $open = $false
    } finally {
        $client.Close()
    }
    return $open
}

# 1. Backend API Service
Write-Host "1. Backend API Service:" -ForegroundColor Cyan
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 3 -ErrorAction Stop
    if ($h.status -eq "ok" -or $h.status -eq "degraded") {
        Write-Host "   [OK] Backend is running and healthy (status: $($h.status), database: $($h.database))" -ForegroundColor Green
    } else {
        Write-Host "   [WARN] Backend responded with unexpected status: $($h.status)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   [ERROR] Backend is NOT reachable on http://127.0.0.1:8000" -ForegroundColor Red
    Write-Host "   ACTION: Double-click START_CIVICLENS.bat to launch the backend server." -ForegroundColor Yellow
    $allGood = $false
}
Write-Host ""

# 2. Frontend Web Interface
Write-Host "2. Frontend Web Interface:" -ForegroundColor Cyan
try {
    $f = Invoke-WebRequest -Uri "http://localhost:5173/" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    if ($f.StatusCode -eq 200) {
        Write-Host "   [OK] Frontend server is reachable at http://localhost:5173" -ForegroundColor Green
    } else {
        Write-Host "   [WARN] Frontend returned HTTP status: $($f.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   [ERROR] Frontend is NOT reachable on http://localhost:5173" -ForegroundColor Red
    Write-Host "   ACTION: Double-click START_CIVICLENS.bat to launch the frontend dev server." -ForegroundColor Yellow
    $allGood = $false
}
Write-Host ""

# 3. Environment Configuration (.env)
Write-Host "3. Environment Configuration (.env):" -ForegroundColor Cyan
$envPath = Join-Path $ProjectDir "backend\.env"
if (Test-Path $envPath) {
    Write-Host "   [OK] backend\.env file is present." -ForegroundColor Green
    $envContent = Get-Content $envPath -Raw
    
    # Check GEMINI_API_KEY without ever echoing its value
    if ($envContent -match '(?m)^\s*GEMINI_API_KEY\s*=\s*(.+?)\s*$') {
        $keyVal = $Matches[1].Trim()
        if ($keyVal -and $keyVal -ne "your_gemini_api_key_here" -and $keyVal -ne '""' -and $keyVal -ne "''") {
            Write-Host "   [OK] GEMINI_API_KEY is configured." -ForegroundColor Green
        } else {
            Write-Host "   [WARN] GEMINI_API_KEY is placeholder or empty (AI features will use offline simulation mode)." -ForegroundColor Yellow
            Write-Host "   ACTION: To enable Gemini AI, add your real GEMINI_API_KEY to backend\.env" -ForegroundColor Gray
        }
    } else {
        Write-Host "   [WARN] GEMINI_API_KEY variable not found in backend\.env" -ForegroundColor Yellow
        Write-Host "   ACTION: Add GEMINI_API_KEY=your_key to backend\.env" -ForegroundColor Gray
    }

    # Check AUTH_SECRET_KEY without ever echoing its value
    if ($envContent -match '(?m)^\s*AUTH_SECRET_KEY\s*=\s*(.+?)\s*$') {
        $secretVal = $Matches[1].Trim()
        if ($secretVal -and $secretVal -ne '""' -and $secretVal -ne "''") {
            Write-Host "   [OK] AUTH_SECRET_KEY is explicitly configured." -ForegroundColor Green
        } else {
            Write-Host "   [WARN] AUTH_SECRET_KEY is empty (development fallback key is used automatically)." -ForegroundColor Yellow
        }
    } else {
        Write-Host "   [WARN] AUTH_SECRET_KEY is not explicitly set (development fallback key is used automatically)." -ForegroundColor Yellow
        Write-Host "   ACTION: For production deployments, add an AUTH_SECRET_KEY into backend\.env." -ForegroundColor Gray
    }
} else {
    Write-Host "   [WARN] backend\.env file not found (system will use default development settings)." -ForegroundColor Yellow
    Write-Host "   ACTION: Copy backend\.env.example to backend\.env if you wish to configure custom settings." -ForegroundColor Gray
}
Write-Host ""

# 4. SQLite Database & Storage
Write-Host "4. SQLite Database & Storage:" -ForegroundColor Cyan
$dbPath = Join-Path $ProjectDir "backend\data\civiclens.db"
if (Test-Path $dbPath) {
    $dbSize = (Get-Item $dbPath).Length / 1KB
    $pyExe = Join-Path $ProjectDir "backend\.venv\Scripts\python.exe"
    if (Test-Path $pyExe) {
        $integrity = & $pyExe -c "import sqlite3; con = sqlite3.connect(r'$dbPath'); cur = con.cursor(); res = cur.execute('PRAGMA quick_check;').fetchone()[0]; con.close(); print(res)" 2>&1
        if ($integrity -eq "ok") {
            Write-Host "   [OK] Database file exists ($([math]::Round($dbSize, 1)) KB) and integrity check passed (quick_check: OK)." -ForegroundColor Green
        } else {
            Write-Host "   [ERROR] Database file integrity check failed: $integrity" -ForegroundColor Red
            Write-Host "   ACTION: Restore from a backup or run safe migration." -ForegroundColor Yellow
            $allGood = $false
        }
    } else {
        Write-Host "   [OK] Database file exists ($([math]::Round($dbSize, 1)) KB)." -ForegroundColor Green
    }
} else {
    Write-Host "   [WARN] Database file not yet created (it will be initialized automatically on first backend launch)." -ForegroundColor Yellow
}
Write-Host ""

# 5. Python Packages & Virtual Environment
Write-Host "5. Python Packages & Virtual Environment:" -ForegroundColor Cyan
$pyExe = Join-Path $ProjectDir "backend\.venv\Scripts\python.exe"
if (Test-Path $pyExe) {
    $pkgCheck = & $pyExe -c "import argon2, email_validator, fastapi, uvicorn; print('ALL_REQUIRED_OK')" 2>&1
    if ($pkgCheck -match "ALL_REQUIRED_OK") {
        Write-Host "   [OK] All core Python packages (argon2-cffi, email-validator, fastapi, uvicorn) are verified." -ForegroundColor Green
    } else {
        Write-Host "   [ERROR] Python package verification failed: $pkgCheck" -ForegroundColor Red
        Write-Host "   ACTION: Run: backend\.venv\Scripts\pip install -r backend\requirements.txt" -ForegroundColor Yellow
        $allGood = $false
    }
} else {
    Write-Host "   [ERROR] Virtual environment backend\.venv does not exist." -ForegroundColor Red
    Write-Host "   ACTION: Double-click START_CIVICLENS.bat to automatically set up the virtual environment." -ForegroundColor Yellow
    $allGood = $false
}
Write-Host ""

# 6. Port Status
Write-Host "6. Port Status:" -ForegroundColor Cyan
$p8000 = Test-PortOpen 8000
$p5173 = Test-PortOpen 5173

if ($p8000) {
    Write-Host "   [OCCUPIED] Port 8000 is listening (Backend active)." -ForegroundColor Green
} else {
    Write-Host "   [FREE] Port 8000 is currently free (Backend not running)." -ForegroundColor Gray
}

if ($p5173) {
    Write-Host "   [OCCUPIED] Port 5173 is listening (Frontend active)." -ForegroundColor Green
} else {
    Write-Host "   [FREE] Port 5173 is currently free (Frontend not running)." -ForegroundColor Gray
}
Write-Host ""

Write-Host "======================================================================" -ForegroundColor Cyan
if ($allGood) {
    Write-Host "Summary: CivicLens environment is in healthy operating condition!" -ForegroundColor Green
} else {
    Write-Host "Summary: One or more checks require attention (see yellow/red hints above)." -ForegroundColor Yellow
}
Write-Host "======================================================================" -ForegroundColor Cyan
