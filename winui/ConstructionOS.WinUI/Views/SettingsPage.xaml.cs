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
        PersonaBox.ItemsSource = DefaultPersonas;
        PersonaBox.SelectedItem = DefaultPersonas.Contains(s.Persona)
            ? s.Persona
            : DefaultPersonas[0];
        Status.Text = "Settings path: " + AppSettings.SettingsPath;
        _ = TryLoadPersonasAsync();
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
            TimeoutSeconds = (int)TimeoutBox.Value,
        };
        try
        {
            s.Save();
            ApiClient.ResetDefault();
            Status.Text = "Saved. Re-open Home from the rail to rebuild the menu.";
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
