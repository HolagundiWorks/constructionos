using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Text;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Tools (the always-on rail utility) — the settings that live in the company
/// data file, over GET/POST /api/firm and /api/modules: the firm's letterhead
/// identity (printed on every outward document) and which modules/tabs are shown.
/// Reads populate the forms; Save posts back (CSRF-gated by ApiClient). No
/// validation logic in C# — the backend owns it. Backup/restore, invoice-number
/// series, reference-data load and language stay in the desktop / browser app for
/// now (not yet exposed through the JSON API).
/// </summary>
public sealed partial class ToolsPage : Page
{
    private readonly List<(string Key, TextBox Box)> _firm = new();
    private readonly List<(string Label, CheckBox Box)> _modules = new();

    public ToolsPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await LoadAsync();

    private async Task LoadAsync()
    {
        Host.Children.Clear();
        _firm.Clear();
        _modules.Clear();
        Host.Children.Add(Ui.Loading());
        try
        {
            var firm = await ApiClient.Default.GetJsonAsync("api/firm");
            var modules = await ApiClient.Default.GetJsonAsync("api/modules");
            Host.Children.Clear();
            Host.Children.Add(FirmCard(firm));
            Host.Children.Add(ModulesCard(modules));
        }
        catch (Exception ex)
        {
            Host.Children.Clear();
            Host.Children.Add(new TextBlock
            {
                Text = ApiException.UserMessage(ex),
                TextWrapping = TextWrapping.Wrap,
                Foreground = (Microsoft.UI.Xaml.Media.Brush)
                    Application.Current.Resources["TextFillColorSecondaryBrush"],
            });
        }
    }

    // ---------------------------------------------------------------- firm
    private FrameworkElement FirmCard(JsonElement firm)
    {
        var panel = SectionPanel("Firm details (letterhead)",
            "Printed as the letterhead on quotations, contracts, invoices and reports.");

        if (firm.TryGetProperty("fields", out var fields)
            && fields.ValueKind == JsonValueKind.Array)
            foreach (var f in fields.EnumerateArray())
            {
                var key = f.TryGetProperty("key", out var k) ? k.GetString() : null;
                if (string.IsNullOrEmpty(key)) continue;
                var label = f.TryGetProperty("label", out var l) ? l.GetString() : key;
                var value = f.TryGetProperty("value", out var v) && v.ValueKind == JsonValueKind.String
                    ? v.GetString() : "";
                var box = new TextBox
                {
                    Header = label,
                    Text = value ?? "",
                    HorizontalAlignment = HorizontalAlignment.Stretch,
                    Margin = new Thickness(0, 4, 0, 0),
                };
                _firm.Add((key!, box));
                panel.Children.Add(box);
            }

        var save = new Button
        {
            Content = "Save firm details",
            Style = (Style)Application.Current.Resources["AccentButtonStyle"],
            Margin = new Thickness(0, 12, 0, 0),
        };
        save.Click += OnSaveFirm;
        panel.Children.Add(save);
        return Card(panel);
    }

    private async void OnSaveFirm(object sender, RoutedEventArgs e)
    {
        var payload = new Dictionary<string, string>();
        foreach (var (key, box) in _firm) payload[key] = box.Text?.Trim() ?? "";
        try
        {
            await ApiClient.Default.PostJsonAsync("api/firm", payload);
            Show("Firm details saved",
                 "They now appear as the letterhead on printed documents.",
                 InfoBarSeverity.Success);
        }
        catch (Exception ex)
        {
            Show("Couldn't save firm details", ApiException.UserMessage(ex),
                 InfoBarSeverity.Error);
        }
    }

    // ------------------------------------------------------------- modules
    private FrameworkElement ModulesCard(JsonElement modules)
    {
        var panel = SectionPanel("Modules",
            "Switch off what you don't use. Hidden modules drop out of the menu the "
            + "next time the app opens.");

        if (modules.TryGetProperty("sections", out var sections)
            && sections.ValueKind == JsonValueKind.Array)
            foreach (var s in sections.EnumerateArray())
            {
                panel.Children.Add(new TextBlock
                {
                    Text = s.TryGetProperty("title", out var t) ? t.GetString() : "",
                    FontWeight = FontWeights.SemiBold,
                    Margin = new Thickness(0, 10, 0, 2),
                });
                if (!s.TryGetProperty("tabs", out var tabs)
                    || tabs.ValueKind != JsonValueKind.Array) continue;
                foreach (var tab in tabs.EnumerateArray())
                {
                    var label = tab.TryGetProperty("label", out var l) ? l.GetString() : null;
                    if (string.IsNullOrEmpty(label)) continue;
                    var enabled = !tab.TryGetProperty("enabled", out var en)
                                  || en.ValueKind != JsonValueKind.False;
                    var cb = new CheckBox { Content = label, IsChecked = enabled };
                    _modules.Add((label!, cb));
                    panel.Children.Add(cb);
                }
            }

        var save = new Button
        {
            Content = "Save modules",
            Style = (Style)Application.Current.Resources["AccentButtonStyle"],
            Margin = new Thickness(0, 12, 0, 0),
        };
        save.Click += OnSaveModules;
        panel.Children.Add(save);
        return Card(panel);
    }

    private async void OnSaveModules(object sender, RoutedEventArgs e)
    {
        var states = new Dictionary<string, bool>();
        foreach (var (label, cb) in _modules) states[label] = cb.IsChecked == true;
        try
        {
            await ApiClient.Default.PostJsonAsync("api/modules", new { states });
            var off = states.Values.Count(v => !v);
            Show("Modules saved",
                 off == 0 ? "All modules enabled."
                          : $"{off} module(s) hidden. Reopen the app (or switch "
                            + "company in Settings) to apply.",
                 InfoBarSeverity.Success);
        }
        catch (Exception ex)
        {
            Show("Couldn't save modules", ApiException.UserMessage(ex),
                 InfoBarSeverity.Error);
        }
    }

    // ---------------------------------------------------------------- chrome
    private static StackPanel SectionPanel(string title, string subtitle)
    {
        var panel = new StackPanel { Spacing = 2 };
        panel.Children.Add(new TextBlock
        {
            Text = title,
            Style = (Style)Application.Current.Resources["SubtitleTextBlockStyle"],
        });
        panel.Children.Add(new TextBlock
        {
            Text = subtitle,
            TextWrapping = TextWrapping.Wrap,
            Foreground = (Microsoft.UI.Xaml.Media.Brush)
                Application.Current.Resources["TextFillColorSecondaryBrush"],
            Margin = new Thickness(0, 0, 0, 4),
        });
        return panel;
    }

    private static Border Card(FrameworkElement content) => new()
    {
        Child = content,
        Background = (Microsoft.UI.Xaml.Media.Brush)
            Application.Current.Resources["CardBackgroundFillColorDefaultBrush"],
        BorderBrush = (Microsoft.UI.Xaml.Media.Brush)
            Application.Current.Resources["CardStrokeColorDefaultBrush"],
        BorderThickness = new Thickness(1),
        CornerRadius = new CornerRadius(8),
        Padding = new Thickness(16),
    };

    private void Show(string title, string message, InfoBarSeverity severity)
    {
        Notice.Title = title;
        Notice.Message = message;
        Notice.Severity = severity;
        Notice.IsOpen = true;
    }
}
