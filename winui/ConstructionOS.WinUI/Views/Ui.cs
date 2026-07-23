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
        // id reads best first.
        if (cols.Remove("id")) cols.Insert(0, "id");

        var root = new Grid();
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        var header = RowGrid(cols, c => Pretty(c), isHeader: true);
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
            var rg = RowGrid(cols, c => r.TryGetValue(c, out var v) ? v : "", isHeader: false);
            rg.Padding = new Thickness(0, 2, 0, 2);
            list.Items.Add(rg);
        }
        Grid.SetRow(list, 1);
        root.Children.Add(list);
        return root;
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

    /// <summary>Header row (bold, prettified column titles) for a columnar list
    /// whose data rows are built with <see cref="DataRow"/> using the same
    /// <paramref name="cols"/> — so columns align.</summary>
    public static Grid HeaderRow(IReadOnlyList<string> cols)
    {
        var g = RowGrid(cols, Pretty, isHeader: true);
        g.Padding = new Thickness(12, 6, 12, 6);
        return g;
    }

    /// <summary>One data row for a columnar list (see <see cref="HeaderRow"/>).</summary>
    public static Grid DataRow(IReadOnlyList<string> cols, IReadOnlyDictionary<string, string> row)
    {
        var g = RowGrid(cols, c => row.TryGetValue(c, out var v) ? v : "", isHeader: false);
        g.Padding = new Thickness(12, 2, 12, 2);
        return g;
    }

    // A single grid row (header or data) with star columns so they align.
    private static Grid RowGrid(IReadOnlyList<string> cols, Func<string, string> value,
                                bool isHeader)
    {
        var g = new Grid { ColumnSpacing = 12 };
        for (var i = 0; i < cols.Count; i++)
            g.ColumnDefinitions.Add(new ColumnDefinition
            {
                Width = cols[i] == "id"
                    ? new GridLength(56)
                    : new GridLength(1, GridUnitType.Star),
            });
        for (var i = 0; i < cols.Count; i++)
        {
            var text = value(cols[i]);
            var tb = new TextBlock
            {
                Text = text,
                TextTrimming = TextTrimming.CharacterEllipsis,
                TextWrapping = TextWrapping.NoWrap,
            };
            if (isHeader)
            {
                tb.Style = (Style)Application.Current.Resources["CaptionTextBlockStyle"];
                tb.FontWeight = FontWeights.SemiBold;
                tb.Foreground = (Microsoft.UI.Xaml.Media.Brush)
                    Application.Current.Resources["TextFillColorSecondaryBrush"];
            }
            // Right-align numeric data cells (amounts/quantities read better on
            // the right). No reformatting — mangling years/pincodes/ids is worse
            // than plain numbers. The "id" column stays left with the header.
            else if (cols[i] != "id" && IsNumber(text))
            {
                tb.TextAlignment = TextAlignment.Right;
            }
            Grid.SetColumn(tb, i);
            g.Children.Add(tb);
        }
        return g;
    }

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

    // "net_payable" → "Net payable".
    private static string Pretty(string key)
    {
        if (string.IsNullOrEmpty(key)) return key;
        var s = key.Replace('_', ' ');
        return char.ToUpperInvariant(s[0]) + s[1..];
    }
}
