# JANIS — setup one-shot WireGuard bridge (Mode A · Windows/WSL hub)
# Apre firewall Windows, tenta install WG in WSL, stampa checklist router/DDNS
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$ForwardScript = Join-Path $ScriptDir "setup-wireguard-forward.ps1"
$WslSetup = Join-Path $RepoRoot "infra\wsl\setup-wireguard.sh"

Write-Host "=== JANIS WireGuard bridge (Mode A) ==="
Write-Host "Hub: windows-pc · LAN 192.168.1.73 · brain :8001 in WSL"
Write-Host ""

# 1) Firewall Windows (richiede Admin)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if ($isAdmin) {
    & $ForwardScript
} else {
    Write-Host "WARN: riesegui questo script come Amministratore per la regola firewall."
    Write-Host "  Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File `"$ForwardScript`"'"
}

Write-Host ""
Write-Host "=== WireGuard in WSL ==="
$wslPath = ($WslSetup -replace '\\', '/')
$wslPath = $wslPath -replace '^([A-Za-z]):', { '/mnt/' + $_.Groups[1].Value.ToLower() }

Write-Host "Tentativo: sudo bash $wslPath"
Write-Host "(richiede password sudo in WSL se non configurato NOPASSWD)"
Write-Host ""

$wgTry = wsl -e bash -lc "sudo -n bash '$wslPath' 2>&1" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host $wgTry
    Write-Host "WireGuard WSL: OK"
} else {
    Write-Host $wgTry
    Write-Host ""
    Write-Host "Setup automatico non riuscito (sudo/kernel). Passi manuali in WSL:"
    Write-Host "  sudo apt install -y wireguard wireguard-tools"
    Write-Host "  sudo bash infra/wsl/setup-wireguard.sh"
    Write-Host "  sudo wg show"
}

Write-Host ""
Write-Host "=== Checklist domani ==="
Write-Host "1. Router: UDP 51820 -> 192.168.1.73"
Write-Host "2. DDNS o IP pubblico in WG_ENDPOINT (peer client.conf)"
Write-Host "3. iPhone: WireGuard ON -> Safari http://192.168.1.73:8001/api/status"
Write-Host "4. Brain API: GET http://192.168.1.73:8001/api/vpn/status"
Write-Host "5. Peer configs: infra/vpn/peers/<device>/client.conf (gitignored)"
Write-Host ""
Write-Host "Docs: infra/vpn/README.md · docs/MOBILE-OPS.md"
