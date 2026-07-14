param(
    [Parameter(Mandatory = $true)][string]$Prompt,
    [string]$Cwd = ""
)

$ErrorActionPreference = "Stop"

$Root = if ($env:JANIS_ROOT) { $env:JANIS_ROOT } else { "C:\APP IA\JANIS" }
$Brain = Join-Path $Root "packages\brain"
Set-Location $Brain

$envFile = Join-Path $Brain ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $k = $matches[1].Trim()
            $v = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($k, $v, "Process")
        }
    }
}

$env:PYTHONPATH = $Brain

$Py = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $Py = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null)
}
if (-not $Py -or -not (Test-Path $Py)) {
    $Py = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $Py) {
    Write-Output '{"type":"error","message":"Python 3.12 non trovato su Windows"}'
    exit 1
}

$cliArgs = @("-m", "dev.cursor_agent_cli", "--prompt", $Prompt)
if ($Cwd) { $cliArgs += @("--cwd", $Cwd) }

& $Py @cliArgs
