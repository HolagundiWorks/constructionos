using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Text;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Shared UI helpers for turning an /api items array into a readable, aligned
/// columnar table (stock controls only — a header <see cref="Grid"/> over a
/// <see cref="ListView"/> of row grids, since CommunityToolkit DataGrid is
/// UWP-only and crashes WinUI 3).
/// </summary>
internal static class Ui
{
    private const int MaxCols = 10;

    /// <summary>
    /// An aligned columnar table for the items array in <paramref name="data"/>.
    /// Columns are the ordered union of row keys (id first, capped at 10);
    /// star-sized so they align across rows. Returns a friendly empty state when
    /// there are no rows.
    /// </summary>
    public static FrameworkElement Table(JsonElement data, params string[] keys)
    {
        if (!TryItems(data, keys, out var items))
            return Empty("Nothing to show yet.");

        var rows = new List<Dictionary<string, string>>();
        var cols = new List<string>();
        foreach (var item in items.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object) continue;
            var row = new Dictionary<string, string>();
            foreach (var p in item.EnumerateObject())
            {
                row[p.Name] = p.Value.ValueKind == JsonValueKind.Null ? "" : Cell(p.Value);
                if (!cols.Contains(p.Name) && cols.Count < MaxCols) cols.Add(p.Name);
            }
            rows.Add(row);
        }
        if (rows.Count == 0) return Empty("No records yet.");
        // Columns: prefer the server's curated [{key,label,align,type}] (CT-6),
        // else the form-field labels (masters / money docs from web_docs/web_masters),
        // else auto-derive from the row keys.
        var spec = ServerColumns(data) ?? FieldColumns(data);
        if (spec is null)
        {
            if (cols.Remove("id")) cols.Insert(0, "id");
            // No metadata at all — infer money columns from the key so amounts
            // still render in rupees.
            spec = cols.ConvertAll(k => Column(k, null));
        }

        var root = new Grid();
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        var header = SpecRow(spec, c => c.Label, isHeader: true);
        header.Padding = new Thickness(12, 6, 12, 6);
        header.BorderThickness = new Thickness(0, 0, 0, 1);
        header.BorderBrush = (Microsoft.UI.Xaml.Media.Brush)
            Application.Current.Resources["CardStrokeColorDefaultBrush"];
        Grid.SetRow(header, 0);
        root.Children.Add(header);

