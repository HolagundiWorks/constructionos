using System.Globalization;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// U3 — Payments. Lists /api/payments and records a new one via a
/// metadata-driven form (fields from the same endpoint), POSTed to
/// /api/payments (the Python engine computes + posts to the ledger). Create-only
/// — a payment is a record of fact. No maths in C#.
/// </summary>
public sealed partial class MoneyPage : Page
{
    private sealed record FieldSpec(string Key, string Label, string Kind,
                                    List<string> Options, string Default,
                                    bool Required);

    private const string Table = "payments";
    private string _label = "Payment";
    private readonly List<FieldSpec> _fields = new();

    public MoneyPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) =>
        await LoadAsync();

    private async Task LoadAsync()
    {
        try
        {
            var data = await ApiClient.Default.GetJsonAsync($"api/{Table}");
            _label = JsonRows.Prop(data, "label", "Payment");
            NewButton.Label = "New " + _label.ToLower();
            ParseFields(data);
            Grid.ItemsSource = Ui.Lines(data, "items");
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
        if (!data.TryGetProperty("fields", out var fields)
            || fields.ValueKind != JsonValueKind.Array) return;
        foreach (var f in fields.EnumerateArray())
        {
            var options = new List<string>();
            if (f.TryGetProperty("options", out var opts)
                && opts.ValueKind == JsonValueKind.Array)
                foreach (var o in opts.EnumerateArray())
                    if (o.ValueKind == JsonValueKind.String
                        && o.GetString() is { } s) options.Add(s);
            _fields.Add(new FieldSpec(
                JsonRows.Prop(f, "key"), JsonRows.Prop(f, "label"),
                JsonRows.Prop(f, "kind", "text"), options,
                JsonRows.Prop(f, "default"),
                f.TryGetProperty("required", out var r)
                    && r.ValueKind == JsonValueKind.True));
        }
    }

    private async void OnNew(object sender, RoutedEventArgs e)
    {
        if (_fields.Count == 0)
        {
            await LoadAsync();
            if (_fields.Count == 0) return;
        }
        var start = _fields.ToDictionary(
            f => f.Key, f => f.Default == "@today" ? Today() : f.Default);
        var payload = await ShowFormAsync($"New {_label}", start);
        if (payload == null) return;
        try
        {
            await ApiClient.Default.PostJsonAsync($"api/{Table}", payload);
            await LoadAsync();
        }
        catch (Exception ex)
        {
            ShowError(ex);
        }
    }

    private async Task<Dictionary<string, string>?> ShowFormAsync(
        string title, Dictionary<string, string> start)
    {
        var panel = new StackPanel { Spacing = 10, MinWidth = 340 };
        var inputs = new Dictionary<string, FrameworkElement>();
        foreach (var f in _fields)
        {
            start.TryGetValue(f.Key, out var current);
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
            XamlRoot = XamlRoot,
            Content = new ScrollViewer { Content = panel, MaxHeight = 520 },
        };
        if (await dialog.ShowAsync() != ContentDialogResult.Primary) return null;
        return _fields.ToDictionary(f => f.Key, f => ReadInput(inputs[f.Key]));
    }

    private static FrameworkElement BuildInput(FieldSpec f, string current)
    {
        switch (f.Kind)
        {
            case "combo":
                var cb = new ComboBox
                {
                    HorizontalAlignment = HorizontalAlignment.Stretch,
                };
                foreach (var o in f.Options) cb.Items.Add(o);
                cb.SelectedItem = f.Options.Contains(current) ? current
                    : (f.Options.Count > 0 ? f.Options[0] : null);
                return cb;
            case "number":
                return new NumberBox
                {
                    Value = double.TryParse(current, out var d) ? d : double.NaN,
                    SpinButtonPlacementMode = NumberBoxSpinButtonPlacementMode.Hidden,
                };
            case "textarea":
                return new TextBox
                {
                    Text = current,
                    AcceptsReturn = true,
                    TextWrapping = TextWrapping.Wrap,
                    Height = 72,
                };
            default:
                return new TextBox { Text = current };
        }
    }

    private static string ReadInput(FrameworkElement input) => input switch
    {
        NumberBox nb => double.IsNaN(nb.Value) ? ""
            : nb.Value.ToString(CultureInfo.InvariantCulture),
        ComboBox cb => cb.SelectedItem as string ?? "",
        TextBox tb => tb.Text,
        _ => "",
    };

    private static string Today() => DateTime.Now.ToString("yyyy-MM-dd");

    private void ShowError(Exception ex)
    {
        Notice.Title = ex is ApiException api
            ? $"Couldn't save ({(int)api.StatusCode})" : "Error";
        Notice.Message = ex.Message;
        Notice.Severity = InfoBarSeverity.Error;
        Notice.IsOpen = true;
    }
}
