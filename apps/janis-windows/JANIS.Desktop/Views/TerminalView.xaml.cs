using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using JANIS.Desktop.Services;

namespace JANIS.Desktop.Views;

public partial class TerminalView : UserControl
{
    readonly JanisBrainClient _brain = new();
    string _shell = "wsl";

    public TerminalView()
    {
        InitializeComponent();
        AppendSystem("Terminale JANIS — comandi su brain WSL o PowerShell Windows.\n");
    }

    void AppendSystem(string text) => OutputBox.AppendText(text + (text.EndsWith("\n") ? "" : "\n"));

    async void Run_Click(object sender, RoutedEventArgs e) => await RunCommandAsync();

    async void InputBox_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            e.Handled = true;
            await RunCommandAsync();
        }
    }

    async Task RunCommandAsync()
    {
        var cmd = InputBox.Text.Trim();
        if (cmd.Length == 0) return;
        InputBox.Clear();
        _shell = ShellCombo.SelectedIndex == 1 ? "win" : "wsl";
        AppendSystem($"[{_shell.ToUpper()}] $ {cmd}");
        try
        {
            var result = await _brain.RunTerminalAsync(cmd, _shell);
            AppendSystem(result);
        }
        catch (Exception ex)
        {
            AppendSystem("ERR: " + ex.Message);
        }
        OutputBox.ScrollToEnd();
    }
}
