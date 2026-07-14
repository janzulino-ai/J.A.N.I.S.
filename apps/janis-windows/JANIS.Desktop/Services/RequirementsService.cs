using System.Diagnostics;
using System.Net.Http;
using JANIS.Desktop.Models;

namespace JANIS.Desktop.Services;

public sealed class RequirementsService
{
    readonly JanisBrainClient _brain = new();

    public async Task<IReadOnlyList<RequirementItem>> ScanAsync(CancellationToken ct = default)
    {
        var items = new List<RequirementItem>
        {
            new()
            {
                Id = "webview2",
                Name = "WebView2 Runtime",
                Description = "Motore Chromium per chat e browser integrati",
                CanAutoFix = true,
                InstallHint = "https://go.microsoft.com/fwlink/p/?LinkId=2124703",
            },
            new()
            {
                Id = "wsl",
                Name = "WSL2 + Ubuntu",
                Description = "Brain JANIS in Linux (porta 8001)",
                CanAutoFix = true,
                InstallHint = "wsl --install -d Ubuntu",
            },
            new()
            {
                Id = "ollama",
                Name = "Ollama (Windows)",
                Description = "LLM locale GPU — gateway per WSL",
                CanAutoFix = true,
                InstallHint = "https://ollama.com/download",
            },
            new()
            {
                Id = "brain",
                Name = "Brain JANIS",
                Description = "API FastAPI su :8001",
                CanAutoFix = true,
            },
            new()
            {
                Id = "venv",
                Name = "venv WSL (janis-venv)",
                Description = "Python brain in ~/janis-venv",
                CanAutoFix = false,
                InstallHint = "bash infra/wsl/finish-setup.sh",
            },
        };

        await Task.WhenAll(
            CheckWebView2Async(items[0], ct),
            CheckWslAsync(items[1], ct),
            CheckOllamaAsync(items[2], ct),
            CheckBrainAsync(items[3], ct),
            CheckVenvAsync(items[4], ct));

        return items;
    }

    static Task CheckWebView2Async(RequirementItem item, CancellationToken ct)
    {
        try
        {
            var version = Microsoft.Web.WebView2.Core.CoreWebView2Environment.GetAvailableBrowserVersionString();
            item.State = string.IsNullOrEmpty(version) ? RequirementState.Missing : RequirementState.Ok;
            item.Detail = version ?? "non trovato";
        }
        catch (Exception ex)
        {
            item.State = RequirementState.Missing;
            item.Detail = ex.Message;
        }
        return Task.CompletedTask;
    }

    static Task CheckWslAsync(RequirementItem item, CancellationToken ct)
    {
        if (StackOrchestrator.IsWslInstalled())
        {
            item.State = RequirementState.Ok;
            item.Detail = "wsl.exe disponibile";
        }
        else
        {
            item.State = RequirementState.Missing;
            item.Detail = "WSL non installato";
        }
        return Task.CompletedTask;
    }

    static async Task CheckOllamaAsync(RequirementItem item, CancellationToken ct)
    {
        try
        {
            using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(4) };
            await http.GetAsync("http://127.0.0.1:11434/api/tags", ct);
            item.State = RequirementState.Ok;
            item.Detail = "11434 OK";
        }
        catch
        {
            var ollama = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Programs", "Ollama", "ollama.exe");
            item.State = File.Exists(ollama) ? RequirementState.Warning : RequirementState.Missing;
            item.Detail = File.Exists(ollama) ? "installato ma non in esecuzione" : "non installato";
        }
    }

    async Task CheckBrainAsync(RequirementItem item, CancellationToken ct)
    {
        var st = await _brain.GetStatusAsync(ct);
        item.State = st.BrainOnline ? RequirementState.Ok : RequirementState.Missing;
        item.Detail = st.BrainOnline ? JanisPaths.BrainUrl : "non raggiungibile";
    }

    static Task CheckVenvAsync(RequirementItem item, CancellationToken ct)
    {
        if (!StackOrchestrator.IsWslInstalled())
        {
            item.State = RequirementState.Unknown;
            item.Detail = "richiede WSL";
            return Task.CompletedTask;
        }
        var code = StackOrchestrator.RunWslBash("test -x ~/janis-venv/bin/python && echo OK || echo NO", out var output);
        item.State = output.Contains("OK") ? RequirementState.Ok : RequirementState.Missing;
        item.Detail = output.Trim();
        return Task.CompletedTask;
    }

    public async Task<bool> TryInstallAsync(RequirementItem item, IProgress<string>? log = null, CancellationToken ct = default)
    {
        item.State = RequirementState.Installing;
        log?.Report($"Installazione / avvio: {item.Name}…");

        return item.Id switch
        {
            "webview2" => await InstallWebView2Async(item, log, ct),
            "wsl" => RunElevatedOrShell("wsl", "--install -d Ubuntu", item, log),
            "ollama" => await StartOrInstallOllamaAsync(item, log, ct),
            "brain" => StackOrchestrator.StartFullStack(log),
            _ => false,
        };
    }

    static async Task<bool> InstallWebView2Async(RequirementItem item, IProgress<string>? log, CancellationToken ct)
    {
        try
        {
            var installer = Path.Combine(Path.GetTempPath(), "MicrosoftEdgeWebview2Setup.exe");
            using var http = new HttpClient();
            log?.Report("Download WebView2 bootstrapper…");
            var bytes = await http.GetByteArrayAsync("https://go.microsoft.com/fwlink/p/?LinkId=2124703", ct);
            await File.WriteAllBytesAsync(installer, bytes, ct);
            Process.Start(new ProcessStartInfo(installer, "/silent /install") { UseShellExecute = true })?.WaitForExit(120_000);
            await CheckWebView2Async(item, ct);
            return item.State == RequirementState.Ok;
        }
        catch (Exception ex)
        {
            item.State = RequirementState.Missing;
            item.Detail = ex.Message;
            return false;
        }
    }

    static async Task<bool> StartOrInstallOllamaAsync(RequirementItem item, IProgress<string>? log, CancellationToken ct)
    {
        var ps1 = Path.Combine(JanisPaths.RepoRoot, "infra", "wsl", "start-ollama-windows.ps1");
        if (File.Exists(ps1))
        {
            StackOrchestrator.RunPowerShellHidden(ps1);
            await Task.Delay(5000, ct);
            await CheckOllamaAsync(item, ct);
            if (item.State == RequirementState.Ok) return true;
        }
        Process.Start(new ProcessStartInfo("https://ollama.com/download") { UseShellExecute = true });
        item.Detail = "Apri installer Ollama, poi riprova";
        item.State = RequirementState.Warning;
        return false;
    }

    static bool RunElevatedOrShell(string file, string args, RequirementItem item, IProgress<string>? log)
    {
        try
        {
            Process.Start(new ProcessStartInfo(file, args) { UseShellExecute = true });
            item.State = RequirementState.Warning;
            item.Detail = "Completare setup manualmente e ri-scansionare";
            return true;
        }
        catch (Exception ex)
        {
            item.Detail = ex.Message;
            item.State = RequirementState.Missing;
            return false;
        }
    }
}
