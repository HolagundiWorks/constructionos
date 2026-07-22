using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// U3 money — payment list + create-only form from GET /api/payments field
/// metadata (docs stay create-only by design).
/// </summary>
public sealed partial class MoneyPage : Page
{
    private List<FieldForm.Spec> _fields = new();

    public MoneyPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        Notice.IsOpen = false;
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/payments");
            _fields = FieldForm.ParseFields(data);
            Grid.ItemsSource = Ui.Lines(data);
        }
        catch (Exception ex)
        {
            Grid.ItemsSource = new[] { "Error: " + ApiException.UserMessage(ex) };
        }
    }

    private async void OnNew(object sender, RoutedEventArgs e)
    {
        if (_fields.Count == 0)
        {
            try
            {
                var data = await ApiClient.Default.GetJsonAsync("api/payments");
                _fields = FieldForm.ParseFields(data);
            }
            catch (Exception ex)
            {
                ShowError(ex);
                return;
            }
        }
        var values = _fields.ToDictionary(f => f.Key, f => f.Default);
        var payload = await FieldForm.ShowAsync(XamlRoot, "New payment", _fields, values);
        if (payload == null) return;
        try
        {
            var created = await ApiClient.Default.PostJsonAsync("api/payments", payload);
            await LoadAsync();
            if (created.TryGetProperty("followups", out var fu)
                && fu.ValueKind == JsonValueKind.Array && fu.GetArrayLength() > 0)
            {
                Notice.Title = "Payment saved — follow-ups pending approval";
                Notice.Message = $"{fu.GetArrayLength()} gated draft(s). Nothing auto-posted.";
                Notice.Severity = InfoBarSeverity.Informational;
                Notice.IsOpen = true;
            }
        }
        catch (Exception ex) { ShowError(ex); }
    }

    private void ShowError(Exception ex)
    {
        Notice.Title = "Couldn't save payment";
        Notice.Message = ApiException.UserMessage(ex);
        Notice.Severity = InfoBarSeverity.Error;
        Notice.IsOpen = true;
    }
}
