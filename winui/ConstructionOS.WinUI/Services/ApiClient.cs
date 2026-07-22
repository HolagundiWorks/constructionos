using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace ConstructionOS.WinUI.Services;

/// <summary>
/// Typed HttpClient over the Python localhost JSON API (U0 / webapi.py).
/// Cookie jar holds cosid; CSRF is sent as X-CSRF-Token on writes.
/// </summary>
public sealed class ApiClient
{
    public static ApiClient Default { get; set; } = new("http://127.0.0.1:8080");

    private readonly HttpClient _http;
    private readonly CookieContainer _cookies = new();
    private string? _csrf;

    public ApiClient(string baseAddress)
    {
        var handler = new HttpClientHandler { CookieContainer = _cookies };
        _http = new HttpClient(handler) { BaseAddress = new Uri(baseAddress.TrimEnd('/') + "/") };
        _http.DefaultRequestHeaders.Accept.Add(
            new MediaTypeWithQualityHeaderValue("application/json"));
    }

    public async Task EnsureSessionAsync(string user = "admin", string password = "BuildSite#2026")
    {
        if (_csrf != null) return;
        // First-run creates the admin; subsequent logins authenticate.
        var body = JsonSerializer.Serialize(new { username = user, password });
        var resp = await _http.PostAsync("api/login",
            new StringContent(body, Encoding.UTF8, "application/json"));
        resp.EnsureSuccessStatusCode();
        using var doc = JsonDocument.Parse(await resp.Content.ReadAsStringAsync());
        _csrf = doc.RootElement.GetProperty("csrf").GetString();
    }

    public async Task<JsonElement> GetJsonAsync(string relativeUrl)
    {
        await EnsureSessionAsync();
        var resp = await _http.GetAsync(relativeUrl);
        resp.EnsureSuccessStatusCode();
        using var doc = JsonDocument.Parse(await resp.Content.ReadAsStringAsync());
        return doc.RootElement.Clone();
    }

    public async Task<JsonElement> PostJsonAsync(string relativeUrl, object payload)
    {
        await EnsureSessionAsync();
        var json = JsonSerializer.Serialize(payload);
        var req = new HttpRequestMessage(HttpMethod.Post, relativeUrl)
        {
            Content = new StringContent(json, Encoding.UTF8, "application/json"),
        };
        if (_csrf != null)
            req.Headers.Add("X-CSRF-Token", _csrf);
        var resp = await _http.SendAsync(req);
        resp.EnsureSuccessStatusCode();
        using var doc = JsonDocument.Parse(await resp.Content.ReadAsStringAsync());
        return doc.RootElement.Clone();
    }
}
