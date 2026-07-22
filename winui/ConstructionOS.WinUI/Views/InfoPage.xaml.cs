using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;

namespace ConstructionOS.WinUI.Views;

/// <summary>
/// Honest placeholder for a section whose feature ships in the ACO desktop / LAN
/// browser app but isn't yet surfaced in the WinUI client (its domain isn't
/// exposed through the JSON API). Names the section so the shell never
/// dead-ends. Navigation parameter is the section/tab label.
/// </summary>
public sealed partial class InfoPage : Page
{
    public InfoPage() => InitializeComponent();

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        base.OnNavigatedTo(e);
        var name = e.Parameter as string ?? "This section";
        if (name.Contains('/')) name = name[(name.LastIndexOf('/') + 1)..];
        TitleText.Text = name;
        Message.Text =
            $"“{name}” is available in the ACO desktop app and the browser view. "
            + "It isn't wired into this native client yet — its data isn't exposed "
            + "through the local JSON API. The money, masters, billing documents, "
            + "registers, dashboards and charts that are wired appear on their own "
            + "tabs.";
    }
}
