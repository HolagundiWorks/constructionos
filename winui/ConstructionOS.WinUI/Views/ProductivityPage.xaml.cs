using System.Text.Json;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class ProductivityPage : Page
{
    public ProductivityPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            try
            {
                var data = await ApiClient.Default.GetJsonAsync("api/productivity");
                if (data.TryGetProperty("units_per_hour", out var uph)
                    || data.TryGetProperty("summary", out _))
                {
                    var u = data.TryGetProperty("units_per_hour", out var a)
                        ? a.ToString() : "—";
                    var p = data.TryGetProperty("plant_util_pct", out var b)
                        ? b.ToString() : "—";
                    Summary.Text = $"Firm units/hr: {u} · plant util %: {p}";
                }
                var rows = new List<Dictionary<string, object?>>();
                if (data.TryGetProperty("sites", out var sites))
                {
                    foreach (var item in sites.EnumerateArray())
                    {
                        var row = new Dictionary<string, object?>();
                        foreach (var prop in item.EnumerateObject())
                            row[prop.Name] = prop.Value.ValueKind == JsonValueKind.Null
                                ? null : prop.Value.ToString();
                        rows.Add(row);
                    }
                }
                Grid.ItemsSource = rows;
            }
            catch (Exception ex)
            {
                Summary.Text = ex.Message;
            }
        };
    }
}
