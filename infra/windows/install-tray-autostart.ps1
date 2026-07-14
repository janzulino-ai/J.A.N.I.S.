# Installa JANIS tray + avvio con Windows
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "janis-services.ps1")

Set-JanisAutostart $true

# Avvia subito la tray (senza console)
$vbs = Join-Path (Get-JanisRoot) "infra\windows\start-janis-tray.vbs"
Start-Process "wscript.exe" -ArgumentList "`"$vbs`"" -WindowStyle Hidden

Write-Host "JANIS tray installata."
Write-Host "- Icona vicino all'orologio (J verde = online)"
Write-Host "- Avvio con Windows: ON"
Write-Host "- HUD: http://127.0.0.1:8001/server?v=hudcli07"
Write-Host ""
Write-Host "Per disinstallare autostart: menu tray -> deseleziona «Avvio con Windows»"
