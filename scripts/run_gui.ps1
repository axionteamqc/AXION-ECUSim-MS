$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$venvActivate = Join-Path $RepoRoot ".venv\Scripts\Activate.ps1"
$venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$setupScript = Join-Path $RepoRoot "scripts\setup.ps1"

if (-not (Test-Path $venvActivate)) {
    if (-not (Test-Path $setupScript)) {
        throw "Missing scripts\setup.ps1. Run from repo root."
    }
    Write-Host "== Setup (venv + deps) ==" 
    & $setupScript
}

if (-not (Test-Path $venvActivate)) {
    throw "Missing .venv activation script at: $venvActivate"
}

Write-Host "== Activate venv ==" 
. $venvActivate

Write-Host "== Launch GUI ==" 
if (Test-Path $venvPython) {
    & $venvPython -m ecusim_ms.gui_app
} else {
    Write-Warning "venv python not found; falling back to system python with PYTHONPATH=src"
    $env:PYTHONPATH = "$RepoRoot\src"
    python -m ecusim_ms.gui_app
}
