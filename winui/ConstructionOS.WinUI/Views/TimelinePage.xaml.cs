using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Project Management › Timeline — the contract programme for one project from
/// GET /api/timeline?project_id=: CPM summary (duration, critical count, delay
/// position) over the task table with plan vs CPM dates, float and a Critical
/// flag. The critical path is named in text, not signalled by colour alone.
/// </summary>
public sealed partial class TimelinePage : Page
{
    private readonly List<(int Id, string Name)> _projects = new();
    private bool _loading;

    public TimelinePage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadProjectsAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async void OnProjectChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!_loading) await LoadAsync();
    }

    private async Task LoadProjectsAsync()
    {
        _loading = true;
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/projects");
            _projects.Clear();
            if (data.TryGetProperty("items", out var items)
                && items.ValueKind == JsonValueKind.Array)
                foreach (var p in items.EnumerateArray())
                {
                    if (!p.TryGetProperty("id", out var id)) continue;
                    var name = p.TryGetProperty("name", out var n) ? n.GetString() : null;
                    _projects.Add((id.GetInt32(), name ?? $"Project {id.GetInt32()}"));
                }
            ProjectBox.ItemsSource = _projects.Select(p => p.Name).ToList();
            if (_projects.Count > 0) ProjectBox.SelectedIndex = 0;
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
        finally { _loading = false; }
        if (_projects.Count > 0) await LoadAsync();
        else
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.EmptyNote(
                "No projects yet. Add one under Project Management › Projects to "
                + "build a programme."));
        }
    }

    private async Task LoadAsync()
    {
        var idx = ProjectBox.SelectedIndex;
        if (idx < 0 || idx >= _projects.Count) return;
        Host.Children.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var data = await ApiClient.Default.GetJsonAsync(
                $"api/timeline?project_id={_projects[idx].Id}");
            Host.Children.Clear();

            if (data.TryGetProperty("summary", out var s) && s.ValueKind == JsonValueKind.Object)
            {
                var stats = new List<(string, string)>();
                foreach (var p in s.EnumerateObject())
                    stats.Add((Pretty(p.Name), Scalar(p.Value)));
                if (stats.Count > 0) Host.Children.Add(Ui.StatStrip(stats));
            }

            // Delay position in words — never colour alone.
            if (data.TryGetProperty("position", out var pos)
                && pos.ValueKind == JsonValueKind.Object)
            {
                var verdict = pos.TryGetProperty("verdict", out var v) ? v.GetString() : null;
                var detail = pos.TryGetProperty("detail", out var d) ? d.GetString() : null;
                if (!string.IsNullOrWhiteSpace(verdict) || !string.IsNullOrWhiteSpace(detail))
                    Host.Children.Add(new InfoBar
                    {
                        Title = string.IsNullOrWhiteSpace(verdict) ? "Programme" : verdict,
                        Message = detail ?? "",
                        IsOpen = true,
                        IsClosable = false,
                        Severity = InfoBarSeverity.Informational,
                    });
            }

            var path = data.TryGetProperty("critical_path", out var cp)
                && cp.ValueKind == JsonValueKind.Array
                ? string.Join(" → ", cp.EnumerateArray().Select(Scalar)) : "";
            if (!string.IsNullOrWhiteSpace(path))
            {
                Host.Children.Add(Ui.SectionTitle("Critical path"));
                Host.Children.Add(new TextBlock { Text = path, TextWrapping = TextWrapping.Wrap });
            }

            Host.Children.Add(Ui.SectionTitle("Tasks"));
            Host.Children.Add(Ui.Table(data, "tasks"));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }

    private static string Scalar(JsonElement v) => v.ValueKind switch
    {
        JsonValueKind.String => v.GetString() ?? "",
        JsonValueKind.Null => "—",
        JsonValueKind.True => "yes",
        JsonValueKind.False => "no",
        _ => v.ToString(),
    };

    private static string Pretty(string key)
    {
        if (string.IsNullOrEmpty(key)) return key;
        var s = key.Replace('_', ' ');
        return char.ToUpperInvariant(s[0]) + s[1..];
    }
}
