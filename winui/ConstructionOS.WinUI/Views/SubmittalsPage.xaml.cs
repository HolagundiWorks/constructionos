using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace ConstructionOS.WinUI.Views;

/// <summary>Controls › Submittals — the live submittal register (GET
/// /api/submittals), as a columnar table.</summary>
public sealed partial class SubmittalsPage : Page
{
    public SubmittalsPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await Load();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await Load();

    private System.Threading.Tasks.Task Load() => Ui.LoadTableAsync(Host, "api/submittals");
}
