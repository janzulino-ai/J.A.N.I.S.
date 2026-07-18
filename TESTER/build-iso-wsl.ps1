# Build JANIS Tester ISO on Windows via WSL2 (local).
# Debootstrap runs on Linux FS (~/janis-iso-build), not on C:\ (NTFS).
# Final ISO is copied to C:\APP IA\JANIS\janis-tester.iso
#
# Run ONLY these two lines in PowerShell (do not paste error output):
#
#   cd "C:\APP IA\JANIS"
#   powershell -ExecutionPolicy Bypass -File .\TESTER\build-iso-wsl.ps1
#
# First run: enter Ubuntu WSL sudo password when prompted.
# Or open WSL and run: sudo -v   then re-run this script.

$ErrorActionPreference = "Stop"
$RepoWin = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Distro = "Ubuntu"
if ($env:JANIS_WSL_DISTRO) { $Distro = $env:JANIS_WSL_DISTRO }

Write-Host "=== JANIS ISO build (local WSL) ==="
Write-Host ("Repo: " + $RepoWin)
Write-Host ("WSL:  " + $Distro)
Write-Host "Build FS: ~/janis-iso-build (Linux ext4, not C: drive)"
Write-Host ""

$repoWsl = (& wsl.exe -d $Distro -e wslpath -a $RepoWin 2>$null)
if (-not $repoWsl) {
    throw "wslpath failed. Check: wsl -d $Distro -e echo ok"
}
$repoWsl = $repoWsl.Trim()

$shPath = $repoWsl + "/TESTER/build-iso-wsl.sh"
Write-Host ("Run in WSL: bash " + $shPath)
& wsl.exe -d $Distro -e bash $shPath
$code = $LASTEXITCODE

$isoRoot = Join-Path $RepoWin "janis-tester.iso"
$isoOut = Join-Path $RepoWin "TESTER\out\janis-tester.iso"

if (Test-Path $isoRoot) {
    $item = Get-Item $isoRoot
    Write-Host ""
    Write-Host "ISO ready in JANIS folder:"
    Write-Host ("  " + $item.FullName)
    Write-Host ("  " + [math]::Round($item.Length / 1MB, 1) + " MB")
    exit 0
}
if (Test-Path $isoOut) {
    Copy-Item $isoOut $isoRoot -Force
    Write-Host ("ISO copied to: " + $isoRoot)
    exit 0
}

Write-Host ("Build exit: " + $code)
throw ("ISO not found. Open WSL and run: bash " + $shPath)
