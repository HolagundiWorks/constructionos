using System.IO;
using Microsoft.UI.Xaml;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI;

/// <summary>
/// WinUI 3 entry — launches the Python backend sidecar (dev: assume already
/// running on 127.0.0.1:8080) then shows <see cref="MainWindow"/>.
/// Scaffold for U1; build on Windows with VS 2022 + Windows App SDK.
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
        UnhandledException += (_, e) => Log("UI", e.Exception);
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
        // Dev default: point at a manually started `python web_main.py`.
        // Packaging (U6) will launch the PyInstaller sidecar here.
        try
        {
            ApiClient.Default = new ApiClient("http://127.0.0.1:8080");
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
