using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Controls.Primitives;   // ToggleButton
using Microsoft.UI.Text;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Accounts › Accounting — the three ledger views the backend exposes as JSON,
/// mirroring the desktop notebook: Profit &amp; Loss (GET /api/pnl), Balance
/// Sheet (GET /api/balance_sheet), and the Journal register (GET
/// /api/journal_entries). All figures come from the Python reports layer; no
/// accounting maths in C#. The period box scopes P&amp;L / Balance Sheet
/// (YYYY-MM, a financial year like 2025-26, "FY", or blank for all posted lines).
/// </summary>
public sealed partial class AccountingPage : Page
{
    private string _view = "pnl";

    public AccountingPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            Select(_view);
            await LoadAsync();
        };
    }

    private async void OnPickView(object sender, RoutedEventArgs e)
    {
        if (sender is ToggleButton tb && tb.Tag is string v && v != _view)
        {
            Select(v);
            await LoadAsync();
        }
        else if (sender is ToggleButton same)
        {
            same.IsChecked = true;   // can't toggle the active view off
        }
    }

    private void Select(string view)
    {
        _view = view;
        PnlTab.IsChecked = view == "pnl";
        BsTab.IsChecked = view == "balance_sheet";
        JournalTab.IsChecked = view == "journal";
        // The period box only scopes the two reports; the register ignores it.
        PeriodBox.Visibility = view == "journal" ? Visibility.Collapsed : Visibility.Visible;
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async void OnPeriodKeyDown(object sender, Microsoft.UI.Xaml.Input.KeyRoutedEventArgs e)
    {
        if (e.Key == Windows.System.VirtualKey.Enter) await LoadAsync();
    }

    private async Task LoadAsync()
    {
        Host.Children.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var data = await ApiClient.Default.GetJsonAsync(Endpoint());
            Host.Children.Clear();
            switch (_view)
            {
                case "journal": Host.Children.Add(Ui.Table(data)); break;
                case "balance_sheet": RenderStatement(data, balanceSheet: true); break;
                default: RenderStatement(data, balanceSheet: false); break;
            }
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

    private string Endpoint()
    {
        if (_view == "journal") return "api/journal_entries";
        var period = (PeriodBox.Text ?? "").Trim();
        var q = period.Length > 0 ? "?period=" + Uri.EscapeDataString(period) : "";
        return (_view == "balance_sheet" ? "api/balance_sheet" : "api/pnl") + q;
    }

    // Render a P&L / Balance Sheet payload: one titled block per section (rows of
    // particulars → amount, a section total), then a balancing summary line.
    private void RenderStatement(JsonElement data, bool balanceSheet)
    {
        if (data.TryGetProperty("sections", out var sections)
            && sections.ValueKind == JsonValueKind.Array)
            foreach (var s in sections.EnumerateArray())
                Host.Children.Add(SectionBlock(s));

        Host.Children.Add(balanceSheet ? BalanceSummary(data) : PnlSummary(data));
    }

    private FrameworkElement SectionBlock(JsonElement section)
    {
        var panel = new StackPanel { Spacing = 2, Margin = new Thickness(0, 8, 0, 0) };
        panel.Children.Add(new TextBlock
        {
            Text = section.TryGetProperty("title", out var t) ? t.GetString() : "",
            Style = (Style)Application.Current.Resources["SubtitleTextBlockStyle"],
        });

        var grid = new Grid { ColumnSpacing = 12 };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(160) });

        var r = 0;
        if (section.TryGetProperty("rows", out var rows) && rows.ValueKind == JsonValueKind.Array)
            foreach (var row in rows.EnumerateArray())
            {
                if (row.ValueKind != JsonValueKind.Array || row.GetArrayLength() < 2) continue;
                var cells = row.EnumerateArray().ToArray();
                AddLine(grid, r++, Scalar(cells[0]), Money(cells[1]), bold: false);
            }

        if (r == 0)
            panel.Children.Add(new TextBlock
            {
                Text = "No entries.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)
                    Application.Current.Resources["TextFillColorSecondaryBrush"],
                Margin = new Thickness(0, 2, 0, 0),
            });

        if (section.TryGetProperty("total", out var total))
            AddLine(grid, r++, "Total", Money(total), bold: true, rule: true);

        panel.Children.Add(grid);
        return panel;
    }

    private static void AddLine(Grid grid, int row, string label, string amount,
                                bool bold, bool rule = false)
    {
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var weight = bold ? FontWeights.SemiBold : FontWeights.Normal;
        // A TextBlock has no border in WinUI, so a ruled (total) row wraps each
        // cell in a Border that carries the top hairline.
        var name = Framed(new TextBlock { Text = label, FontWeight = weight }, rule);
        var amt = Framed(new TextBlock
        {
            Text = amount, TextAlignment = TextAlignment.Right, FontWeight = weight,
        }, rule);
        Grid.SetRow(name, row); Grid.SetColumn(name, 0);
        Grid.SetRow(amt, row); Grid.SetColumn(amt, 1);
        grid.Children.Add(name);
        grid.Children.Add(amt);
    }

    private static Border Framed(TextBlock tb, bool rule) => new()
    {
        Child = tb,
        Padding = new Thickness(0, rule ? 4 : 3, 0, 3),
        Margin = new Thickness(0, rule ? 1 : 0, 0, 0),
        BorderThickness = new Thickness(0, rule ? 1 : 0, 0, 0),
        BorderBrush = (Microsoft.UI.Xaml.Media.Brush)
            Application.Current.Resources["CardStrokeColorDefaultBrush"],
    };

    private FrameworkElement PnlSummary(JsonElement data)
    {
        var net = Num(data, "net_profit") ?? Num(data, "grand_total") ?? 0;
        var caption = net >= 0 ? "Net profit" : "Net loss";
        return SummaryBar(caption, Money(net), positive: net >= 0);
    }

    private FrameworkElement BalanceSummary(JsonElement data)
    {
        var balanced = data.TryGetProperty("balanced", out var b)
            && b.ValueKind == JsonValueKind.True;
        var assets = Num(data, "total_assets") ?? 0;
        var claims = Num(data, "total_liabilities_equity") ?? 0;
        var text = $"Assets {Money(assets)}   ·   Liabilities + Equity {Money(claims)}";
        return SummaryBar(balanced ? "Balanced" : "Out of balance", text,
                          positive: balanced);
    }

    private FrameworkElement SummaryBar(string caption, string value, bool positive)
    {
        var accent = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources[
            positive ? "SystemFillColorSuccessBrush" : "SystemFillColorCautionBrush"];
        var panel = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 12,
            Margin = new Thickness(0, 12, 0, 0),
        };
        panel.Children.Add(new TextBlock
        {
            Text = caption,
            Style = (Style)Application.Current.Resources["SubtitleTextBlockStyle"],
            Foreground = accent,
            VerticalAlignment = VerticalAlignment.Center,
        });
        panel.Children.Add(new TextBlock
        {
            Text = value,
            VerticalAlignment = VerticalAlignment.Center,
            Foreground = (Microsoft.UI.Xaml.Media.Brush)
                Application.Current.Resources["TextFillColorSecondaryBrush"],
        });
        return panel;
    }

    private static double? Num(JsonElement data, string key) =>
        data.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.Number
            ? v.GetDouble() : null;

    private static string Scalar(JsonElement v) => v.ValueKind switch
    {
        JsonValueKind.String => v.GetString() ?? "",
        JsonValueKind.Number => v.ToString(),
        JsonValueKind.Null => "",
        _ => v.ToString(),
    };

    // Rupee amount with the sign and Indian lakh/crore grouping (₹1,00,000.00).
    // Blank for a null cell.
    private static string Money(JsonElement v) => v.ValueKind == JsonValueKind.Number
        ? Money(v.GetDouble())
        : v.ValueKind == JsonValueKind.Null ? "" : Scalar(v);

    private static string Money(double d) => Ui.Rupees(d);
}
