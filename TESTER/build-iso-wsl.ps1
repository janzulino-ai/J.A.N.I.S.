# Build JANIS Tester ISO on Windows via WSL2 (local).
# Esegui SOLO queste due righe in PowerShell (non incollare errori):
#
#   cd "C:\APP IA\JANIS"
#   powershell -ExecutionPolicy Bypass -File .\TESTER\build-iso-wsl.ps1
#
# Output:
#   C:\APP IA\JANIS\janis-tester.iso
#   C:\APP IA\JANIS\TESTER\out\janis-tester.iso

$ErrorActionPreference = "Stop"
$RepoWin = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Distro = "Ubuntu"
if ($env:JANIS_WSL_DISTRO) { $Distro = $env:JANIS_WSL_DISTRO }

Write-Host "=== JANIS ISO build (locale WSL) ==="
Write-Host "Repo: $RepoWin"
Write-Host "WSL:  $Distro"
Write-Host ""

$tmpSh = Join-Path $env:TEMP "janis-build-iso.sh"
$lines = @(
    "#!/usr/bin/env bash"
    "set -euo pipefail"
    "REPO=`$(wslpath -a '$RepoWin')"
    "echo WSL path: `$REPO"
    "cd `"`$REPO`""
    "sudo apt-get update -qq"
    "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq debootstrap xorriso squashfs-tools grub-pc-bin grub-efi-amd64-bin mtools dosfstools"
    "cd `"`$REPO/TESTER`""
    "sudo BUILD_FORCE=1 bash build-base.sh"
    "sudo bash verify-rootfs.sh"
    "sudo bash build-iso.sh"
    "ls -lh out/janis-tester.iso `"../janis-tester.iso`""
    "echo OK ISO ready"
)

# Scrivi senza Set-Content (compatibilita Windows PowerShell 5.1)
[System.IO.File]::WriteAllLines($tmpSh, $lines)

$tmpShWsl = (& wsl.exe -d $Distro -e wslpath -a $tmpSh 2>$null)
if (-not $tmpShWsl) {
    throw "wslpath fallito. Controlla: wsl -d $Distro -e echo ok"
}
$tmpShWsl = $tmpShWsl.Trim()

Write-Host "Eseguo in WSL: $tmpShWsl"
& wsl.exe -d $Distro -e bash $tmpShWsl
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
throw "ISO non trovata. Apri WSL e guarda errori sudo/debootstrap."
