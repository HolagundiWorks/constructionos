using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using ConstructionOS.WinUI.Services;

namespace ConstructionOS.WinUI.Views;

/// <summary>Controls › Risk Register — the live risk register (GET /api/risks:
/// likelihood × impact → score / band / expected exposure), as a columnar
/// table, plus detect-and-accept.
/// <para>Detection (POST /api/risks/detect) runs the Python risk_detect rules
/// over a live dashboard snapshot and is a <em>dry run</em> — it proposes and
/// writes nothing. Adding the proposals to the register is a second, explicit
/// click (POST /api/risks/accept with <c>detect_and_apply</c>), which is the
/// house rule: AI proposes, a human approves anything that moves money or a
/// date. No risk scoring happens in C#.</para></summary>
public sealed partial class RisksPage : Page
{
    public RisksPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await Load();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e)
    {
        Proposals.Children.Clear();
        Notice.IsOpen = false;
        await Load();
    }

    private System.Threading.Tasks.Task Load() => Ui.LoadTableAsync(Host, "api/risks");

    /// <summary>Dry-run detection: show what the rules found, write nothing.</summary>
    private async void OnDetect(object sender, RoutedEventArgs e)
    {
        DetectButton.IsEnabled = false;
        Proposals.Children.Clear();
        Proposals.Children.Add(Ui.Loading("Scanning for risks…"));
        try
        {
            // apply omitted ⇒ false ⇒ nothing is persisted by this call.
            var res = await ApiClient.Default.PostJsonAsync("api/risks/detect",
                new Dictionary<string, object?>());
            var count = res.TryGetProperty("count", out var c)
                && c.ValueKind == JsonValueKind.Number ? c.GetInt32() : 0;

            Proposals.Children.Clear();
            if (count == 0)
            {
                Show("Nothing to add", "The detection rules found no new risks in "
                     + "the current snapshot.", InfoBarSeverity.Success);
                return;
            }

            Proposals.Children.Add(Ui.SectionTitle(
                $"Proposed — {count} risk(s) detected, not yet in the register"));
            Proposals.Children.Add(Ui.Table(res, "detected"));

            var add = new Button
            {
                Content = $"Add {count} to the register…",
                Style = (Style)Application.Current.Resources["AccentButtonStyle"],
            };
            add.Click += async (_, _) => await AcceptAsync(count);
            Proposals.Children.Add(add);
            Proposals.Children.Add(Ui.EmptyNote(
                "Nothing has been written yet. Adding them files each as an "
                + "Accepted risk owned by you; duplicates are skipped."));
        }
        catch (Exception ex)
        {
            Proposals.Children.Clear();
            Proposals.Children.Add(Ui.ErrorNote(ex));
        }
        finally { DetectButton.IsEnabled = true; }
    }

    /// <summary>Persist the detected risks. The server re-detects rather than
    /// trusting a list posted from the client, so what lands in the register is
    /// what the rules say now — and it dedupes.</summary>
    private async Task AcceptAsync(int count)
    {
        var confirm = new ContentDialog
        {
            Title = $"Add {count} risk(s) to the register?",
            Content = "Each is filed as an Accepted risk with you as the decider. "
                      + "Risks already in the register are skipped.",
            PrimaryButtonText = "Add to register",
            CloseButtonText = "Cancel",
            DefaultButton = ContentDialogButton.Close,
            XamlRoot = XamlRoot,
            RequestedTheme = ActualTheme,
        };
        if (await confirm.ShowAsync() != ContentDialogResult.Primary) return;
        try
        {
            var res = await ApiClient.Default.PostJsonAsync("api/risks/accept",
                new Dictionary<string, object?> { ["detect_and_apply"] = true });
            var accepted = Len(res, "accepted_ids");
            Proposals.Children.Clear();
            Show("Register updated",
                 accepted == 0
                     ? "No new risks were added — they were already on the register."
                     : $"{accepted} risk(s) added and marked Accepted.",
                 InfoBarSeverity.Success);
            await Load();
        }
        catch (Exception ex)
        {
            Show("Couldn't update the register", ApiException.UserMessage(ex),
                 InfoBarSeverity.Error);
        }
    }

    private static int Len(JsonElement o, string key) =>
        o.TryGetProperty(key, out var a) && a.ValueKind == JsonValueKind.Array
            ? a.GetArrayLength() : 0;

    private void Show(string title, string message, InfoBarSeverity severity)
    {
        Notice.Title = title;
        Notice.Message = message;
        Notice.Severity = severity;
        Notice.IsOpen = true;
    }
}
