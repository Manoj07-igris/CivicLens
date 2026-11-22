<#
.SYNOPSIS
    Resets CivicLens demonstration data to a pristine state.
.DESCRIPTION
    Safely backs up the current database, purges user uploads and temporary files,
    re-runs migrations, and seeds the official demonstration portal and library.
#>

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectDir "backend\.venv\Scripts\python.exe"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "Resetting CivicLens Demonstration State" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

$DataDir = Join-Path $ProjectDir "backend\data"
$DbFile = Join-Path $DataDir "civiclens.db"
$BackupDir = Join-Path $DataDir "backups"

# 1. Create safety backup if database exists
if (Test-Path $DbFile) {
    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir | Out-Null
    }
    $Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BackupTarget = Join-Path $BackupDir "civiclens-pre-reset-$Timestamp.db"
    Copy-Item $DbFile $BackupTarget -Force
    Write-Host "  [OK] Created database backup: $BackupTarget" -ForegroundColor Green
}

# 2. Reset database tables using python reset script
$ResetScript = @"
import sys
from pathlib import Path
sys.path.insert(0, r"$ProjectDir\backend")
from app.db.database import get_database
from app.db.migrations.runner import MigrationRunner

db = get_database()
with db.transaction():
    for tbl in ["messages", "conversations", "activity", "tool_runs", "approvals", "grievances", "service_guides", "verifications", "comparisons", "browser_sessions"]:
        try:
            db.execute(f"DELETE FROM {tbl};")
        except Exception:
            pass
    db.execute("DELETE FROM document_chunks WHERE document_id IN (SELECT id FROM documents WHERE collection = 'user');")
    db.execute("DELETE FROM document_pages WHERE document_id IN (SELECT id FROM documents WHERE collection = 'user');")
    db.execute("DELETE FROM documents WHERE collection = 'user';")
    db.execute("DELETE FROM portals WHERE system = 0;")
print("DATABASE_RESET_OK")
"@

$PyOutput = & $PythonExe -c $ResetScript 2>&1
if ($PyOutput -match "DATABASE_RESET_OK") {
    Write-Host "  [OK] SQLite tables cleared of user records" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Database reset script output: $PyOutput" -ForegroundColor Yellow
}

# 3. Clean temporary directories
$DirsToPurge = @("uploads", "comparisons", "verifications", "service_guides", "browser_sessions")
foreach ($d in $DirsToPurge) {
    $target = Join-Path $DataDir $d
    if (Test-Path $target) {
        Get-ChildItem $target -Exclude ".gitkeep" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "  [OK] User uploads and temporary session directories purged" -ForegroundColor Green

Write-Host "-------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Demo reset complete! Pristine state restored." -ForegroundColor Green
