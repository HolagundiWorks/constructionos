using System.Text.Json;
using Microsoft.UI.Xaml.Controls;
using LiveChartsCore;
using LiveChartsCore.SkiaSharpView;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// U4 charts — KPI columns, cash-flow lines, ageing columns. All series from
/// the Python JSON API; no business maths in C#.
/// </summary>
public sealed partial class ChartsPage : Page
{
    private static readonly (string Label, string Key)[] KpiBars =
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
        Loaded += async (_, _) => await LoadAllAsync();
    }

    async Task LoadAllAsync()
    {
        await LoadKpiAsync();
        await LoadCashflowAsync();
        await LoadAgeingAsync();
    }

    async Task LoadKpiAsync()
    {
        KpiStatus.Text = "Loading KPI…";
        try
        {
            var kpi = await ApiClient.Default.GetJsonAsync("api/kpi");
            var snap = kpi.TryGetProperty("snapshot", out var s) ? s : kpi;
            var values = new double[KpiBars.Length];
            for (var i = 0; i < KpiBars.Length; i++)
                values[i] = Number(snap, KpiBars[i].Key);

            KpiChart.Series = new ISeries[]
            {
                new ColumnSeries<double> { Name = "₹", Values = values },
            };
            KpiChart.XAxes = new[]
            {
                new Axis { Labels = KpiBars.Select(b => b.Label).ToArray() },
            };
            KpiChart.YAxes = new[] { new Axis { Name = "₹" } };

            var allZero = values.All(v => v == 0);
            KpiStatus.Text = allZero
                ? "No money recorded yet — bars populate as payments and bills land."
                : string.Join("    ",
                    KpiBars.Select((b, i) => $"{b.Label}: ₹{values[i]:N0}"));
        }
        catch (Exception ex)
        {
            KpiCaption.Text = "Couldn't load KPIs.";
            KpiStatus.Text = ApiException.UserMessage(ex);
        }
    }

    async Task LoadCashflowAsync()
    {
        CashflowStatus.Text = "Loading cash-flow…";
        try
        {
            var data = await ApiClient.Default.GetJsonAsync(
                "api/cashflow?periods=8&mode=week");
            if (!data.TryGetProperty("buckets", out var buckets)
                || buckets.ValueKind != JsonValueKind.Array)
            {
                CashflowStatus.Text = "No cash-flow buckets.";
                return;
            }
            var labels = new List<string>();
            var inflow = new List<double>();
            var outflow = new List<double>();
            var balance = new List<double>();
            foreach (var b in buckets.EnumerateArray())
            {
                var start = b.TryGetProperty("start", out var st) ? st.ToString() : "";
                labels.Add(start.Length >= 10 ? start[..10] : start);
                inflow.Add(Number(b, "in"));
                outflow.Add(Number(b, "out"));
                balance.Add(Number(b, "balance"));
            }
            CashflowChart.Series = new ISeries[]
            {
                new ColumnSeries<double> { Name = "In", Values = inflow },
                new ColumnSeries<double> { Name = "Out", Values = outflow },
                new LineSeries<double> { Name = "Balance", Values = balance },
            };
            CashflowChart.XAxes = new[] { new Axis { Labels = labels.ToArray() } };
            CashflowChart.YAxes = new[] { new Axis { Name = "₹" } };

            var closing = data.TryGetProperty("closing_balance", out var c)
                ? c.ToString() : "—";
            var warn = data.TryGetProperty("first_negative", out var fn)
                       && fn.ValueKind != JsonValueKind.Null
                ? $"  ·  first shortfall: {fn}"
                : "";
            CashflowStatus.Text = $"Closing ₹{closing}{warn}";
        }
        catch (Exception ex)
        {
            CashflowStatus.Text = ApiException.UserMessage(ex);
        }
    }

    async Task LoadAgeingAsync()
    {
        AgeingStatus.Text = "Loading ageing…";
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/ageing");
            var labels = new List<string>();
            var amounts = new List<double>();
            if (data.TryGetProperty("buckets", out var buckets)
                && buckets.ValueKind == JsonValueKind.Array)
            {
                foreach (var b in buckets.EnumerateArray())
                {
                    labels.Add(b.TryGetProperty("label", out var lab)
                        ? lab.GetString() ?? "" : "");
                    amounts.Add(Number(b, "amount"));
                }
            }
            AgeingChart.Series = new ISeries[]
            {
                new ColumnSeries<double> { Name = "Open", Values = amounts },
            };
            AgeingChart.XAxes = new[] { new Axis { Labels = labels.ToArray() } };
            AgeingChart.YAxes = new[] { new Axis { Name = "₹" } };
            var total = data.TryGetProperty("total", out var t) ? t.ToString() : "—";
            AgeingStatus.Text = labels.Count == 0
                ? "No ageing buckets."
                : $"Total open ₹{total}";
        }
        catch (Exception ex)
        {
            AgeingStatus.Text = ApiException.UserMessage(ex);
        }
    }

    static double Number(JsonElement obj, string key) =>
        obj.ValueKind == JsonValueKind.Object
        && obj.TryGetProperty(key, out var v)
        && v.ValueKind == JsonValueKind.Number
            ? v.GetDouble() : 0;
}
