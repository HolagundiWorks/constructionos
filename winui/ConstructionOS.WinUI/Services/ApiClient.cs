using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace ConstructionOS.WinUI.Services;

/// <summary>
/// HttpClient over the Python localhost JSON API (U0 / webapi.py).
/// Cookie jar holds cosid; CSRF is sent as X-CSRF-Token on writes.
/// </summary>
public sealed class ApiClient : IDisposable
{
    public static ApiClient Default { get; set; } = FromSettings();

    private readonly HttpClient _http;
    private readonly CookieContainer _cookies = new();
    private string? _csrf;
    private readonly string _username;
    private readonly string _password;
    private bool _disposed;

    public string BaseAddress { get; }

    public ApiClient(string baseAddress, string? username = null, string? password = null,
                     int timeoutSeconds = 30)
    {
        BaseAddress = baseAddress.Trim().TrimEnd('/') + "/";
        _username = string.IsNullOrWhiteSpace(username) ? "admin" : username.Trim();
        _password = password ?? "";
        var handler = new HttpClientHandler { CookieContainer = _cookies };
        _http = new HttpClient(handler)
        {
            BaseAddress = new Uri(BaseAddress),
            Timeout = TimeSpan.FromSeconds(Math.Clamp(timeoutSeconds, 5, 120)),
        };
        _http.DefaultRequestHeaders.Accept.Add(
            new MediaTypeWithQualityHeaderValue("application/json"));
    }

    public static ApiClient FromSettings(AppSettings? settings = null)
    {
        settings ??= AppSettings.Current;
        settings.Normalize();
        return new ApiClient(
            settings.BaseUrl,
            settings.Username,
            settings.Password,
            settings.TimeoutSeconds);
    }

    /// <summary>Replace <see cref="Default"/> from current settings (after Save).</summary>
    public static void ResetDefault()
    {
        var old = Default;
        Default = FromSettings();
        try { old.Dispose(); } catch { /* ignore */ }
    }

    public void ResetSession() => _csrf = null;

    public async Task<JsonElement> HealthAsync(CancellationToken ct = default)
    {
        // Health is unauthenticated on the API.
        var resp = await _http.GetAsync("api/health", ct).ConfigureAwait(false);
        return await ReadJsonOrThrowAsync(resp, ct).ConfigureAwait(false);
    }

    public async Task EnsureSessionAsync(CancellationToken ct = default)
    {
        if (_csrf != null) return;
        var body = JsonSerializer.Serialize(new { username = _username, password = _password });
        using var content = new StringContent(body, Encoding.UTF8, "application/json");
        var resp = await _http.PostAsync("api/login", content, ct).ConfigureAwait(false);
        var doc = await ReadJsonOrThrowAsync(resp, ct).ConfigureAwait(false);
        if (!doc.TryGetProperty("csrf", out var csrfEl)
            || csrfEl.ValueKind != JsonValueKind.String
            || string.IsNullOrEmpty(csrfEl.GetString()))
        {
            throw new ApiException(
                "Login response missing csrf",
                resp.StatusCode,
                doc.ToString());
        }
        _csrf = csrfEl.GetString();
    }

    public Task<JsonElement> GetJsonAsync(string relativeUrl, CancellationToken ct = default)
        => SendJsonAsync(HttpMethod.Get, relativeUrl, payload: null, ct);

    public Task<JsonElement> PostJsonAsync(string relativeUrl, object? payload,
                                           CancellationToken ct = default)
        => SendJsonAsync(HttpMethod.Post, relativeUrl, payload, ct);

    public Task<JsonElement> PutJsonAsync(string relativeUrl, object? payload,
                                          CancellationToken ct = default)
        => SendJsonAsync(HttpMethod.Put, relativeUrl, payload, ct);

    public Task<JsonElement> DeleteJsonAsync(string relativeUrl,
                                             CancellationToken ct = default)
        => SendJsonAsync(HttpMethod.Delete, relativeUrl, payload: null, ct);

    async Task<JsonElement> SendJsonAsync(HttpMethod method, string relativeUrl,
                                          object? payload, CancellationToken ct)
    {
        await EnsureSessionAsync(ct).ConfigureAwait(false);
        relativeUrl = (relativeUrl ?? "").TrimStart('/');
        using var req = new HttpRequestMessage(method, relativeUrl);
        if (payload != null)
        {
            var json = JsonSerializer.Serialize(payload);
            req.Content = new StringContent(json, Encoding.UTF8, "application/json");
        }
        if (_csrf != null
            && (method == HttpMethod.Post || method == HttpMethod.Put
                || method == HttpMethod.Delete || method.Method == "PATCH"))
        {
            req.Headers.TryAddWithoutValidation("X-CSRF-Token", _csrf);
        }
        var resp = await _http.SendAsync(req, ct).ConfigureAwait(false);
        return await ReadJsonOrThrowAsync(resp, ct).ConfigureAwait(false);
    }

    static async Task<JsonElement> ReadJsonOrThrowAsync(HttpResponseMessage resp,
                                                        CancellationToken ct)
    {
        var text = await resp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
        if (!resp.IsSuccessStatusCode)
        {
            var msg = TryErrorMessage(text) ?? resp.ReasonPhrase ?? "Request failed";
            throw new ApiException(msg, resp.StatusCode, text);
        }
        if (string.IsNullOrWhiteSpace(text))
            return JsonDocument.Parse("{}").RootElement.Clone();
        try
        {
            using var doc = JsonDocument.Parse(text);
            return doc.RootElement.Clone();
        }
        catch (JsonException ex)
        {
            throw new ApiException(
                "Invalid JSON from API: " + ex.Message,
                resp.StatusCode,
                text);
        }
    }

    static string? TryErrorMessage(string? text)
    {
        if (string.IsNullOrWhiteSpace(text)) return null;
        try
        {
            using var doc = JsonDocument.Parse(text);
            if (doc.RootElement.TryGetProperty("error", out var err)
                && err.ValueKind == JsonValueKind.String)
                return err.GetString();
        }
        catch { /* not JSON */ }
        return null;
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _http.Dispose();
    }
}
