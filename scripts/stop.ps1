$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$stopFile = Join-Path $RepoRoot "data\stop.flag"
New-Item -ItemType File -Force -Path $stopFile | Out-Null
Write-Host "stop.flag set at $stopFile"
