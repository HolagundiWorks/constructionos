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
        {
            var tag = item.Tag?.ToString() ?? "";
            ContentFrame.Navigate(NavRoute.Resolve(tag));
        }
    }
}
