# Avvio DEV — finestra + browser, senza overlay fullscreen
$Host.UI.RawUI.WindowTitle = "JANIS Dev"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Get-Py312 {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $exe = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($exe -and (Test-Path $exe)) { return $exe.Trim() }
    }
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    return $null
}

$PyExe = Get-Py312
if (-not $PyExe) {
    Write-Host "ERRORE: Python 3.12 non trovato." -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = $Root

# Libera porta 8001 se occupata
$pids = netstat -ano | Select-String ":8001.*LISTENING" | ForEach-Object {
    ($_ -split '\s+')[-1]
} | Select-Object -Unique
foreach ($procId in $pids) {
    if ($procId -match '^\d+$') {
        Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 1

Write-Host "Avvio backend dev (hot-reload)..." -ForegroundColor Cyan
$backend = Start-Process -FilePath $PyExe `
    -ArgumentList @("dev\start_backend.py") `
    -WorkingDirectory $Root `
    -PassThru

Write-Host ""
Write-Host "JANIS dev attivo." -ForegroundColor Green
Write-Host "  Browser: http://127.0.0.1:8001/?mode=browser"
Write-Host "  Finestra: .\start-janis-window.ps1 (in un altro terminale)"
Write-Host "  Stop:     .\dev\stop-backend.ps1"
Write-Host ""
Write-Host "Lascia questo terminale aperto. Ctrl+C non ferma il backend — usa stop-backend.ps1"
Write-Host ""

# Non chiudere subito: attendi che l'utente chiuda manualmente
while (-not $backend.HasExited) {
    Start-Sleep -Seconds 2
}
