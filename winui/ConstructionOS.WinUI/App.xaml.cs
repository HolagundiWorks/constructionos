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

    public App()
    {
        InitializeComponent();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        var settings = AppSettings.Load();
        ApiClient.Default = ApiClient.FromSettings(settings);
        _window = new MainWindow();
        _window.Activate();
    }
}
