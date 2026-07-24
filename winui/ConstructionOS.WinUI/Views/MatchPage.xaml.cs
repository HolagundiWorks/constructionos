using System.Globalization;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Purchases › Goods Receipt — the PO ↔ GRN ↔ invoice three-way match from GET
/// /api/match: money at risk / awaiting delivery / received-not-invoiced as
/// cards, the plain-language narration, then the per-PO detail. Status is shown
/// as text + severity (never colour alone) so it survives colour-blindness.
/// </summary>
public sealed partial class MatchPage : Page
{
    // POs from the last match load, for the receive picker.
    private readonly List<(int Id, string Label)> _pos = new();
    // The line editors currently on screen: (material_id, description, unit,
    // ordered qty, received box, rejected box, rate).
    private sealed record LineEdit(int? MaterialId, string Desc, string Unit,
                                   double Ordered, TextBox Received, TextBox Rejected,
                                   double Rate);
    private readonly List<LineEdit> _lines = new();
    private int? _receivePo;

    public MatchPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e)
    {
        Receive.Children.Clear();
        _lines.Clear();
        Notice.IsOpen = false;
        await LoadAsync();
    }

    private async Task LoadAsync()
    {
        Host.Children.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/match");
            Host.Children.Clear();

            // Remember the POs so the receive picker can list them by number.
            _pos.Clear();
            if (data.TryGetProperty("items", out var its) && its.ValueKind == JsonValueKind.Array)
                foreach (var it in its.EnumerateArray())
                {
                    var id = it.TryGetProperty("id", out var idv)
                        && idv.TryGetInt32(out var i) ? i : 0;
                    if (id == 0) continue;
                    var lbl = it.TryGetProperty("po_no", out var p)
                        && p.ValueKind == JsonValueKind.String ? p.GetString() : $"PO {id}";
                    var vendor = it.TryGetProperty("vendor", out var v)
                        && v.ValueKind == JsonValueKind.String ? v.GetString() : null;
                    _pos.Add((id, string.IsNullOrEmpty(vendor) ? lbl! : $"{lbl} — {vendor}"));
                }
            ReceiveButton.IsEnabled = _pos.Count > 0;

            if (data.TryGetProperty("summary", out var s) && s.ValueKind == JsonValueKind.Object)
                Host.Children.Add(Ui.StatStrip(new (string, string)[]
                {
                    ("At risk", Money(s, "at_risk")),
                    ("Awaiting delivery", Money(s, "awaiting_delivery")),
                    ("Received, not invoiced", Money(s, "received_not_invoiced")),
                    ("Problems", Count(s, "problem_count")),
                    ("Purchase orders", Count(s, "total_count")),
                }));

            var problems = data.TryGetProperty("summary", out var s2)
                && s2.TryGetProperty("problem_count", out var pc)
                && pc.ValueKind == JsonValueKind.Number ? pc.GetInt32() : 0;
            if (data.TryGetProperty("narration", out var n)
                && n.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(n.GetString()))
                Host.Children.Add(new InfoBar
                {
                    Title = problems > 0 ? "Check these before paying" : "Nothing over-billed",
                    Message = n.GetString(),
                    IsOpen = true,
                    IsClosable = false,
                    Severity = problems > 0 ? InfoBarSeverity.Warning : InfoBarSeverity.Success,
                });

            Host.Children.Add(Ui.SectionTitle("By purchase order"));
            Host.Children.Add(Ui.Table(data));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }

    /// <summary>Open the receive panel: pick a PO, then record what arrived.</summary>
    private void OnReceive(object sender, RoutedEventArgs e)
    {
        Receive.Children.Clear();
        _lines.Clear();
        _receivePo = null;

        Receive.Children.Add(Ui.SectionTitle("Record a goods receipt"));
        var picker = new ComboBox
        {
            Header = "Purchase order",
            PlaceholderText = "Choose a PO",
            MinWidth = 320,
            ItemsSource = _pos.Select(p => p.Label).ToList(),
        };
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(picker, "Purchase order");
        picker.SelectionChanged += async (_, _) =>
        {
            var idx = picker.SelectedIndex;
            if (idx >= 0 && idx < _pos.Count) await LoadLinesAsync(_pos[idx].Id);
        };
        Receive.Children.Add(picker);
    }

    /// <summary>Fetch a PO's ordered lines (GET /api/purchase_orders/{id}) and
    /// lay out one editable receipt row each — received defaults to ordered, so
    /// a full delivery is one click; rejected defaults to zero.</summary>
    private async Task LoadLinesAsync(int poId)
    {
        // Drop any editors below the picker (keep title + picker at indices 0,1).
        while (Receive.Children.Count > 2)
            Receive.Children.RemoveAt(Receive.Children.Count - 1);
        _lines.Clear();
        _receivePo = poId;
        Receive.Children.Add(Ui.Loading("Loading ordered lines…"));
        try
        {
            var po = await ApiClient.Default.GetJsonAsync($"api/purchase_orders/{poId}");
            while (Receive.Children.Count > 2)
                Receive.Children.RemoveAt(Receive.Children.Count - 1);

            if (!po.TryGetProperty("items", out var items)
                || items.ValueKind != JsonValueKind.Array || items.GetArrayLength() == 0)
            {
                Receive.Children.Add(Note("This PO has no line items to receive."));
                return;
            }

            var grid = new Grid { ColumnSpacing = 12, RowSpacing = 6 };
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(70) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(90) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(110) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(110) });
            AddLineHeader(grid);

            var r = 1;
            foreach (var it in items.EnumerateArray())
            {
                var desc = Str(it, "description");
                var unit = Str(it, "unit");
                var ordered = NumOf(it, "qty");
                var rate = NumOf(it, "rate");
                // material_id is often null on a PO line; TryGetInt32 THROWS on a
                // JSON null (it doesn't just return false), so gate on kind first.
                var mid = it.TryGetProperty("material_id", out var mv)
                    && mv.ValueKind == JsonValueKind.Number
                    && mv.TryGetInt32(out var m) ? m : (int?)null;

                grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                var recv = new TextBox
                {
                    Text = ordered.ToString("0.###", CultureInfo.InvariantCulture),
                    TextAlignment = TextAlignment.Right, MinWidth = 100,
                };
                Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(recv, $"Received qty for {desc}");
                var rej = new TextBox
                {
                    Text = "0", TextAlignment = TextAlignment.Right, MinWidth = 100,
                };
                Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(rej, $"Rejected qty for {desc}");

                Put(grid, r, 0, new TextBlock { Text = desc, TextWrapping = TextWrapping.Wrap, VerticalAlignment = VerticalAlignment.Center });
                Put(grid, r, 1, new TextBlock { Text = unit, VerticalAlignment = VerticalAlignment.Center });
                Put(grid, r, 2, new TextBlock { Text = ordered.ToString("0.###", CultureInfo.InvariantCulture), TextAlignment = TextAlignment.Right, VerticalAlignment = VerticalAlignment.Center });
                Put(grid, r, 3, recv);
                Put(grid, r, 4, rej);
                _lines.Add(new LineEdit(mid, desc, unit, ordered, recv, rej, rate));
                r++;
            }
            Receive.Children.Add(grid);

            var confirm = new Button
            {
                Content = "Confirm receipt…",
                Style = (Style)Application.Current.Resources["AccentButtonStyle"],
                Margin = new Thickness(0, 4, 0, 0),
            };
            confirm.Click += async (_, _) => await ConfirmReceiptAsync();
            Receive.Children.Add(confirm);
            Receive.Children.Add(Note("Received defaults to the ordered quantity — "
                + "adjust it and any rejected quantity, then confirm. This records a "
                + "goods receipt against the PO."));
        }
        catch (Exception ex)
        {
            while (Receive.Children.Count > 2)
                Receive.Children.RemoveAt(Receive.Children.Count - 1);
            Receive.Children.Add(Ui.ErrorNote(ex));
        }
    }

    /// <summary>POST /api/grn/confirm with the edited lines. The Python handler
    /// derives accepted = received − rejected and the line amount; C# only
    /// collects the two quantities the user typed.</summary>
    private async Task ConfirmReceiptAsync()
    {
        if (_receivePo is null) return;
        var lines = new List<Dictionary<string, object?>>();
        foreach (var l in _lines)
        {
            var recv = ParseNum(l.Received.Text);
            var rej = ParseNum(l.Rejected.Text);
            if (recv <= 0 && rej <= 0) continue;         // nothing received on this line
            lines.Add(new Dictionary<string, object?>
            {
                ["material_id"] = l.MaterialId,
                ["description"] = l.Desc,
                ["unit"] = l.Unit,
                ["qty_received"] = recv,
                ["qty_rejected"] = rej,
                ["rate"] = l.Rate,
            });
        }
        if (lines.Count == 0)
        {
            Show("Nothing to record", "Enter a received quantity on at least one line.",
                 InfoBarSeverity.Warning);
            return;
        }

        var confirm = new ContentDialog
        {
            Title = "Confirm this goods receipt?",
            Content = $"Records {lines.Count} line(s) received against this PO. "
                      + "Rejected quantities are logged but never enter stock.",
            PrimaryButtonText = "Confirm receipt",
            CloseButtonText = "Cancel",
            DefaultButton = ContentDialogButton.Close,
            XamlRoot = XamlRoot,
            RequestedTheme = ActualTheme,
        };
        if (await confirm.ShowAsync() != ContentDialogResult.Primary) return;
        try
        {
            var res = await ApiClient.Default.PostJsonAsync("api/grn/confirm",
                new Dictionary<string, object?>
                {
                    ["purchase_order_id"] = _receivePo,
                    ["lines"] = lines,
                });
            var grnNo = res.TryGetProperty("grn_no", out var g)
                && g.ValueKind == JsonValueKind.String ? g.GetString() : null;
            Show("Goods receipt recorded",
                 string.IsNullOrEmpty(grnNo)
                     ? $"{lines.Count} line(s) received."
                     : $"GRN {grnNo} — {lines.Count} line(s) received.",
                 InfoBarSeverity.Success);
            Receive.Children.Clear();
            _lines.Clear();
            await LoadAsync();     // the three-way match reflects the new receipt
        }
        catch (Exception ex)
        {
            Show("Couldn't record the receipt", ApiException.UserMessage(ex),
                 InfoBarSeverity.Error);
        }
    }

    private static void AddLineHeader(Grid g)
    {
        g.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var heads = new[] { "Item", "Unit", "Ordered", "Received", "Rejected" };
        for (var i = 0; i < heads.Length; i++)
            Put(g, 0, i, new TextBlock
            {
                Text = heads[i],
                FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
                TextAlignment = i >= 2 ? TextAlignment.Right : TextAlignment.Left,
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

    private static double ParseNum(string s) =>
        double.TryParse(s?.Trim(), System.Globalization.NumberStyles.Any,
                        CultureInfo.InvariantCulture, out var d) ? d : 0;

    private static double NumOf(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? v.GetDouble() : 0;

    private static string Str(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.String
            ? v.GetString() ?? "" : "";

    private TextBlock Note(string text) => new()
    {
        Text = text,
        TextWrapping = TextWrapping.Wrap,
        Foreground = (Microsoft.UI.Xaml.Media.Brush)
            Application.Current.Resources["TextFillColorSecondaryBrush"],
    };

    private void Show(string title, string message, InfoBarSeverity severity)
    {
        Notice.Title = title;
        Notice.Message = message;
        Notice.Severity = severity;
        Notice.IsOpen = true;
    }

    private static string Money(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? Ui.Rupees(v.GetDouble()) : "—";

    private static string Count(JsonElement o, string k) =>
        o.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? v.GetInt32().ToString() : "0";
}
