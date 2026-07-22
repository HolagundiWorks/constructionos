using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class HomePage : Page
{
    public HomePage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            try
            {
                var dash = await ApiClient.Default.GetJsonAsync("api/dashboard");
                Status.Text = "Dashboard loaded.";
                if (dash.TryGetProperty("advisories", out var list))
                {
                    var items = new List<string>();
                    foreach (var a in list.EnumerateArray())
                    {
                        var title = a.TryGetProperty("title", out var t) ? t.GetString() : "";
                        var sev = a.TryGetProperty("severity", out var s) ? s.GetString() : "";
                        items.Add($"[{sev}] {title}");
                    }
                    Advisories.ItemsSource = items;
                }
            }
            catch (Exception ex)
            {
                Status.Text = "Failed: " + ex.Message;
            }
        };
    }
}
