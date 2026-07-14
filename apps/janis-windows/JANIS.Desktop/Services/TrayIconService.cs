using System.Drawing;
using System.Windows;
using System.Windows.Forms;

namespace JANIS.Desktop.Services;

public sealed class TrayIconService : IDisposable
{
    readonly NotifyIcon _icon;
    readonly MainWindow _window;

    public TrayIconService(MainWindow window)
    {
        _window = window;
        _icon = new NotifyIcon
        {
            Text = "J.A.N.I.S.",
            Visible = true,
            Icon = SystemIcons.Application,
        };
        _icon.DoubleClick += (_, _) => ShowMain();
        var menu = new ContextMenuStrip();
        menu.Items.Add("Mostra JANIS", null, (_, _) => ShowMain());
        menu.Items.Add("Apri HUD", null, (_, _) => OpenUrl(JanisPaths.HudUrl));
        menu.Items.Add("Avvia stack", null, (_, _) => StackOrchestrator.StartFullStack());
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Esci", null, (_, _) => ExitApp());
        _icon.ContextMenuStrip = menu;
    }

    void ShowMain()
    {
        _window.Dispatcher.Invoke(() =>
        {
            _window.Show();
            _window.WindowState = WindowState.Normal;
            _window.Activate();
        });
    }

    static void OpenUrl(string url) =>
        System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(url) { UseShellExecute = true });

    void ExitApp() =>
        _window.Dispatcher.Invoke(() =>
        {
            _icon.Visible = false;
            Application.Current.Shutdown();
        });

    public void Dispose() => _icon.Dispose();
}
