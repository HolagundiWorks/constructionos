using System.IO;
using Microsoft.UI.Xaml;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI;

/// <summary>
/// WinUI 3 entry — loads saved API settings, points <see cref="ApiClient.Default"/>
/// at the Python localhost backend, then shows <see cref="MainWindow"/>.
/// Packaging (U6) can launch the PyInstaller sidecar before Activate.
/// </summary>
public partial class App : Application
{
    private Window? _window;

    // Dev crash log — unhandled UI/CLR/task exceptions land here so a headless
    // launch can be diagnosed without a debugger. Safe to remove for release.
    private static readonly string CrashLog =
        Path.Combine(Path.GetTempPath(), "cos_winui_crash.log");

    public App()
    {
        InitializeComponent();
        // A single page's load failure must never take down the whole app.
        // Log the exception, then mark it handled so WinUI keeps the process
        // alive — the user stays on a usable window and can navigate elsewhere
        // instead of the app vanishing. (Native COM/XAML fail-fasts bypass this
        // handler entirely; those are addressed at their source, e.g. keeping
        // build output out of OneDrive — see winui/Directory.Build.props.)
        UnhandledException += (_, e) =>
        {
            Log("UI", e.Exception);
            e.Handled = true;
        };
        AppDomain.CurrentDomain.UnhandledException +=
            (_, e) => Log("CLR", e.ExceptionObject as Exception);
        System.Threading.Tasks.TaskScheduler.UnobservedTaskException +=
            (_, e) => Log("Task", e.Exception);
    }

    private static void Log(string source, Exception? ex)
    {
        try
        {
            File.AppendAllText(CrashLog,
                $"[{source}] {DateTime.Now:HH:mm:ss}\n{ex}\n\n");
        }
        catch { /* logging must never throw */ }
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        // Load saved connection settings (URL / user / persona); the crash-logger
        // wraps activation so a head-less launch failure is diagnosable.
        try
        {
            var settings = AppSettings.Load();
            ApiClient.Default = ApiClient.FromSettings(settings);
            _window = new MainWindow();
            _window.Activate();
        }
        catch (Exception ex)
        {
            Log("OnLaunched", ex);
            throw;
        }
    }
}
