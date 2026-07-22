using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class LessonsPage : Page
{
    public LessonsPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await PageLoad.BindListAsync(
            Grid, Status,
            async () =>
            {
                var data = await ApiClient.Default.GetJsonAsync("api/lessons");
                return JsonRows.FromEnvelope(data, "items");
            },
            "No lessons yet.");
    }
}
