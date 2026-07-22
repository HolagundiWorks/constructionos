using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class PortfolioPage : Page
{
    public PortfolioPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            Headline.Text = "Loading…";
            try
            {
                var data = await ApiClient.Default.GetJsonAsync("api/portfolio");
                if (data.TryGetProperty("totals", out var totals))
                    Headline.Text = JsonRows.Pretty(totals);
                else
                    Headline.Text = "Portfolio";
                var rows = JsonRows.FromEnvelope(data, "per_file", "files", "items");
                Grid.ItemsSource = rows;
                Status.Text = rows.Count == 0 ? "No firm/year files." : $"{rows.Count} file(s).";
            }
            catch (Exception ex)
            {
                var msg = ApiException.UserMessage(ex);
                Headline.Text = msg;
                Status.Text = msg;
                Grid.ItemsSource = new[] { new Dictionary<string, object?> { ["error"] = msg } };
            }
        };
    }
}
