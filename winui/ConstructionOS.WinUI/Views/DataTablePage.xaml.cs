using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Generic read-only register/report table over any API endpoint that returns an
/// items array. Navigation parameter is "path" or "path|Title|itemsKey" — e.g.
/// "purchase_orders|Purchase orders". Renders with <see cref="Ui.Table"/>.
/// </summary>
public sealed partial class DataTablePage : Page
{
    private string _path = "";
    private string _title = "Records";
    private string[] _keys = System.Array.Empty<string>();

    public DataTablePage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        base.OnNavigatedTo(e);
        if (e.Parameter is not string s || s.Length == 0) return;
        var parts = s.Split('|');
        _path = parts[0];
        _title = parts.Length > 1 && parts[1].Length > 0 ? parts[1] : Pretty(_path);
        _keys = parts.Length > 2 && parts[2].Length > 0
            ? new[] { parts[2] } : System.Array.Empty<string>();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        TitleText.Text = _title;
        if (string.IsNullOrEmpty(_path)) return;
        Host.Children.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/" + _path);
            Host.Children.Clear();
            Host.Children.Add(Ui.Table(data, _keys));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }

    private static string Pretty(string p)
    {
        var last = p.Contains('/') ? p[(p.LastIndexOf('/') + 1)..] : p;
        last = last.Replace('_', ' ');
        return last.Length == 0 ? "Records"
            : char.ToUpperInvariant(last[0]) + last[1..];
    }
}
