# Build JANIS Tester ISO on Windows via WSL2 (local — not GitHub).
# Uso (PowerShell come admin opzionale; serve WSL Ubuntu con sudo):
#   cd "C:\APP IA\JANIS\TESTER"
#   powershell -ExecutionPolicy Bypass -File .\build-iso-wsl.ps1
#
# Output: TESTER\out\janis-tester.iso

$ErrorActionPreference = "Stop"
$RepoWin = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Distro = if ($env:JANIS_WSL_DISTRO) { $env:JANIS_WSL_DISTRO } else { "Ubuntu" }

Write-Host "Repo: $RepoWin"
Write-Host "WSL:  $Distro"
Write-Host "Build ISO locale (debootstrap puo richiedere 15-40+ min)..."

# Path WSL del repo (spazio in "APP IA")
$bash = @'
set -euo pipefail
REPO="$(wslpath -a '"$RepoWin"')"
cd "$REPO"
echo "WSL path: $REPO"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  debootstrap xorriso squashfs-tools grub-pc-bin grub-efi-amd64-bin \
  mtools dosfstools
cd "$REPO/TESTER"
sudo BUILD_FORCE=1 bash build-base.sh
sudo bash verify-rootfs.sh
sudo bash build-iso.sh
ls -lh out/janis-tester.iso
echo "OK: ISO in $REPO/TESTER/out/janis-tester.iso"
echo "Su Windows: $REPO/TESTER/out -> $RepoWin\TESTER\out"
'@

# Inject Windows path into script safely
$bash = $bash.Replace('"$RepoWin"', "`"$RepoWin`"")

wsl -d $Distro -- bash -lc $bash
if ($LASTEXITCODE -ne 0) {
    Write-Error "Build fallita (exit $LASTEXITCODE). Controlla output WSL / sudo."
}

$iso = Join-Path $RepoWin "TESTER\out\janis-tester.iso"
if (Test-Path $iso) {
    Write-Host "ISO pronta: $iso"
    Get-Item $iso | Format-List FullName, Length, LastWriteTime
} else {
    Write-Warning "File non trovato su Windows path. Controlla WSL: ~/ o /mnt/c/.../TESTER/out/"
}
