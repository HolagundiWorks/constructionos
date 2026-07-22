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

    public App()
    {
        InitializeComponent();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        // Dev default: point at a manually started `python web_main.py`.
        // Packaging (U6) will launch the PyInstaller sidecar here.
        ApiClient.Default = new ApiClient("http://127.0.0.1:8080");
        _window = new MainWindow();
        _window.Activate();
    }
}
