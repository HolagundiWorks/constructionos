using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class RisksPage : Page
{
    public RisksPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await PageLoad.BindListAsync(
            Grid, Status,
            async () =>
            {
                var data = await ApiClient.Default.GetJsonAsync("api/risks");
                return JsonRows.FromEnvelope(data, "items");
            },
            "No risks yet.");
    }
}
