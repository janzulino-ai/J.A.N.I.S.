# Espone brain WSL :8001 sulla LAN Windows (fleet Mac, Pocket, VPN)
# Richiede PowerShell amministratore
#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"

$Port = 8001
$WslIp = (wsl -e hostname -I).Trim().Split(" ")[0]
if (-not $WslIp) { throw "WSL IP non trovato" }

Write-Host "WSL IP: $WslIp -> LAN :$Port"

netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0 2>$null | Out-Null
netsh interface portproxy add v4tov4 listenport=$Port listenaddress=0.0.0.0 connectport=$Port connectaddress=$WslIp

if (-not (Get-NetFirewallRule -DisplayName "JANIS Brain LAN 8001" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "JANIS Brain LAN 8001" -Direction Inbound -LocalPort $Port -Protocol TCP -Action Allow | Out-Null
}

Write-Host "Portproxy attivo:"
netsh interface portproxy show v4tov4 | Select-String $Port
$lan = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" } | Select-Object -First 1).IPAddress
Write-Host "Fleet/Pocket URL LAN: http://${lan}:$Port"
