using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Controls.Primitives;   // ToggleButton
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;
using ConstructionOS.WinUI.Views;

namespace ConstructionOS.WinUI;

/// <summary>
/// U1 shell as an Excel-style ribbon. A row of <see cref="ToggleButton"/>s is the
/// section tab strip (from GET /api/menu); picking a section fills the ribbon band
/// with that section's tabs as icon commands (<see cref="AppBarButton"/>), and
/// clicking one navigates. Always-on entries (Home/Assistant/Process/Tools) and
/// Settings are leaf tabs that navigate directly with no band. Built from the
/// simplest stock primitives so the shell has no overflow-measure native code to
/// fail-fast on (NavigationView Top / SelectorBar both did on this SDK build).
/// </summary>
public sealed partial class MainWindow : Window
{
    // Menu tab label → API master table. One generic MastersPage serves them all.
    private static readonly Dictionary<string, string> MasterTables = new()
    {
        ["Sites"] = "sites", ["Clients"] = "clients", ["Vendors"] = "vendors",
        ["Materials"] = "materials", ["Labour"] = "labor",
        ["Equipment"] = "equipment", ["Thekedars"] = "thekedars",
        ["Projects"] = "projects", ["Milestones"] = "milestones",
        ["Rate Book"] = "rate_book", ["Contracts"] = "contracts",
    };

    // Money-document menu tabs → the API doc table the one generic MoneyPage
    // creates + lists (U3). These labels otherwise fall through to Home; the
    // ambiguous "BOQ / RA Bills" tab stays on ImportPage so BOQ import isn't
    // lost. Payments reach MoneyPage via NavRoute (its default table).
    private static readonly Dictionary<string, string> MoneyDocs = new()
    {
        ["Tax Invoice"] = "tax_invoices",
        ["Vendor Invoices"] = "vendor_invoices",
        ["Running Bills"] = "bills",
    };

    // Section title → its (tab label, routing tag) items, for the ribbon band.
    // A section title absent here is a leaf tab that navigates to itself.
    private readonly Dictionary<string, List<(string Label, string Tag)>> _sectionTabs = new();

    public MainWindow()
    {
        InitializeComponent();
        // Keep the standard OS title bar above the ribbon.
        ExtendsContentIntoTitleBar = false;
        // Open wide enough for the ribbon to breathe (the strip scrolls if it
        // still doesn't fit). Set here so nothing resizes the window mid-render.
        try { AppWindow?.Resize(new Windows.Graphics.SizeInt32(1400, 900)); }
        catch { /* sizing is best-effort */ }
    }

    private async void OnRootLoaded(object sender, RoutedEventArgs e)
    {
        try
        {
            // Log in FIRST — /api/menu (and /api/health) need a session; probing
            // health before login 401s and would abort the whole ribbon build.
            await ApiClient.Default.EnsureSessionAsync();
            var apiVer = "?";
            try
            {
                var health = await ApiClient.Default.HealthAsync();
                if (health.TryGetProperty("api", out var v)) apiVer = v.ToString();
            }
            catch { /* health is cosmetic — never block the ribbon on it */ }

            var persona = Uri.EscapeDataString(AppSettings.Current.Persona);
            var menu = await ApiClient.Default.GetJsonAsync("api/menu?persona=" + persona);

            Tabs.Children.Clear();
            _sectionTabs.Clear();

            // Always-on leaves (Home, Assistant, Process, Tools) — no band.
            if (menu.TryGetProperty("always_on", out var always))
                foreach (var item in always.EnumerateArray())
                    AddTab(item.GetString() ?? "");

            // Sections carry tabs → shown in the band when the section is picked.
            if (menu.TryGetProperty("sections", out var sections))
                foreach (var section in sections.EnumerateArray())
                {
                    var title = section.GetProperty("title").GetString() ?? "";
                    var tabs = new List<(string Label, string Tag)>();
                    if (section.TryGetProperty("tabs", out var tabArr))
                        foreach (var tab in tabArr.EnumerateArray())
                        {
                            var name = tab.GetString() ?? "";
                            tabs.Add((name, $"{title}/{name}"));
                        }
                    _sectionTabs[title] = tabs;
                    AddTab(title);
                }

            AddTab("Settings");   // leaf → SettingsPage via NavRoute

            Title = $"ACO (api {apiVer})";
            // Defer the first navigation to a later (Low-priority) UI turn. Doing
            // it synchronously here — in the same async continuation that just
            // built the tab strip, while the window's initial layout is still in
            // flight — races the first render pass and intermittently corrupts the
            // native heap (a 0xc000027b fail-fast in Microsoft.ui.xaml.dll that no
            // managed handler sees). Posting it lets the shell's layout settle
            // first. Verified: 0/14 startups crash deferred vs 11/12 synchronous.
            if (Tabs.Children.Count > 0 && Tabs.Children[0] is ToggleButton first)
                DispatcherQueue.TryEnqueue(
                    Microsoft.UI.Dispatching.DispatcherQueuePriority.Low,
                    () => SelectTab(first));   // Home
        }
        catch (Exception ex)
        {
            ShowOffline(ex);
        }
    }

