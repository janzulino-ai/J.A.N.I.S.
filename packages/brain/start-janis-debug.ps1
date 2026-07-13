# Avvio JANIS con finestra di stato (per debug)
$Host.UI.RawUI.WindowTitle = "JANIS"
& "$PSScriptRoot\start-janis-window.ps1"
$code = $LASTEXITCODE
Write-Host ""
if ($code -eq 0) {
    Write-Host "JANIS finestra avviata." -ForegroundColor Green
    Write-Host "  Browser: http://127.0.0.1:8001/?mode=browser"
    Write-Host "  Log:     $PSScriptRoot\data\desktop.log"
} else {
    Write-Host "Avvio fallito. Leggi $PSScriptRoot\data\start.log" -ForegroundColor Red
}
Write-Host ""
Write-Host "Puoi chiudere questa finestra — JANIS resta attiva."
