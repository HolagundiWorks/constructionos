using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using LiveChartsCore;
using LiveChartsCore.SkiaSharpView;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Money › Cash Flow — the lagged cash-flow forecast from GET /api/cashflow: the
/// weekly in/out/running-balance chart, the opening/closing totals, and the
/// flagged first week the balance goes negative. All figures from the Python
/// cashflow assembler; no maths in C#.
/// </summary>
public sealed partial class CashFlowPage : Page
{
    public CashFlowPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/cashflow");

            // The headline: when does the balance first go negative?
            var firstNeg = data.TryGetProperty("first_negative", out var fn)
                && fn.ValueKind == JsonValueKind.String ? fn.GetString() : null;
            if (!string.IsNullOrEmpty(firstNeg))
            {
                Warning.Title = "Cash gap ahead";
                Warning.Message = $"On this forecast the running balance first goes "
                                  + $"negative in the week of {firstNeg}. Pull receipts "
                                  + "forward or defer payments before then.";
                Warning.Severity = InfoBarSeverity.Warning;
                Warning.IsOpen = true;
            }
            else
            {
                Warning.Title = "Balance stays positive";
                Warning.Message = "The running balance does not go negative over the "
                                  + "forecast horizon.";
                Warning.Severity = InfoBarSeverity.Success;
                Warning.IsOpen = true;
            }

            Cards.Children.Clear();
            Cards.Children.Add(Ui.Stat("Opening", Money(data, "opening_balance")));
            Cards.Children.Add(Ui.Stat("Total in", Money(data, "total_in")));
            Cards.Children.Add(Ui.Stat("Total out", Money(data, "total_out")));
            Cards.Children.Add(Ui.Stat("Closing", Money(data, "closing_balance"),
                                       accent: true));

            // Chart: in / out columns with the running balance as a line.
            var labels = Arr(data, "labels");
            var inS = Nums(data, "series", "in");
            var outS = Nums(data, "series", "out");
            var bal = Nums(data, "series", "balance");
            Chart.Series = new ISeries[]
            {
                new ColumnSeries<double> { Name = "In", Values = inS },
                new ColumnSeries<double> { Name = "Out", Values = outS },
                new LineSeries<double> { Name = "Balance", Values = bal, Fill = null },
            };
            Chart.XAxes = new[] { new Axis { Labels = labels } };

            TableHost.Children.Clear();
            TableHost.Children.Add(Ui.Table(data, "buckets"));
        }
        catch (Exception ex)
        {
            Warning.Title = "Couldn't load cash flow";
            Warning.Message = ApiException.UserMessage(ex);
            Warning.Severity = InfoBarSeverity.Error;
            Warning.IsOpen = true;
        }
    }

    private static string Money(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? Ui.Rupees(v.GetDouble()) : "—";

    private static string[] Arr(JsonElement o, string k)
    {
        var list = new List<string>();
        if (o.TryGetProperty(k, out var a) && a.ValueKind == JsonValueKind.Array)
            foreach (var e in a.EnumerateArray())
                list.Add(e.ValueKind == JsonValueKind.String ? e.GetString() ?? "" : e.ToString());
        return list.ToArray();
    }

    private static double[] Nums(JsonElement o, string outer, string inner)
    {
        var list = new List<double>();
        if (o.TryGetProperty(outer, out var s) && s.ValueKind == JsonValueKind.Object
            && s.TryGetProperty(inner, out var a) && a.ValueKind == JsonValueKind.Array)
            foreach (var e in a.EnumerateArray())
                list.Add(e.ValueKind == JsonValueKind.Number ? e.GetDouble() : 0);
        return list.ToArray();
    }
}
