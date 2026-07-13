# Test layer desktop JANIS (WorkerW) — richiede backend attivo
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:PYTHONPATH = $Root

Write-Host "Installo pywin32 se mancante..."
python -m pip install pywin32 -q

Write-Host "Avvio layer desktop (Ctrl+C per uscire)..."
python -m desktop.wallpaper_host
