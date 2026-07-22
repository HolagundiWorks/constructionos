using System.Text.Json;

namespace ConstructionOS.WinUI.Views;

/// <summary>Shared helper: turn an /api items array into readable ListView lines
/// (one "key: value    …" string per row). Stock ListView replaces the
/// CommunityToolkit DataGrid, which was UWP-only and crashed WinUI 3.</summary>
internal static class Ui
{
    public static List<string> Lines(JsonElement data, params string[] keys)
    {
        JsonElement items = default;
        var found = false;
        foreach (var k in (keys.Length > 0 ? keys : new[] { "items" }))
            if (data.TryGetProperty(k, out items) && items.ValueKind == JsonValueKind.Array)
            { found = true; break; }
        var rows = new List<string>();
        if (!found) return rows;
        foreach (var item in items.EnumerateArray())
        {
            var parts = new List<string>();
            foreach (var p in item.EnumerateObject())
                if (p.Value.ValueKind != JsonValueKind.Null)
                    parts.Add($"{p.Name}: {p.Value}");
            rows.Add(string.Join("    ", parts));
        }
        return rows;
    }
}
