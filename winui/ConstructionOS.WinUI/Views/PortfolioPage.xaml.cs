using System.Text.Json;
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
                var rows = new List<Dictionary<string, object?>>();
                if (data.TryGetProperty("per_file", out var items)
                    || data.TryGetProperty("files", out items))
                {
                    if (items.ValueKind == JsonValueKind.Array)
                    {
                        foreach (var item in items.EnumerateArray())
                        {
                            var row = new Dictionary<string, object?>();
                            foreach (var p in item.EnumerateObject())
                                row[p.Name] = p.Value.ValueKind == JsonValueKind.Null
                                    ? null : p.Value.ToString();
                            rows.Add(row);
                        }
                    }
                }
                Grid.ItemsSource = rows;
            }
            catch (Exception ex)
            {
                Headline.Text = ex.Message;
            }
        };
    }
}
