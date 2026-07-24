using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Accounts › GST &amp; TDS — the monthly GST/TDS report from GET /api/gst
/// (computed by the Python <c>gst.py</c>; no maths in C#). Four labelled sections
/// (outward, HSN, inward, TDS) rendered as tables with totals. Column headers
/// mirror gst.py's row order.
/// </summary>
public sealed partial class GstPage : Page
{
    private static readonly string[] Outward =
        { "Source", "No", "Date", "Party", "Taxable", "CGST", "SGST", "IGST", "Total" };
    private static readonly string[] Hsn =
        { "HSN/SAC", "Taxable", "CGST", "SGST", "IGST", "Tax" };
    private static readonly string[] Inward =
        { "No", "Date", "Party", "Taxable", "CGST", "SGST", "IGST", "Total" };
    private static readonly string[] Tds =
        { "No", "Date", "Party", "Taxable", "TDS %", "TDS" };

    public GstPage()
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
            var data = await ApiClient.Default.GetJsonAsync("api/gst");
            var month = data.TryGetProperty("month", out var m) ? m.GetString() : null;
            TitleText.Text = string.IsNullOrEmpty(month) ? "GST & TDS" : $"GST & TDS — {month}";

            AddSection("Outward supply (sales)", Outward, data, "outward", withTotal: true);
            AddSection("HSN / SAC summary", Hsn, data, "hsn", withTotal: false);
            AddSection("Inward supply (purchases)", Inward, data, "inward", withTotal: true);
            AddSection("TDS on vendor invoices", Tds, data, "tds", withTotal: false);
        }
        catch (Exception ex)
        {
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }

    private void AddSection(string title, string[] headers, JsonElement data,
                            string key, bool withTotal)
    {
        Host.Children.Add(new TextBlock
        {
            Text = title,
            Style = (Style)Application.Current.Resources["SubtitleTextBlockStyle"],
            Margin = new Thickness(0, 8, 0, 0),
        });
        if (!data.TryGetProperty(key, out var section))
        {
            Host.Children.Add(Note("No data."));
            return;
        }
        var rows = Rows(section);
        Host.Children.Add(Ui.TableFrom(headers, rows));

        var totalLine = Totals(section);
        if (totalLine.Length > 0) Host.Children.Add(Note(totalLine));
    }

    private static List<IReadOnlyList<string>> Rows(JsonElement section)
    {
        var rows = new List<IReadOnlyList<string>>();
        if (section.TryGetProperty("rows", out var arr) && arr.ValueKind == JsonValueKind.Array)
            foreach (var r in arr.EnumerateArray())
            {
                var cells = new List<string>();
                if (r.ValueKind == JsonValueKind.Array)
                    foreach (var c in r.EnumerateArray()) cells.Add(Scalar(c));
                else cells.Add(Scalar(r));
                rows.Add(cells);
            }
        return rows;
    }

    private static string Totals(JsonElement section)
    {
        if (section.TryGetProperty("total", out var t))   // TDS: single total
            return "Total TDS: " + Scalar(t);
        if (!section.TryGetProperty("totals", out var tot)
            || tot.ValueKind != JsonValueKind.Object) return "";
        var parts = new List<string>();
        foreach (var p in tot.EnumerateObject())
            parts.Add($"{Cap(p.Name)} {Scalar(p.Value)}");
        return parts.Count > 0 ? "Totals — " + string.Join("   ", parts) : "";
    }

    private TextBlock Note(string text) => new()
    {
        Text = text,
        Foreground = (Microsoft.UI.Xaml.Media.Brush)
            Application.Current.Resources["TextFillColorSecondaryBrush"],
        Margin = new Thickness(12, 2, 0, 6),
    };

    private static string Scalar(JsonElement v) => v.ValueKind switch
    {
        JsonValueKind.String => v.GetString() ?? "",
        JsonValueKind.Number => v.GetDouble().ToString("N2"),
        _ => v.ToString(),
    };

    private static string Cap(string s) =>
        string.IsNullOrEmpty(s) ? s : char.ToUpperInvariant(s[0]) + s[1..];
}
