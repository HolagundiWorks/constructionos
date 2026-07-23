using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

public sealed partial class SettingsPage : Page
{
    // Keep in sync with construction_app/menu.py PERSONAS.
    static readonly string[] DefaultPersonas =
    {
        "Owner", "Commercial / QS", "Site Engineer", "Accountant", "Storekeeper",
    };

    // Display label -> stored AppSettings.Theme value.
    static readonly (string Label, string Value)[] Themes =
    {
        ("Light", "Light"), ("Dark", "Dark"), ("Use Windows setting", "System"),
    };

    public SettingsPage()
    {
        InitializeComponent();
        Loaded += (_, _) => LoadForm();
    }

    void LoadForm()
    {
        var s = AppSettings.Load();
        BaseUrlBox.Text = s.BaseUrl;
        UserBox.Text = s.Username;
        PasswordBox.Password = s.Password;
        CompanyBox.Text = s.Company;
        TimeoutBox.Value = s.TimeoutSeconds;
        AutoStartBox.IsOn = s.AutoStartBackend;
        BackendCmdBox.Text = s.BackendCommand;
        BackendDirBox.Text = s.BackendWorkingDir;
        PersonaBox.ItemsSource = DefaultPersonas;
        PersonaBox.SelectedItem = DefaultPersonas.Contains(s.Persona)
            ? s.Persona
            : DefaultPersonas[0];
        ThemeBox.ItemsSource = Themes.Select(t => t.Label).ToList();
        ThemeBox.SelectedItem =
            Themes.FirstOrDefault(t => t.Value == s.Theme).Label ?? Themes[0].Label;
        Status.Text = "Settings path: " + AppSettings.SettingsPath;
        _ = TryLoadPersonasAsync();
        _ = TryLoadCompaniesAsync();
    }

    // Populate the company picker from GET /api/companies (public list of
    // registered books). The field stays editable — a book the client hasn't
    // registered can still be typed by path/name; blank = the server's active
    // book. Creating/importing books lives in the desktop/browser app.
    async Task TryLoadCompaniesAsync()
    {
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/companies");
            var names = new List<string>();
            string? active = null;
            if (data.TryGetProperty("items", out var list)
                && list.ValueKind == System.Text.Json.JsonValueKind.Array)
                foreach (var c in list.EnumerateArray())
                {
                    var name = c.TryGetProperty("name", out var n) ? n.GetString() : null;
                    if (string.IsNullOrWhiteSpace(name)) continue;
                    names.Add(name!);
                    if (c.TryGetProperty("active", out var a)
                        && a.ValueKind == System.Text.Json.JsonValueKind.True)
                        active = name;
                }
            if (names.Count > 0)
            {
                var saved = CompanyBox.Text;          // preserve the saved value
                CompanyBox.ItemsSource = names;
                CompanyBox.Text = saved;
            }
            if (!string.IsNullOrEmpty(active))
                Status.Text = $"Active book: {active}.  " + Status.Text;
        }
        catch
        {
            // Backend down — keep the free-text field, no picker.
        }
    }

    async Task TryLoadPersonasAsync()
    {
        try
        {
            var menu = await ApiClient.Default.GetJsonAsync(
                "api/menu?persona=" + Uri.EscapeDataString(AppSettings.Current.Persona));
            if (menu.TryGetProperty("personas", out var list)
                && list.ValueKind == System.Text.Json.JsonValueKind.Array)
            {
                var names = new List<string>();
                foreach (var p in list.EnumerateArray())
                {
                    var n = p.GetString();
                    if (!string.IsNullOrWhiteSpace(n)) names.Add(n!);
                }
                if (names.Count > 0)
                {
                    PersonaBox.ItemsSource = names;
                    var cur = AppSettings.Current.Persona;
                    PersonaBox.SelectedItem = names.Contains(cur) ? cur : names[0];
                }
            }
        }
        catch
        {
            // Keep default persona list when backend is down.
        }
    }

    void Save_Click(object sender, RoutedEventArgs e)
    {
        var s = new AppSettings
        {
            BaseUrl = BaseUrlBox.Text,
            Username = UserBox.Text,
            Password = PasswordBox.Password,
            Company = CompanyBox.Text?.Trim() ?? "",
            Persona = PersonaBox.SelectedItem?.ToString() ?? "Owner",
            Theme = Themes.FirstOrDefault(
                t => t.Label == ThemeBox.SelectedItem?.ToString()).Value ?? "Light",
            TimeoutSeconds = (int)TimeoutBox.Value,
            AutoStartBackend = AutoStartBox.IsOn,
            BackendCommand = BackendCmdBox.Text?.Trim() ?? "",
            BackendWorkingDir = BackendDirBox.Text?.Trim() ?? "",
        };
        try
        {
            s.Save();
            ApiClient.ResetDefault();
            Status.Text = "Saved — reconnecting…";
            // Apply the appearance choice immediately, then re-log in to the
            // (possibly new) company and rebuild the shell in place. Lands on Home.
            App.MainWindow?.ApplyTheme();
            App.MainWindow?.ReloadShell();
        }
        catch (Exception ex)
        {
            Status.Text = "Save failed: " + ex.Message;
        }
    }

    async void Health_Click(object sender, RoutedEventArgs e)
    {
        Status.Text = "Checking…";
        try
        {
            // Use form values without requiring Save first.
            using var probe = new ApiClient(
                BaseUrlBox.Text,
                UserBox.Text,
                PasswordBox.Password,
                (int)TimeoutBox.Value,
                CompanyBox.Text?.Trim() ?? "");
            var health = await probe.HealthAsync();
            var api = health.TryGetProperty("api", out var v) ? v.ToString() : "?";
            Status.Text = $"OK — api={api} at {probe.BaseAddress}";
        }
        catch (Exception ex)
        {
            Status.Text = ApiException.UserMessage(ex);
        }
    }
}
