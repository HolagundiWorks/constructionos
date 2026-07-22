using System.Text.Json;

namespace ConstructionOS.WinUI.Helpers;

/// <summary>
/// Shared JSON → row dictionaries for DataGrid pages (no duplicated parse loops).
/// </summary>
public static class JsonRows
{
    public static List<Dictionary<string, object?>> FromArray(JsonElement array)
    {
        var rows = new List<Dictionary<string, object?>>();
        if (array.ValueKind != JsonValueKind.Array) return rows;
        foreach (var item in array.EnumerateArray())
            rows.Add(FromObject(item));
        return rows;
    }

    public static Dictionary<string, object?> FromObject(JsonElement item)
    {
        var row = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase);
        if (item.ValueKind != JsonValueKind.Object) return row;
        foreach (var p in item.EnumerateObject())
            row[p.Name] = CellValue(p.Value);
        return row;
    }

    /// <summary>
    /// Prefer the first property that is a JSON array among <paramref name="keys"/>.
    /// </summary>
    public static List<Dictionary<string, object?>> FromEnvelope(
        JsonElement root, params string[] keys)
    {
        foreach (var key in keys)
        {
            if (root.TryGetProperty(key, out var el) && el.ValueKind == JsonValueKind.Array)
                return FromArray(el);
        }
        return new List<Dictionary<string, object?>>();
    }

    public static object? CellValue(JsonElement v) => v.ValueKind switch
    {
        JsonValueKind.Null => null,
        JsonValueKind.True => true,
        JsonValueKind.False => false,
        JsonValueKind.Number => v.TryGetInt64(out var i) ? i : v.GetDouble(),
        JsonValueKind.String => v.GetString(),
        _ => v.ToString(),
    };

    public static string Pretty(JsonElement el)
    {
        try
        {
            return JsonSerializer.Serialize(
                el,
                new JsonSerializerOptions { WriteIndented = true });
        }
        catch
        {
            return el.ToString();
        }
    }

    public static string Prop(JsonElement el, string name, string fallback = "")
    {
        if (!el.TryGetProperty(name, out var p)) return fallback;
        return p.ValueKind switch
        {
            JsonValueKind.Null => fallback,
            JsonValueKind.String => p.GetString() ?? fallback,
            _ => p.ToString(),
        };
    }
}
