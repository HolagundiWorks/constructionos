using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Money › Insight — the analytics cuts from GET /api/insight: site
/// profitability, contract progress and material budget-vs-actual, each a
/// curated {rows, cols} block. Separate from Key Numbers (the KPI scorecard).
/// </summary>
public sealed partial class InsightPage : Page
{
    // API block key -> section heading, in reading order.
    private static readonly (string Key, string Title)[] Blocks =
    {
        ("site_profitability", "Site profitability"),
        ("contract_progress", "Contract progress"),
        ("material_budget", "Material budget vs actual"),
    };

    public InsightPage()
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
            var data = await ApiClient.Default.GetJsonAsync("api/insight");
            Host.Children.Clear();
            var shown = 0;
            foreach (var (key, title) in Blocks)
            {
                if (!data.TryGetProperty(key, out var block)
                    || block.ValueKind != JsonValueKind.Object) continue;
                Host.Children.Add(Ui.SectionTitle(title));
                // Each block carries its own rows + cols metadata.
                Host.Children.Add(Ui.Table(block, "rows"));
                shown++;
            }
            if (shown == 0)
                Host.Children.Add(Ui.EmptyNote(
                    "No insight yet — add sites, contracts and material entries to "
                    + "see profitability and budget cuts."));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }
}
