using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Text;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Operations › Muster &amp; wages — the day's attendance grid for a site
/// (GET/POST /api/muster) and the week's wage payout (GET/POST
/// /api/muster/payout). One mark per labourer per day; wages and advance
/// recovery are computed by the Python muster_ops, never in C#.
/// </summary>
public sealed partial class MusterPage : Page
{
    private readonly List<(int Id, string Name)> _sites = new();
    private readonly List<(int LaborId, ComboBox Status, TextBox Hours)> _marks = new();
    private string[] _statuses = { "Present", "Absent", "Half Day" };
    private bool _loading;

    public MusterPage()
    {
        InitializeComponent();
        DayBox.Date = DateTimeOffset.Now;
        Loaded += async (_, _) => await LoadSitesAsync();
    }

    private async void OnScopeChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!_loading) await LoadGridAsync();
    }

    private async void OnDayChanged(object sender, DatePickerValueChangedEventArgs e)
    {
        if (!_loading) await LoadGridAsync();
    }

    private string Day => DayBox.Date.ToString("yyyy-MM-dd");

    private int? SiteId =>
        SiteBox.SelectedIndex >= 0 && SiteBox.SelectedIndex < _sites.Count
            ? _sites[SiteBox.SelectedIndex].Id : null;

    private async Task LoadSitesAsync()
    {
        _loading = true;
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/sites");
            _sites.Clear();
            if (data.TryGetProperty("items", out var items)
                && items.ValueKind == JsonValueKind.Array)
                foreach (var s in items.EnumerateArray())
                {
                    if (!s.TryGetProperty("id", out var id)) continue;
                    var name = s.TryGetProperty("name", out var n) ? n.GetString() : null;
                    _sites.Add((id.GetInt32(), name ?? $"Site {id.GetInt32()}"));
                }
            SiteBox.ItemsSource = _sites.Select(s => s.Name).ToList();
            if (_sites.Count > 0) SiteBox.SelectedIndex = 0;
        }
        catch (Exception ex) { Show("Couldn't load sites", ex); }
        finally { _loading = false; }

        if (_sites.Count > 0) await LoadGridAsync();
        else Host.Children.Add(Ui.EmptyNote(
            "No sites yet. Add one under Masters › Sites to take attendance."));
    }

    // The day's grid: one row per Active labourer, with the mark and hours.
    private async Task LoadGridAsync()
    {
        var site = SiteId;
        if (site is null) return;
        Host.Children.Clear();
        _marks.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var data = await ApiClient.Default.GetJsonAsync(
                $"api/muster?site_id={site}&att_date={Day}");
            Host.Children.Clear();

            if (data.TryGetProperty("statuses", out var st)
                && st.ValueKind == JsonValueKind.Array && st.GetArrayLength() > 0)
                _statuses = st.EnumerateArray()
                    .Select(x => x.GetString() ?? "").Where(x => x.Length > 0).ToArray();

            if (!data.TryGetProperty("rows", out var rows)
                || rows.ValueKind != JsonValueKind.Array || rows.GetArrayLength() == 0)
            {
                SaveButton.IsEnabled = false;
                Host.Children.Add(Ui.EmptyNote(
                    "No active labour on this site. Add labour under Masters › Labour."));
                return;
            }
            SaveButton.IsEnabled = true;

            var grid = new Grid { ColumnSpacing = 12, RowSpacing = 4 };
            foreach (var w in new[] { 2.0, 1.0, 1.4, 1.0 })
                grid.ColumnDefinitions.Add(new ColumnDefinition
                { Width = new GridLength(w, GridUnitType.Star) });
            AddHeader(grid, 0, "Labourer", "Daily wage (₹)", "Mark", "Hours");

            var r = 1;
            foreach (var row in rows.EnumerateArray())
            {
                grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                var labor = row.TryGetProperty("labor_id", out var li) ? li.GetInt32() : 0;
                var name = row.TryGetProperty("name", out var nm) ? nm.GetString() ?? "" : "";
                var wage = row.TryGetProperty("daily_wage", out var dw)
                    && dw.ValueKind == JsonValueKind.Number ? Ui.Rupees(dw.GetDouble()) : "—";
                var status = row.TryGetProperty("status", out var stv) ? stv.GetString() : null;
                var hours = row.TryGetProperty("hours", out var hv)
                    && hv.ValueKind == JsonValueKind.Number ? hv.GetDouble().ToString("0.##") : "";

                Put(grid, r, 0, new TextBlock { Text = name, VerticalAlignment = VerticalAlignment.Center });
                Put(grid, r, 1, new TextBlock
                {
                    Text = wage,
                    TextAlignment = TextAlignment.Right,
                    VerticalAlignment = VerticalAlignment.Center,
                });
                var mark = new ComboBox
                {
                    ItemsSource = _statuses,
                    SelectedItem = _statuses.Contains(status) ? status : _statuses[0],
                    HorizontalAlignment = HorizontalAlignment.Stretch,
                };
                Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(
                    mark, $"Attendance mark for {name}");
                Put(grid, r, 2, mark);
                var hrs = new TextBox { Text = hours, TextAlignment = TextAlignment.Right };
                Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(
                    hrs, $"Hours for {name}");
                Put(grid, r, 3, hrs);

                _marks.Add((labor, mark, hrs));
                r++;
            }
            Host.Children.Add(grid);
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }

    private async void OnSave(object sender, RoutedEventArgs e)
    {
        var site = SiteId;
        if (site is null || _marks.Count == 0) return;
        var rows = _marks.Select(m => new Dictionary<string, object?>
        {
            ["labor_id"] = m.LaborId,
            ["status"] = m.Status.SelectedItem?.ToString(),
            ["hours"] = double.TryParse(m.Hours.Text, out var h) ? h : (double?)null,
        }).ToList();
        try
        {
            var res = await ApiClient.Default.PostJsonAsync(
                "api/muster", new { site_id = site, att_date = Day, rows });
            var saved = res.TryGetProperty("saved", out var s)
                && s.ValueKind == JsonValueKind.Number ? s.GetInt32() : rows.Count;
            Show("Attendance saved", $"{saved} mark(s) recorded for {Day}.",
                 InfoBarSeverity.Success);
        }
        catch (Exception ex) { Show("Couldn't save attendance", ex); }
    }

    // The week's wage run for the selected site, week starting on the chosen day.
    private async void OnPayout(object sender, RoutedEventArgs e)
    {
        var site = SiteId;
        if (site is null) return;
        Host.Children.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var data = await ApiClient.Default.GetJsonAsync(
                $"api/muster/payout?site_id={site}&week_start={Day}");
            Host.Children.Clear();
            var from = data.TryGetProperty("week_start", out var ws) ? ws.GetString() : Day;
            var to = data.TryGetProperty("week_end", out var we) ? we.GetString() : "";
            Host.Children.Add(Ui.StatStrip(new (string, string)[]
            {
                ("Week", $"{from} – {to}"),
                ("Payable", Count(data, "payable_count")),
                ("Total net", Money(data, "total_net")),
            }));
            Host.Children.Add(Ui.SectionTitle("Wages this week"));
            Host.Children.Add(Ui.Table(data, "rows"));
            Host.Children.Add(Ui.EmptyNote(
                "Recording the payout writes cash wage payments — do that in the "
                + "desktop app for now; this view is read-only."));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }

    private static void AddHeader(Grid g, int row, params string[] labels)
    {
        g.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        for (var i = 0; i < labels.Length; i++)
            Put(g, row, i, new TextBlock
            {
                Text = labels[i],
                FontWeight = FontWeights.SemiBold,
                TextAlignment = i >= 1 ? TextAlignment.Right : TextAlignment.Left,
                Foreground = (Microsoft.UI.Xaml.Media.Brush)
                    Application.Current.Resources["TextFillColorSecondaryBrush"],
            });
    }

    private static void Put(Grid g, int row, int col, FrameworkElement el)
    {
        Grid.SetRow(el, row);
        Grid.SetColumn(el, col);
        g.Children.Add(el);
    }

    private void Show(string title, string message, InfoBarSeverity severity)
    {
        Notice.Title = title;
        Notice.Message = message;
        Notice.Severity = severity;
        Notice.IsOpen = true;
    }

    private void Show(string title, Exception ex) =>
        Show(title, ApiException.UserMessage(ex), InfoBarSeverity.Error);

    private static string Money(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? Ui.Rupees(v.GetDouble()) : "—";

    private static string Count(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? v.GetInt32().ToString() : "0";
}
