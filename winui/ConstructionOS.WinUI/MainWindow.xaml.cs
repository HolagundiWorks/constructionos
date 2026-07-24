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
        // "Subcontractors" now routes to SubcontractorsPage (work orders + sub
        // bills); "Thekedars" stays the labour-contractor master.
        ["Thekedars"] = "thekedars",
    };

    // Read-only register/report tabs → a generic DataTablePage over an API
    // endpoint ("path|Title[|itemsKey]"). Endpoint-backed tabs that aren't a
    // master, money doc, or a dedicated page.
    private static readonly Dictionary<string, string> TableTabs = new()
    {
        // Purchases ("Goods Receipt" -> MatchPage: PO/GRN/invoice three-way match)
        ["Purchase Orders"] = "purchase_orders|Purchase orders",
        ["Sourcing"] = "material_requisitions|Requisitions / sourcing",
        // Operations ("Muster & Wages" -> MusterPage: the attendance grid + payout)
        ["Warehouse"] = "material_ledger|Stock ledger",
        ["Labour Ops"] = "payroll|Payroll",
        ["Equipment Hire"] = "equipment_hire|Equipment hire",
        ["Plant"] = "plant_logs|Plant logs",
        ["Consumption"] = "consumption_norms|Consumption norms",
        ["Site Reports"] = "daily_progress|Daily progress",
        ["Quality"] = "ncrs|NCRs / quality",
        ["Safety"] = "incidents|Safety incidents",
        ["Closeout"] = "snags|Snag list",
        // Billing
        ["Rate Analysis"] = "rate_analysis|Rate analysis",
        ["Takeoff"] = "takeoffs|Takeoffs",
        ["Bid / No Bid"] = "bid_assessments|Bid / no-bid",
        ["Quotations"] = "quotations|Quotations",
        ["Estimates"] = "estimates|Estimates",
        ["Variations"] = "variations|Variations",
        // Project Management ("Timeline" -> TimelinePage: CPM programme view)
        // Money · Accounts
        ["Approvals"] = "approvals|Approvals",
        ["Retention"] = "retention_releases|Retention releases",
        ["Compliance"] = "filings/feed|Compliance calendar|events",
        // "Accounting" and "Look-ahead" resolve to their own pages (AccountingPage
        // combines P&L / Balance Sheet / Journal; LookaheadPage adds PPC + trend)
        // via NavRoute — not the generic single-table view.
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

    // One-shot timer that defers the shell build until the window has rendered a
    // few frames, so tree mutation doesn't race first layout (heap-corruption).
    private DispatcherTimer? _startupTimer;

    public MainWindow()
    {
        InitializeComponent();
        // Keep the standard OS title bar above the ribbon.
        ExtendsContentIntoTitleBar = false;
        // NOTE: MicaBackdrop was removed — setting a SystemBackdrop at
        // construction time intermittently contributed to a native 0xc000027b
        // heap-corruption fail-fast in Microsoft.ui.xaml.dll during the window's
        // first layout on this Windows App SDK build. A stable shell beats the
        // Mica material; revisit applying it post-activation if it proves safe.
        // Open wide enough for the ribbon to breathe (the strip scrolls if it
        // still doesn't fit). Set here so nothing resizes the window mid-render.
        try { AppWindow?.Resize(new Windows.Graphics.SizeInt32(1400, 900)); }
        catch { /* sizing is best-effort */ }
        ApplyTheme();   // honour the saved Light / Dark / System choice
    }

    /// <summary>Apply the saved UI theme (Light / Dark / follow-Windows) to the
    /// whole window at runtime — Fluent "Personal". Called at startup and after a
    /// Settings change. The brand accent ramp (App.xaml Dark1–3) holds in both.</summary>
    public void ApplyTheme()
    {
        Root.RequestedTheme = (AppSettings.Current.Theme ?? "Light").Trim().ToLowerInvariant() switch
        {
            "dark" => ElementTheme.Dark,
            "system" or "default" or "windows" => ElementTheme.Default,
            _ => ElementTheme.Light,
        };
    }

    private async void OnRootLoaded(object sender, RoutedEventArgs e) =>
        await LoadShellAsync(deferred: true);

    /// <summary>Reload the shell after a company/connection change (from
    /// Settings): re-log in to the (possibly new) company, rebuild the ribbon,
    /// and refresh the title + page. Synchronous build — the window is already
    /// up, so there's no first-layout race to defer around.</summary>
    public async void ReloadShell() => await LoadShellAsync(deferred: false);

    private async Task LoadShellAsync(bool deferred)
    {
        try
        {
            // Make sure the localhost backend is up (auto-launch the sidecar if
            // configured/bundled) before anything talks to it. No-op if already
            // running or the API is remote.
            await BackendLauncher.EnsureAsync();
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

            // Parse the menu into plain data only — no UI-tree mutation here.
            var alwaysOn = new List<string>();
            if (menu.TryGetProperty("always_on", out var always))
                foreach (var item in always.EnumerateArray())
                {
                    var s = item.GetString();
                    if (!string.IsNullOrEmpty(s)) alwaysOn.Add(s!);
                }
            var sectionList = new List<(string Title, List<(string Label, string Tag)> Tabs)>();
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
                    sectionList.Add((title, tabs));
                }

            // Active company (multi-company): show which book is open in the
            // title. /api/companies (public) returns the registry's friendly names
            // + the active book. Best-effort — never block the shell on it.
            var book = "";
            try
            {
                var co = await ApiClient.Default.GetJsonAsync("api/companies");
                if (co.TryGetProperty("items", out var items)
                    && items.ValueKind == System.Text.Json.JsonValueKind.Array)
                    foreach (var it in items.EnumerateArray())
                        if (it.TryGetProperty("active", out var a)
                            && a.ValueKind == System.Text.Json.JsonValueKind.True
                            && it.TryGetProperty("name", out var n))
                            { book = (n.GetString() ?? "").Trim(); break; }
            if (book.EndsWith(".db", StringComparison.OrdinalIgnoreCase))
                book = book[..^3];   // registry names sometimes keep the extension
                if (book.Length == 0
                    && co.TryGetProperty("active", out var act)
                    && act.ValueKind == System.Text.Json.JsonValueKind.String)
                    book = System.IO.Path.GetFileNameWithoutExtension(act.GetString() ?? "");
            }
            catch { /* company is cosmetic in the title */ }

            Title = string.IsNullOrEmpty(book)
                ? $"ACO (api {apiVer})"
                : $"ACO — {book} (api {apiVer})";
            // Build the whole shell only AFTER the window has actually rendered a
            // few frames. Mutating the visual tree in this async continuation (or
            // even on a Low-priority enqueue, which can fire mid-composition)
            // races the window's first layout pass and intermittently corrupts the
            // native heap — a 0xc000027b fail-fast in Microsoft.ui.xaml.dll that no
            // managed handler sees. A short one-shot timer waits real wall-clock
            // time, so first layout is done before any tree mutation.
            if (deferred)
            {
                _startupTimer = new DispatcherTimer
                { Interval = TimeSpan.FromMilliseconds(150) };
                _startupTimer.Tick += (_, _) =>
                {
                    _startupTimer!.Stop();
                    _startupTimer = null;
                    BuildShell(alwaysOn, sectionList);
                };
                _startupTimer.Start();
            }
            else
            {
                // Mid-session reload: window already rendered, no race — build now.
                BuildShell(alwaysOn, sectionList);
            }
        }
        catch (Exception ex)
        {
            ShowOffline(ex);
        }
    }

    // Builds the tab strip + utility cluster, then defers the first navigation.
    // Home leads the primary strip; the other always-on helpers and Settings go
    // to the right-hand utility cluster (Fluent navigation-basics: keep top-level
    // peers under ~8, hide less-important items).
    private void BuildShell(
        List<string> alwaysOn,
        List<(string Title, List<(string Label, string Tag)> Tabs)> sectionList)
    {
        Tabs.Children.Clear();
        Utilities.Children.Clear();
        _sectionTabs.Clear();

        var firstLeaf = true;
        foreach (var label in alwaysOn)
        {
            if (firstLeaf) { AddTab(label); firstLeaf = false; }
            else AddUtility(label);
        }
        foreach (var (title, tabs) in sectionList)
        {
            _sectionTabs[title] = tabs;
            AddTab(title);
        }
        AddUtility("Settings");   // standard gear location, off the strip

        // Defer the first navigation (page load) — loading synchronously here is
        // the single biggest crash source (it races the just-built strip's layout
        // and corrupts the native heap). Low-priority enqueue was the best config.
        if (Tabs.Children.Count > 0 && Tabs.Children[0] is ToggleButton first)
            DispatcherQueue.TryEnqueue(
                Microsoft.UI.Dispatching.DispatcherQueuePriority.Low,
                () => SelectTab(first));   // Home
    }

    private void AddTab(string title)
    {
        var tab = new ToggleButton { Content = title, Tag = title };
        tab.Click += (s, _) => SelectTab((ToggleButton)s);
        Tabs.Children.Add(tab);
    }

    // Always-on helpers (Assistant/Process/Tools) and Settings live as icon
    // buttons in the right-hand cluster — off the primary tab strip, in their
    // standard location. Icon-only; the label is the accessible name. (No
    // ToolTipService here — creating ToolTip popups during the startup build was
    // implicated in the intermittent 0xc000027b heap-corruption fail-fast.)
    private void AddUtility(string title)
    {
        var btn = new Button
        {
            Content = new FontIcon { Glyph = RibbonIcons.Glyph(title), FontSize = 16 },
            Tag = title,
        };
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(btn, title);
        btn.Click += (_, _) => NavigateToUtility(title);
        Utilities.Children.Add(btn);
    }

    // A utility navigates directly and clears any section-tab selection + band,
    // since it lives outside the section model.
    private void NavigateToUtility(string tag)
    {
        foreach (var child in Tabs.Children)
            if (child is ToggleButton tb) tb.IsChecked = false;
        Ribbon.Children.Clear();
        RibbonBand.Visibility = Visibility.Collapsed;
        NavigateTo(tag);
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
        Utilities.Children.Clear();
        _sectionTabs.Clear();
        RibbonBand.Visibility = Visibility.Collapsed;
        AddUtility("Settings");   // still reachable offline to fix the URL
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
        else if (TableTabs.TryGetValue(tab, out var spec))
            ContentFrame.Navigate(typeof(DataTablePage), spec);
        else if (NavRoute.TryResolve(tag, out var page))
            ContentFrame.Navigate(page);
        else
            // No master, doc, table, or dedicated page — a section the API
            // doesn't expose yet. Land on a named placeholder, never a dead-end.
            ContentFrame.Navigate(typeof(InfoPage), tab);
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
