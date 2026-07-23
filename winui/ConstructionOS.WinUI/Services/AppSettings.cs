using System.Text.Json;

namespace ConstructionOS.WinUI.Services;

/// <summary>
/// Persisted WinUI client settings (localhost API + login + persona).
/// File lives under LocalApplicationData\ACO — same family as the Python
/// app's paths.APP_DIR_NAME. Legacy LocalApplicationData\Construction OS is
/// still read if the ACO file is missing.
/// </summary>
public sealed class AppSettings
{
    public string BaseUrl { get; set; } = "http://127.0.0.1:8080";
    public string Username { get; set; } = "admin";
    public string Password { get; set; } = "BuildSite#2026";
    /// <summary>Optional company path or display name for POST /api/login.</summary>
    public string Company { get; set; } = "";
    public string Persona { get; set; } = "Owner";
    public int TimeoutSeconds { get; set; } = 30;

    public static AppSettings Current { get; private set; } = Load();

    static string DataFolder
    {
        get
        {
            var root = Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData);
            var aco = Path.Combine(root, "ACO");
            if (Directory.Exists(aco)) return aco;
            var legacy = Path.Combine(root, "Construction OS");
            if (Directory.Exists(legacy)) return legacy;
            return aco;
        }
    }

    public static string SettingsPath =>
        Path.Combine(DataFolder, "winui-settings.json");

    public static AppSettings Load()
    {
        try
        {
            var path = SettingsPath;
            if (File.Exists(path))
            {
                var json = File.ReadAllText(path);
                var loaded = JsonSerializer.Deserialize<AppSettings>(json);
                if (loaded != null)
                {
                    loaded.Normalize();
                    Current = loaded;
                    return loaded;
                }
            }
        }
        catch
        {
            // Fall through to defaults — never block launch on settings IO.
        }

        var defaults = new AppSettings();
        Current = defaults;
        return defaults;
    }

    public void Save()
    {
        Normalize();
        var dir = Path.GetDirectoryName(SettingsPath);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);
        var json = JsonSerializer.Serialize(this, new JsonSerializerOptions
        {
            WriteIndented = true,
        });
        File.WriteAllText(SettingsPath, json);
        Current = this;
    }

    public void Normalize()
    {
        BaseUrl = (BaseUrl ?? "").Trim().TrimEnd('/');
        if (string.IsNullOrWhiteSpace(BaseUrl))
            BaseUrl = "http://127.0.0.1:8080";
        Username = (Username ?? "").Trim();
        if (string.IsNullOrWhiteSpace(Username))
            Username = "admin";
        Password ??= "";
        Company = (Company ?? "").Trim();
        Persona = string.IsNullOrWhiteSpace(Persona) ? "Owner" : Persona.Trim();
        if (TimeoutSeconds < 5) TimeoutSeconds = 5;
        if (TimeoutSeconds > 120) TimeoutSeconds = 120;
    }
}
