using System.Globalization;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Text;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Project Management › Look-ahead — the weekly commitment plan and PPC (Percent
/// Plan Complete) from GET /api/lookahead. All figures are computed by the Python
/// <c>planning.py</c> / <c>lookahead_store.py</c>; this page only lays them out:
/// headline PPC + promised/done, the per-week PPC trend, the commitments register
/// (curated columns via <see cref="Ui.Table"/>), and the reasons commitments were
/// missed.
/// </summary>
public sealed partial class LookaheadPage : Page
{
    public LookaheadPage()
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
            var data = await ApiClient.Default.GetJsonAsync("api/lookahead");
            Host.Children.Clear();

            Host.Children.Add(Headline(data));

            var weeks = Section("Weekly PPC");
            weeks.Add(WeeklyTrend(data));
            Host.Children.Add(weeks.Panel);

            var commitments = Section("Commitments");
            commitments.Add(Ui.Table(data));
            Host.Children.Add(commitments.Panel);

            if (data.TryGetProperty("miss_reasons", out var mr)
                && mr.ValueKind == JsonValueKind.Array && mr.GetArrayLength() > 0)
            {
                var misses = Section("Reasons for misses");
                misses.Add(MissReasons(mr));
                Host.Children.Add(misses.Panel);
            }
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }

    // Headline cards: overall PPC, promised, done, average PPC.
    private FrameworkElement Headline(JsonElement data)
    {
        var row = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 12 };
        row.Children.Add(Stat("PPC (this plan)", Pct(Num(data, "ppc")), accent: true));
        row.Children.Add(Stat("Promised", Count(data, "promised")));
        row.Children.Add(Stat("Done", Count(data, "done")));
        row.Children.Add(Stat("PPC (avg)", Pct(Num(data, "ppc_average"))));
        return row;
    }

    private FrameworkElement Stat(string caption, string value, bool accent = false)
    {
        var card = new Border
        {
            Background = (Microsoft.UI.Xaml.Media.Brush)
                Application.Current.Resources["CardBackgroundFillColorDefaultBrush"],
            BorderBrush = (Microsoft.UI.Xaml.Media.Brush)
                Application.Current.Resources["CardStrokeColorDefaultBrush"],
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(16, 12, 16, 12),
            MinWidth = 130,
        };
        // Read the pair as one item ("PPC (this plan): 66%") rather than two.
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(card, $"{caption}: {value}");
        var stack = new StackPanel { Spacing = 2 };
        stack.Children.Add(new TextBlock
        {
            Text = value,
            Style = (Style)Application.Current.Resources["TitleTextBlockStyle"],
            Foreground = accent
                ? (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AccentTextFillColorPrimaryBrush"]
                : (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["TextFillColorPrimaryBrush"],
        });
        stack.Children.Add(new TextBlock
        {
            Text = caption,
            Style = (Style)Application.Current.Resources["CaptionTextBlockStyle"],
            Foreground = (Microsoft.UI.Xaml.Media.Brush)
                Application.Current.Resources["TextFillColorSecondaryBrush"],
        });
        card.Child = stack;
        return card;
    }

    // One labelled progress bar per week (PPC 0–100). Empty note if no weeks.
    private FrameworkElement WeeklyTrend(JsonElement data)
    {
        if (!data.TryGetProperty("weeks", out var weeks)
            || weeks.ValueKind != JsonValueKind.Array || weeks.GetArrayLength() == 0)
            return Note("No weekly commitments yet.");

        var grid = new Grid { ColumnSpacing = 12 };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(110) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(64) });

        var r = 0;
        foreach (var w in weeks.EnumerateArray())
        {
            grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            var week = w.TryGetProperty("week", out var wk) ? Scalar(wk) : "";
            var ppc = w.TryGetProperty("ppc", out var p) ? p : default;
            var val = ppc.ValueKind == JsonValueKind.Number ? ppc.GetDouble() : 0;

            var label = new TextBlock { Text = week, Margin = new Thickness(0, 4, 0, 4) };
            var bar = new ProgressBar
            {
                Minimum = 0, Maximum = 100, Value = val,
                VerticalAlignment = VerticalAlignment.Center,
            };
            // A bare progress bar reads as an anonymous "NN%"; name it with the week.
            Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(
                bar, $"Week {week} PPC {Pct(ppc.ValueKind == JsonValueKind.Number ? val : (double?)null)}");
            var num = new TextBlock
            {
                Text = Pct(ppc.ValueKind == JsonValueKind.Number ? val : (double?)null),
                TextAlignment = TextAlignment.Right,
                Margin = new Thickness(0, 4, 0, 4),
            };
            Grid.SetRow(label, r); Grid.SetColumn(label, 0);
            Grid.SetRow(bar, r); Grid.SetColumn(bar, 1);
            Grid.SetRow(num, r); Grid.SetColumn(num, 2);
            grid.Children.Add(label); grid.Children.Add(bar); grid.Children.Add(num);
            r++;
        }
        return grid;
    }

    private FrameworkElement MissReasons(JsonElement reasons)
    {
        var grid = new Grid { ColumnSpacing = 12 };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(64) });
        var r = 0;
        foreach (var m in reasons.EnumerateArray())
        {
            grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            var reason = m.TryGetProperty("reason", out var rs) ? Scalar(rs) : "";
            var count = m.TryGetProperty("count", out var c) ? Scalar(c) : "";
            var name = new TextBlock
            {
                Text = string.IsNullOrEmpty(reason) ? "(unstated)" : reason,
                Margin = new Thickness(0, 3, 0, 3),
            };
            var cnt = new TextBlock
            {
                Text = count,
                TextAlignment = TextAlignment.Right,
                Margin = new Thickness(0, 3, 0, 3),
                FontWeight = FontWeights.SemiBold,
            };
            Grid.SetRow(name, r); Grid.SetColumn(name, 0);
            Grid.SetRow(cnt, r); Grid.SetColumn(cnt, 1);
            grid.Children.Add(name); grid.Children.Add(cnt);
            r++;
        }
        return grid;
    }

    // A titled section: a subtitle + a spacing panel the caller fills.
    private (StackPanel Panel, Action<FrameworkElement> Add) Section(string title)
    {
        var panel = new StackPanel { Spacing = 6 };
        panel.Children.Add(new TextBlock
        {
            Text = title,
            Style = (Style)Application.Current.Resources["SubtitleTextBlockStyle"],
        });
        return (panel, panel.Children.Add);
    }

    private FrameworkElement Note(string text) => new TextBlock
    {
        Text = text,
        Foreground = (Microsoft.UI.Xaml.Media.Brush)
            Application.Current.Resources["TextFillColorSecondaryBrush"],
    };

    private static double? Num(JsonElement data, string key) =>
        data.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.Number
            ? v.GetDouble() : null;

    private static string Count(JsonElement data, string key) =>
        data.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.Number
            ? v.GetInt64().ToString(CultureInfo.InvariantCulture) : "0";

    private static string Pct(double? v) =>
        v is null ? "—" : v.Value.ToString("0.#", CultureInfo.InvariantCulture) + "%";

    private static string Scalar(JsonElement v) => v.ValueKind switch
    {
        JsonValueKind.String => v.GetString() ?? "",
        JsonValueKind.Number => v.ToString(),
        JsonValueKind.Null => "",
        _ => v.ToString(),
    };
}
