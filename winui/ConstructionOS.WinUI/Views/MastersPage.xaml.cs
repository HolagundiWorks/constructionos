using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Generic master-data register (U2), bound to GET/POST/PUT/DELETE
/// /api/{table}. Its add/edit form is generated from the API's field metadata
/// (<c>fields</c>), so this one page serves every master — no per-master XAML.
/// The list is a stock WinUI ListView (the CommunityToolkit DataGrid is UWP-only
/// and crashes WinUI 3); rows show as readable lines and selection maps back to
/// the underlying record by index. No business rules live here.
/// </summary>
public sealed partial class MastersPage : Page
{
    private sealed record FieldSpec(string Key, string Label, string Kind,
                                    List<string> Options, string Default, bool Required);

    private string _table = "";
    private string _label = "Masters";
    private readonly List<FieldSpec> _fields = new();
    private List<Dictionary<string, object?>> _rows = new();

    public MastersPage() => InitializeComponent();

    protected override async void OnNavigatedTo(NavigationEventArgs e)
    {
        base.OnNavigatedTo(e);
        _table = e.Parameter as string ?? "";
        await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        if (string.IsNullOrEmpty(_table)) return;
        try
        {
            var data = await ApiClient.Default.GetJsonAsync($"api/{_table}");
            _label = data.TryGetProperty("label", out var l) ? l.GetString() ?? _table : _table;
            TitleText.Text = _label + " register";
            ParseFields(data);
            _rows = ParseItems(data);
            Grid.ItemsSource = _rows.Select(Line).ToList();
            UpdateButtons();
            Notice.IsOpen = false;
        }
        catch (Exception ex)
        {
            ShowError(ex);
        }
    }

    private void ParseFields(JsonElement data)
    {
        _fields.Clear();
        if (!data.TryGetProperty("fields", out var fields)) return;
        foreach (var f in fields.EnumerateArray())
        {
            var options = new List<string>();
            if (f.TryGetProperty("options", out var opts) && opts.ValueKind == JsonValueKind.Array)
                foreach (var o in opts.EnumerateArray())
                    if (o.GetString() is { } s) options.Add(s);
            _fields.Add(new FieldSpec(
                Key: f.GetProperty("key").GetString() ?? "",
                Label: f.TryGetProperty("label", out var lb) ? lb.GetString() ?? "" : "",
                Kind: f.TryGetProperty("kind", out var k) ? k.GetString() ?? "text" : "text",
                Options: options,
                Default: f.TryGetProperty("default", out var d) ? d.GetString() ?? "" : "",
                Required: f.TryGetProperty("required", out var r) && r.ValueKind == JsonValueKind.True));
        }
    }

    private static List<Dictionary<string, object?>> ParseItems(JsonElement data)
    {
        var rows = new List<Dictionary<string, object?>>();
        if (!data.TryGetProperty("items", out var items)) return rows;
        foreach (var item in items.EnumerateArray())
        {
            var row = new Dictionary<string, object?>();
            foreach (var p in item.EnumerateObject())
                row[p.Name] = p.Value.ValueKind == JsonValueKind.Null ? "" : p.Value.ToString();
            rows.Add(row);
        }
        return rows;
    }

    // One readable line per record for the ListView (id first, then the fields).
    private string Line(Dictionary<string, object?> r)
    {
        var parts = new List<string>();
        if (r.TryGetValue("id", out var id)) parts.Add($"#{id}");
        foreach (var f in _fields)
            if (r.TryGetValue(f.Key, out var v) && !string.IsNullOrEmpty(v?.ToString()))
                parts.Add($"{f.Label}: {v}");
        return string.Join("    ", parts);
    }

    private Dictionary<string, object?>? Selected =>
        (Grid.SelectedIndex >= 0 && Grid.SelectedIndex < _rows.Count)
            ? _rows[Grid.SelectedIndex] : null;

    private void OnSelectionChanged(object sender, SelectionChangedEventArgs e) => UpdateButtons();

    private void UpdateButtons()
    {
        var has = Selected != null;
        EditButton.IsEnabled = has;
        DeleteButton.IsEnabled = has;
    }

    // ------------------------------------------------------------- create/edit
    private async void OnNew(object sender, RoutedEventArgs e)
    {
        var values = _fields.ToDictionary(f => f.Key, f => f.Default);
        var payload = await ShowFormAsync($"New {_label}", values);
        if (payload == null) return;
        try
        {
            await ApiClient.Default.PostJsonAsync($"api/{_table}", payload);
            await LoadAsync();
        }
        catch (Exception ex) { ShowError(ex); }
    }

