using System.Windows;
using System.Windows.Controls;
using JANIS.Desktop.Services;

namespace JANIS.Desktop.Views;

public partial class PluginsView : UserControl
{
    readonly JanisBrainClient _brain = new();

    public PluginsView()
    {
        InitializeComponent();
        Loaded += async (_, _) => await RefreshAsync();
    }

    async Task RefreshAsync()
    {
        ToolsBox.Text = "Caricamento…";
        var tools = await _brain.GetActiveToolsAsync();
        ToolsBox.Text = tools ?? "(brain offline — avvia stack dalla sezione Requisiti)";
        InfoText.Text =
            "Plugin / tool attivi esposti al LLM (local-first).\n" +
            "Nuovi plugin: registra tool in packages/brain/backend/core/tools/ — compariranno qui via HUD dashboard.\n" +
            "Auto-implementazione: reflect → autodev (richiede Cursor PRO) oppure sviluppo manuale.";
    }

    async void Refresh_Click(object sender, RoutedEventArgs e) => await RefreshAsync();
}
