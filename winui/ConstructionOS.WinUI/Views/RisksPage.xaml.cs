using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace ConstructionOS.WinUI.Views;

/// <summary>Controls › Risk Register — the live risk register (GET /api/risks:
/// likelihood × impact → score / band / expected exposure), as a columnar
/// table.</summary>
public sealed partial class RisksPage : Page
{
    public RisksPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await Load();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await Load();

    private System.Threading.Tasks.Task Load() => Ui.LoadTableAsync(Host, "api/risks");
}
