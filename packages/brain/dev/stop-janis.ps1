# Ferma TUTTO JANIS (backend, shell, launcher) e libera porta 8001
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:PYTHONPATH = $Root

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
if ($PyExe) {
    & $PyExe -c "from desktop.process_util import stop_all; import logging; stop_all(8001, logging.getLogger('stop'))"
}

# Fallback: taskkill processi JANIS per command line
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
    Where-Object {
        $_.CommandLine -match 'backend\.main|desktop\.launcher|desktop\.shell' -and
        $_.CommandLine -match 'JANIS|backend\.main'
    } |
    ForEach-Object {
        Write-Host "Termino PID $($_.ProcessId)..."
        taskkill /PID $_.ProcessId /F /T 2>$null | Out-Null
    }

Start-Sleep -Seconds 1
$listen = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
if ($listen) {
    $listen | ForEach-Object {
        $procId = $_.OwningProcess
        if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
            Write-Host "Termino listener PID $procId..."
            taskkill /PID $procId /F /T 2>$null | Out-Null
        }
    }
    Start-Sleep -Seconds 1
}

$still = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue |
    Where-Object { Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue }
if ($still) {
    Write-Host "ATTENZIONE: porta 8001 ancora occupata" -ForegroundColor Yellow
    exit 1
}

Remove-Item "$Root\data\janis.pids" -Force -ErrorAction SilentlyContinue
Write-Host "JANIS fermato. Porta 8001 libera." -ForegroundColor Green
exit 0
