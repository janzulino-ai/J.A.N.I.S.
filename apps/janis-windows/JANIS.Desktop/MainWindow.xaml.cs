using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using JANIS.Desktop.Services;
using JANIS.Desktop.Views;

namespace JANIS.Desktop;

public partial class MainWindow : Window
{
    readonly JanisBrainClient _brain = new();
    readonly DispatcherTimer _statusTimer = new() { Interval = TimeSpan.FromSeconds(12) };
    TrayIconService? _tray;

    WebPanelView? _chatPanel;
    WebPanelView? _previewPanel;

    public MainWindow()
    {
        InitializeComponent();
        _statusTimer.Tick += async (_, _) => await UpdateStatusAsync();
        Loaded += OnLoaded;
        Closing += (_, e) =>
        {
            if (_tray != null)
            {
                Hide();
                e.Cancel = true;
            }
        };
    }

    async void OnLoaded(object sender, RoutedEventArgs e)
    {
        _tray = new TrayIconService(this);
        NavList.SelectedIndex = 0;
        _statusTimer.Start();
        await UpdateStatusAsync();
    }

    async Task UpdateStatusAsync()
    {
        var st = await _brain.GetStatusAsync();
        StatusPill.Text = st.Label;
        StatusPill.Foreground = st.BrainOnline
            ? (System.Windows.Media.Brush)FindResource("AccentGreen")!
            : (System.Windows.Media.Brush)FindResource("TextMuted")!;
    }

    void NavList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (NavList.SelectedItem is not ListBoxItem item || item.Tag is not string tag)
            return;

        ContentHost.Content = tag switch
        {
            "agent" => new AgentView(),
            "setup" => new SetupView(),
            "chat" => _chatPanel ??= CreateWebPanel($"{JanisPaths.BrainUrl.TrimEnd('/')}/brain?device_id=janis-desktop"),
            "preview" => _previewPanel ??= CreateWebPanel(JanisPaths.HudUrl),
            "terminal" => new TerminalView(),
            "browser" => new BrowserView(),
            "plugins" => new PluginsView(),
            "settings" => new SettingsView(),
            _ => new SetupView(),
        };

        if (ContentHost.Content is SetupView setup)
            setup.SetupComplete += (_, _) => NavList.SelectedIndex = 0;
    }

    static WebPanelView CreateWebPanel(string url)
    {
        var v = new WebPanelView();
        v.Navigate(url);
        return v;
    }

    protected override void OnClosed(EventArgs e)
    {
        _tray?.Dispose();
        base.OnClosed(e);
    }
}
