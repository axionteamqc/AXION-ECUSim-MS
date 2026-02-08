$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$env:PYTHONPATH = "$RepoRoot\src"

Write-Host "== Ruff =="
python -m ruff check src scripts

Write-Host "== Black =="
python -m black --check src scripts

Write-Host "== isort =="
python -m isort --check-only src scripts

Write-Host "== CLI sanity =="
python -m ecusim_ms.cli_runner --help | Out-Null

Write-Host "== Selftest (virtual loop 5s) =="
python -m ecusim_ms.selftest

Write-Host "All checks passed."
