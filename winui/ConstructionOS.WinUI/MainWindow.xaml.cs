using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;
using ConstructionOS.WinUI.Views;

namespace ConstructionOS.WinUI;

/// <summary>
/// U1 shell: NavigationView items from GET /api/menu?persona=…; Settings gear
/// opens connection settings.
/// </summary>
public sealed partial class MainWindow : Window
{
    // Menu tab label → API master table. The tab labels come from the persona
    // menu (/api/menu); the API registers are the lowercase table names. One
    // generic MastersPage serves them all (U2).
    private static readonly Dictionary<string, string> MasterTables = new()
    {
        ["Sites"] = "sites", ["Clients"] = "clients", ["Vendors"] = "vendors",
        ["Materials"] = "materials", ["Labour"] = "labor",
        ["Equipment"] = "equipment", ["Thekedars"] = "thekedars",
        ["Projects"] = "projects", ["Milestones"] = "milestones",
        ["Rate Book"] = "rate_book", ["Contracts"] = "contracts",
    };

    public MainWindow()
    {
        InitializeComponent();
        // Keep a standard OS title bar: with the top-ribbon NavigationView,
        // extending content into the title bar makes the ribbon collide with the
        // caption/close buttons. A normal title bar sits above the ribbon.
        ExtendsContentIntoTitleBar = false;
    }

    private async void Nav_Loaded(object sender, RoutedEventArgs e)
    {
        try
        {
            // Log in FIRST — /api/health (and /api/menu) require a session, so
            // probing health before the session 401s and would abort the whole
            // nav. The health call is only for the title's API version, so keep
            // it after login and non-fatal.
            await ApiClient.Default.EnsureSessionAsync();
            var apiVer = "?";
            try
            {
                var health = await ApiClient.Default.HealthAsync();
                if (health.TryGetProperty("api", out var v)) apiVer = v.ToString();
            }
            catch { /* health is cosmetic — never block the menu on it */ }
            var persona = Uri.EscapeDataString(AppSettings.Current.Persona);
            var menu = await ApiClient.Default.GetJsonAsync("api/menu?persona=" + persona);
            Nav.MenuItems.Clear();
            if (menu.TryGetProperty("always_on", out var always))
            {
                foreach (var item in always.EnumerateArray())
                {
                    var label = item.GetString() ?? "";
                    Nav.MenuItems.Add(new NavigationViewItem
                    {
                        Content = label,
                        Tag = label,
                    });
                }
            }
            if (menu.TryGetProperty("sections", out var sections))
            {
                foreach (var section in sections.EnumerateArray())
                {
                    var title = section.GetProperty("title").GetString() ?? "";
                    var parent = new NavigationViewItem { Content = title, Tag = title };
                    if (section.TryGetProperty("tabs", out var tabs))
                    {
                        foreach (var tab in tabs.EnumerateArray())
                        {
                            var name = tab.GetString() ?? "";
                            parent.MenuItems.Add(new NavigationViewItem
                            {
                                Content = name,
                                Tag = $"{title}/{name}",
                            });
                        }
                    }
                    Nav.MenuItems.Add(parent);
                }
            }
            ContentFrame.Navigate(typeof(HomePage));
            Title = $"ACO (api {apiVer})";
        }
        catch (Exception ex)
        {
            ContentFrame.Content = new TextBlock
            {
                Text = "Backend unreachable. Start:\n"
                       + "  cd construction_app && python web_main.py --host 127.0.0.1 --port 8080\n\n"
                       + "Or open Settings (gear) after fixing the URL.\n\n"
                       + ApiException.UserMessage(ex),
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(24),
            };
            // Still allow Settings when offline.
            Nav.MenuItems.Clear();
            Nav.MenuItems.Add(new NavigationViewItem
            {
                Content = "Home",
                Tag = "Home",
            });
        }
    }

    private void Nav_SelectionChanged(NavigationView sender,
                                      NavigationViewSelectionChangedEventArgs args)
    {
        if (args.IsSettingsSelected)
        {
            ContentFrame.Navigate(typeof(SettingsPage));
            return;
        }
        if (args.SelectedItem is NavigationViewItem item)
            NavigateTo(item.Tag?.ToString() ?? "");
    }

    // Master tabs carry a table name to the one generic MastersPage (U2);
    // everything else resolves by NavRoute (typed tag → page). Shared by the
    // rail selection and the search palette so they route identically.
    private void NavigateTo(string tag)
    {
        var tab = tag.Contains('/') ? tag[(tag.LastIndexOf('/') + 1)..] : tag;
        if (MasterTables.TryGetValue(tab, out var table))
            ContentFrame.Navigate(typeof(MastersPage), table);
        else
            ContentFrame.Navigate(NavRoute.Resolve(tag));
    }

    // ------------------------------------------------------ U5 command palette
    // Each suggestion is a tab the backend matched; keep the section+tab so a
    // chosen label routes exactly like clicking that rail item.
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
