# Registra JANIS all'accesso Windows (avvio automatico)
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$StartScript = Join-Path $Root "start-janis.ps1"
$TaskName = "JANIS_AutoStart"

if (-not (Test-Path $StartScript)) {
    Write-Error "start-janis.ps1 non trovato in $Root"
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

Write-Host "Autostart registrato: $TaskName"
Write-Host "JANIS partira al login automaticamente."
Write-Host ""
Write-Host "Per rimuovere: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
Write-Host "Avvio manuale ora:  & `"$StartScript`""
