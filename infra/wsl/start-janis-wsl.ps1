# Avvio unificato JANIS — Ollama Windows + brain WSL (+ tray opzionale)
param(
    [switch]$Tray,
    [switch]$NoTray
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WindowsDir = Join-Path (Split-Path -Parent $ScriptDir) "windows"
. (Join-Path $WindowsDir "janis-services.ps1")

$status = Start-JanisAll
Write-Host "JANIS: $($status.Label)"
Write-Host "HUD: $($status.HudUrl)"

if ($Tray -or (-not $NoTray)) {
    $vbs = Join-Path $WindowsDir "start-janis-tray.vbs"
    if (Test-Path $vbs) {
        $running = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*janis-tray.ps1*" }
        if (-not $running) {
            Start-Process "wscript.exe" -ArgumentList "`"$vbs`"" -WindowStyle Hidden
            Write-Host "Tray avviata."
        }
    }
}

if (-not $status.Brain) { exit 1 }
exit 0
