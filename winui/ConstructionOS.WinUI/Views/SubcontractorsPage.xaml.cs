using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Purchases › Subcontractors — back-to-back work orders and the sub-bills raised
/// against them (GET /api/work_orders, /api/sub_bills). Replaces the old
/// thekedars-master proxy: this is the subcontractor billing side, not the
/// labour-contractor master.
/// </summary>
public sealed partial class SubcontractorsPage : Page
{
    public SubcontractorsPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        Host.Children.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var wos = await ApiClient.Default.GetJsonAsync("api/work_orders");
            var bills = await ApiClient.Default.GetJsonAsync("api/sub_bills");
            Host.Children.Clear();
            Host.Children.Add(Ui.SectionTitle("Work orders"));
            Host.Children.Add(Ui.Table(wos));
            Host.Children.Add(Ui.SectionTitle("Sub bills"));
            Host.Children.Add(Ui.Table(bills));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }
}
