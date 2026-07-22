using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class MoneyPage : Page
{
    public MoneyPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            try
            {
                var data = await ApiClient.Default.GetJsonAsync("api/payments");
                Grid.ItemsSource = Ui.Lines(data);
            }
            catch (Exception ex)
            {
                Grid.ItemsSource = new[] { "Error: " + ex.Message };
            }
        };
    }
}
