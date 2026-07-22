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
