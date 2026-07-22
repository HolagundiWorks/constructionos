using System.Text;
using System.Text.Json;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// U4 charts page — surfaces KPI / dashboard keys from the API so LiveCharts
/// series can be bound on a Windows box. No business maths in C#.
/// </summary>
public sealed partial class ChartsPage : Page
{
    public ChartsPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            Status.Text = "Loading KPI…";
            try
            {
                var kpi = await ApiClient.Default.GetJsonAsync("api/kpi");
                var sb = new StringBuilder();
                sb.AppendLine("KPI payload keys (bind LiveCharts on Windows):");
                if (kpi.ValueKind == JsonValueKind.Object)
                {
                    foreach (var p in kpi.EnumerateObject())
                    {
                        var preview = p.Value.ValueKind switch
                        {
                            JsonValueKind.Number => p.Value.ToString(),
                            JsonValueKind.String => p.Value.GetString(),
                            JsonValueKind.Array => $"[{p.Value.GetArrayLength()} items]",
                            JsonValueKind.Object => "{…}",
                            _ => p.Value.ToString(),
                        };
                        sb.AppendLine($"  · {p.Name}: {preview}");
                    }
                }
                try
                {
                    var dash = await ApiClient.Default.GetJsonAsync("api/dashboard");
                    if (dash.TryGetProperty("advisories", out var adv)
                        && adv.ValueKind == JsonValueKind.Array)
                        sb.AppendLine($"Dashboard advisories: {adv.GetArrayLength()}");
                }
                catch
                {
                    // KPI alone is enough for the scaffold.
                }
                Status.Text = sb.ToString().Trim();
            }
            catch (Exception ex)
            {
                Status.Text = ApiException.UserMessage(ex);
            }
        };
    }
}
