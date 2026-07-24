using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>Money › Portfolio — the live portfolio snapshot from GET
/// /api/portfolio: the active book, its project/risk/opportunity/lesson counts as
/// headline cards, and any portfolio advisories. (Federated multi-book roll-up is
/// surfaced when the backend reports it.)</summary>
public sealed partial class PortfolioPage : Page
{
    public PortfolioPage()
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
            var data = await ApiClient.Default.GetJsonAsync("api/portfolio");
            Host.Children.Clear();

            if (data.TryGetProperty("current", out var cur) && cur.ValueKind == JsonValueKind.Object)
            {
                var name = cur.TryGetProperty("name", out var n) ? n.GetString() : null;
                if (!string.IsNullOrEmpty(name))
                    Host.Children.Add(new TextBlock
                    {
                        Text = name,
                        Style = (Style)Application.Current.Resources["SubtitleTextBlockStyle"],
                    });

                var stats = new List<(string, string)>();
                foreach (var (key, caption) in new[]
                {
                    ("projects", "Projects"), ("risks", "Risks"),
                    ("opportunities", "Opportunities"), ("lessons", "Lessons"),
                })
                    if (cur.TryGetProperty(key, out var v))
                        stats.Add((caption, Count(v)));
                if (stats.Count > 0) Host.Children.Add(Ui.StatStrip(stats));
            }

            if (data.TryGetProperty("advisories", out var adv)
                && adv.ValueKind == JsonValueKind.Array && adv.GetArrayLength() > 0)
            {
                Host.Children.Add(new TextBlock
                {
                    Text = "Advisories",
                    Style = (Style)Application.Current.Resources["SubtitleTextBlockStyle"],
                    Margin = new Thickness(0, 8, 0, 0),
                });
                foreach (var a in adv.EnumerateArray())
                    Host.Children.Add(new InfoBar
                    {
                        Title = a.TryGetProperty("title", out var t) ? t.GetString() : "Advisory",
                        Message = a.TryGetProperty("detail", out var d) ? d.GetString()
                                  : (a.ValueKind == JsonValueKind.String ? a.GetString() : ""),
                        IsOpen = true,
                        IsClosable = false,
                        Severity = InfoBarSeverity.Informational,
                    });
            }

            if (Host.Children.Count == 0)
                Host.Children.Add(new TextBlock
                {
                    Text = "No portfolio data yet — add a project to populate it.",
                    Foreground = (Microsoft.UI.Xaml.Media.Brush)
                        Application.Current.Resources["TextFillColorSecondaryBrush"],
                });
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }

    // A count: the number itself, or an array's length, else the scalar text.
    private static string Count(JsonElement v) => v.ValueKind switch
    {
        JsonValueKind.Number => v.ToString(),
        JsonValueKind.Array => v.GetArrayLength().ToString(),
        JsonValueKind.Null => "0",
        _ => v.ToString(),
    };
}
