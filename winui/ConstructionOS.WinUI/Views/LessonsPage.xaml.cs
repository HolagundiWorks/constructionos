using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace ConstructionOS.WinUI.Views;

/// <summary>Controls › Lessons Learned — the live lessons-learned register (GET
/// /api/lessons), as a columnar table.</summary>
public sealed partial class LessonsPage : Page
{
    public LessonsPage()
    {
        InitializeComponent();
        Loaded += async (_, _) => await Load();
    }

    private async void OnRefresh(object sender, RoutedEventArgs e) => await Load();

    private System.Threading.Tasks.Task Load() => Ui.LoadTableAsync(Host, "api/lessons");
}
