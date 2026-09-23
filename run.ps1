param(
    [ValidateSet("smoke", "paper")]
    [string]$Mode = "smoke",
    [ValidateSet("normal", "v2")]
    [string]$AuroraVersion = "normal",
    [int]$Threads = 8,
    [switch]$SkipBuild,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$WindowsDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$WslDirectory = (wsl wslpath -a $WindowsDirectory).Trim()
if (-not $WslDirectory) {
    throw "Could not translate the benchmark directory for WSL."
}

$Command = "cd '$WslDirectory' && bash ./run.sh '$Mode' --aurora-version '$AuroraVersion' --threads '$Threads'"
if ($SkipBuild) { $Command += " --skip-build" }
if ($SkipTests) { $Command += " --skip-tests" }
wsl bash -lc $Command
exit $LASTEXITCODE
