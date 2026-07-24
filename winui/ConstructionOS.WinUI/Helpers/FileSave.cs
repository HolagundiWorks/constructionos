using System.IO;
using Windows.Storage.Pickers;

namespace ConstructionOS.WinUI.Helpers;

/// <summary>
/// Save text to a file the user picks. A desktop (unpackaged) WinUI 3 app has no
/// implicit window for a WinRT picker, so the picker must be given the main
/// window's HWND via <c>InitializeWithWindow</c> — without it the call throws
/// <c>COMException 0x8000000E</c>. Stock <see cref="FileSavePicker"/>, no
/// third-party dialog.
/// </summary>
internal static class FileSave
{
    /// <summary>Prompt for a location and write <paramref name="content"/> there.
    /// Returns the saved path, or null if the user cancelled.</summary>
    /// <param name="choices">Extension → display name, e.g. <c>[".csv"] = "CSV"</c>.
    /// The first entry is the default.</param>
    public static async Task<string?> TextAsync(
        string suggestedName, string content,
        IReadOnlyDictionary<string, string> choices)
    {
        var window = App.MainWindow;
        if (window is null) return null;

        var picker = new FileSavePicker { SuggestedFileName = suggestedName };
        foreach (var (ext, label) in choices)
            picker.FileTypeChoices.Add(label, new List<string> { ext });

        WinRT.Interop.InitializeWithWindow.Initialize(
            picker, WinRT.Interop.WindowNative.GetWindowHandle(window));

        var file = await picker.PickSaveFileAsync();
        if (file is null) return null;                 // user cancelled

        // Write through System.IO: the picked StorageFile already carries the
        // user's consent for this path, and this keeps encoding explicit (UTF-8,
        // so rupee signs and Devanagari survive the round-trip into Excel/Tally).
        await File.WriteAllTextAsync(file.Path, content, new System.Text.UTF8Encoding(true));
        return file.Path;
    }
}
