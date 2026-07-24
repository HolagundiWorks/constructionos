using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Billing › BOQ &amp; RA bills — the civil billing spine: pick a contract, see
/// its BOQ, then snapshot the measured quantities into a **Draft** RA bill
/// (POST /api/ra_bills/generate). Every figure — measured quantity, retention,
/// TDS, net payable — is computed by the Python <c>ra_generate</c>/<c>civil</c>
/// modules. The bill is created as a Draft: a human still approves it before it
/// counts as billed.
/// </summary>
public sealed partial class BoqRaPage : Page
{
    private readonly List<(int Id, string Label)> _contracts = new();
    private bool _loading;

    public BoqRaPage()
    {
        InitializeComponent();
        BillDate.Date = DateTimeOffset.Now;
        Loaded += async (_, _) => await LoadContractsAsync();
    }

    private async void OnContractChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!_loading) await LoadBoqAsync();
    }

    private int? ContractId =>
        ContractBox.SelectedIndex >= 0 && ContractBox.SelectedIndex < _contracts.Count
            ? _contracts[ContractBox.SelectedIndex].Id : null;

    private async Task LoadContractsAsync()
    {
        _loading = true;
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/contracts");
            _contracts.Clear();
            if (data.TryGetProperty("items", out var items)
                && items.ValueKind == JsonValueKind.Array)
                foreach (var c in items.EnumerateArray())
                {
                    if (!c.TryGetProperty("id", out var id)) continue;
                    var no = c.TryGetProperty("contract_no", out var n) ? n.GetString() : null;
                    _contracts.Add((id.GetInt32(),
                        string.IsNullOrWhiteSpace(no) ? $"Contract {id.GetInt32()}" : no!));
                }
            ContractBox.ItemsSource = _contracts.Select(c => c.Label).ToList();
            if (_contracts.Count > 0) ContractBox.SelectedIndex = 0;
        }
        catch (Exception ex) { Show("Couldn't load contracts", ex); }
        finally { _loading = false; }

        if (_contracts.Count > 0) await LoadBoqAsync();
        else
        {
            GenerateButton.IsEnabled = false;
            Host.Children.Add(Ui.EmptyNote(
                "No contracts yet. Add one under Billing › Contracts, then import "
                + "its BOQ to bill against it."));
        }
    }

    private async Task LoadBoqAsync()
    {
        var cid = ContractId;
        if (cid is null) return;
        Host.Children.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var boq = await ApiClient.Default.GetJsonAsync($"api/boq_items?contract_id={cid}");
            Host.Children.Clear();

            var prev = await PreviousBilledAsync(cid.Value);
            if (prev != null)
                Host.Children.Add(Ui.StatStrip(new (string, string)[]
                {
                    ("Already billed (approved)", prev),
                }));

            Host.Children.Add(Ui.SectionTitle("Bill of quantities"));
            var hasBoq = boq.TryGetProperty("items", out var items)
                && items.ValueKind == JsonValueKind.Array && items.GetArrayLength() > 0;
            GenerateButton.IsEnabled = hasBoq;
            if (!hasBoq)
                Host.Children.Add(Ui.EmptyNote(
                    "This contract has no BOQ yet — import one under Billing › "
                    + "BOQ import before generating an RA bill."));
            else
                Host.Children.Add(Ui.Table(boq));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(Ui.ErrorNote(ex));
        }
    }

    private static async Task<string?> PreviousBilledAsync(int contractId)
    {
        try
        {
            var p = await ApiClient.Default.GetJsonAsync(
                $"api/bills/previous?contract_id={contractId}");
            return p.TryGetProperty("previous_billed", out var v)
                && v.ValueKind == JsonValueKind.Number ? Ui.Rupees(v.GetDouble()) : null;
        }
        catch { return null; }
    }

    private async void OnGenerate(object sender, RoutedEventArgs e)
    {
        var cid = ContractId;
        if (cid is null) return;
        GenerateButton.IsEnabled = false;
        try
        {
            var payload = new
            {
                contract_id = cid,
                bill_date = BillDate.Date.ToString("yyyy-MM-dd"),
                retention_pct = RetentionBox.Value,
                tds_pct = TdsBox.Value,
            };
            var res = await ApiClient.Default.PostJsonAsync("api/ra_bills/generate", payload);

            var billNo = res.TryGetProperty("bill_no", out var bn) ? bn.GetString() : "(new)";
            var lines = res.TryGetProperty("line_count", out var lc)
                && lc.ValueKind == JsonValueKind.Number ? lc.GetInt32() : 0;
            Show($"Draft RA bill {billNo} created",
                 $"{lines} measured line(s) snapshotted. It is a **Draft** — approve "
                 + "it in Billing › Running Bills before it counts as billed.",
                 InfoBarSeverity.Success);

            Host.Children.Clear();
            if (res.TryGetProperty("totals", out var t) && t.ValueKind == JsonValueKind.Object)
            {
                var stats = new List<(string, string)>();
                foreach (var p in t.EnumerateObject())
                    stats.Add((Pretty(p.Name),
                        p.Value.ValueKind == JsonValueKind.Number
                            ? Ui.Rupees(p.Value.GetDouble()) : p.Value.ToString()));
                Host.Children.Add(Ui.SectionTitle($"RA bill {billNo} — totals"));
                Host.Children.Add(Ui.StatStrip(stats));
            }
            Host.Children.Add(Ui.SectionTitle("Billed lines"));
            Host.Children.Add(Ui.Table(res, "items"));
        }
        catch (Exception ex) { Show("Couldn't generate the RA bill", ex); }
        finally { GenerateButton.IsEnabled = true; }
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

    private static string Pretty(string key)
    {
        if (string.IsNullOrEmpty(key)) return key;
        var s = key.Replace('_', ' ');
        return char.ToUpperInvariant(s[0]) + s[1..];
    }
}
