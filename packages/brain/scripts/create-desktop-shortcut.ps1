# Crea collegamento JANIS sul Desktop
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "JANIS.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Root\start-janis.ps1`""
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "Avvia JANIS - Assistente AI locale"
$Shortcut.WindowStyle = 1
$Shortcut.IconLocation = "C:\Windows\System32\imageres.dll,109"
$Shortcut.Save()

Write-Host "Collegamento creato: $shortcutPath"
