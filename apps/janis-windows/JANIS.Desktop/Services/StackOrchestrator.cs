using System.Diagnostics;

namespace JANIS.Desktop.Services;

public static class StackOrchestrator
{
    public static bool IsWslInstalled()
    {
        try
        {
            return RunProcess("wsl.exe", "--status", out _, 8000) == 0
                   || RunProcess("where", "wsl", out var o, 3000) == 0 && o.Contains("wsl");
        }
        catch
        {
            return false;
        }
    }

    public static int RunWslBash(string bashCommand, out string output)
    {
        return RunProcess("wsl.exe", $"-d Ubuntu -- bash -lc \"{bashCommand.Replace("\"", "\\\"")}\"", out output, 30_000);
    }

    public static void RunPowerShellHidden(string scriptPath)
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments = $"-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"{scriptPath}\"",
            WorkingDirectory = JanisPaths.RepoRoot,
            UseShellExecute = false,
            CreateNoWindow = true,
        });
    }

    public static bool StartFullStack(IProgress<string>? log = null)
    {
        var script = JanisPaths.StartJanisWslPs1;
        if (!File.Exists(script))
        {
            log?.Report($"Script mancante: {script}");
            return false;
        }
        log?.Report("Avvio Ollama + brain WSL…");
        RunPowerShellHidden(script);
        return true;
    }

    public static bool StartBrainOnly(IProgress<string>? log = null)
    {
        log?.Report("Avvio brain WSL…");
        RunWslBash(
            "cd ~/projects/J.A.N.I.S./packages/brain && nohup ~/janis-venv/bin/python run.py >/tmp/janis-brain.log 2>&1 &",
            out _);
        return true;
    }

    static int RunProcess(string file, string args, out string output, int timeoutMs)
    {
        output = "";
        using var p = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = file,
                Arguments = args,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            },
        };
        p.Start();
        output = p.StandardOutput.ReadToEnd() + p.StandardError.ReadToEnd();
        p.WaitForExit(timeoutMs);
        return p.HasExited ? p.ExitCode : -1;
    }
}
