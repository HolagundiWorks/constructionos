using System.Net;

namespace ConstructionOS.WinUI.Services;

/// <summary>
/// HTTP / JSON API failure with status and response body (no stack dump to UI).
/// </summary>
public sealed class ApiException : Exception
{
    public HttpStatusCode StatusCode { get; }
    public string? ResponseBody { get; }

    public ApiException(string message, HttpStatusCode statusCode, string? body = null)
        : base(message)
    {
        StatusCode = statusCode;
        ResponseBody = body;
    }

    public static string UserMessage(Exception ex)
    {
        if (ex is ApiException api)
        {
            var detail = Truncate(api.ResponseBody, 240);
            // Distinguish the honest cases (research §3.3): endpoint missing vs
            // permission vs expired session vs a server-side error — never a
            // blank grid that reads as "zero work".
            var hint = (int)api.StatusCode switch
            {
                404 => "Not available in the native client yet — open this in the "
                       + "desktop or browser app.",
                403 => "You don't have permission for this (it may be read-only for "
                       + "your role).",
                401 => "Your session ended — reopen the app to sign in again.",
                >= 500 => "The backend hit an error handling this. Try again, or "
                          + "check the backend log.",
                _ => null,
            };
            if (hint != null)
                return string.IsNullOrWhiteSpace(detail) ? hint : $"{hint} ({detail})";
            return string.IsNullOrWhiteSpace(detail)
                ? $"{(int)api.StatusCode} {api.Message}"
                : $"{(int)api.StatusCode} {api.Message}: {detail}";
        }
        if (ex is HttpRequestException or TaskCanceledException)
            return "Backend unreachable. Start: cd construction_app && python web_main.py — "
                   + ex.Message;
        return ex.Message;
    }

    static string? Truncate(string? s, int max)
    {
        if (string.IsNullOrWhiteSpace(s)) return null;
        s = s.Trim();
        return s.Length <= max ? s : s[..max] + "…";
    }
}
