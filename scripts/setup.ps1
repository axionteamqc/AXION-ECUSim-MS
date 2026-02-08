$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$venvPath = Join-Path $RepoRoot ".venv"

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath"
    python -m venv $venvPath
}
else {
    Write-Host "Virtual environment already exists at $venvPath"
}

$activate = Join-Path (Join-Path $venvPath "Scripts") "Activate.ps1"
if (-not (Test-Path $activate)) {
    throw "Activate script not found at $activate"
}

Write-Host "Activating virtual environment..."
. $activate

Write-Host "Upgrading pip..."
python -m pip install --upgrade pip

Write-Host "Installing runtime requirements..."
python -m pip install -r requirements.txt

Write-Host "Installing dev requirements..."
python -m pip install -r requirements-dev.txt

Write-Host "Editable install of the package..."
python -m pip install -e .

Write-Host "Setup complete."
