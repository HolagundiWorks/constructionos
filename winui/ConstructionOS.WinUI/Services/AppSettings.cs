using System.Text.Json;

namespace ConstructionOS.WinUI.Services;

/// <summary>
/// Persisted WinUI client settings (localhost API + login + persona).
/// File lives under LocalApplicationData\Construction OS — same family as the
/// Python data folder — so packaged and unpackaged runs share one place.
/// </summary>
public sealed class AppSettings
{
    public string BaseUrl { get; set; } = "http://127.0.0.1:8080";
    public string Username { get; set; } = "admin";
    public string Password { get; set; } = "BuildSite#2026";
    public string Persona { get; set; } = "Owner";
    public int TimeoutSeconds { get; set; } = 30;

    public static AppSettings Current { get; private set; } = Load();

    public static string SettingsPath =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Construction OS",
            "winui-settings.json");

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
        Persona = string.IsNullOrWhiteSpace(Persona) ? "Owner" : Persona.Trim();
        if (TimeoutSeconds < 5) TimeoutSeconds = 5;
        if (TimeoutSeconds > 120) TimeoutSeconds = 120;
    }
}
