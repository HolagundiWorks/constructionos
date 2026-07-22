using System.Text.Json;
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
                var rows = new List<Dictionary<string, object?>>();
                if (data.TryGetProperty("items", out var items))
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
                Grid.ItemsSource = rows;
            }
            catch (Exception ex)
            {
                Grid.ItemsSource = new[] { new { error = ex.Message } };
            }
        };
    }
}
