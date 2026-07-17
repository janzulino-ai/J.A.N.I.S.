# Avvia SearXNG via Docker Desktop + reminder ComfyUI
$ErrorActionPreference = "Continue"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Compose = Join-Path $PSScriptRoot "docker-compose.searxng.yml"

Write-Host "=== SearXNG ==="
if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker compose -f $Compose up -d
    Start-Sleep -Seconds 2
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:8080/" -UseBasicParsing -TimeoutSec 5 | Out-Null
        Write-Host "SearXNG OK :8080"
    } catch {
        Write-Host "WARN: SearXNG non risponde ancora"
    }
} else {
    Write-Host "docker non nel PATH — installa Docker Desktop"
}

Write-Host ""
Write-Host "=== ComfyUI ==="
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:8188/system_stats" -UseBasicParsing -TimeoutSec 2 | Out-Null
    Write-Host "ComfyUI già up :8188"
} catch {
    Write-Host "ComfyUI non up. Avvia: .\infra\sidecars\install-comfyui-windows.ps1 -Start"
}

Write-Host ""
Write-Host "Da WSL: bash infra/wsl/configure-sidecar-urls.sh"
Write-Host "Repo: $Root"
