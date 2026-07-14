using System.Collections.ObjectModel;
using System.Windows;
using System.Windows.Controls;
using JANIS.Desktop.Models;
using JANIS.Desktop.Services;

namespace JANIS.Desktop.Views;

public partial class SetupView : UserControl
{
    readonly RequirementsService _req = new();
    readonly ObservableCollection<RequirementItem> _items = new();
    readonly Progress<string> _log;

    public event EventHandler? SetupComplete;

    public SetupView()
    {
        InitializeComponent();
        ReqList.ItemsSource = _items;
        _log = new Progress<string>(s => LogBox.AppendText(s + "\n"));
        Loaded += async (_, _) => await RefreshAsync();
    }

    async Task RefreshAsync()
    {
        ScanBtn.IsEnabled = false;
        _items.Clear();
        foreach (var r in await _req.ScanAsync())
            _items.Add(r);
        ScanBtn.IsEnabled = true;
        if (_items.All(x => x.State == RequirementState.Ok))
            SetupComplete?.Invoke(this, EventArgs.Empty);
    }

    async void Scan_Click(object sender, RoutedEventArgs e) => await RefreshAsync();

    async void StartAll_Click(object sender, RoutedEventArgs e)
    {
        LogBox.Clear();
        StackOrchestrator.StartFullStack(_log);
        await Task.Delay(8000);
        await RefreshAsync();
    }

    async void Fix_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button btn || btn.Tag is not RequirementItem item) return;
        if (!item.CanAutoFix)
        {
            LogBox.AppendText($"{item.Name}: installazione manuale — {item.InstallHint}\n");
            return;
        }
        LogBox.AppendText($"→ {item.Name}\n");
        await _req.TryInstallAsync(item, _log);
        await RefreshAsync();
    }
}
