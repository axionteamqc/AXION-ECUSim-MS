$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -m ecusim_ms.cli_runner --iface virtual --mode loop
} else {
    Write-Warning "venv python not found; ensure setup.ps1 was run. Falling back to system python with PYTHONPATH=src."
    $env:PYTHONPATH = "$RepoRoot\src"
    python -m ecusim_ms.cli_runner --iface virtual --mode loop
}
