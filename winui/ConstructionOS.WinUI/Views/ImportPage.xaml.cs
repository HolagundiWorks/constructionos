using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class ImportPage : Page
{
    public ImportPage()
    {
        InitializeComponent();
    }

    private async void Grn_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var data = await ApiClient.Default.PostJsonAsync(
                "api/grn/draft", new { text = PasteBox.Text });
            Result.Text = data.ToString();
        }
        catch (Exception ex) { Result.Text = ex.Message; }
    }

    private async void Boq_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var data = await ApiClient.Default.PostJsonAsync(
                "api/boq/import/draft", new { text = PasteBox.Text });
            Result.Text = data.ToString();
        }
        catch (Exception ex) { Result.Text = ex.Message; }
    }

    private async void Text_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var data = await ApiClient.Default.PostJsonAsync(
                "api/text/extract", new { text = PasteBox.Text });
            Result.Text = data.ToString();
        }
        catch (Exception ex) { Result.Text = ex.Message; }
    }

    private async void Signals_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var data = await ApiClient.Default.PostJsonAsync(
                "api/signals/suggest", new { apply = false });
            Result.Text = data.ToString();
        }
        catch (Exception ex) { Result.Text = ex.Message; }
    }

    private async void VendorInvoice_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var data = await ApiClient.Default.PostJsonAsync(
                "api/vendor_invoice/draft", new { text = PasteBox.Text });
            Result.Text = data.ToString();
        }
        catch (Exception ex) { Result.Text = ex.Message; }
    }
}
