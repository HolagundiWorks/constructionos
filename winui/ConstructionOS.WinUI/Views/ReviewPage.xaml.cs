using System.Text.Json;
using Microsoft.UI.Text;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Money › Review — the assembled weekly review from GET /api/review (built by
/// the Python <c>review_assemble</c>; no maths in C#). Plain-language narrative,
/// money KPI cards, advisories as InfoBars, and the risk / opportunity summary.
/// A read-only draft — it books, files and pays nothing.
/// </summary>
public sealed partial class ReviewPage : Page
{
    private static readonly (string Key, string Label)[] Kpis =
    {
        ("cash", "Cash in hand"), ("receivable", "Receivable"),
        ("receivable_90plus", "Receivable 90+ days"), ("payable", "Payable"),
        ("billed_this_month", "Billed (mo)"), ("collected_this_month", "Collected (mo)"),
        ("retention_due_now", "Retention due"),
    };

    public ReviewPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        Host.Children.Clear();
        try
        {
            var r = await ApiClient.Default.GetJsonAsync("api/review");
            if (r.TryGetProperty("generated", out var gen) && gen.ValueKind == JsonValueKind.String)
                TitleText.Text = $"Weekly review — {gen.GetString()}";

            // Narrative (plain-language sentences).
            if (r.TryGetProperty("narrative", out var narr) && narr.ValueKind == JsonValueKind.Object)
            {
                if (narr.TryGetProperty("kpi", out var kpiLines)
                    && kpiLines.ValueKind == JsonValueKind.Array)
                    foreach (var line in kpiLines.EnumerateArray())
                        if (line.ValueKind == JsonValueKind.String)
                            Host.Children.Add(Paragraph(line.GetString() ?? ""));
                if (narr.TryGetProperty("risk", out var riskLine)
                    && riskLine.ValueKind == JsonValueKind.String)
                    Host.Children.Add(Paragraph(riskLine.GetString() ?? ""));
            }

            // Money KPI cards.
            if (r.TryGetProperty("kpis", out var kpis) && kpis.ValueKind == JsonValueKind.Object)
            {
                Host.Children.Add(Heading("Money at a glance"));
                var cards = new StackPanel
                {
                    Orientation = Orientation.Horizontal, Spacing = 8,
                };
                foreach (var (key, label) in Kpis)
                    cards.Children.Add(Card(label, Money(kpis, key)));
                Host.Children.Add(new ScrollViewer
                {
                    Content = cards,
                    HorizontalScrollMode = ScrollMode.Auto,
                    HorizontalScrollBarVisibility = ScrollBarVisibility.Auto,
                    VerticalScrollMode = ScrollMode.Disabled,
                });
            }

            // Advisories → InfoBars.
            if (r.TryGetProperty("advisories", out var adv)
                && adv.TryGetProperty("cards", out var acards)
                && acards.ValueKind == JsonValueKind.Array
                && acards.GetArrayLength() > 0)
            {
                Host.Children.Add(Heading("Advisories"));
                foreach (var a in acards.EnumerateArray())
                    Host.Children.Add(AdvisoryBar(a));
            }

            // Risk / opportunity summary.
            var risk = Summary(r, "risks", "needs_action", "raised");
            var opp = Summary(r, "opportunities", "pursue_now", "open");
            if (risk.Length > 0 || opp.Length > 0)
            {
                Host.Children.Add(Heading("Risk & opportunity"));
                if (risk.Length > 0) Host.Children.Add(Paragraph(risk));
                if (opp.Length > 0) Host.Children.Add(Paragraph(opp));
            }
        }
        catch (Exception ex)
        {
            Host.Children.Add(Paragraph(ApiException.UserMessage(ex)));
        }
    }

    private static string Summary(JsonElement root, string key, string actionKey, string noun)
    {
        if (!root.TryGetProperty(key, out var s) || s.ValueKind != JsonValueKind.Object)
            return "";
        var count = s.TryGetProperty("count", out var c) && c.ValueKind == JsonValueKind.Number
            ? c.GetInt32() : 0;
        var action = s.TryGetProperty(actionKey, out var a) && a.ValueKind == JsonValueKind.Number
            ? a.GetInt32() : 0;
        var name = char.ToUpperInvariant(key[0]) + key[1..];
        return count == 0 ? $"{name}: none {noun}."
            : $"{name}: {count} {noun}, {action} need action.";
    }

    private static TextBlock Heading(string text) => new()
    {
        Text = text,
        Style = (Style)Application.Current.Resources["SubtitleTextBlockStyle"],
        Margin = new Thickness(0, 8, 0, 0),
    };

    private static TextBlock Paragraph(string text) => new()
    {
        Text = text,
        TextWrapping = TextWrapping.Wrap,
        Style = (Style)Application.Current.Resources["BodyTextBlockStyle"],
    };

    private static Border Card(string label, string value)
    {
        var panel = new StackPanel { Spacing = 4 };
        panel.Children.Add(new TextBlock
        {
            Text = label, FontSize = 12,
            Foreground = (Microsoft.UI.Xaml.Media.Brush)
                Application.Current.Resources["TextFillColorSecondaryBrush"],
        });
        panel.Children.Add(new TextBlock
        {
            Text = value, FontSize = 20, FontWeight = FontWeights.SemiBold,
        });
        return new Border
        {
            Child = panel, MinWidth = 150,
            Padding = new Thickness(16, 12, 16, 12),
            CornerRadius = new CornerRadius(8),
            Background = (Microsoft.UI.Xaml.Media.Brush)
                Application.Current.Resources["CardBackgroundFillColorDefaultBrush"],
            BorderBrush = (Microsoft.UI.Xaml.Media.Brush)
                Application.Current.Resources["CardStrokeColorDefaultBrush"],
            BorderThickness = new Thickness(1),
        };
    }

    private static InfoBar AdvisoryBar(JsonElement a) => new()
    {
        Title = JsonRows.Prop(a, "title"),
        Message = string.IsNullOrEmpty(JsonRows.Prop(a, "action"))
            ? JsonRows.Prop(a, "detail")
            : $"{JsonRows.Prop(a, "detail")}  ·  Do: {JsonRows.Prop(a, "action")}",
        Severity = JsonRows.Prop(a, "severity", "info") switch
        {
            "act" => InfoBarSeverity.Error,
            "watch" => InfoBarSeverity.Warning,
            "good" => InfoBarSeverity.Success,
            _ => InfoBarSeverity.Informational,
        },
        IsOpen = true, IsClosable = false,
    };

    private static string Money(JsonElement obj, string key) =>
        obj.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.Number
            ? "₹ " + v.GetDouble().ToString("N0") : "₹ 0";
}
