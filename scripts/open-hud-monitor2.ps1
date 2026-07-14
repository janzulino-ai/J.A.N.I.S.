# JANIS HUD — secondo monitor (DISPLAY2)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
$screen = [System.Windows.Forms.Screen]::AllScreens | Where-Object { -not $_.Primary } | Select-Object -First 1
if (-not $screen) {
    Write-Error "Secondo monitor non trovato"
}
$b = $screen.Bounds
$url = "${env:JANIS_HUD_URL:-http://localhost:8001/server}"
$browsers = @(
    "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe"
)
$exe = $browsers | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $exe) { throw "Chrome/Edge non trovato" }
$args = @(
    "--new-window",
    "--app=$url",
    "--window-position=$($b.X),$($b.Y)",
    "--window-size=$($b.Width),$($b.Height)"
)
Start-Process -FilePath $exe -ArgumentList $args
Write-Host "HUD: $url su $($screen.DeviceName) $($b.Width)x$($b.Height)"