    private async void OnEdit(object sender, RoutedEventArgs e)
    {
        var row = Selected;
        var id = row != null && row.TryGetValue("id", out var v) ? v?.ToString() : null;
        if (row == null || id == null) return;
        var values = _fields.ToDictionary(
            f => f.Key,
            f => row.TryGetValue(f.Key, out var cur) ? cur?.ToString() ?? "" : "");
        var payload = await ShowFormAsync($"Edit {_label} #{id}", values);
        if (payload == null) return;
        try
        {
            await ApiClient.Default.PutJsonAsync($"api/{_table}/{id}", payload);
            await LoadAsync();
        }
        catch (Exception ex) { ShowError(ex); }
    }

    private async void OnDelete(object sender, RoutedEventArgs e)
    {
        var row = Selected;
        var id = row != null && row.TryGetValue("id", out var v) ? v?.ToString() : null;
        if (id == null) return;
        var confirm = new ContentDialog
        {
            Title = $"Delete {_label} #{id}?",
            Content = "This cannot be undone. A record still referenced elsewhere "
                      + "cannot be deleted.",
            PrimaryButtonText = "Delete",
            CloseButtonText = "Cancel",
            DefaultButton = ContentDialogButton.Close,
            XamlRoot = XamlRoot,
        };
        if (await confirm.ShowAsync() != ContentDialogResult.Primary) return;
        try
        {
            await ApiClient.Default.DeleteAsync($"api/{_table}/{id}");
            await LoadAsync();
        }
        catch (Exception ex) { ShowError(ex); }
    }

    /// <summary>Builds a stock-input form from the field metadata and returns the
    /// entered values (or null if cancelled). One input per field, by kind.</summary>
    private async Task<Dictionary<string, string>?> ShowFormAsync(
        string title, Dictionary<string, string> values)
    {
        var panel = new StackPanel { Spacing = 10, MinWidth = 360 };
        var inputs = new Dictionary<string, FrameworkElement>();
        foreach (var f in _fields)
        {
            values.TryGetValue(f.Key, out var current);
            var input = BuildInput(f, current ?? "");
            inputs[f.Key] = input;
            var cell = new StackPanel { Spacing = 2 };
            cell.Children.Add(new TextBlock
            {
                Text = f.Label + (f.Required ? " *" : ""),
                Style = (Style)Application.Current.Resources["CaptionTextBlockStyle"],
            });
            cell.Children.Add(input);
            panel.Children.Add(cell);
        }
        var dialog = new ContentDialog
        {
            Title = title,
            PrimaryButtonText = "Save",
            CloseButtonText = "Cancel",
            DefaultButton = ContentDialogButton.Primary,
            Content = new ScrollViewer { Content = panel, MaxHeight = 480 },
            XamlRoot = XamlRoot,
        };
        if (await dialog.ShowAsync() != ContentDialogResult.Primary) return null;
        return _fields.ToDictionary(f => f.Key, f => ReadInput(f, inputs[f.Key]));
    }

    private static FrameworkElement BuildInput(FieldSpec f, string current)
    {
        switch (f.Kind)
        {
            case "number":
                return new NumberBox
                {
                    SpinButtonPlacementMode = NumberBoxSpinButtonPlacementMode.Hidden,
                    Value = double.TryParse(current, out var d) ? d : double.NaN,
                };
            case "combo":
                var cb = new ComboBox { HorizontalAlignment = HorizontalAlignment.Stretch };
                foreach (var o in f.Options) cb.Items.Add(o);
                cb.SelectedItem = f.Options.Contains(current) ? current : null;
                return cb;
            case "textarea":
                return new TextBox
                {
                    Text = current, AcceptsReturn = true,
                    TextWrapping = TextWrapping.Wrap, Height = 72,
                };
            case "fk":
                // Foreign keys are entered by id for now; a picker is a noted refinement.
                return new NumberBox
                {
                    SpinButtonPlacementMode = NumberBoxSpinButtonPlacementMode.Hidden,
                    Value = double.TryParse(current, out var fv) ? fv : double.NaN,
                    PlaceholderText = "id",
                };
            default:
                return new TextBox { Text = current };
        }
    }

    private static string ReadInput(FieldSpec f, FrameworkElement input) => input switch
    {
        NumberBox nb => double.IsNaN(nb.Value)
            ? "" : nb.Value.ToString(System.Globalization.CultureInfo.InvariantCulture),
        ComboBox cb => cb.SelectedItem as string ?? "",
        TextBox tb => tb.Text,
        _ => "",
    };

    private void ShowError(Exception ex)
    {
        Notice.Title = ex is ApiException api ? $"Couldn't save ({(int)api.Status})" : "Error";
        Notice.Message = ex.Message;
        Notice.Severity = InfoBarSeverity.Error;
        Notice.IsOpen = true;
    }
}
