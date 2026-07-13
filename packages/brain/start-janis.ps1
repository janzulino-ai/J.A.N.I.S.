# Avvio silenzioso JANIS - backend + widget desktop + tray
# Nessuna console visibile (usa pythonw per la GUI).

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$LogDir = Join-Path $Root "data"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "start.log"

function Log([string]$msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Get-Py312 {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $exe = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($exe -and (Test-Path $exe)) { return $exe.Trim() }
    }
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    return $null
}

# Evita doppio avvio (controlla widget gia in esecuzione)
try {
    $null = Invoke-RestMethod "http://127.0.0.1:8001/api/status" -TimeoutSec 1
    $running = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -like "*desktop.shell*" }
    if ($running) {
        Log "JANIS gia in esecuzione"
        exit 0
    }
} catch {}

$PyExe = Get-Py312
if (-not $PyExe) {
    Log "ERRORE: Python 3.12 non trovato. Installa: winget install Python.Python.3.12"
    [System.Windows.Forms.MessageBox]::Show(
        "Python 3.12 non trovato.`nInstalla Python 3.12 e riprova.",
        "JANIS", 0, 48) | Out-Null
    exit 1
}

$PyW = $PyExe -replace "\\python.exe$", "\pythonw.exe"
if (-not (Test-Path $PyW)) { $PyW = $PyExe }

Log "Python: $PyExe"
Log "Installazione dipendenze..."
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $PyExe -m pip install -r (Join-Path $Root "requirements.txt") -q *> $null
$ErrorActionPreference = $prevEap

$env:PYTHONPATH = $Root

# Ollama
$ollamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
if (-not (Get-Process -Name ollama -ErrorAction SilentlyContinue) -and (Test-Path $ollamaExe)) {
    Log "Avvio Ollama"
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 2
}

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
}

# Backend
$backendOk = $false
try {
    $null = Invoke-RestMethod "http://127.0.0.1:8001/api/status" -TimeoutSec 2
    $backendOk = $true
    Log "Backend gia attivo"
} catch {}

    if (-not $backendOk) {
    $hostBind = "0.0.0.0"
    try {
        $hostBind = (& $PyExe -c "from backend.config import settings; print(settings.HOST)" 2>$null).Trim()
        if (-not $hostBind) { $hostBind = "0.0.0.0" }
    } catch {}
    Log "Avvio backend :8001 (host=$hostBind)"
    Start-Process -FilePath $PyExe `
        -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", $hostBind, "--port", "8001") `
        -WorkingDirectory $Root -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 8
    try {
        $null = Invoke-RestMethod "http://127.0.0.1:8001/api/status" -TimeoutSec 8
        $backendOk = $true
        Log "Backend online"
    } catch {
        Log "ERRORE: backend non risponde su :8001"
    }
}

if (-not $backendOk) {
    [System.Windows.Forms.MessageBox]::Show(
        "JANIS: backend non avviato.`nControlla $LogFile",
        "JANIS", 0, 48) | Out-Null
    exit 1
}

# Widget + tray (pythonw = niente console, ma GUI visibile)
Log "Avvio widget desktop (pythonw)"
$shell = Start-Process -FilePath $PyW `
    -ArgumentList @("-m", "desktop.shell") `
    -WorkingDirectory $Root -PassThru

Start-Sleep -Seconds 8
$alive = Get-Process -Id $shell.Id -ErrorAction SilentlyContinue
if ($alive) {
    Log "JANIS avviata - overlay fullscreen PID $($shell.Id) - tray: Interagisci / Pass-through"
} else {
    Log "ERRORE: widget terminato subito - controlla data\desktop.log"
    [System.Windows.Forms.MessageBox]::Show(
        "JANIS widget non partito.`nControlla $(Join-Path $Root 'data\desktop.log')",
        "JANIS", 0, 48) | Out-Null
    exit 1
}

exit 0
