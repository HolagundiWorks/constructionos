using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Helpers;

/// <summary>Shared loading / error UX for list pages.</summary>
public static class PageLoad
{
    public static async Task BindListAsync(
        ItemsControl? grid,
        TextBlock? status,
        Func<Task<IEnumerable<object>>> loadRows,
        string emptyMessage = "No rows.")
    {
        if (status != null) status.Text = "Loading…";
        try
        {
            var rows = (await loadRows().ConfigureAwait(true)).ToList();
            if (grid != null)
                grid.ItemsSource = rows;
            if (status != null)
                status.Text = rows.Count == 0 ? emptyMessage : $"{rows.Count} row(s).";
        }
        catch (Exception ex)
        {
            var msg = ApiException.UserMessage(ex);
            if (grid != null)
                grid.ItemsSource = new[] { new Dictionary<string, object?> { ["error"] = msg } };
            if (status != null)
                status.Text = msg;
        }
    }
}
