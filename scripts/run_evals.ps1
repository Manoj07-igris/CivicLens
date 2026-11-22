<#
.SYNOPSIS
    Runs the CivicLens Quality Evaluation Harness.
.DESCRIPTION
    Benchmarks all 5 civic intelligence modules and central agent orchestrator.
    Defaults to offline deterministic evaluation consuming 0 Gemini API quota.
.PARAMETER Live
    Enable live AI evaluation against Google Gemini API.
.PARAMETER YesUseQuota
    Required confirmation flag when running in -Live mode.
.PARAMETER MaxCalls
    Hard maximum ceiling on outbound Gemini API calls (default 60).
#>
param(
    [switch]$Live,
    [switch]$YesUseQuota,
    [int]$MaxCalls = 60
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PythonExe = Join-Path $ProjectDir "backend\.venv\Scripts\python.exe"
$RunnerPy = Join-Path $ProjectDir "backend\evals\runner.py"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Backend virtual environment python not found at $PythonExe"
    exit 1
}

$ArgsList = @()
if ($Live) {
    $ArgsList += "--live"
    if ($YesUseQuota) {
        $ArgsList += "--yes-use-quota"
    }
    $ArgsList += "--max-calls"
    $ArgsList += "$MaxCalls"
} else {
    $ArgsList += "--offline"
}

Write-Host "Executing CivicLens Quality Evaluation Harness ($ProjectDir)..." -ForegroundColor Cyan
& $PythonExe $RunnerPy @ArgsList
