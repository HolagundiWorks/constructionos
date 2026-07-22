using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Generic master-data register (U2), bound to GET/POST/PUT/DELETE
/// /api/{table}. Form fields come from API metadata; FK options are resolved
/// ComboBoxes (U0.7). Stock ListView only — no DataGrid.
/// </summary>
public sealed partial class MastersPage : Page
{
    private string _table = "";
    private string _label = "Masters";
    private List<FieldForm.Spec> _fields = new();
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
            _fields = FieldForm.ParseFields(data);
            _rows = ParseItems(data);
            RenderTable();
            UpdateButtons();
            Notice.IsOpen = false;
        }
        catch (Exception ex)
        {
            ShowError(ex);
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

    // Render the rows as an aligned columnar table (header + one row grid per
    // record) while keeping the ListView's selection for edit/delete — item
    // order matches _rows, so Grid.SelectedIndex still indexes _rows.
    private void RenderTable()
    {
        var cols = new List<string> { "id" };
        foreach (var f in _fields)
            if (!cols.Contains(f.Key) && cols.Count < 10) cols.Add(f.Key);
        if (cols.Count == 1 && _rows.Count > 0)
            foreach (var k in _rows[0].Keys)
                if (!cols.Contains(k) && cols.Count < 10) cols.Add(k);

        HeaderHost.Child = Ui.HeaderRow(cols);
        Grid.Items.Clear();
        foreach (var r in _rows)
        {
            var sr = new Dictionary<string, string>();
            foreach (var kv in r) sr[kv.Key] = kv.Value?.ToString() ?? "";
            Grid.Items.Add(Ui.DataRow(cols, sr));
        }
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

    private async void OnNew(object sender, RoutedEventArgs e)
    {
        var values = _fields.ToDictionary(f => f.Key, f => f.Default);
        var payload = await FieldForm.ShowAsync(XamlRoot, $"New {_label}", _fields, values);
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
        var payload = await FieldForm.ShowAsync(XamlRoot, $"Edit {_label} #{id}", _fields, values);
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
            await ApiClient.Default.DeleteJsonAsync($"api/{_table}/{id}");
            await LoadAsync();
        }
        catch (Exception ex) { ShowError(ex); }
    }

    private void ShowError(Exception ex)
    {
        Notice.Title = ex is ApiException api ? $"Couldn't save ({(int)api.StatusCode})" : "Error";
        Notice.Message = ApiException.UserMessage(ex);
        Notice.Severity = InfoBarSeverity.Error;
        Notice.IsOpen = true;
    }
}
