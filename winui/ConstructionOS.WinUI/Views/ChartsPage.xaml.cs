using System.Text.Json;
using Microsoft.UI.Xaml.Controls;
using LiveChartsCore;
using LiveChartsCore.SkiaSharpView;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// U4 charts page — plots the money snapshot from GET /api/kpi as a stock
/// LiveCharts column series. No business maths in C#: the API computes every
/// figure; this only renders what it returns.
/// </summary>
public sealed partial class ChartsPage : Page
{
    // (label shown on the axis, JSON key in the /api/kpi snapshot)
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

                var allZero = values.All(v => v == 0);
                Status.Text = allZero
                    ? "No money recorded yet — bars populate as payments, bills "
                      + "and invoices are entered."
                    : string.Join("    ",
                        Bars.Select((b, i) => $"{b.Label}: ₹{values[i]:N0}"));
            }
            catch (Exception ex)
            {
                Caption.Text = "Couldn't load KPIs.";
                Status.Text = ApiException.UserMessage(ex);
            }
        };
    }

    private static double Number(JsonElement obj, string key) =>
        obj.ValueKind == JsonValueKind.Object
        && obj.TryGetProperty(key, out var v)
        && v.ValueKind == JsonValueKind.Number
            ? v.GetDouble() : 0;
}
