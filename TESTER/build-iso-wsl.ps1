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

$env:JANIS_REPO_WIN = $RepoWin

$cmd = @'
set -euo pipefail
REPO="$(wslpath -a "$JANIS_REPO_WIN")"
echo "WSL path: $REPO"
cd "$REPO"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  debootstrap xorriso squashfs-tools grub-pc-bin grub-efi-amd64-bin \
  mtools dosfstools
cd "$REPO/TESTER"
sudo BUILD_FORCE=1 bash build-base.sh
sudo bash verify-rootfs.sh
sudo bash build-iso.sh
ls -lh out/janis-tester.iso
echo "OK ISO: $REPO/TESTER/out/janis-tester.iso"
'@

wsl -d $Distro -e bash -lc "export JANIS_REPO_WIN='$RepoWin'; $cmd"
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Error "Build fallita (exit $code). Verifica: wsl -d $Distro, sudo, spazio disco."
}

$iso = Join-Path $RepoWin "TESTER\out\janis-tester.iso"
if (Test-Path $iso) {
    $item = Get-Item $iso
    Write-Host ""
    Write-Host "ISO pronta:"
    Write-Host "  $($item.FullName)"
    Write-Host "  $([math]::Round($item.Length/1MB, 1)) MB"
} else {
    Write-Warning "ISO non trovata su path Windows. Controlla in WSL: ls `"$(wsl -d $Distro wslpath -a $RepoWin`)/TESTER/out/`""
}
