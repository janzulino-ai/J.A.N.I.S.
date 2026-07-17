namespace JANIS.Desktop;

/// <summary>Path monorepo e servizi JANIS su Windows.</summary>
public static class JanisPaths
{
    public static string RepoRoot { get; } = DetectRepoRoot();

    public static string BrainUrl { get; set; } = "http://127.0.0.1:8001";

    public static string HudUrl => $"{BrainUrl.TrimEnd('/')}/server?v=hudcli09";

    public static string ChatWsUrl => BrainUrl.Replace("http://", "ws://").Replace("https://", "wss://").TrimEnd('/') + "/ws/janis?device_id=janis-desktop";

    public static string StartJanisWslPs1 => Path.Combine(RepoRoot, "infra", "wsl", "start-janis-wsl.ps1");

    public static string InstallTrayPs1 => Path.Combine(RepoRoot, "infra", "windows", "install-tray-autostart.ps1");

    public static string DataDir => Path.Combine(RepoRoot, "data", "desktop-win");

    public static void EnsureDataDir() => Directory.CreateDirectory(DataDir);

    static string DetectRepoRoot()
    {
        var env = Environment.GetEnvironmentVariable("JANIS_ROOT");
        if (!string.IsNullOrWhiteSpace(env) && Directory.Exists(env))
            return Path.GetFullPath(env);

        // Walk up from exe (bin/Debug/net8.0-windows) -> apps/janis-windows -> repo
        var dir = AppContext.BaseDirectory;
        for (var i = 0; i < 8; i++)
        {
            if (File.Exists(Path.Combine(dir, "infra", "wsl", "start-brain.sh")))
                return dir;
            var parent = Directory.GetParent(dir)?.FullName;
            if (parent == null) break;
            dir = parent;
        }

        return @"C:\APP IA\JANIS";
    }
}
