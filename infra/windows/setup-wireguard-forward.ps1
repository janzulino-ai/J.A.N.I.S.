# JANIS — firewall + port exposure WireGuard UDP 51820 (WSL2 hub)
# Esegui come Amministratore su Windows host (Mode A · 192.168.1.73)
$ErrorActionPreference = "Stop"

$Port = if ($env:WG_WG_PORT) { [int]$env:WG_WG_PORT } else { 51820 }
$RuleName = "JANIS WireGuard UDP $Port"

function Get-WslIp {
    $raw = (wsl -e bash -lc "hostname -I 2>/dev/null" 2>$null)
    if (-not $raw) { return $null }
    return ($raw.Trim() -split '\s+')[0]
}

Write-Host "JANIS WireGuard forward — UDP $Port"
Write-Host ""

# Firewall inbound (Windows host)
$existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Firewall rule già presente: $RuleName"
} else {
    New-NetFirewallRule `
        -DisplayName $RuleName `
        -Direction Inbound `
        -Protocol UDP `
        -LocalPort $Port `
        -Action Allow `
        -Profile Any | Out-Null
    Write-Host "Firewall: regola inbound UDP $Port creata."
}

$wslIp = Get-WslIp
if ($wslIp) {
    Write-Host "WSL IP attuale: $wslIp"
} else {
    Write-Host "WARN: impossibile leggere IP WSL — avvia WSL e riprova."
}

Write-Host ""
Write-Host "=== Networking WSL2 (consigliato) ==="
Write-Host "Per UDP stabile senza portproxy TCP-only, abilita mirrored mode in"
Write-Host "  %USERPROFILE%\.wslconfig"
Write-Host ""
Write-Host "[wsl2]"
Write-Host "networkingMode=mirrored"
Write-Host "firewall=true"
Write-Host ""
Write-Host "Poi: wsl --shutdown && riavvia WireGuard in WSL."
Write-Host ""
Write-Host "=== Router (obbligatorio per accesso esterno) ==="
Write-Host "Forward UDP $Port WAN -> 192.168.1.73 (questo PC Windows)."
Write-Host "Endpoint client: <IP_pubblico_o_DDNS>:$Port"
Write-Host ""
Write-Host "Test LAN: wg show (in WSL) · Test brain: curl http://192.168.1.73:8001/api/vpn/status"
