# JANIS in Cursor - solo backend hot-reload, UI nel browser integrato di Cursor
$Host.UI.RawUI.WindowTitle = "JANIS Cursor Dev"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:PYTHONPATH = $Root

& "$Root\dev\stop-janis.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ATTENZIONE: stop-janis non ha liberato la porta 8001." -ForegroundColor Yellow
}

Write-Host ""
Write-Host '  JANIS - modalita Cursor' -ForegroundColor Cyan
Write-Host '  [1] Backend hot-reload (questo terminale)' -ForegroundColor Gray
Write-Host '  [2] In Cursor: Ctrl+Shift+P, Simple Browser: Show' -ForegroundColor Yellow
Write-Host '     URL: http://127.0.0.1:8001/?mode=browser' -ForegroundColor Yellow
Write-Host '  [3] Se la memoria non funziona: Shift+F5 (stop debug) poi F5' -ForegroundColor Yellow
Write-Host '     Verifica: GET /api/status deve avere brain_version: 3' -ForegroundColor Gray
Write-Host '     Fallback porta bloccata: http://127.0.0.1:8010/?mode=browser' -ForegroundColor Gray
Write-Host '  [4] Affianca browser a destra per vedere le modifiche al volo' -ForegroundColor Gray
Write-Host ""

python dev/start_backend.py
