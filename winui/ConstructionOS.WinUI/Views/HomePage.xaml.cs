using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class HomePage : Page
{
    public HomePage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            Status.Text = "Loading dashboard…";
            try
            {
                var dash = await ApiClient.Default.GetJsonAsync("api/dashboard");
                var items = new List<string>();
                if (dash.TryGetProperty("advisories", out var list)
                    && list.ValueKind == System.Text.Json.JsonValueKind.Array)
                {
                    foreach (var a in list.EnumerateArray())
                    {
                        var title = JsonRows.Prop(a, "title");
                        var sev = JsonRows.Prop(a, "severity", "info");
                        items.Add($"[{sev}] {title}");
                    }
                }
                Advisories.ItemsSource = items;
                Status.Text = items.Count == 0
                    ? "Dashboard loaded — no advisories."
                    : $"Dashboard loaded — {items.Count} advisories.";
            }
            catch (Exception ex)
            {
                Status.Text = ApiException.UserMessage(ex);
                Advisories.ItemsSource = null;
            }
        };
    }
}
