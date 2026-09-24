param(
    [Parameter(Mandatory = $true)]
    [System.Net.IPAddress]$HotspotAddress,
    [ValidateRange(1024, 65535)]
    [int]$Port = 8766
)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script in an administrator PowerShell after enabling Mobile Hotspot.'
}
if ($HotspotAddress.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
    throw 'An IPv4 hotspot address is required.'
}
$address = $HotspotAddress.ToString()
$adapter = Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -eq $address
if (-not $adapter) { throw 'The requested hotspot address is not assigned to this PC.' }
$wslAddresses = ((wsl hostname -I) -join ' ').Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
$target = $wslAddresses | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' } | Select-Object -First 1
if (-not $target) { throw 'Could not determine the WSL IPv4 address.' }
netsh interface portproxy add v4tov4 listenaddress=$address listenport=$Port connectaddress=$target connectport=$Port
if ($LASTEXITCODE -ne 0) { throw 'Port forwarding failed.' }
$ruleName = "BDAC Exhibition $address $Port"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalAddress $address -LocalPort $Port -RemoteAddress LocalSubnet | Out-Null
}
Write-Host "Hotspot route ready: http://${address}:$Port"
Write-Host "Restart the exhibition server with --public-url http://${address}:$Port"
Write-Host "After the event, remove the named firewall rule and this portproxy entry."
