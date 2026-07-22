using System.Text;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Soft-fail capture surface: shows sidecar readiness and stages an empty
/// draft when OCR/STT/VLM are not running (weights installed locally only).
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
        try
        {
            var data = await ApiClient.Default.GetJsonAsync("api/sidecar/status");
            var sb = new StringBuilder();
            if (data.TryGetProperty("sidecars", out var sides))
            {
                foreach (var p in sides.EnumerateObject())
                {
                    var avail = p.Value.TryGetProperty("available", out var a)
                                && a.GetBoolean();
                    var stub = p.Value.TryGetProperty("stub", out var s)
                               && s.GetBoolean();
                    sb.AppendLine($"{p.Name}: stub={stub} live={avail}");
                }
            }
            Status.Text = sb.ToString().Trim();
        }
        catch (Exception ex)
        {
            Status.Text = ex.Message;
        }
    }

    private async void Extract_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var data = await ApiClient.Default.PostJsonAsync(
                "api/sidecar/extract",
                new { kind = "ocr", payload = new { path = "" } });
            Detail.Text = data.ToString();
        }
        catch (Exception ex)
        {
            Detail.Text = ex.Message;
        }
    }
}