    private void AddTab(string title)
    {
        var tab = new ToggleButton { Content = title, Tag = title };
        tab.Click += (s, _) => SelectTab((ToggleButton)s);
        Tabs.Children.Add(tab);
    }

    // Excel-style: selecting a section shows its commands in the band but does not
    // itself change the page — the user clicks a command to navigate. A leaf tab
    // (always-on / Settings) has no commands, so selecting it navigates directly.
    private void SelectTab(ToggleButton tab)
    {
        foreach (var child in Tabs.Children)
            if (child is ToggleButton other)
                other.IsChecked = ReferenceEquals(other, tab);

        if (tab.Tag is not string key) return;
        if (_sectionTabs.TryGetValue(key, out var tabs) && tabs.Count > 0)
        {
            BuildRibbon(tabs);
            RibbonBand.Visibility = Visibility.Visible;
        }
        else
        {
            Ribbon.Children.Clear();
            RibbonBand.Visibility = Visibility.Collapsed;
            NavigateTo(key);
        }
    }

    private void BuildRibbon(IEnumerable<(string Label, string Tag)> tabs)
    {
        Ribbon.Children.Clear();
        foreach (var (label, tag) in tabs)
        {
            var btn = new AppBarButton
            {
                Label = label,
                Icon = new FontIcon { Glyph = RibbonIcons.Glyph(label) },
                Tag = tag,
            };
            btn.Click += (_, _) => NavigateTo((string)btn.Tag);
            Ribbon.Children.Add(btn);
        }
    }

    private void ShowOffline(Exception ex)
    {
        ContentFrame.Content = new TextBlock
        {
            Text = "Backend unreachable. Start:\n"
                   + "  cd construction_app && python web_main.py --host 127.0.0.1 --port 8080\n\n"
                   + "Or open Settings after fixing the URL.\n\n"
                   + ApiException.UserMessage(ex),
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(24),
        };
        Tabs.Children.Clear();
        _sectionTabs.Clear();
        RibbonBand.Visibility = Visibility.Collapsed;
        AddTab("Settings");   // still reachable offline to fix the URL
    }

    // Master tabs carry a table name to the one generic MastersPage; money-doc
    // tabs carry a doc table to MoneyPage; everything else resolves by NavRoute
    // (typed tag → page). Shared by the ribbon and the search palette.
    private void NavigateTo(string tag)
    {
        var tab = tag.Contains('/') ? tag[(tag.LastIndexOf('/') + 1)..] : tag;
        if (MasterTables.TryGetValue(tab, out var table))
            ContentFrame.Navigate(typeof(MastersPage), table);
        else if (MoneyDocs.TryGetValue(tab, out var doc))
            ContentFrame.Navigate(typeof(MoneyPage), doc);
        else
            ContentFrame.Navigate(NavRoute.Resolve(tag));
    }

    // ------------------------------------------------------ U5 command palette
    // Each suggestion is a tab the backend matched; keep the section+tab so a
    // chosen label routes exactly like clicking that ribbon command.
    private readonly List<(string Section, string Tab, string Label)> _hits = new();

    private async void Search_TextChanged(AutoSuggestBox sender,
                                          AutoSuggestBoxTextChangedEventArgs args)
    {
        if (args.Reason != AutoSuggestionBoxTextChangeReason.UserInput) return;
        var q = (sender.Text ?? "").Trim();
        if (q.Length == 0) { sender.ItemsSource = null; return; }
        try
        {
            var data = await ApiClient.Default.GetJsonAsync(
                "api/search?q=" + Uri.EscapeDataString(q));
            _hits.Clear();
            if (data.TryGetProperty("hits", out var hits)
                && hits.ValueKind == System.Text.Json.JsonValueKind.Array)
                foreach (var h in hits.EnumerateArray())
                    _hits.Add((Prop(h, "section"), Prop(h, "tab"),
                               Prop(h, "label")));
            sender.ItemsSource = _hits.Select(h => h.Label).ToList();
        }
        catch
        {
            sender.ItemsSource = null;   // search is best-effort, never fatal
        }
    }

    private void Search_SuggestionChosen(
        AutoSuggestBox sender, AutoSuggestBoxSuggestionChosenEventArgs args) =>
        GoToHit(args.SelectedItem as string);

    private void Search_QuerySubmitted(
        AutoSuggestBox sender, AutoSuggestBoxQuerySubmittedEventArgs args) =>
        GoToHit(args.ChosenSuggestion as string
                ?? (_hits.Count > 0 ? _hits[0].Label : null));

    private void GoToHit(string? label)
    {
        var hit = _hits.FirstOrDefault(h => h.Label == label);
        if (hit.Tab is null) return;
        NavigateTo(string.IsNullOrEmpty(hit.Section) ? hit.Tab
                   : $"{hit.Section}/{hit.Tab}");
        Search.Text = "";
    }

    private static string Prop(System.Text.Json.JsonElement o, string key) =>
        o.TryGetProperty(key, out var v) ? v.GetString() ?? "" : "";
}
