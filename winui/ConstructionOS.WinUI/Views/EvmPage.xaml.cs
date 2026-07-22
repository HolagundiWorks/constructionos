using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class EvmPage : Page
{
    public EvmPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            try
            {
                var data = await ApiClient.Default.GetJsonAsync("api/evm");
                Grid.ItemsSource = Ui.Lines(data, "projects", "items");
            }
            catch (Exception ex)
            {
                Grid.ItemsSource = new[] { "Error: " + ex.Message };
            }
        };
    }
}
