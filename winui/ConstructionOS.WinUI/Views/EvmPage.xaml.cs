using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class EvmPage : Page
{
    public EvmPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await PageLoad.BindListAsync(
            Grid, Status,
            async () =>
            {
                var data = await ApiClient.Default.GetJsonAsync("api/evm");
                return JsonRows.FromEnvelope(data, "projects", "items");
            },
            "No EVM rows yet.");
    }
}
