# Build JANIS.exe con PyInstaller
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

pip install pyinstaller
pyinstaller build/janis.spec --noconfirm

Write-Host "Build completata: dist\JANIS.exe"
