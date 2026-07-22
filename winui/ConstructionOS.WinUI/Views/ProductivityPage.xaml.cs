using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class ProductivityPage : Page
{
    public ProductivityPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            Summary.Text = "Loading…";
            try
            {
                var data = await ApiClient.Default.GetJsonAsync("api/productivity");
                var u = JsonRows.Prop(data, "units_per_hour", "—");
                var p = JsonRows.Prop(data, "plant_util_pct", "—");
                Summary.Text = $"Firm units/hr: {u} · plant util %: {p}";
                var rows = JsonRows.FromEnvelope(data, "sites", "items");
                Grid.ItemsSource = rows;
                Status.Text = rows.Count == 0 ? "No site rows." : $"{rows.Count} site(s).";
            }
            catch (Exception ex)
            {
                var msg = ApiException.UserMessage(ex);
                Summary.Text = msg;
                Status.Text = msg;
            }
        };
    }
}
