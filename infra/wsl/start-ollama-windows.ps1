# Avvia Ollama Windows accessibile da WSL (bind 0.0.0.0)
$ErrorActionPreference = "Stop"
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")
Get-Process ollama* -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
Start-Process -FilePath "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve"
Start-Sleep -Seconds 4
Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10 | Out-Null
Write-Host "Ollama OK — WSL usa http://192.168.128.1:11434 (gateway)"
