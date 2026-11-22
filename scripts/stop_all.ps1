<#
.SYNOPSIS
    Gracefully stops all CivicLens backend, frontend, and browser worker processes.
.DESCRIPTION
    Releases port 8000 and 5173, terminates uvicorn and vite processes,
    and sweeps for any orphaned chrome.exe processes.
#>

$ErrorActionPreference = "Continue"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "Stopping CivicLens System & Reaping Orphan Processes" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

$StoppedCount = 0

function Stop-PortListener($Port) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($c in $connections) {
            $pidToKill = $c.OwningProcess
            if ($pidToKill -and $pidToKill -gt 4) {
                Write-Host "  Stopping process on port $($Port) (PID: $($pidToKill))..." -ForegroundColor Yellow
                Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
                $script:StoppedCount++
            }
        }
    } else {
        Write-Host "  Port $($Port) is free." -ForegroundColor Green
    }
}

# 1. Stop Backend (port 8000)
Stop-PortListener 8000

# 2. Stop Frontend (port 5173)
Stop-PortListener 5173

# 3. Sweep for any orphaned chrome.exe spawned with playwright flag
Write-Host "  Sweeping for orphaned Playwright Chrome processes..." -ForegroundColor Gray
$ChromeProcs = Get-Process chrome -ErrorAction SilentlyContinue
if ($ChromeProcs) {
    foreach ($p in $ChromeProcs) {
        try {
            $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)").CommandLine
            if ($cmd -match "--remote-debugging-pipe" -or $cmd -match "playwright") {
                Write-Host "  Terminated orphan headless browser PID $($p.Id)" -ForegroundColor Yellow
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
                $script:StoppedCount++
            }
        } catch {}
    }
}

Write-Host "-------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Shutdown complete. Total processes stopped: $StoppedCount" -ForegroundColor Green
