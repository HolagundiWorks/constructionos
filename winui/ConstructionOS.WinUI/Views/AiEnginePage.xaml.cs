using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// AI engine — what the on-device engine is and whether it's running: the
/// provider (Foundry Local / Azure) from GET /api/agents/provider, the model
/// sidecars from /api/sidecar/status, and the agent + workflow catalog from
/// /api/agents. Read-only status; every agent still proposes and a human
/// approves anything that moves money or a date.
/// </summary>
public sealed partial class AiEnginePage : Page
{
    public AiEnginePage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        Host.Children.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var agents = await ApiClient.Default.GetJsonAsync("api/agents");
            Host.Children.Clear();

            await AddProviderAsync();
            await AddSidecarsAsync();

            if (agents.TryGetProperty("note", out var note)
                && note.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(note.GetString()))
                Host.Children.Add(new TextBlock
                {
                    Text = note.GetString(),
                    TextWrapping = TextWrapping.Wrap,
                    Foreground = (Microsoft.UI.Xaml.Media.Brush)
                        Application.Current.Resources["TextFillColorSecondaryBrush"],
                });

            Host.Children.Add(Ui.SectionTitle("Agents"));
            Host.Children.Add(Ui.Table(agents, "items"));
            Host.Children.Add(Ui.SectionTitle("Workflows"));
            Host.Children.Add(Ui.Table(agents, "workflows"));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }

    // Which provider is active, and is the local model actually there?
    private async Task AddProviderAsync()
    {
        try
        {
            var p = await ApiClient.Default.GetJsonAsync("api/agents/provider");
            var active = p.TryGetProperty("active", out var a) ? a.GetString() : null;
            var local = p.TryGetProperty("foundry_local", out var fl)
                && fl.ValueKind == JsonValueKind.Object ? fl : default;
            var available = local.ValueKind == JsonValueKind.Object
                && local.TryGetProperty("available", out var av)
                && av.ValueKind == JsonValueKind.True;
            var model = local.ValueKind == JsonValueKind.Object
                && local.TryGetProperty("model", out var m) ? m.GetString() : null;

            Host.Children.Add(new InfoBar
            {
                Title = available ? "AI engine is running" : "AI engine is off",
                Message = available
                    ? $"Provider {active}; model {model}. Ask questions on the "
                      + "Assistant page."
                    : "Start the local engine (Foundry) to use the Assistant's "
                      + "text-to-SQL. The exact quick answers work without it.",
                IsOpen = true,
                IsClosable = false,
                Severity = available ? InfoBarSeverity.Success : InfoBarSeverity.Informational,
            });
        }
        catch
        {
            // Provider status is a courtesy — the catalog below still renders.
        }
    }

    // OCR / STT / VLM sidecars: stub until real weights are installed locally.
    private async Task AddSidecarsAsync()
    {
        try
        {
            var s = await ApiClient.Default.GetJsonAsync("api/sidecar/status");
            if (!s.TryGetProperty("sidecars", out var side)
                || side.ValueKind != JsonValueKind.Object) return;
            var stats = new List<(string, string)>();
            foreach (var p in side.EnumerateObject())
            {
                var live = p.Value.TryGetProperty("available", out var av)
                    && av.ValueKind == JsonValueKind.True;
                stats.Add((p.Name.ToUpperInvariant(), live ? "Live" : "Stub"));
            }
            if (stats.Count == 0) return;
            Host.Children.Add(Ui.SectionTitle("Model sidecars"));
            Host.Children.Add(Ui.StatStrip(stats));
        }
        catch
        {
            // Sidecars are optional.
        }
    }
}
