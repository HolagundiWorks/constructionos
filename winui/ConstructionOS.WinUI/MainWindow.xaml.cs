using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;
using ConstructionOS.WinUI.Views;

namespace ConstructionOS.WinUI;

/// <summary>
/// U1 shell: NavigationView items come from GET /api/menu?persona=Owner.
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
        ["Rate Book"] = "rate_book",
    };

    public MainWindow()
    {
        InitializeComponent();
        ExtendsContentIntoTitleBar = true;
    }

    private async void Nav_Loaded(object sender, RoutedEventArgs e)
    {
        try
        {
            await ApiClient.Default.EnsureSessionAsync();
            var menu = await ApiClient.Default.GetJsonAsync("api/menu?persona=Owner");
            Nav.MenuItems.Clear();
            if (menu.TryGetProperty("always_on", out var always))
            {
                foreach (var item in always.EnumerateArray())
                {
                    Nav.MenuItems.Add(new NavigationViewItem
                    {
                        Content = item.GetString(),
                        Tag = item.GetString(),
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
                            parent.MenuItems.Add(new NavigationViewItem
                            {
                                Content = tab.GetString(),
                                Tag = $"{title}/{tab.GetString()}",
                            });
                        }
                    }
                    Nav.MenuItems.Add(parent);
                }
            }
            ContentFrame.Navigate(typeof(HomePage));
        }
        catch (Exception ex)
        {
            ContentFrame.Content = new TextBlock
            {
                Text = "Backend unreachable. Start: cd construction_app && python web_main.py\n\n"
                       + ex.Message,
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(24),
            };
        }
    }

    private void Nav_SelectionChanged(NavigationView sender,
                                      NavigationViewSelectionChangedEventArgs args)
    {
        if (args.SelectedItem is NavigationViewItem item)
        {
            var tag = item.Tag?.ToString() ?? "";
            // Tags are "Section/Tab" (or a bare label for always-on rows); the
            // register is identified by the tab label, section-agnostic.
            var tab = tag.Contains('/') ? tag[(tag.LastIndexOf('/') + 1)..] : tag;
            if (MasterTables.TryGetValue(tab, out var table))
                ContentFrame.Navigate(typeof(MastersPage), table);
            else if (tag is "Home" or "")
                ContentFrame.Navigate(typeof(HomePage));
            else if (tab.Contains("Risk", StringComparison.OrdinalIgnoreCase))
                ContentFrame.Navigate(typeof(RisksPage));
            else if (tag.Contains("Opportun", StringComparison.OrdinalIgnoreCase))
                ContentFrame.Navigate(typeof(OpportunitiesPage));
            else if (tag.Contains("Lesson", StringComparison.OrdinalIgnoreCase))
                ContentFrame.Navigate(typeof(LessonsPage));
            else if (tag.Contains("Submittal", StringComparison.OrdinalIgnoreCase))
                ContentFrame.Navigate(typeof(SubmittalsPage));
            else if (tag.Contains("Cash", StringComparison.OrdinalIgnoreCase)
                     || tag.Contains("Payment", StringComparison.OrdinalIgnoreCase)
                     || tag.Contains("Money", StringComparison.OrdinalIgnoreCase))
                ContentFrame.Navigate(typeof(MoneyPage));
            else if (tag.Contains("Earned", StringComparison.OrdinalIgnoreCase)
                     || tag.Contains("EVM", StringComparison.OrdinalIgnoreCase))
                ContentFrame.Navigate(typeof(EvmPage));
            else if (tag.Contains("Portfolio", StringComparison.OrdinalIgnoreCase))
                ContentFrame.Navigate(typeof(PortfolioPage));
            else if (tag.Contains("Chart", StringComparison.OrdinalIgnoreCase)
                     || tag.Contains("Key Numbers", StringComparison.OrdinalIgnoreCase))
                ContentFrame.Navigate(typeof(ChartsPage));
            else if (tag.Contains("Process", StringComparison.OrdinalIgnoreCase)
                     || tag == "What's next")
                ContentFrame.Navigate(typeof(ProcessPage));
            else
                ContentFrame.Navigate(typeof(HomePage));
        }
    }
}
