using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Money › Key Numbers — the KPI scorecard from GET /api/kpi: a plain-language
/// headline, how many need action, then every KPI with its verdict. Separate
/// from Insight (analytics) — the audit flagged both landing on ChartsPage.
/// </summary>
public sealed partial class KpiPage : Page
{
    public KpiPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        Host.Children.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/kpi");
            Host.Children.Clear();

            var actions = data.TryGetProperty("action_count", out var ac)
                && ac.ValueKind == JsonValueKind.Number ? ac.GetInt32() : 0;
            if (data.TryGetProperty("headline", out var h)
                && h.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(h.GetString()))
                Host.Children.Add(new InfoBar
                {
                    Title = actions > 0
                        ? $"{actions} need{(actions == 1 ? "s" : "")} action"
                        : "All key numbers look healthy",
                    Message = h.GetString(),
                    IsOpen = true,
                    IsClosable = false,
                    Severity = actions > 0 ? InfoBarSeverity.Warning : InfoBarSeverity.Success,
                });

            Host.Children.Add(Ui.Table(data, "rows"));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }
}
