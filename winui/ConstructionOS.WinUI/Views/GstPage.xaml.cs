using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
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

    private string _month = "";

    public GstPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    /// <summary>Save the CA export pack (GET /api/gst/export) — the same month
    /// shown on screen. The pack is assembled by the Python <c>gst_export.pack</c>
    /// (combined CSV over outward/HSN/inward/TDS, plus a printable HTML
    /// summary); C# only chooses which of the two to write.</summary>
    private async void OnExport(object sender, RoutedEventArgs e)
    {
        ExportButton.IsEnabled = false;
        try
        {
            var url = string.IsNullOrEmpty(_month)
                ? "api/gst/export" : $"api/gst/export?month={_month}";
            var pack = await ApiClient.Default.GetJsonAsync(url);

            var name = "ACO-GST-" + (string.IsNullOrEmpty(_month) ? "all" : _month);
            var path = await FileSave.TextAsync(name, Text(pack, "csv"),
                new Dictionary<string, string>
                {
                    [".csv"] = "CSV for the CA / Excel",
                    [".html"] = "Printable summary",
                });
            if (path is null) return;                       // cancelled

            // Honour the extension the user actually chose.
            if (path.EndsWith(".html", StringComparison.OrdinalIgnoreCase))
                await System.IO.File.WriteAllTextAsync(
                    path, Text(pack, "html"), new System.Text.UTF8Encoding(true));

            Notice.Title = "Export saved";
            Notice.Message = path;
            Notice.Severity = InfoBarSeverity.Success;
            Notice.IsOpen = true;
        }
        catch (Exception ex)
        {
            Notice.Title = "Couldn't export";
            Notice.Message = ApiException.UserMessage(ex);
            Notice.Severity = InfoBarSeverity.Error;
            Notice.IsOpen = true;
        }
        finally { ExportButton.IsEnabled = true; }
    }

    private static string Text(JsonElement o, string key) =>
        o.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.String
            ? v.GetString() ?? "" : "";

    private async Task LoadAsync()
    {
        Host.Children.Clear();
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/gst");
            var month = data.TryGetProperty("month", out var m) ? m.GetString() : null;
            _month = month ?? "";        // the export follows what's on screen
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
