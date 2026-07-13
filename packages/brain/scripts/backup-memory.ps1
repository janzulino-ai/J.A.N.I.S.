# Backup memoria JANIS
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Src = Join-Path $Root "data\memory"
$Dest = Join-Path $Root "data\backups"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Out = Join-Path $Dest "memory-$Stamp"

New-Item -ItemType Directory -Force -Path $Out | Out-Null
Copy-Item -Path (Join-Path $Src "*") -Destination $Out -Recurse -Force
Write-Host "Backup salvato in: $Out"
