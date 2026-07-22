using System.Text.Json;
using Microsoft.UI.Xaml.Controls;
using LiveChartsCore;
using LiveChartsCore.SkiaSharpView;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// U4 charts — the money snapshot (GET /api/kpi) as a column series and the
/// cash-flow forecast (GET /api/cashflow: in/out columns + running-balance line)
/// on stock LiveCharts. No maths in C#: the API computes and shapes the arrays.
/// </summary>
public sealed partial class ChartsPage : Page
{
    private static readonly (string Label, string Key)[] Bars =
    {
        ("Cash", "cash"),
        ("Receivable", "receivable"),
        ("Payable", "payable"),
        ("Net", "net_position"),
        ("Billed (mo)", "billed_month"),
        ("Collected (mo)", "collected_month"),
    };

    public ChartsPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            await LoadKpiAsync();
            await LoadCashflowAsync();
        };
    }

    private async Task LoadKpiAsync()
    {
        Status.Text = "Loading KPI…";
        try
        {
            var kpi = await ApiClient.Default.GetJsonAsync("api/kpi");
            var snap = kpi.TryGetProperty("snapshot", out var s) ? s : kpi;
            var values = new double[Bars.Length];
            for (var i = 0; i < Bars.Length; i++)
                values[i] = Number(snap, Bars[i].Key);

            Chart.Series = new ISeries[]
            {
                new ColumnSeries<double> { Name = "₹", Values = values },
            };
            Chart.XAxes = new[]
            {
                new Axis { Labels = Bars.Select(b => b.Label).ToArray() },
            };
            Chart.YAxes = new[] { new Axis { Name = "₹" } };

            Status.Text = values.All(v => v == 0)
                ? "No money recorded yet — bars populate as payments, bills and "
                  + "invoices are entered."
                : string.Join("    ",
                    Bars.Select((b, i) => $"{b.Label}: ₹{values[i]:N0}"));
        }
        catch (Exception ex)
        {
            Caption.Text = "Couldn't load KPIs.";
            Status.Text = ApiException.UserMessage(ex);
        }
    }

    private async Task LoadCashflowAsync()
    {
        try
        {
            var cf = await ApiClient.Default.GetJsonAsync("api/cashflow");
            var labels = StrArray(cf, "labels");
            var series = cf.TryGetProperty("series", out var s) ? s : default;

            CashChart.Series = new ISeries[]
            {
                new ColumnSeries<double> { Name = "In", Values = NumArray(series, "in") },
                new ColumnSeries<double> { Name = "Out", Values = NumArray(series, "out") },
                new LineSeries<double> { Name = "Balance", Values = NumArray(series, "balance"), Fill = null },
            };
            CashChart.XAxes = new[] { new Axis { Labels = labels } };
            CashChart.YAxes = new[] { new Axis { Name = "₹" } };
            if (labels.Length == 0)
                CashCaption.Text = "No cash-flow to project yet — record some "
                    + "receivables / payables first.";
        }
        catch (Exception ex)
        {
            CashCaption.Text = "Cash-flow forecast unavailable — "
                + ApiException.UserMessage(ex);
        }
    }

    private static string[] StrArray(JsonElement obj, string key) =>
        obj.TryGetProperty(key, out var a) && a.ValueKind == JsonValueKind.Array
            ? a.EnumerateArray().Select(e => e.GetString() ?? "").ToArray()
            : Array.Empty<string>();

    private static double[] NumArray(JsonElement obj, string key)
    {
        if (obj.ValueKind == JsonValueKind.Object
            && obj.TryGetProperty(key, out var a)
            && a.ValueKind == JsonValueKind.Array)
            return a.EnumerateArray()
                .Select(e => e.ValueKind == JsonValueKind.Number ? e.GetDouble() : 0.0)
                .ToArray();
        return Array.Empty<double>();
    }

    private static double Number(JsonElement obj, string key) =>
        obj.ValueKind == JsonValueKind.Object
        && obj.TryGetProperty(key, out var v)
        && v.ValueKind == JsonValueKind.Number
            ? v.GetDouble() : 0;
}
