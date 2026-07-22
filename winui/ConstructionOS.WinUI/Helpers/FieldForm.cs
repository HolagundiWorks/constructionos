using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace ConstructionOS.WinUI.Helpers;

/// <summary>
/// Shared field-metadata form builder for masters and create-only money docs.
/// Understands combo string options and FK <c>{id,label}</c> options from U0.7.
/// </summary>
public static class FieldForm
{
    public sealed record Spec(
        string Key,
        string Label,
        string Kind,
        IReadOnlyList<string> ComboOptions,
        IReadOnlyList<(string Id, string Label)> FkOptions,
        string Default,
        bool Required);

    public static List<Spec> ParseFields(JsonElement data)
    {
        var fields = new List<Spec>();
        if (!data.TryGetProperty("fields", out var arr)
            || arr.ValueKind != JsonValueKind.Array)
            return fields;
        foreach (var f in arr.EnumerateArray())
        {
            var kind = f.TryGetProperty("kind", out var k) ? k.GetString() ?? "text" : "text";
            var combo = new List<string>();
            var fk = new List<(string, string)>();
            if (f.TryGetProperty("options", out var opts)
                && opts.ValueKind == JsonValueKind.Array)
            {
                foreach (var o in opts.EnumerateArray())
                {
                    if (o.ValueKind == JsonValueKind.String)
                    {
                        var s = o.GetString();
                        if (!string.IsNullOrEmpty(s)) combo.Add(s!);
                    }
                    else if (o.ValueKind == JsonValueKind.Object)
                    {
                        var id = o.TryGetProperty("id", out var idEl)
                            ? idEl.ToString() : "";
                        var lab = o.TryGetProperty("label", out var labEl)
                            ? labEl.GetString() ?? id : id;
                        if (!string.IsNullOrEmpty(id))
                            fk.Add((id, $"{id} — {lab}"));
                    }
                }
            }
            fields.Add(new Spec(
                Key: f.GetProperty("key").GetString() ?? "",
                Label: f.TryGetProperty("label", out var lb) ? lb.GetString() ?? "" : "",
                Kind: kind,
                ComboOptions: combo,
                FkOptions: fk,
                Default: DefaultString(f),
                Required: f.TryGetProperty("required", out var r)
                          && r.ValueKind == JsonValueKind.True));
        }
        return fields;
    }

    static string DefaultString(JsonElement f)
    {
        if (!f.TryGetProperty("default", out var d)) return "";
        return d.ValueKind switch
        {
            JsonValueKind.Null => "",
            JsonValueKind.String => d.GetString() ?? "",
            JsonValueKind.Number => d.ToString(),
            JsonValueKind.True => "1",
            JsonValueKind.False => "0",
            _ => d.ToString(),
        };
    }

    public static async Task<Dictionary<string, string>?> ShowAsync(
        XamlRoot root, string title, IReadOnlyList<Spec> fields,
        IReadOnlyDictionary<string, string>? values = null)
    {
        var panel = new StackPanel { Spacing = 12, MinWidth = 360 };
        var inputs = new Dictionary<string, FrameworkElement>();
        foreach (var f in fields)
        {
            values ??= new Dictionary<string, string>();
            values.TryGetValue(f.Key, out var current);
            if (string.IsNullOrEmpty(current)) current = f.Default;
            if (current == "@today")
                current = DateTime.Today.ToString("yyyy-MM-dd");
            var input = BuildInput(f, current ?? "");
            inputs[f.Key] = input;
            var cell = new StackPanel { Spacing = 4 };
            cell.Children.Add(new TextBlock
            {
                Text = f.Label + (f.Required ? " *" : ""),
                Style = (Style)Application.Current.Resources["CaptionTextBlockStyle"],
            });
            cell.Children.Add(input);
            panel.Children.Add(cell);
        }
        var dialog = new ContentDialog
        {
            Title = title,
            PrimaryButtonText = "Save",
            CloseButtonText = "Cancel",
            DefaultButton = ContentDialogButton.Primary,
            Content = new ScrollViewer { Content = panel, MaxHeight = 480 },
            XamlRoot = root,
        };
        if (await dialog.ShowAsync() != ContentDialogResult.Primary) return null;
        return fields.ToDictionary(f => f.Key, f => ReadInput(f, inputs[f.Key]));
    }

    public static FrameworkElement BuildInput(Spec f, string current)
    {
        switch (f.Kind)
        {
            case "number":
                return new NumberBox
                {
                    SpinButtonPlacementMode = NumberBoxSpinButtonPlacementMode.Hidden,
                    Value = double.TryParse(current,
                        System.Globalization.NumberStyles.Any,
                        System.Globalization.CultureInfo.InvariantCulture, out var d)
                        ? d : double.NaN,
                };
            case "combo":
            {
                var cb = new ComboBox { HorizontalAlignment = HorizontalAlignment.Stretch };
                foreach (var o in f.ComboOptions) cb.Items.Add(o);
                cb.SelectedItem = f.ComboOptions.Contains(current) ? current : null;
                return cb;
            }
            case "fk":
            {
                var cb = new ComboBox { HorizontalAlignment = HorizontalAlignment.Stretch };
                foreach (var (id, label) in f.FkOptions)
                    cb.Items.Add(new ComboBoxItem { Content = label, Tag = id });
                foreach (ComboBoxItem item in cb.Items)
                {
                    if ((item.Tag as string) == current)
                    {
                        cb.SelectedItem = item;
                        break;
                    }
                }
                if (cb.SelectedItem == null && f.FkOptions.Count > 0)
                    cb.PlaceholderText = "Select…";
                return cb;
            }
            case "textarea":
                return new TextBox
                {
                    Text = current, AcceptsReturn = true,
                    TextWrapping = TextWrapping.Wrap, Height = 72,
                };
            default:
                return new TextBox { Text = current };
        }
    }

    public static string ReadInput(Spec f, FrameworkElement input) => input switch
    {
        NumberBox nb => double.IsNaN(nb.Value)
            ? "" : nb.Value.ToString(System.Globalization.CultureInfo.InvariantCulture),
        ComboBox cb when f.Kind == "fk" =>
            (cb.SelectedItem as ComboBoxItem)?.Tag as string ?? "",
        ComboBox cb => cb.SelectedItem as string ?? "",
        TextBox tb => tb.Text,
        _ => "",
    };
}
