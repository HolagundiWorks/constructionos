using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// U3 money documents — a create-only list + form for any money doc the API
/// exposes (payments, tax/vendor invoices, running bills, RA bills). The doc
/// table arrives as the navigation parameter (default "payments"); the fields,
/// label and rows all come from GET /api/&lt;table&gt;, so one page serves every
/// doc type through the shared <see cref="FieldForm"/>. Money documents are
/// create + view only by design — posting goes through the backend's own engine.
/// </summary>
public sealed partial class MoneyPage : Page
{
    private string _table = "payments";
    private string _label = "document";
    private List<FieldForm.Spec> _fields = new();

    public MoneyPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    // The doc table is passed by MainWindow's nav (e.g. "tax_invoices"); default
    // stays "payments" so an untagged navigation still lands somewhere sensible.
    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        base.OnNavigatedTo(e);
        if (e.Parameter is string t && t.Length > 0) _table = t;
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        Notice.IsOpen = false;
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/" + _table);
            _fields = FieldForm.ParseFields(data);
            if (data.TryGetProperty("label", out var lbl)
                && lbl.ValueKind == JsonValueKind.String)
                _label = lbl.GetString() ?? _label;
            PageTitle.Text = Plural(_label);
            NewButton.Label = "New " + _label.ToLowerInvariant();
            Host.Children.Clear();
            Host.Children.Add(Ui.Table(data));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(new TextBlock
            {
                Text = ApiException.UserMessage(ex),
                TextWrapping = TextWrapping.Wrap,
            });
        }
    }

    private async void OnNew(object sender, RoutedEventArgs e)
    {
        if (_fields.Count == 0)
        {
            try
            {
                var data = await ApiClient.Default.GetJsonAsync("api/" + _table);
                _fields = FieldForm.ParseFields(data);
            }
            catch (Exception ex)
            {
                ShowError(ex);
                return;
            }
        }
        var values = _fields.ToDictionary(f => f.Key, f => f.Default);
        var payload = await FieldForm.ShowAsync(
            XamlRoot, "New " + _label.ToLowerInvariant(), _fields, values);
        if (payload == null) return;
        try
        {
            var created = await ApiClient.Default.PostJsonAsync("api/" + _table, payload);
            await LoadAsync();
            if (created.TryGetProperty("followups", out var fu)
                && fu.ValueKind == JsonValueKind.Array && fu.GetArrayLength() > 0)
            {
                Notice.Title = _label + " saved — follow-ups pending approval";
                Notice.Message = $"{fu.GetArrayLength()} gated draft(s). Nothing auto-posted.";
                Notice.Severity = InfoBarSeverity.Informational;
                Notice.IsOpen = true;
            }
        }
        catch (Exception ex) { ShowError(ex); }
    }

    private void ShowError(Exception ex)
    {
        Notice.Title = "Couldn't save " + _label.ToLowerInvariant();
        Notice.Message = ApiException.UserMessage(ex);
        Notice.Severity = InfoBarSeverity.Error;
        Notice.IsOpen = true;
    }

    // The API labels are singular ("Payment", "Tax Invoice", "Running Bill");
    // pluralise for the page title. Good enough for the doc labels in play.
    private static string Plural(string s) =>
        s.EndsWith("s", StringComparison.OrdinalIgnoreCase) ? s : s + "s";
}
