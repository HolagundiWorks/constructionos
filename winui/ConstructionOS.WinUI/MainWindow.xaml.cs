using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;
using ConstructionOS.WinUI.Views;

namespace ConstructionOS.WinUI;

/// <summary>
/// U1 shell: NavigationView from GET /api/menu; AutoSuggest from GET /api/search;
/// Settings gear; master tabs → MastersPage.
/// </summary>
public sealed partial class MainWindow : Window
{
    private static readonly Dictionary<string, string> MasterTables = new()
    {
        ["Sites"] = "sites", ["Clients"] = "clients", ["Vendors"] = "vendors",
        ["Materials"] = "materials", ["Labour"] = "labor",
        ["Equipment"] = "equipment", ["Thekedars"] = "thekedars",
        ["Projects"] = "projects", ["Milestones"] = "milestones",
        ["Rate Book"] = "rate_book", ["Contracts"] = "contracts",
    };

    private sealed record SearchHit(string Display, string? NavTag, string? Table, int? Id);

    private List<SearchHit> _searchHits = new();

    public MainWindow()
    {
        InitializeComponent();
        ExtendsContentIntoTitleBar = true;
    }

    private async void Nav_Loaded(object sender, RoutedEventArgs e)
    {
        try
        {
            var health = await ApiClient.Default.HealthAsync();
            var apiVer = health.TryGetProperty("api", out var v) ? v.ToString() : "?";
            await ApiClient.Default.EnsureSessionAsync();
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
            Title = $"Construction OS (api {apiVer})";
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
            NavigateTag(item.Tag?.ToString() ?? "");
    }

    void NavigateTag(string tag)
    {
        var tab = tag.Contains('/') ? tag[(tag.LastIndexOf('/') + 1)..] : tag;
        if (MasterTables.TryGetValue(tab, out var table))
            ContentFrame.Navigate(typeof(MastersPage), table);
        else
            ContentFrame.Navigate(NavRoute.Resolve(tag));
    }

    private async void SearchBox_TextChanged(AutoSuggestBox sender,
        AutoSuggestBoxTextChangedEventArgs args)
    {
        if (args.Reason != AutoSuggestionBoxTextChangeReason.UserInput) return;
        var q = (sender.Text ?? "").Trim();
        if (q.Length < 2)
        {
            sender.ItemsSource = null;
            _searchHits = new();
            return;
        }
        try
        {
            var data = await ApiClient.Default.GetJsonAsync(
                "api/search?q=" + Uri.EscapeDataString(q));
            _searchHits = new List<SearchHit>();
            if (data.TryGetProperty("tabs", out var tabs)
                && tabs.ValueKind == JsonValueKind.Array)
            {
                foreach (var t in tabs.EnumerateArray())
                {
                    var label = t.TryGetProperty("label", out var lb)
                        ? lb.GetString() : t.GetString();
                    var section = t.TryGetProperty("section", out var sec)
                        ? sec.GetString() : null;
                    var tab = t.TryGetProperty("tab", out var tb)
                        ? tb.GetString() : label;
                    var nav = !string.IsNullOrEmpty(section) && !string.IsNullOrEmpty(tab)
                        ? $"{section}/{tab}" : tab;
                    _searchHits.Add(new SearchHit(label ?? tab ?? "?", nav, null, null));
                }
            }
            if (data.TryGetProperty("records", out var recs)
                && recs.ValueKind == JsonValueKind.Array)
            {
                foreach (var r in recs.EnumerateArray())
                {
                    var display = r.TryGetProperty("display", out var d)
                        ? d.GetString()
                        : r.TryGetProperty("label", out var l) ? l.GetString() : "?";
                    var nav = r.TryGetProperty("nav", out var n) ? n.GetString()
                        : r.TryGetProperty("tag", out var tg) ? tg.GetString() : null;
                    var table = r.TryGetProperty("table", out var tbl)
                        ? tbl.GetString() : null;
                    int? id = null;
                    if (r.TryGetProperty("id", out var idEl)
                        && idEl.TryGetInt32(out var iid))
                        id = iid;
                    _searchHits.Add(new SearchHit(display ?? "?", nav, table, id));
                }
            }
            sender.ItemsSource = _searchHits.Select(h => h.Display).Take(20).ToList();
        }
        catch
        {
            sender.ItemsSource = null;
        }
    }

    private void SearchBox_SuggestionChosen(AutoSuggestBox sender,
        AutoSuggestBoxSuggestionChosenEventArgs args)
    {
        var text = args.SelectedItem as string;
        OpenSearchHit(text);
    }

    private void SearchBox_QuerySubmitted(AutoSuggestBox sender,
        AutoSuggestBoxQuerySubmittedEventArgs args)
    {
        OpenSearchHit(args.ChosenSuggestion as string ?? sender.Text);
    }

    void OpenSearchHit(string? display)
    {
        if (string.IsNullOrWhiteSpace(display)) return;
        var hit = _searchHits.FirstOrDefault(h => h.Display == display);
        if (hit == null) return;
        if (!string.IsNullOrEmpty(hit.Table)
            && MasterTables.Values.Contains(hit.Table))
        {
            ContentFrame.Navigate(typeof(MastersPage), hit.Table);
            return;
        }
        if (!string.IsNullOrEmpty(hit.NavTag))
            NavigateTag(hit.NavTag!);
    }
}
