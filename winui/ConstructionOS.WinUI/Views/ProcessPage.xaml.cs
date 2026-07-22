using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class ProcessPage : Page
{
    public ProcessPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            try
            {
                var data = await ApiClient.Default.GetJsonAsync("api/workflow");
                var lines = new List<string>();
                if (data.TryGetProperty("progress", out var progress))
                {
                    foreach (var flow in progress.EnumerateObject())
                    {
                        var pct = flow.Value.TryGetProperty("pct", out var p)
                            ? p.ToString() : "—";
                        var next = "";
                        if (flow.Value.TryGetProperty("next", out var n)
                            && n.ValueKind == System.Text.Json.JsonValueKind.Object
                            && n.TryGetProperty("label", out var lab))
                            next = lab.GetString() ?? "";
                        lines.Add($"{flow.Name}: {pct}% — next: {next}");
                    }
                }
                Flows.ItemsSource = lines;
                Status.Text = "Workflow progress";
            }
            catch (Exception ex)
            {
                Status.Text = ex.Message;
            }
        };
    }
}
