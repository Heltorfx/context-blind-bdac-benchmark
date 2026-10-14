param(
    [ValidateSet("issuance", "presentation")]
    [string]$Command = "presentation",
    [ValidateSet("aurora", "longfellow")]
    [string]$Backend = "aurora"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$wslScriptDir = (wsl wslpath -a ($scriptDir -replace '\\', '/')).Trim()

if (-not $wslScriptDir) {
    throw "Unable to resolve the artifact directory in WSL."
}

wsl bash -lc "cd '$wslScriptDir' && ./demo.sh '$Command' '$Backend'"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
