using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Money › Cash &amp; Parties — per-party outstanding ("baaki") from GET
/// /api/parties: how much clients owe you (receivable) and how much you owe
/// vendors (payable), each billed vs settled, with totals. All arithmetic in the
/// Python parties_store; no maths in C#.
/// </summary>
public sealed partial class PartiesPage : Page
{
    public PartiesPage()
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
            var data = await ApiClient.Default.GetJsonAsync("api/parties");
            Host.Children.Clear();

            Host.Children.Add(Ui.StatStrip(new (string, string)[]
            {
                ("Receivable (clients owe)", Money(data, "total_receivable")),
                ("Payable (we owe)", Money(data, "total_payable")),
            }));

            await AddAgeingAsync();

            Host.Children.Add(Section("Receivable — clients"));
            Host.Children.Add(Ui.Table(data, "receivable"));
            Host.Children.Add(Section("Payable — vendors"));
            Host.Children.Add(Ui.Table(data, "payable"));
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

    // How old is the receivable money — the firm-level ageing buckets
    // (0–30 / 30–60 / …) from /api/ageing. Best-effort: never blocks the page.
    private async Task AddAgeingAsync()
    {
        try
        {
            var age = await ApiClient.Default.GetJsonAsync("api/ageing");
            if (!age.TryGetProperty("buckets", out var buckets)
                || buckets.ValueKind != JsonValueKind.Array
                || buckets.GetArrayLength() == 0)
                return;
            Host.Children.Add(Section("Receivables ageing"));
            var stats = new List<(string, string)>();
            foreach (var b in buckets.EnumerateArray())
            {
                var label = b.TryGetProperty("label", out var l) ? l.GetString() : "";
                var amount = b.TryGetProperty("amount", out var a)
                    && a.ValueKind == JsonValueKind.Number ? Ui.Rupees(a.GetDouble()) : "—";
                stats.Add((label ?? "", amount));
            }
            Host.Children.Add(Ui.StatStrip(stats));
        }
        catch
        {
            // Ageing is a complement to the balances — its absence isn't fatal.
        }
    }

    private static TextBlock Section(string title) => new()
    {
        Text = title,
        Style = (Style)Application.Current.Resources["SubtitleTextBlockStyle"],
        Margin = new Thickness(0, 8, 0, 0),
    };

    private static string Money(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? Ui.Rupees(v.GetDouble()) : "—";
}
