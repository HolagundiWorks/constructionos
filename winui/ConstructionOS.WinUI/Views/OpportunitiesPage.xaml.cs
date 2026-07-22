using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class OpportunitiesPage : Page
{
    public OpportunitiesPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await PageLoad.BindListAsync(
            Grid, Status,
            async () =>
            {
                var data = await ApiClient.Default.GetJsonAsync("api/opportunities");
                return JsonRows.FromEnvelope(data, "items");
            },
            "No opportunities yet.");
    }
}
