using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class ImportPage : Page
{
    public ImportPage()
    {
        InitializeComponent();
    }

    async Task RunAsync(string label, Func<Task<System.Text.Json.JsonElement>> call)
    {
        Result.Text = label + "…";
        SetBusy(true);
        try
        {
            var data = await call();
            Result.Text = JsonRows.Pretty(data);
        }
        catch (Exception ex)
        {
            Result.Text = ApiException.UserMessage(ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    void SetBusy(bool busy)
    {
        GrnBtn.IsEnabled = !busy;
        VendorBtn.IsEnabled = !busy;
        BoqBtn.IsEnabled = !busy;
        TextBtn.IsEnabled = !busy;
        SignalsBtn.IsEnabled = !busy;
    }

    private async void Grn_Click(object sender, RoutedEventArgs e)
        => await RunAsync("GRN draft", () => ApiClient.Default.PostJsonAsync(
            "api/grn/draft", new { text = PasteBox.Text }));

    private async void Boq_Click(object sender, RoutedEventArgs e)
        => await RunAsync("BOQ draft", () => ApiClient.Default.PostJsonAsync(
            "api/boq/import/draft", new { text = PasteBox.Text }));

    private async void Text_Click(object sender, RoutedEventArgs e)
        => await RunAsync("Text extract", () => ApiClient.Default.PostJsonAsync(
            "api/text/extract", new { text = PasteBox.Text }));

    private async void Signals_Click(object sender, RoutedEventArgs e)
        => await RunAsync("Signals", () => ApiClient.Default.PostJsonAsync(
            "api/signals/suggest", new { apply = false }));

    private async void VendorInvoice_Click(object sender, RoutedEventArgs e)
        => await RunAsync("Vendor invoice", () => ApiClient.Default.PostJsonAsync(
            "api/vendor_invoice/draft", new { text = PasteBox.Text }));
}
