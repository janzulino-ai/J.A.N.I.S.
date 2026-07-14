# JANIS — icona system tray (Ollama + brain WSL + HUD)
# Avvio: doppio click su start-janis-tray.vbs oppure install-tray-autostart.ps1

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "janis-services.ps1")

function New-JanisTrayIcon([string]$Tone) {
    $bmp = New-Object System.Drawing.Bitmap 32, 32
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)

    $color = switch ($Tone) {
        "ok"    { [System.Drawing.Color]::FromArgb(255, 61, 255, 154) }
        "warn"  { [System.Drawing.Color]::FromArgb(255, 255, 196, 77) }
        default { [System.Drawing.Color]::FromArgb(255, 255, 80, 80) }
    }
    $brush = New-Object System.Drawing.SolidBrush $color
    $g.FillEllipse($brush, 3, 3, 26, 26)
    $font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
    $g.DrawString("J", $font, [System.Drawing.Brushes]::Black, 8, 5)
    $g.Dispose()
    $brush.Dispose()
    $font.Dispose()
    return [System.Drawing.Icon]::FromHandle($bmp.GetHicon())
}

function Show-JanisBalloon([System.Windows.Forms.NotifyIcon]$Icon, [string]$Title, [string]$Text) {
    $Icon.BalloonTipTitle = $Title
    $Icon.BalloonTipText = $Text
    $Icon.ShowBalloonTip(4000)
}

$status = Get-JanisStatus
$autostart = Get-JanisAutostartEnabled

$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = New-JanisTrayIcon $(if ($status.Ollama -and $status.Brain) { "ok" } elseif ($status.Ollama -or $status.Brain) { "warn" } else { "bad" })
$notify.Text = "JANIS - $($status.Label)"
$notify.Visible = $true

$menu = New-Object System.Windows.Forms.ContextMenuStrip

$miHud = New-Object System.Windows.Forms.ToolStripMenuItem "Apri HUD"
$miStatus = New-Object System.Windows.Forms.ToolStripMenuItem "Stato: $($status.Label)"
$miStart = New-Object System.Windows.Forms.ToolStripMenuItem "Avvia tutto"
$miRestart = New-Object System.Windows.Forms.ToolStripMenuItem "Riavvia brain"
$miAuto = New-Object System.Windows.Forms.ToolStripMenuItem "Avvio con Windows"
$miAuto.Checked = $autostart
$miQuit = New-Object System.Windows.Forms.ToolStripMenuItem "Esci tray"

$miHud.Add_Click({
    $s = Get-JanisStatus
    if (-not $s.Brain) {
        [System.Windows.Forms.MessageBox]::Show(
            "Brain non attivo. Usa «Avvia tutto» dal menu tray.",
            "JANIS", [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
        return
    }
    Start-Process $s.HudUrl
})

$miStart.Add_Click({
    $s = Start-JanisAll
    $tone = if ($s.Ollama -and $s.Brain) { "ok" } elseif ($s.Ollama -or $s.Brain) { "warn" } else { "bad" }
    $notify.Icon = New-JanisTrayIcon $tone
    $notify.Text = "JANIS - $($s.Label)"
    $miStatus.Text = "Stato: $($s.Label)"
    Show-JanisBalloon $notify "JANIS" $s.Label
})

$miRestart.Add_Click({
    $ok = Restart-JanisBrainWsl
    $s = Get-JanisStatus
    $tone = if ($s.Ollama -and $s.Brain) { "ok" } elseif ($s.Ollama -or $s.Brain) { "warn" } else { "bad" }
    $notify.Icon = New-JanisTrayIcon $tone
    $notify.Text = "JANIS - $($s.Label)"
    $miStatus.Text = "Stato: $($s.Label)"
    Show-JanisBalloon $notify "JANIS" $(if ($ok) { "Brain riavviato" } else { "Riavvio fallito" })
})

$miAuto.Add_Click({
    $miAuto.Checked = -not $miAuto.Checked
    Set-JanisAutostart $miAuto.Checked
    Show-JanisBalloon $notify "JANIS" $(if ($miAuto.Checked) { "Avvio con Windows attivo" } else { "Avvio con Windows disattivato" })
})

$miQuit.Add_Click({
    $notify.Visible = $false
    [System.Windows.Forms.Application]::Exit()
})

$menu.Items.AddRange(@($miHud, $miStatus, (New-Object System.Windows.Forms.ToolStripSeparator), $miStart, $miRestart, $miAuto, (New-Object System.Windows.Forms.ToolStripSeparator), $miQuit))
$notify.ContextMenuStrip = $menu

$notify.Add_DoubleClick({ $miHud.PerformClick() })

Write-JanisTrayLog "Tray avviato - $($status.Label)"

# Avvio automatico servizi se offline (utile al boot Windows)
if (-not $status.Brain -or -not $status.Ollama) {
    Write-JanisTrayLog "Servizi offline - avvio automatico"
    $s = Start-JanisAll
    $tone = if ($s.Ollama -and $s.Brain) { "ok" } elseif ($s.Ollama -or $s.Brain) { "warn" } else { "bad" }
    $notify.Icon = New-JanisTrayIcon $tone
    $notify.Text = "JANIS - $($s.Label)"
    $miStatus.Text = "Stato: $($s.Label)"
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 15000
$timer.Add_Tick({
    $s = Get-JanisStatus
    $tone = if ($s.Ollama -and $s.Brain) { "ok" } elseif ($s.Ollama -or $s.Brain) { "warn" } else { "bad" }
    $notify.Icon = New-JanisTrayIcon $tone
    $notify.Text = "JANIS - $($s.Label)"
    $miStatus.Text = "Stato: $($s.Label)"
})
$timer.Start()

[System.Windows.Forms.Application]::Run()
