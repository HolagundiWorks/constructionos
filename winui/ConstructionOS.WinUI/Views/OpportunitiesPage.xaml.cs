using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace ConstructionOS.WinUI.Views;

/// <summary>Controls › Opportunity Register — the live opportunity register (GET
/// /api/opportunities: likelihood × impact → band, probability-weighted expected
/// upside), as a columnar table.</summary>
public sealed partial class OpportunitiesPage : Page
{
    public OpportunitiesPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await Load();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await Load();

    private System.Threading.Tasks.Task Load() =>
        Ui.LoadTableAsync(Host, "api/opportunities");
}
