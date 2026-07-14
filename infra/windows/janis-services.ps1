# JANIS — avvio/stato servizi (Ollama Windows + brain WSL)
$ErrorActionPreference = "Stop"

function Get-JanisRoot {
    if ($env:JANIS_ROOT -and (Test-Path $env:JANIS_ROOT)) {
        return (Resolve-Path $env:JANIS_ROOT).Path
    }
    $here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
    return (Resolve-Path (Join-Path $here "..\..")).Path
}

function Get-JanisLogDir {
    $dir = Join-Path (Get-JanisRoot) "data\tray"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    return $dir
}

function Write-JanisTrayLog([string]$Message) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Add-Content -Path (Join-Path (Get-JanisLogDir) "tray.log") -Value $line -Encoding UTF8
}

function Test-JanisOllama {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 4 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Test-JanisBrain {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/status" -TimeoutSec 4
        return [bool]($r.service -eq "JANIS")
    } catch {
        return $false
    }
}

function Get-JanisStatus {
    $ollama = Test-JanisOllama
    $brain = Test-JanisBrain
    $label = if ($ollama -and $brain) { "ONLINE" }
        elseif ($brain) { "BRAIN OK · NO OLLAMA" }
        elseif ($ollama) { "OLLAMA OK · NO BRAIN" }
        else { "OFFLINE" }
    [pscustomobject]@{
        Ollama = $ollama
        Brain  = $brain
        Label  = $label
        HudUrl = "http://127.0.0.1:8001/server?v=hudcli08"
    }
}

function Start-JanisOllama {
    $root = Get-JanisRoot
    $script = Join-Path $root "infra\wsl\start-ollama-windows.ps1"
    if (-not (Test-Path $script)) {
        throw "Script mancante: $script"
    }
    Write-JanisTrayLog "Avvio Ollama"
    & $script | Out-Null
    return (Test-JanisOllama)
}

function Start-JanisBrainWsl {
    if (Test-JanisBrain) {
        Write-JanisTrayLog "Brain gia attivo"
        return $true
    }
    Write-JanisTrayLog "Avvio brain WSL"
    $null = Start-Process -FilePath "wsl.exe" -ArgumentList @(
        "-d", "Ubuntu",
        "--", "bash", "-lc",
        "cd ~/projects/J.A.N.I.S./packages/brain && exec ~/janis-venv/bin/python run.py"
    ) -WindowStyle Hidden -PassThru
    $deadline = (Get-Date).AddSeconds(25)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Test-JanisBrain) {
            Write-JanisTrayLog "Brain online"
            return $true
        }
    }
    Write-JanisTrayLog "Brain non risponde entro timeout"
    return $false
}

function Start-JanisAll {
    $ollamaOk = if (Test-JanisOllama) { $true } else { Start-JanisOllama }
    $brainOk = Start-JanisBrainWsl
    return (Get-JanisStatus)
}

function Stop-JanisBrainWsl {
    Write-JanisTrayLog "Stop brain WSL"
    wsl.exe -d Ubuntu -- bash -lc "pkill -f 'python run.py' 2>/dev/null || true" | Out-Null
    Start-Sleep -Seconds 1
}

function Restart-JanisBrainWsl {
    Stop-JanisBrainWsl
    return (Start-JanisBrainWsl)
}

function Get-JanisAutostartEnabled {
    $lnk = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\JANIS Tray.lnk"
    return (Test-Path $lnk)
}

function Set-JanisAutostart([bool]$Enabled) {
    $root = Get-JanisRoot
    $startup = [Environment]::GetFolderPath("Startup")
    $lnk = Join-Path $startup "JANIS Tray.lnk"
    $vbs = Join-Path $root "infra\windows\start-janis-tray.vbs"

    if ($Enabled) {
        $vbsContent = @"
Set sh = CreateObject("WScript.Shell")
root = "$($root -replace '\\', '\\')"
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & root & "\infra\windows\janis-tray.ps1""", 0, False
"@
        Set-Content -Path $vbs -Value $vbsContent -Encoding ASCII
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($lnk)
        $Shortcut.TargetPath = "wscript.exe"
        $Shortcut.Arguments = "`"$vbs`""
        $Shortcut.WorkingDirectory = $root
        $Shortcut.Description = "JANIS tray - Ollama + brain WSL"
        $Shortcut.Save()
        Write-JanisTrayLog "Autostart abilitato"
    } else {
        if (Test-Path $lnk) { Remove-Item $lnk -Force }
        Write-JanisTrayLog "Autostart disabilitato"
    }
}
