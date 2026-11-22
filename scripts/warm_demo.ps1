<#
.SYNOPSIS
    Pre-warms models, vectors, and demo data for live presentation.
.DESCRIPTION
    Seeds the demo portal and official policy documents into the library,
    downloads/loads the embedding model into cache, and builds vector indexes.
#>

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectDir "backend\.venv\Scripts\python.exe"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "Warming Up CivicLens Demonstration Environment" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

$WarmupScript = @"
import sys
from pathlib import Path
sys.path.insert(0, r"$ProjectDir\backend")

print("1. Checking Database and Portal Registry...")
from app.db.database import get_database
from app.services.portal_registry import get_portal_registry_service
ps = get_portal_registry_service()
portals = ps.list_portals()
print(f"   Registered Portals: {len(portals)} active")

print("2. Pre-loading Multilingual Embedding Model...")
from app.services.rag_service import get_rag_service
rag = get_rag_service()
embedder = rag.embedder
test_vector = embedder.embed_text("CivicLens Warmup Vector Search")
print(f"   Model active: {embedder.model_name} (dim: {len(test_vector)})")

print("3. Generating Benchmark Demo Policy Documents...")
from evals.generator import generate_benchmark_assets
bench_dir = Path(r"$ProjectDir\backend\data\official_sources")
assets = generate_benchmark_assets(bench_dir)
print(f"   Demo policy PDFs seeded in official source library: {len(assets)} files")

print("WARMUP_SUCCESS")
"@

$Output = & $PythonExe -c $WarmupScript 2>&1
Write-Host $Output -ForegroundColor Gray

if ($Output -match "WARMUP_SUCCESS") {
    Write-Host "-------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "Warmup successful! Models and demo assets are primed." -ForegroundColor Green
} else {
    Write-Host "Warmup encountered an issue." -ForegroundColor Yellow
}
