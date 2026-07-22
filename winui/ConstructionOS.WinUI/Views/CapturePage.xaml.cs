using System.Text;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Helpers;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Soft-fail capture surface: sidecar readiness + extract probe. OCR/STT/VLM
/// weights are local-only; stub_server.py answers without models.
/// </summary>
public sealed partial class CapturePage : Page
{
    public CapturePage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await RefreshAsync();
    }

    private async void Refresh_Click(object sender, RoutedEventArgs e)
        => await RefreshAsync();

    private async Task RefreshAsync()
    {
        Status.Text = "Loading sidecar status…";
        Detail.Text = "";
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/sidecar/status");
            var sb = new StringBuilder();
            if (data.TryGetProperty("sidecars", out var sides)
                && sides.ValueKind == JsonValueKind.Object)
            {
                foreach (var p in sides.EnumerateObject())
                {
                    var avail = p.Value.TryGetProperty("available", out var a)
                                && a.ValueKind == JsonValueKind.True;
                    var stub = p.Value.TryGetProperty("stub", out var s)
                               && s.ValueKind == JsonValueKind.True;
                    var url = JsonRows.Prop(p.Value, "url", "—");
                    sb.AppendLine($"{p.Name}: stub={stub} live={avail} ({url})");
                }
            }
            Status.Text = sb.Length == 0
                ? "No sidecar entries."
                : sb.ToString().Trim();
        }
        catch (Exception ex)
        {
            Status.Text = ApiException.UserMessage(ex);
        }
    }

    private async void Extract_Click(object sender, RoutedEventArgs e)
    {
        Detail.Text = "Probing…";
        try
        {
            var kind = KindBox.SelectedItem as string ?? "ocr";
            var data = await ApiClient.Default.PostJsonAsync(
                "api/sidecar/extract",
                new { kind, payload = new { path = "", note = "winui-probe" } });
            Detail.Text = JsonRows.Pretty(data);
        }
        catch (Exception ex)
        {
            Detail.Text = ApiException.UserMessage(ex);
        }
    }
}
