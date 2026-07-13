# JANIS App — avvio silenzioso (senza terminale visibile)
$ErrorActionPreference = "Stop"
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
    [System.Windows.Forms.MessageBox]::Show(
        "Python 3.12 non trovato.", "JANIS", 0, 48) | Out-Null
    exit 1
}

$PyW = $PyExe -replace "\\python.exe$", "\pythonw.exe"
if (-not (Test-Path $PyW)) { $PyW = $PyExe }

$env:PYTHONPATH = $Root

& "$Root\dev\stop-janis.ps1" | Out-Null

# pythonw = nessuna console; errori -> MessageBox + launcher.log
$p = Start-Process -FilePath $PyW `
    -ArgumentList @("-m", "desktop.launcher") `
    -WorkingDirectory $Root `
    -PassThru `
    -WindowStyle Hidden

Start-Sleep -Seconds 6

if (-not $p.HasExited) {
    exit 0
}

# Processo terminato subito = errore
$log = Get-Content "$Root\data\launcher.log" -Tail 8 -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.MessageBox]::Show(
    "JANIS non si e' avviata.`n`n$log`n`nUsa dev\run-debug.ps1 per dettagli.",
    "JANIS", 0, 48) | Out-Null
exit 1
