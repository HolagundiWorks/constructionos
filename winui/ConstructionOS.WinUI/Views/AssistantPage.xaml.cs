using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Assistant — read-only, plain-language questions over your own data (GET
/// /api/assistant/quick for the exact no-model figures; POST /api/assistant for a
/// text-to-SQL turn). The SQL runs read-only in the Python pipeline; an answer is
/// the model's summary over real rows, or an honest "turn on the AI engine" note.
/// </summary>
public sealed partial class AssistantPage : Page
{
    public AssistantPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadQuickAsync();
    }

    private async Task LoadQuickAsync()
    {
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/assistant/quick");
            Quick.Children.Clear();
            if (data.TryGetProperty("items", out var items)
                && items.ValueKind == JsonValueKind.Array)
                foreach (var i in items.EnumerateArray())
                {
                    var label = i.TryGetProperty("label", out var l) ? l.GetString() : "";
                    var value = i.TryGetProperty("value", out var v)
                        && v.ValueKind == JsonValueKind.Number ? Ui.Rupees(v.GetDouble()) : "—";
                    Quick.Children.Add(Ui.Stat(label ?? "", value));
                }
        }
        catch
        {
            // Quick answers are best-effort; the ask box still works.
        }
    }

    private async void OnKey(object sender, Microsoft.UI.Xaml.Input.KeyRoutedEventArgs e)
    {
        if (e.Key == Windows.System.VirtualKey.Enter) await AskAsync();
    }

    private async void OnAsk(object sender, RoutedEventArgs e) => await AskAsync();

    // The trust boundary, on demand (Fluent 2 TeachingTip).
    private void OnAbout(object sender, RoutedEventArgs e) => AboutTip.IsOpen = true;

    private async Task AskAsync()
    {
        var question = (Ask.Text ?? "").Trim();
        if (question.Length == 0) return;
        Answer.Children.Clear();
        Answer.Children.Add(Ui.Loading());
        AskButton.IsEnabled = false;
        try
        {
            var data = await ApiClient.Default.PostJsonAsync(
                "api/assistant", new { question });
            Answer.Children.Clear();

            if (data.TryGetProperty("error", out var err)
                && err.ValueKind == JsonValueKind.String)
            {
                Answer.Children.Add(new InfoBar
                {
                    Title = "Couldn't answer that",
                    Message = err.GetString(),
                    IsOpen = true,
                    IsClosable = false,
                    Severity = InfoBarSeverity.Informational,
                });
                return;
            }

            if (data.TryGetProperty("summary", out var s)
                && s.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(s.GetString()))
                Answer.Children.Add(new TextBlock
                {
                    Text = s.GetString(),
                    TextWrapping = TextWrapping.Wrap,
                    Style = (Style)Application.Current.Resources["BodyStrongTextBlockStyle"],
                });

            var (headers, rows) = ResultTable(data);
            if (headers.Count > 0)
                Answer.Children.Add(Ui.TableFrom(headers, rows));

            if (data.TryGetProperty("sql", out var sql)
                && sql.ValueKind == JsonValueKind.String)
                Answer.Children.Add(new TextBlock
                {
                    Text = sql.GetString(),
                    FontFamily = new Microsoft.UI.Xaml.Media.FontFamily("Cascadia Mono"),
                    TextWrapping = TextWrapping.Wrap,
                    Foreground = (Microsoft.UI.Xaml.Media.Brush)
                        Application.Current.Resources["TextFillColorSecondaryBrush"],
                    Margin = new Thickness(0, 8, 0, 0),
                });
        }
        catch (Exception ex)
        {
            Answer.Children.Clear();
            Answer.Children.Add(Ui.ErrorNote(ex));
        }
        finally
        {
            AskButton.IsEnabled = true;
        }
    }

    // {columns:[...], rows:[[...],...]} → headers + positional string rows.
    private static (List<string> Headers, List<IReadOnlyList<string>> Rows) ResultTable(JsonElement data)
    {
        var headers = new List<string>();
        var rows = new List<IReadOnlyList<string>>();
        if (data.TryGetProperty("columns", out var cols) && cols.ValueKind == JsonValueKind.Array)
            foreach (var c in cols.EnumerateArray())
                headers.Add(c.ValueKind == JsonValueKind.String ? c.GetString() ?? "" : c.ToString());
        if (headers.Count > 0 && data.TryGetProperty("rows", out var rs)
            && rs.ValueKind == JsonValueKind.Array)
            foreach (var r in rs.EnumerateArray())
            {
                var cells = new List<string>();
                if (r.ValueKind == JsonValueKind.Array)
                    foreach (var c in r.EnumerateArray())
                        cells.Add(c.ValueKind == JsonValueKind.String ? c.GetString() ?? ""
                                  : c.ValueKind == JsonValueKind.Null ? "" : c.ToString());
                rows.Add(cells);
            }
        return (headers, rows);
    }
}
