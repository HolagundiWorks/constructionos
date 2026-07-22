using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class ChartsPage : Page
{
    public ChartsPage()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            try
            {
                await ApiClient.Default.GetJsonAsync("api/kpi");
                Status.Text = "KPI payload reachable — bind LiveCharts series locally.";
            }
            catch (Exception ex)
            {
                Status.Text = "Backend unreachable: " + ex.Message;
            }
        };
    }
}
