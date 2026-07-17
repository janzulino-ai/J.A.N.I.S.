# Build JANIS Tester ISO on Windows via WSL2 (local — not GitHub CI).
#
#   cd "C:\APP IA\JANIS\TESTER"
#   powershell -ExecutionPolicy Bypass -File .\build-iso-wsl.ps1
#
# Output: C:\APP IA\JANIS\TESTER\out\janis-tester.iso

$ErrorActionPreference = "Stop"
$RepoWin = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Distro = if ($env:JANIS_WSL_DISTRO) { $env:JANIS_WSL_DISTRO } else { "Ubuntu" }

Write-Host "=== JANIS ISO build (locale WSL) ==="
Write-Host "Repo: $RepoWin"
Write-Host "WSL:  $Distro"
Write-Host "Nota: debootstrap puo richiedere 15-40+ minuti e diversi GB di disco."
Write-Host ""

# Script bash temporaneo (evita quoting rotto PowerShell <-> WSL)
$tmpSh = Join-Path $env:TEMP "janis-build-iso.sh"
@(
    '#!/usr/bin/env bash'
    'set -euo pipefail'
    "REPO=`$(wslpath -a '$RepoWin')"
    'echo "WSL path: $REPO"'
    'cd "$REPO"'
    'sudo apt-get update -qq'
    'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \'
    '  debootstrap xorriso squashfs-tools grub-pc-bin grub-efi-amd64-bin \'
    '  mtools dosfstools'
    'cd "$REPO/TESTER"'
    'sudo BUILD_FORCE=1 bash build-base.sh'
    'sudo bash verify-rootfs.sh'
    'sudo bash build-iso.sh'
    'ls -lh out/janis-tester.iso'
    'echo "OK ISO: $REPO/TESTER/out/janis-tester.iso"'
) | Set-Content -Path $tmpSh -Encoding utf8NoBOM

$tmpShWsl = (wsl -d $Distro -e wslpath -a $tmpSh).Trim()
if (-not $tmpShWsl) {
    Write-Error "wslpath fallito per $tmpSh"
}

Write-Host "Eseguo: $tmpShWsl"
wsl -d $Distro -e bash "$tmpShWsl"
$code = $LASTEXITCODE

$iso = Join-Path $RepoWin "TESTER\out\janis-tester.iso"
if ($code -ne 0) {
    Write-Host ""
    Write-Warning "Build exit code: $code"
    if (-not (Test-Path $iso)) {
        Write-Error "Build fallita. Verifica WSL Ubuntu, sudo, e spazio disco."
    }
}

if (Test-Path $iso) {
    $item = Get-Item $iso
    Write-Host ""
    Write-Host "ISO pronta:"
    Write-Host ("  " + $item.FullName)
    Write-Host ("  " + [math]::Round($item.Length / 1MB, 1) + " MB")
} else {
    Write-Warning "ISO non trovata. Controlla in WSL:"
    Write-Warning "  ls -la \"/mnt/c/APP IA/JANIS/TESTER/out/\""
}
