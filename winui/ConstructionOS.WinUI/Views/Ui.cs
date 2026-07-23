using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Text;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Shared UI helpers for turning an /api items array into a readable, aligned
/// columnar table (stock controls only — a header <see cref="Grid"/> over a
/// <see cref="ListView"/> of row grids, since CommunityToolkit DataGrid is
/// UWP-only and crashes WinUI 3). <see cref="Lines"/> is kept for the few call
/// sites that still want one string per row.
/// </summary>
internal static class Ui
{
    private const int MaxCols = 10;

    /// <summary>One "key: value    …" string per row (legacy list rendering).</summary>
    public static List<string> Lines(JsonElement data, params string[] keys)
    {
        var rows = new List<string>();
        if (!TryItems(data, keys, out var items)) return rows;
        foreach (var item in items.EnumerateArray())
        {
            var parts = new List<string>();
            foreach (var p in item.EnumerateObject())
                if (p.Value.ValueKind != JsonValueKind.Null)
                    parts.Add($"{p.Name}: {Cell(p.Value)}");
            rows.Add(string.Join("    ", parts));
        }
        return rows;
    }

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
            Grid.SetColumn(tb, i);
            g.Children.Add(tb);
        }
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

    /// <summary>A centered progress ring for the "loading…" state while an API
    /// call is in flight (put it in the page's content host before the await).</summary>
    public static FrameworkElement Loading() => new ProgressRing
    {
        IsActive = true,
        Width = 32,
        Height = 32,
        HorizontalAlignment = HorizontalAlignment.Center,
        VerticalAlignment = VerticalAlignment.Top,
        Margin = new Thickness(0, 48, 0, 0),
    };

    private static FrameworkElement Empty(string message) => new TextBlock
    {
        Text = message,
        Foreground = (Microsoft.UI.Xaml.Media.Brush)
            Application.Current.Resources["TextFillColorSecondaryBrush"],
        Margin = new Thickness(4, 12, 4, 4),
    };

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
        "salary", "subtotal", "tax",
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
