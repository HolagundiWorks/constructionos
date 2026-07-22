using System.Text.Json;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class ProcessPage : Page
{
    public ProcessPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            Status.Text = "Loading workflow…";
            try
            {
                var data = await ApiClient.Default.GetJsonAsync("api/workflow");
                var lines = new List<string>();
                if (data.TryGetProperty("progress", out var progress)
                    && progress.ValueKind == JsonValueKind.Object)
                {
                    foreach (var flow in progress.EnumerateObject())
                    {
                        var pct = flow.Value.TryGetProperty("pct", out var p)
                            ? p.ToString() : "—";
                        var next = "";
                        if (flow.Value.TryGetProperty("next", out var n)
                            && n.ValueKind == JsonValueKind.Object)
                            next = JsonRows.Prop(n, "label");
                        lines.Add($"{flow.Name}: {pct}% — next: {next}");
                    }
                }
                Flows.ItemsSource = lines;
                Status.Text = lines.Count == 0
                    ? "No workflow progress yet."
                    : $"{lines.Count} flow(s).";
            }
            catch (Exception ex)
            {
                Status.Text = ApiException.UserMessage(ex);
                Flows.ItemsSource = null;
            }
        };
    }
}
