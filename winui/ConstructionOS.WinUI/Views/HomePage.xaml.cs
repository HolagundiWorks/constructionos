using System.Text.Json;
using Microsoft.UI.Text;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Home dashboard — the money snapshot as stock KPI stat cards (from
/// GET /api/kpi) plus the advisories as stock InfoBars (from /api/dashboard).
/// No maths in C#: every figure comes from the Python API.
/// </summary>
public sealed partial class HomePage : Page
{
    private static readonly (string Label, string Key)[] Kpis =
    {
        ("Cash in hand", "cash"),
        ("Receivable", "receivable"),
        ("Payable", "payable"),
        ("Net position", "net_position"),
        ("Billed (mo)", "billed_month"),
        ("Collected (mo)", "collected_month"),
    };

    public HomePage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async Task LoadAsync()
    {
        Status.Text = "Loading dashboard…";
        try
        {
            var kpi = await ApiClient.Default.GetJsonAsync("api/kpi");
            var snap = kpi.TryGetProperty("snapshot", out var s) ? s : kpi;
            Cards.Children.Clear();
            foreach (var (label, key) in Kpis)
                Cards.Children.Add(Card(label, Money(snap, key)));

            var dash = await ApiClient.Default.GetJsonAsync("api/dashboard");
            Advisories.Children.Clear();
            var count = 0;
            if (dash.TryGetProperty("advisories", out var list)
                && list.ValueKind == JsonValueKind.Array)
            {
                foreach (var a in list.EnumerateArray())
                {
                    Advisories.Children.Add(AdvisoryBar(a));
                    count++;
                }
            }
            Status.Text = count == 0
                ? "No advisories — nothing needs attention."
                : $"{count} advisor{(count == 1 ? "y" : "ies")} to review.";
        }
        catch (Exception ex)
        {
            Status.Text = ApiException.UserMessage(ex);
        }
    }

    private static Border Card(string label, string value)
    {
        var panel = new StackPanel { Spacing = 4 };
        panel.Children.Add(new TextBlock
        {
            Text = label,
            FontSize = 12,
            Foreground = Brush("TextFillColorSecondaryBrush"),
        });
        panel.Children.Add(new TextBlock
        {
            Text = value,
            FontSize = 22,
            FontWeight = FontWeights.SemiBold,
        });
        return new Border
        {
            Child = panel,
            MinWidth = 150,
            Padding = new Thickness(16, 12, 16, 12),
            CornerRadius = new CornerRadius(8),
            Background = Brush("CardBackgroundFillColorDefaultBrush"),
            BorderBrush = Brush("CardStrokeColorDefaultBrush"),
            BorderThickness = new Thickness(1),
        };
    }

    private static InfoBar AdvisoryBar(JsonElement a)
    {
        var detail = JsonRows.Prop(a, "detail");
        var action = JsonRows.Prop(a, "action");
        return new InfoBar
        {
            Title = JsonRows.Prop(a, "title"),
            Message = string.IsNullOrEmpty(action) ? detail
                      : $"{detail}  ·  Do: {action}",
            Severity = JsonRows.Prop(a, "severity", "info") switch
            {
                "act" => InfoBarSeverity.Error,
                "watch" => InfoBarSeverity.Warning,
                "good" => InfoBarSeverity.Success,
                _ => InfoBarSeverity.Informational,
            },
            IsOpen = true,
            IsClosable = false,
        };
    }

    private static Brush Brush(string resourceKey) =>
        (Brush)Application.Current.Resources[resourceKey];

    private static string Money(JsonElement obj, string key)
    {
        if (obj.ValueKind == JsonValueKind.Object
            && obj.TryGetProperty(key, out var v)
            && v.ValueKind == JsonValueKind.Number)
            return "₹ " + v.GetDouble().ToString("N0");
        return "₹ 0";
    }
}
