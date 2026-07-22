using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class PortfolioPage : Page
{
    public PortfolioPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            try
            {
                var data = await ApiClient.Default.GetJsonAsync("api/portfolio");
                if (data.TryGetProperty("totals", out var totals))
                    Headline.Text = totals.ToString();
                Grid.ItemsSource = Ui.Lines(data, "per_file", "files");
            }
            catch (Exception ex)
            {
                Headline.Text = ex.Message;
            }
        };
    }
}
