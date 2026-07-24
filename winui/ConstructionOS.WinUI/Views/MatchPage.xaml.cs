using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Purchases › Goods Receipt — the PO ↔ GRN ↔ invoice three-way match from GET
/// /api/match: money at risk / awaiting delivery / received-not-invoiced as
/// cards, the plain-language narration, then the per-PO detail. Status is shown
/// as text + severity (never colour alone) so it survives colour-blindness.
/// </summary>
public sealed partial class MatchPage : Page
{
    public MatchPage()
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
            var data = await ApiClient.Default.GetJsonAsync("api/match");
            Host.Children.Clear();

            if (data.TryGetProperty("summary", out var s) && s.ValueKind == JsonValueKind.Object)
                Host.Children.Add(Ui.StatStrip(new (string, string)[]
                {
                    ("At risk", Money(s, "at_risk")),
                    ("Awaiting delivery", Money(s, "awaiting_delivery")),
                    ("Received, not invoiced", Money(s, "received_not_invoiced")),
                    ("Problems", Count(s, "problem_count")),
                    ("Purchase orders", Count(s, "total_count")),
                }));

            var problems = data.TryGetProperty("summary", out var s2)
                && s2.TryGetProperty("problem_count", out var pc)
                && pc.ValueKind == JsonValueKind.Number ? pc.GetInt32() : 0;
            if (data.TryGetProperty("narration", out var n)
                && n.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(n.GetString()))
                Host.Children.Add(new InfoBar
                {
                    Title = problems > 0 ? "Check these before paying" : "Nothing over-billed",
                    Message = n.GetString(),
                    IsOpen = true,
                    IsClosable = false,
                    Severity = problems > 0 ? InfoBarSeverity.Warning : InfoBarSeverity.Success,
                });

            Host.Children.Add(Ui.SectionTitle("By purchase order"));
            Host.Children.Add(Ui.Table(data));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }

    private static string Money(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? Ui.Rupees(v.GetDouble()) : "—";

    private static string Count(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? v.GetInt32().ToString() : "0";
}
