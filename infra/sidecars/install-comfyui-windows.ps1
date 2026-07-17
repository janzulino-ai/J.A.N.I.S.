# Install / update ComfyUI su Windows (RTX) per image_gen Mode A
param(
    [string]$InstallDir = "$env:USERPROFILE\ComfyUI",
    [string]$Listen = "0.0.0.0",
    [int]$Port = 8188,
    [switch]$Start
)

$ErrorActionPreference = "Stop"
Write-Host "=== ComfyUI -> $InstallDir :$Port ==="

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "git richiesto nel PATH"
}

if (-not (Test-Path $InstallDir)) {
    git clone https://github.com/comfyanonymous/ComfyUI.git $InstallDir
} else {
    Write-Host "Repo esistente - pull"
    Push-Location $InstallDir
    git pull --ff-only
    Pop-Location
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "python richiesto"
}

Push-Location $InstallDir
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -U pip
& .\.venv\Scripts\pip.exe install -r requirements.txt
Pop-Location

$launcher = Join-Path $InstallDir "start-janis-comfy.ps1"
$lines = @(
    "# Avvio ComfyUI per JANIS",
    "Set-Location '$InstallDir'",
    "& .\.venv\Scripts\python.exe main.py --listen $Listen --port $Port"
)
$lines | Set-Content -Encoding UTF8 $launcher

Write-Host "OK launcher: $launcher"
Write-Host "Da WSL: bash infra/wsl/configure-sidecar-urls.sh"
Write-Host "COMFYUI_URL=http://IP-WINDOWS:$Port"

if ($Start) {
    Write-Host "Avvio ComfyUI..."
    Start-Process powershell -ArgumentList "-NoExit", "-File", $launcher
}
