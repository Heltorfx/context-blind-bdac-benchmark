[CmdletBinding()]
param([switch]$Silent)

$ErrorActionPreference = 'SilentlyContinue'
$ExhibitDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateFile = Join-Path $ExhibitDir '.exhibit-runtime.json'

if (-not (Test-Path -LiteralPath $StateFile)) {
    if (-not $Silent) { Write-Host 'No active VEIL exhibition was found.' }
    exit 0
}

$state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
if ($state.RelayPid) { Stop-Process -Id ([int]$state.RelayPid) -Force }
Remove-Item -LiteralPath $StateFile -Force
if (-not $Silent) { Write-Host 'VEIL exhibition stopped.' -ForegroundColor Green }
