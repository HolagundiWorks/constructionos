using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class RisksPage : Page
{
    public RisksPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            try
            {
                var data = await ApiClient.Default.GetJsonAsync("api/risks");
                Grid.ItemsSource = Ui.Lines(data);
            }
            catch (Exception ex)
            {
                Grid.ItemsSource = new[] { "Error: " + ex.Message };
            }
        };
    }
}
