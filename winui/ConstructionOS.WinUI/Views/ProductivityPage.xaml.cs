using System.Globalization;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>Operations › Productivity — the live productivity snapshot from GET
/// /api/productivity: headline output rates (units/hour, hours/unit, plant
/// utilisation) as cards, over the per-site breakdown table. No maths in C#.</summary>
public sealed partial class ProductivityPage : Page
{
    public ProductivityPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        Host.Children.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/productivity");
            Host.Children.Clear();

            Host.Children.Add(Ui.StatStrip(new (string, string)[]
            {
                ("Units / hour", Num(data, "units_per_hour")),
                ("Hours / unit", Num(data, "hours_per_unit")),
                ("Plant util.", Pct(data, "plant_util_pct")),
                ("Quantity", Num(data, "qty")),
                ("Labour hours", Num(data, "labour_hours")),
            }));

            Host.Children.Add(new TextBlock
            {
                Text = "By site",
                Style = (Style)Application.Current.Resources["SubtitleTextBlockStyle"],
                Margin = new Thickness(0, 8, 0, 0),
            });
            Host.Children.Add(Ui.Table(data, "sites"));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(new TextBlock
            {
                Text = ApiException.UserMessage(ex),
                TextWrapping = TextWrapping.Wrap,
                Foreground = (Microsoft.UI.Xaml.Media.Brush)
                    Application.Current.Resources["TextFillColorSecondaryBrush"],
            });
        }
    }

    private static string Num(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? v.GetDouble().ToString("0.##", CultureInfo.InvariantCulture) : "—";

    private static string Pct(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? v.GetDouble().ToString("0.#", CultureInfo.InvariantCulture) + "%" : "—";
}
