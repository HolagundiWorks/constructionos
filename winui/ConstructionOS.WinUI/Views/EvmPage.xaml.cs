using System.Text.Json;
using Microsoft.UI.Xaml.Controls;
using LiveChartsCore;
using LiveChartsCore.SkiaSharpView;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Earned Value — per-project cost (CPI) and schedule (SPI) performance as a
/// stock LiveCharts grouped column chart, over a portfolio summary line, with
/// the full per-project detail below. All figures from GET /api/evm
/// ({rows, portfolio}); no EVM maths in C#.
/// </summary>
public sealed partial class EvmPage : Page
{
    public EvmPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async Task LoadAsync()
    {
        Status.Text = "Loading earned value…";
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/evm");

            var names = new List<string>();
            var cpi = new List<double?>();
            var spi = new List<double?>();
            if (data.TryGetProperty("rows", out var rows)
                && rows.ValueKind == JsonValueKind.Array)
            {
                foreach (var row in rows.EnumerateArray())
                {
                    names.Add(Str(row, "name"));
                    cpi.Add(Num(row, "cpi"));   // null ⇒ a gap (AC not booked yet)
                    spi.Add(Num(row, "spi"));
                }
            }

            Chart.Series = new ISeries[]
            {
                new ColumnSeries<double?> { Name = "CPI (cost)", Values = cpi },
                new ColumnSeries<double?> { Name = "SPI (schedule)", Values = spi },
            };
            Chart.XAxes = new[] { new Axis { Labels = names.ToArray() } };

            if (data.TryGetProperty("portfolio", out var p)
                && p.ValueKind == JsonValueKind.Object)
            {
                Summary.Text = string.Format(
                    "{0} project(s) measured  ·  portfolio CPI {1}  ·  SPI {2}  ·  "
                    + "{3} over cost  ·  {4} behind  ·  1.0 = on plan",
                    Int(p, "projects"), Idx(p, "cpi"), Idx(p, "spi"),
                    Int(p, "over_cost"), Int(p, "behind_schedule"));
            }

            Detail.Children.Clear();
            Detail.Children.Add(Ui.Table(data, "rows"));   // per-project EVM table
            Status.Text = names.Count == 0
                ? "No projects with a contract value or budget yet — add one to "
                  + "measure earned value against it."
                : "";
        }
        catch (Exception ex)
        {
            Status.Text = ApiException.UserMessage(ex);
        }
    }

    private static string Str(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) ? v.GetString() ?? "" : "";

    private static double? Num(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? v.GetDouble() : (double?)null;

    private static int Int(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.TryGetInt32(out var i) ? i : 0;

    private static string Idx(JsonElement o, string k)
    {
        var n = Num(o, k);
        return n.HasValue ? n.Value.ToString("0.00") : "—";
    }
}
