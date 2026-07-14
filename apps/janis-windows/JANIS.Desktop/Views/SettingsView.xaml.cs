using System.Windows;
using System.Windows.Controls;
using JANIS.Desktop.Services;

namespace JANIS.Desktop.Views;

public partial class SettingsView : UserControl
{
    readonly JanisBrainClient _brain = new();

    public SettingsView()
    {
        InitializeComponent();
        BrainUrlBox.Text = JanisPaths.BrainUrl;
        RepoBox.Text = JanisPaths.RepoRoot;
        Loaded += async (_, _) => await LoadRuntimeAsync();
    }

    async Task LoadRuntimeAsync()
    {
        var json = await _brain.GetRuntimeJsonAsync();
        RuntimeBox.Text = json ?? "(brain offline)";
    }

    void SaveUrl_Click(object sender, RoutedEventArgs e)
    {
        JanisPaths.BrainUrl = BrainUrlBox.Text.Trim().TrimEnd('/');
        StatusText.Text = "URL salvato per questa sessione.";
    }

    void OpenHud_Click(object sender, RoutedEventArgs e)
    {
        System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(JanisPaths.HudUrl) { UseShellExecute = true });
    }

    void InstallAutostart_Click(object sender, RoutedEventArgs e)
    {
        if (File.Exists(JanisPaths.InstallTrayPs1))
            StackOrchestrator.RunPowerShellHidden(JanisPaths.InstallTrayPs1);
        StatusText.Text = "Autostart tray avviato in background.";
    }
}
