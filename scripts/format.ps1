$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$env:PYTHONPATH = "$RepoRoot\src"

Write-Host "== isort =="
python -m isort src scripts

Write-Host "== Black =="
python -m black src scripts

Write-Host "== Ruff format (or fallback to fix) =="
try {
    python -m ruff format src scripts
} catch {
    Write-Host "ruff format failed or unavailable; falling back to ruff check --fix"
    python -m ruff check --fix src scripts
}

Write-Host "Formatting complete."
