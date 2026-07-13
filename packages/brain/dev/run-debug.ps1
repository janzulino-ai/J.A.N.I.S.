# JANIS DEBUG - avvio visibile con log nel terminale
$Host.UI.RawUI.WindowTitle = "JANIS Debug"
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
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
    Read-Host "Premi Invio"
    exit 1
}

$env:PYTHONPATH = $Root
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  JANIS DEBUG - log visibili qui sotto" -ForegroundColor Cyan
Write-Host "  Chiudi con Ctrl+C o chiudendo JANIS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

& "$Root\dev\stop-janis.ps1"
& $PyExe -m desktop.launcher --console --reload
$code = $LASTEXITCODE

Write-Host ""
if ($code -eq 0) {
    Write-Host "JANIS chiusa normalmente." -ForegroundColor Green
} else {
    Write-Host "JANIS terminata con errore ($code)." -ForegroundColor Red
    Write-Host "Log: $Root\data\launcher.log"
    Write-Host "Log: $Root\data\backend.log"
}
Write-Host ""
Read-Host "Premi Invio per chiudere"
