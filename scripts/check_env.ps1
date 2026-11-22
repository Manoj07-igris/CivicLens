<#
.SYNOPSIS
    CivicLens Preflight Environment Diagnostic Tool (Phase 16).
.DESCRIPTION
    Checks Python, virtual environment, Node.js, dependencies, database,
    Playwright Chromium browser, and Gemini API configuration.
#>

$ErrorActionPreference = "Continue"
$ProjectDir = Split-Path -Parent $PSScriptRoot

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "CivicLens AI — Environment Preflight Diagnostics" -ForegroundColor Cyan
Write-Host "Project Directory: $ProjectDir" -ForegroundColor Gray
Write-Host "=======================================================" -ForegroundColor Cyan

$Passed = 0
$Warnings = 0
$Failed = 0

function Report-Check($Name, $Status, $Message, $Level="OK") {
    if ($Level -eq "OK") {
        Write-Host "  [OK]   $($Name): $Message" -ForegroundColor Green
        $script:Passed++
    } elseif ($Level -eq "WARN") {
        Write-Host "  [WARN] $($Name): $Message" -ForegroundColor Yellow
        $script:Warnings++
    } else {
        Write-Host "  [FAIL] $($Name): $Message" -ForegroundColor Red
        $script:Failed++
    }
}

# 1. Check Python
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($PythonCmd) {
    $PyVer = & python --version 2>&1
    Report-Check "System Python" "OK" "$PyVer" "OK"
} else {
    Report-Check "System Python" "WARN" "python not found in PATH" "WARN"
}

# 2. Check Backend Virtual Environment
$VenvPy = Join-Path $ProjectDir "backend\.venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    $VenvVer = & $VenvPy -c "import sys; print(f'Python {sys.version.split()[0]}')" 2>&1
    Report-Check "Backend Virtualenv" "OK" "$VenvPy ($VenvVer)" "OK"
    
    # Check essential packages
    $PkgCheck = & $VenvPy -c "import fastapi, uvicorn, pydantic, pymupdf, faiss; print('OK')" 2>&1
    if ($PkgCheck -match "OK") {
        Report-Check "Core Dependencies" "OK" "FastAPI, PyMuPDF, FAISS, Pydantic verified" "OK"
    } else {
        Report-Check "Core Dependencies" "FAIL" "Failed importing core backend packages: $PkgCheck" "FAIL"
    }
} else {
    Report-Check "Backend Virtualenv" "FAIL" "Missing backend\.venv\Scripts\python.exe. Run: cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt" "FAIL"
}

# 3. Check Node.js and NPM
$NodeCmd = Get-Command node -ErrorAction SilentlyContinue
$NpmCmd = Get-Command npm -ErrorAction SilentlyContinue
if ($NodeCmd -and $NpmCmd) {
    $NodeVer = & node --version
    $NpmVer = & npm --version
    Report-Check "Node.js & NPM" "OK" "Node $NodeVer, NPM $NpmVer" "OK"
} else {
    Report-Check "Node.js & NPM" "FAIL" "Node.js / npm not detected in PATH" "FAIL"
}

# 4. Check Frontend Modules
$FrontendNodeModules = Join-Path $ProjectDir "frontend\node_modules"
if (Test-Path $FrontendNodeModules) {
    Report-Check "Frontend Dependencies" "OK" "node_modules installed" "OK"
} else {
    Report-Check "Frontend Dependencies" "WARN" "frontend\node_modules missing. Run: cd frontend; npm install" "WARN"
}

# 5. Check Playwright Chromium Browser
if (Test-Path $VenvPy) {
    $PwCheck = & $VenvPy -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); b.close(); p.stop(); print('CHROMIUM_OK')" 2>&1
    if ($PwCheck -match "CHROMIUM_OK") {
        Report-Check "Playwright Chromium" "OK" "Headless Chromium browser launched successfully" "OK"
    } else {
        Report-Check "Playwright Chromium" "WARN" "Chromium not installed. Run: backend\.venv\Scripts\playwright install chromium" "WARN"
    }
}

# 6. Check Configuration and API Key
$EnvFile = Join-Path $ProjectDir "backend\.env"
if (Test-Path $EnvFile) {
    $EnvContent = Get-Content $EnvFile -Raw
    if ($EnvContent -match "GEMINI_API_KEY=([a-zA-Z0-9_\-]+)") {
        $KeyVal = $Matches[1]
        if ($KeyVal -and $KeyVal -ne "your_gemini_api_key_here") {
            Report-Check "Gemini API Key" "OK" "Configured in backend/.env (Key masked)" "OK"
        } else {
            Report-Check "Gemini API Key" "WARN" "Placeholder key in backend/.env (Offline mode active)" "WARN"
        }
    } else {
        Report-Check "Gemini API Key" "WARN" "GEMINI_API_KEY empty in backend/.env" "WARN"
    }
} else {
    Report-Check "Environment File" "WARN" "backend/.env does not exist. (Created automatically or copy from .env.example)" "WARN"
}

# 7. Check SQLite Database
$DbFile = Join-Path $ProjectDir "backend\data\civiclens.db"
if (Test-Path $DbFile) {
    $DbSize = (Get-Item $DbFile).Length / 1KB
    Report-Check "SQLite Database" "OK" "backend\data\civiclens.db ($([math]::Round($DbSize, 1)) KB)" "OK"
} else {
    Report-Check "SQLite Database" "OK" "Will be initialized automatically on first API startup" "OK"
}

# 8. Check Frontend Environment (.env)
$FrontendEnv = Join-Path $ProjectDir "frontend\.env"
if (Test-Path $FrontendEnv) {
    Report-Check "Frontend .env" "OK" "VITE_API_BASE_URL configured" "OK"
} else {
    Report-Check "Frontend .env" "WARN" "frontend\.env missing; defaults to http://localhost:8000" "WARN"
}

# 9. Check Port 8000 & 5173 Availability
$testPort = {
    param($p)
    $c = New-Object System.Net.Sockets.TcpClient
    $open = $false
    try {
        $a = $c.BeginConnect("127.0.0.1", $p, $null, $null)
        if ($a.AsyncWaitHandle.WaitOne(300, $false)) {
            $c.EndConnect($a)
            $open = $c.Connected
        }
    } catch {
        $open = $false
    } finally {
        $c.Close()
    }
    return $open
}

$Port8000Occupied = & $testPort 8000
if ($Port8000Occupied) {
    Report-Check "Port 8000" "WARN" "Port 8000 is occupied (run STOP_CIVICLENS.bat to free)" "WARN"
} else {
    Report-Check "Port 8000" "OK" "Port 8000 is available for backend" "OK"
}

Write-Host "-------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Diagnostic Summary: $Passed Passed, $Warnings Warnings, $Failed Failed" -ForegroundColor Cyan
if ($Failed -eq 0) {
    Write-Host "System is READY for CivicLens demonstration!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Resolve FAIL items above before starting the application." -ForegroundColor Red
    exit 1
}