        var list = new ListView
        {
            SelectionMode = ListViewSelectionMode.Single,
            Padding = new Thickness(0, 4, 0, 4),
        };
        // Name the region from the server's curated label so a screen reader can
        // say which table it is ("Payroll, list") rather than an anonymous list.
        if (data.TryGetProperty("label", out var lbl)
            && lbl.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(lbl.GetString()))
            Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(list, lbl.GetString());
        foreach (var r in rows)
        {
            var rg = SpecRow(spec, c => r.TryGetValue(c.Key, out var v) ? v : "", isHeader: false);
            rg.Padding = new Thickness(0, 2, 0, 2);
            list.Items.Add(rg);
        }
        Grid.SetRow(list, 1);
        root.Children.Add(list);
        return root;
    }

    /// <summary>One rendered column: display key, human label, right-align,
    /// per-cell numeric auto-align, and a money flag (rupee formatting).</summary>
    public sealed record Col(string Key, string Label, bool Right,
                             bool AutoNumeric, bool Money);

    /// <summary>Build a column from a master/register field: the field's own
    /// label, right-aligned for numeric kinds, and money-formatted when the key
    /// names an amount. Null label falls back to a prettified key.</summary>
    public static Col Column(string key, string? label, string? kind = null)
    {
        var money = IsMoneyKey(key);
        var numeric = money || kind == "number";
        return new Col(key, string.IsNullOrEmpty(label) ? Pretty(key) : label!,
                       numeric, false, money);
    }

    // Parse the server's curated columns [{key,label,align}] (CT-6 uses "columns";
    // the look-ahead report uses "cols" — accept either). Null if none.
    private static List<Col>? ServerColumns(JsonElement data)
    {
        if ((!data.TryGetProperty("columns", out var cs) || cs.ValueKind != JsonValueKind.Array)
            && (!data.TryGetProperty("cols", out cs) || cs.ValueKind != JsonValueKind.Array))
            return null;
        if (cs.GetArrayLength() == 0)
            return null;
        var spec = new List<Col>();
        foreach (var c in cs.EnumerateArray())
        {
            if (c.ValueKind != JsonValueKind.Object) continue;
            var key = c.TryGetProperty("key", out var k) ? k.GetString() : null;
            if (string.IsNullOrEmpty(key)) continue;
            var label = c.TryGetProperty("label", out var l)
                && l.ValueKind == JsonValueKind.String ? l.GetString()! : Pretty(key!);
            var right = c.TryGetProperty("align", out var a)
                && a.ValueKind == JsonValueKind.String && a.GetString() == "right";
            var money = c.TryGetProperty("type", out var ty)
                && ty.ValueKind == JsonValueKind.String && ty.GetString() == "money";
            spec.Add(new Col(key!, label, right || money, false, money));
        }
        return spec.Count > 0 ? spec : null;
    }

    // Derive columns from a form-field array [{key,label,kind}] (masters / money
    // docs) — real field labels + money formatting, id first. Null if no fields.
    private static List<Col>? FieldColumns(JsonElement data)
    {
        if (!data.TryGetProperty("fields", out var fs)
            || fs.ValueKind != JsonValueKind.Array || fs.GetArrayLength() == 0)
            return null;
        var spec = new List<Col> { new("id", "ID", false, true, false) };
        foreach (var f in fs.EnumerateArray())
        {
            if (f.ValueKind != JsonValueKind.Object) continue;
            var key = f.TryGetProperty("key", out var k) ? k.GetString() : null;
            if (string.IsNullOrEmpty(key) || spec.Any(c => c.Key == key)) continue;
            var label = f.TryGetProperty("label", out var l)
                && l.ValueKind == JsonValueKind.String ? l.GetString() : null;
            var kind = f.TryGetProperty("kind", out var kd)
                && kd.ValueKind == JsonValueKind.String ? kd.GetString() : null;
            spec.Add(Column(key!, label, kind));
            if (spec.Count >= MaxCols) break;
        }
        return spec.Count > 1 ? spec : null;
    }

    // A grid row from a column spec (header labels or data values). Star columns
    // (id fixed narrow) so rows align; right-aligns numeric/marked columns.
    private static Grid SpecRow(IReadOnlyList<Col> spec,
                                Func<Col, string> text, bool isHeader)
    {
        var g = new Grid { ColumnSpacing = 12 };
        foreach (var s in spec)
            g.ColumnDefinitions.Add(new ColumnDefinition
            {
                Width = s.Key == "id"
                    ? new GridLength(56) : new GridLength(1, GridUnitType.Star),
            });
        // A stock ListView can't express a header↔cell relationship, so each data
        // row also announces itself as one labelled unit (WCAG 1.3.1): screen
        // readers hear "Date 01-07-2026, Labour Ramesh, Status Present".
        var spoken = isHeader ? null : new List<string>();
        for (var i = 0; i < spec.Count; i++)
        {
            var s = spec[i];
            var value = text(s);
            var tb = new TextBlock
            {
                TextTrimming = TextTrimming.CharacterEllipsis,
                TextWrapping = TextWrapping.NoWrap,
            };
            if (isHeader)
            {
                // Money columns carry the rupee sign in the header, so the cells
                // stay clean lakh/crore-grouped numbers.
                tb.Text = s.Money ? value + "  (₹)" : value;
                tb.Style = (Style)Application.Current.Resources["CaptionTextBlockStyle"];
                tb.FontWeight = FontWeights.SemiBold;
                tb.Foreground = (Microsoft.UI.Xaml.Media.Brush)
                    Application.Current.Resources["TextFillColorSecondaryBrush"];
                if (s.Right) tb.TextAlignment = TextAlignment.Right;
            }
            else if (s.Money && TryNum(value, out var mv))
            {
                tb.Text = Grouped(mv);              // 1,00,000.00 (Indian grouping)
                tb.TextAlignment = TextAlignment.Right;
            }
            else
            {
                tb.Text = value;
                if (s.Key != "id" && (s.Right || (s.AutoNumeric && IsNumber(value))))
                    tb.TextAlignment = TextAlignment.Right;
            }
            if (spoken != null && !string.IsNullOrWhiteSpace(tb.Text))
                spoken.Add($"{s.Label} {tb.Text}");
            Grid.SetColumn(tb, i);
            g.Children.Add(tb);
        }
        if (spoken is { Count: > 0 })
            Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(
                g, string.Join(", ", spoken));
        return g;
    }

    /// <summary>
    /// A columnar table from explicit <paramref name="headers"/> + positional
    /// string rows (for report endpoints that return arrays-of-arrays, e.g. GST).
    /// </summary>
    public static FrameworkElement TableFrom(
        IReadOnlyList<string> headers,
        IReadOnlyList<IReadOnlyList<string>> rows)
    {
        if (rows.Count == 0) return Empty("No records for this period.");

        Grid Row(Func<int, string> cell, bool head)
        {
            var g = new Grid
            {
                ColumnSpacing = 12,
                Padding = new Thickness(12, head ? 6 : 2, 12, head ? 6 : 2),
            };
            for (var i = 0; i < headers.Count; i++)
                g.ColumnDefinitions.Add(new ColumnDefinition
                { Width = new GridLength(1, GridUnitType.Star) });
            for (var i = 0; i < headers.Count; i++)
            {
                var tb = new TextBlock
                {
                    Text = cell(i),
                    TextTrimming = TextTrimming.CharacterEllipsis,
                    TextWrapping = TextWrapping.NoWrap,
                };
                if (head)
                {
                    tb.Style = (Style)Application.Current.Resources["CaptionTextBlockStyle"];
                    tb.FontWeight = FontWeights.SemiBold;
                    tb.Foreground = (Microsoft.UI.Xaml.Media.Brush)
                        Application.Current.Resources["TextFillColorSecondaryBrush"];
                }
                Grid.SetColumn(tb, i);
                g.Children.Add(tb);
            }
            return g;
        }

        var root = new Grid();
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        var header = Row(i => headers[i], head: true);
        header.BorderThickness = new Thickness(0, 0, 0, 1);
        header.BorderBrush = (Microsoft.UI.Xaml.Media.Brush)
            Application.Current.Resources["CardStrokeColorDefaultBrush"];
        Grid.SetRow(header, 0);
        root.Children.Add(header);
        var list = new ListView { SelectionMode = ListViewSelectionMode.None };
        foreach (var r in rows)
            list.Items.Add(Row(i => i < r.Count ? r[i] : "", head: false));
        Grid.SetRow(list, 1);
        root.Children.Add(list);
        return root;
    }

    /// <summary>Header row (bold labels; money columns get a "… (₹)" head) for a
    /// columnar list whose data rows are built with <see cref="DataRow"/> using
    /// the same <paramref name="cols"/> — so columns align.</summary>
    public static Grid HeaderRow(IReadOnlyList<Col> cols)
    {
        var g = SpecRow(cols, c => c.Label, isHeader: true);
        g.Padding = new Thickness(12, 6, 12, 6);
        return g;
    }

    /// <summary>One data row for a columnar list (see <see cref="HeaderRow"/>) —
    /// money cells rendered in rupees with Indian grouping.</summary>
    public static Grid DataRow(IReadOnlyList<Col> cols, IReadOnlyDictionary<string, string> row)
    {
        var g = SpecRow(cols, c => row.TryGetValue(c.Key, out var v) ? v : "", isHeader: false);
        g.Padding = new Thickness(12, 2, 12, 2);
        return g;
    }

    /// <summary>The standard "live register" page body: fetch an endpoint, show a
    /// loading ring, then render its items as a columnar table (or a friendly
    /// error). Keeps the register pages to a couple of lines each.</summary>
    public static async Task LoadTableAsync(Panel host, string endpoint,
                                            params string[] keys)
    {
        host.Children.Clear();
        host.Children.Add(Loading());
        try
        {
            var data = await ApiClient.Default.GetJsonAsync(endpoint);
            host.Children.Clear();
            host.Children.Add(Table(data, keys));
        }
        catch (Exception ex)
        {
            host.Children.Clear();
            host.Children.Add(new TextBlock
            {
                Text = ApiException.UserMessage(ex),
                TextWrapping = TextWrapping.Wrap,
                Foreground = (Microsoft.UI.Xaml.Media.Brush)
                    Application.Current.Resources["TextFillColorSecondaryBrush"],
            });
        }
    }

    // Windows' "Show animations" switch (Settings › Accessibility › Visual
    // effects). Read once — it is a per-session OS preference.
    private static readonly bool AnimationsOn = ReadAnimationsEnabled();

    private static bool ReadAnimationsEnabled()
    {
        try { return new Windows.UI.ViewManagement.UISettings().AnimationsEnabled; }
        catch { return true; }   // if we can't ask, don't take motion away
    }

    /// <summary>Honour the OS "show animations" preference on a chart (WCAG
    /// 2.3.3 Animation from interactions). When the user has animations off, the
    /// series snap into place instead of easing.</summary>
    public static void RespectMotion(LiveChartsCore.SkiaSharpView.WinUI.CartesianChart chart)
    {
        if (AnimationsOn) return;
        // Zero duration = the series snap straight to their final position.
        chart.AnimationsSpeed = TimeSpan.Zero;
    }

    /// <summary>Mark an element as a live region so screen readers announce it
    /// when it appears or changes (WCAG 4.1.3 Status messages). Polite for
    /// progress/empty states, assertive for errors.</summary>
    public static T Live<T>(T element, bool assertive = false) where T : DependencyObject
    {
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetLiveSetting(
            element,
            assertive
                ? Microsoft.UI.Xaml.Automation.Peers.AutomationLiveSetting.Assertive
                : Microsoft.UI.Xaml.Automation.Peers.AutomationLiveSetting.Polite);
        return element;
    }

    /// <summary>A centered progress ring for the "loading…" state while an API
    /// call is in flight (put it in the page's content host before the await).
    /// Named and announced — a silent spinner is invisible to a screen reader
    /// (WCAG 1.1.1 / 4.1.2 / 4.1.3).</summary>
    public static FrameworkElement Loading(string label = "Loading")
    {
        var ring = new ProgressRing
        {
            IsActive = true,
            Width = 32,
            Height = 32,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Top,
            Margin = new Thickness(0, 48, 0, 0),
        };
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(ring, label);
        return Live(ring);
    }

    private static FrameworkElement Empty(string message) => new TextBlock
    {
        Text = message,
        Foreground = (Microsoft.UI.Xaml.Media.Brush)
            Application.Current.Resources["TextFillColorSecondaryBrush"],
        Margin = new Thickness(4, 12, 4, 4),
    };

    /// <summary>A section subtitle above a table/block — sentence case, one
    /// elevation level (Fluent: hierarchy by type, not nested boxes). It is also
    /// a real <b>Level 2 heading</b> in the accessibility tree (WCAG 1.3.1) so a
    /// screen reader can jump between sections instead of reading a flat page.</summary>
    public static TextBlock SectionTitle(string text)
    {
        var tb = new TextBlock
        {
            Text = text,
            Style = (Style)Application.Current.Resources["SubtitleTextBlockStyle"],
            Margin = new Thickness(0, 8, 0, 0),
        };
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetHeadingLevel(
            tb, Microsoft.UI.Xaml.Automation.Peers.AutomationHeadingLevel.Level2);
        return tb;
    }

    /// <summary>The one error recipe (Fluent 2): an <see cref="InfoBar"/> at
    /// Error severity carrying a calm, status-aware sentence (missing endpoint vs
    /// permission vs session vs server) — never a stack trace, and never a fake
    /// empty table that reads as "zero work".</summary>
    public static FrameworkElement ErrorNote(Exception ex, string? title = null) =>
        Live(new InfoBar
        {
            Title = title ?? "Couldn't load this",
            Message = ApiException.UserMessage(ex),
            Severity = InfoBarSeverity.Error,
            IsOpen = true,
            IsClosable = false,
        }, assertive: true);   // a failure interrupts — WCAG 4.1.3

    /// <summary>The one "no data yet" recipe — honestly empty, with the next
    /// step. Distinct from an error and from a missing endpoint.</summary>
    public static FrameworkElement EmptyNote(string message) => Live(new TextBlock
    {
        Text = message,
        TextWrapping = TextWrapping.Wrap,
        Foreground = (Microsoft.UI.Xaml.Media.Brush)
            Application.Current.Resources["TextFillColorSecondaryBrush"],
        Margin = new Thickness(0, 8, 0, 0),
    });

    /// <summary>A headline stat card — a big value over a caption. The value is
    /// tinted with the brand accent when <paramref name="accent"/>.</summary>
    public static FrameworkElement Stat(string caption, string value, bool accent = false)
    {
        var stack = new StackPanel { Spacing = 2 };
        stack.Children.Add(new TextBlock
        {
            Text = value,
            Style = (Style)Application.Current.Resources["TitleTextBlockStyle"],
            Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources[
                accent ? "AccentTextFillColorPrimaryBrush" : "TextFillColorPrimaryBrush"],
        });
        stack.Children.Add(new TextBlock
        {
            Text = caption,
            Style = (Style)Application.Current.Resources["CaptionTextBlockStyle"],
            Foreground = (Microsoft.UI.Xaml.Media.Brush)
                Application.Current.Resources["TextFillColorSecondaryBrush"],
        });
        var card = new Border
        {
            Child = stack,
            Background = (Microsoft.UI.Xaml.Media.Brush)
                Application.Current.Resources["CardBackgroundFillColorDefaultBrush"],
            BorderBrush = (Microsoft.UI.Xaml.Media.Brush)
                Application.Current.Resources["CardStrokeColorDefaultBrush"],
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(16, 12, 16, 12),
            MinWidth = 130,
        };
        // WCAG 4.1.2 — announce the pair as one fact ("Receivable: ₹70,000"),
        // not two orphaned strings.
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(card, $"{caption}: {value}");
        return card;
    }

    /// <summary>A horizontal strip of stat cards.</summary>
    public static FrameworkElement StatStrip(IEnumerable<(string Caption, string Value)> stats)
    {
        var host = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 12 };
        foreach (var (c, v) in stats) host.Children.Add(Stat(c, v));
        return host;
    }

    private static bool TryItems(JsonElement data, string[] keys, out JsonElement items)
    {
        items = default;
        foreach (var k in (keys.Length > 0 ? keys : new[] { "items" }))
            if (data.TryGetProperty(k, out items) && items.ValueKind == JsonValueKind.Array)
                return true;
        // Some endpoints return a bare array.
        if (data.ValueKind == JsonValueKind.Array) { items = data; return true; }
        return false;
    }

    // JSON scalar → display string (numbers without quotes, etc.).
    private static string Cell(JsonElement v) => v.ValueKind switch
    {
        JsonValueKind.String => v.GetString() ?? "",
        JsonValueKind.Number => v.ToString(),
        JsonValueKind.True => "yes",
        JsonValueKind.False => "no",
        JsonValueKind.Null => "",
        _ => v.ToString(),
    };

    private static bool IsNumber(string s) =>
        !string.IsNullOrEmpty(s)
        && double.TryParse(s, System.Globalization.NumberStyles.Any,
            System.Globalization.CultureInfo.InvariantCulture, out _);

    // Indian English culture: the rupee sign + lakh/crore grouping (3;2), so
    // 1234567.5 renders 12,34,567.50 / ₹12,34,567.50 without a hand-rolled grouper.
    private static readonly System.Globalization.CultureInfo InIn =
        System.Globalization.CultureInfo.GetCultureInfo("en-IN");

    /// <summary>A rupee amount with the sign and Indian lakh/crore grouping
    /// (₹1,00,000.00) — for standalone figures (KPI cards, summary lines).</summary>
    public static string Rupees(double d) => d.ToString("C2", InIn);

    /// <summary>Rupees with the sign, or the raw string if it isn't numeric.</summary>
    public static string Rupees(string s) => TryNum(s, out var d) ? Rupees(d) : s;

    // Lakh/crore-grouped number, two decimals, no sign (money table cells; the
    // column header carries the ₹).
    private static string Grouped(double d) => d.ToString("N2", InIn);

    private static bool TryNum(string s, out double d) =>
        double.TryParse(s, System.Globalization.NumberStyles.Any,
            System.Globalization.CultureInfo.InvariantCulture, out d);

    // Money-like column keys (token match, so "generated_at" isn't caught by
    // "rate"). Mirrors web_tables._MONEY_HINTS for endpoints without type metadata.
    private static readonly HashSet<string> MoneyWords = new(StringComparer.OrdinalIgnoreCase)
    {
        "amount", "amt", "total", "rate", "gross", "deduction", "net", "debit",
        "credit", "value", "payable", "price", "cost", "balance", "wage", "wages",
        "salary", "subtotal", "tax", "billed", "settled", "outstanding",
        "receivable", "payable",
    };

    private static bool IsMoneyKey(string key)
    {
        foreach (var tok in key.Split('_'))
            if (MoneyWords.Contains(tok)) return true;
        return false;
    }

    // "net_payable" → "Net payable".
    private static string Pretty(string key)
    {
        if (string.IsNullOrEmpty(key)) return key;
        var s = key.Replace('_', ' ');
        return char.ToUpperInvariant(s[0]) + s[1..];
    }
}
