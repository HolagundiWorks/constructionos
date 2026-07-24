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

    /// <summary>The single main window (per the WinUI 3 desktop convention — use
    /// this instead of the UWP <c>Window.Current</c>). Lets pages reach the shell
    /// (e.g. to reload after a company switch) and supply a window handle to
    /// pickers/dialogs.</summary>
    public static MainWindow? MainWindow { get; private set; }

    // Dev crash log — unhandled UI/CLR/task exceptions land here so a headless
    // launch can be diagnosed without a debugger. Safe to remove for release.
    private static readonly string CrashLog =
        Path.Combine(Path.GetTempPath(), "cos_winui_crash.log");

    public App()
    {
        // Before InitializeComponent: the only window in which the application
        // theme is writable (setting it later throws COMException 0x80131515).
        ApplySavedTheme(AppSettings.Load().Theme);
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

    /// <summary>
    /// Set the saved theme on the <see cref="Application"/> itself, before the
    /// first window exists — the only place it takes effect app-wide.
    /// <para>
    /// <c>MainWindow.ApplyTheme</c> sets <c>Root.RequestedTheme</c>, which only
    /// reaches elements inside that Grid. Two things live outside it and were
    /// therefore rendering in the *Windows* theme rather than the app's:
    /// popups (ContentDialog, MenuFlyout — they are hosted in a separate popup
    /// root), and every <c>Application.Current.Resources[...]</c> brush lookup
    /// in code-behind, which resolves against the application-level theme
    /// dictionary. On a Dark-themed Windows with the app set to Light that put
    /// dark-theme greys on light backgrounds — table headers and stat-card
    /// labels came out near-invisible (a WCAG 1.4.3 failure, not a nicety).
    /// </para>
    /// Light/Dark only: "system" leaves the default, which already follows Windows.
    /// </summary>
    private void ApplySavedTheme(string? theme)
    {
        var wanted = (theme ?? "Light").Trim().ToLowerInvariant() switch
        {
            "dark" => ApplicationTheme.Dark,
            "system" or "default" or "windows" => (ApplicationTheme?)null,
            _ => ApplicationTheme.Light,
        };
        // Never let a theme preference be fatal — a wrong-looking app beats none.
        try { if (wanted.HasValue) RequestedTheme = wanted.Value; }
        catch (Exception ex) { Log("Theme", ex); }
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
            MainWindow = new MainWindow();
            _window = MainWindow;
            _window.Activate();
        }
        catch (Exception ex)
        {
            Log("OnLaunched", ex);
            throw;
        }
    }
}
