[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8766,
    [string]$PublicUrl = 'http://192.168.137.1:8766'
)

$ErrorActionPreference = 'Stop'
$ExhibitDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateFile = Join-Path $ExhibitDir '.exhibit-runtime.json'
$ServerScript = Join-Path $ExhibitDir 'run_server.sh'
$RelayScript = Join-Path $ExhibitDir 'Hotspot-Relay.ps1'

trap {
    Write-Host ''
    Write-Host 'VEIL could not start.' -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    if ($Host.Name -eq 'ConsoleHost') { Read-Host 'Press Enter to close this window' }
    exit 1
}

# Stop a server left by the previous detached launcher, if one exists.
if (Test-Path -LiteralPath $StateFile) {
    & (Join-Path $ExhibitDir 'Stop-Exhibit.ps1') -Silent
}

$resolvedServerScript = [IO.Path]::GetFullPath($ServerScript)
if ($resolvedServerScript -notmatch '^([A-Za-z]):\\(.*)$') {
    throw 'The exhibit server must be stored on a Windows drive visible to WSL.'
}
$linuxScript = '/mnt/{0}/{1}' -f $Matches[1].ToLowerInvariant(), ($Matches[2] -replace '\\', '/')

$linuxScriptEscaped = $linuxScript.Replace("'", "'\''")
$bashCommand = "bash '$linuxScriptEscaped' --port $Port --public-url '$PublicUrl'"

$publicUri = [Uri]$PublicUrl
$listenAddress = $publicUri.Host
$listenPort = if ($publicUri.IsDefaultPort) { $Port } else { $publicUri.Port }
$wslAddress = ((@(& wsl.exe hostname -I 2>$null)) -join ' ').Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries) |
    Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' } |
    Select-Object -First 1
if (-not $wslAddress) {
    throw 'Could not determine the WSL IPv4 address.'
}

$relay = Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -PassThru -ArgumentList @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', ('"' + $RelayScript + '"'),
    '-ListenAddress', $listenAddress,
    '-ListenPort', $listenPort,
    '-TargetAddress', $wslAddress,
    '-TargetPort', $Port
)
@{ RelayPid = $relay.Id } | ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding ASCII

Write-Host ''
Write-Host 'VEIL exhibition server' -ForegroundColor Cyan
Write-Host "Server script: $ServerScript"
Write-Host "Public URL:    $PublicUrl"
Write-Host ''
Write-Host 'Starting run_server.sh. Keep this window open during the demonstration.' -ForegroundColor DarkCyan
Write-Host 'Press Ctrl+C in this window to stop the server.' -ForegroundColor DarkCyan
Write-Host ''

try {
    # Run WSL directly in this window. This avoids the detached WSL launch issue.
    & wsl.exe bash -lc $bashCommand
    if ($LASTEXITCODE -ne 0) {
        throw "The exhibit server exited with code $LASTEXITCODE."
    }
}
finally {
    if ($relay -and -not $relay.HasExited) {
        Stop-Process -Id $relay.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
}
