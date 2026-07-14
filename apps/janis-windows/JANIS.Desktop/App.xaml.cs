using System.Windows;

namespace JANIS.Desktop;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        JanisPaths.EnsureDataDir();
    }
}
