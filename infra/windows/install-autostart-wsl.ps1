# Task Scheduler — avvio JANIS WSL (Ollama + brain + tray) al login Windows
$ErrorActionPreference = "Stop"
$Root = if ($env:JANIS_ROOT) { $env:JANIS_ROOT } else { (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }
$StartScript = Join-Path $Root "infra\wsl\start-janis-wsl.ps1"
$TaskName = "JANIS_WSL_AutoStart"

if (-not (Test-Path $StartScript)) {
    Write-Error "Script mancante: $StartScript"
    exit 1
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$StartScript`"" `
    -WorkingDirectory $Root

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal -Force | Out-Null

# Tray startup folder (backup se task non parte)
$WindowsDir = Join-Path $Root "infra\windows"
& (Join-Path $WindowsDir "install-tray-autostart.ps1") | Out-Null

Write-Host "Autostart WSL registrato: $TaskName"
Write-Host "Al login: Ollama + brain WSL + tray"
Write-Host "Rimuovi: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
