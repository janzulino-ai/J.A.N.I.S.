# Build JANIS Tester ISO on Windows via WSL2 (local).
# debootstrap gira su filesystem Linux (~/janis-iso-build), non su C:\ (NTFS).
# L'ISO finale viene copiata in C:\APP IA\JANIS\janis-tester.iso
#
# Esegui SOLO queste due righe in PowerShell (non incollare errori):
#
#   cd "C:\APP IA\JANIS"
#   powershell -ExecutionPolicy Bypass -File .\TESTER\build-iso-wsl.ps1
#
# Prima volta: in WSL digita la password sudo quando richiesto.
# Oppure apri WSL e fai: sudo -v   poi rilancia questo script.

$ErrorActionPreference = "Stop"
$RepoWin = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Distro = "Ubuntu"
if ($env:JANIS_WSL_DISTRO) { $Distro = $env:JANIS_WSL_DISTRO }

Write-Host "=== JANIS ISO build (locale WSL) ==="
Write-Host "Repo: $RepoWin"
Write-Host "WSL:  $Distro"
Write-Host "Build FS: ~/janis-iso-build (Linux ext4 — non C:\)"
Write-Host ""

$repoWsl = (& wsl.exe -d $Distro -e wslpath -a $RepoWin 2>$null)
if (-not $repoWsl) {
    throw "wslpath fallito. Controlla: wsl -d $Distro -e echo ok"
}
$repoWsl = $repoWsl.Trim()

# Chiama lo script bash nel repo (gestisce BUILD su ~/janis-iso-build)
$shPath = "$repoWsl/TESTER/build-iso-wsl.sh"
Write-Host "Eseguo in WSL: bash `"$shPath`""
& wsl.exe -d $Distro -e bash $shPath
$code = $LASTEXITCODE

$isoRoot = Join-Path $RepoWin "janis-tester.iso"
$isoOut = Join-Path $RepoWin "TESTER\out\janis-tester.iso"

if (Test-Path $isoRoot) {
    $item = Get-Item $isoRoot
    Write-Host ""
    Write-Host "ISO pronta in cartella JANIS:"
    Write-Host ("  " + $item.FullName)
    Write-Host ("  " + [math]::Round($item.Length / 1MB, 1) + " MB")
    exit 0
}
if (Test-Path $isoOut) {
    Copy-Item $isoOut $isoRoot -Force
    Write-Host "ISO copiata in: $isoRoot"
    exit 0
}

Write-Host "Build exit: $code"
throw "ISO non trovata. Apri WSL e rilancia: bash `"$shPath`""
