using ConstructionOS.WinUI.Views;

namespace ConstructionOS.WinUI.Helpers;

/// <summary>
/// Maps menu tags (from GET /api/menu) to WinUI pages. Longest / most-specific
/// match wins — avoids fragile string.Contains cascades.
/// </summary>
public static class NavRoute
{
    // Order matters: first matching predicate wins.
    static readonly (Func<string, bool> Match, Type Page)[] Routes =
    {
        (t => Eq(t, "Home") || t.Length == 0, typeof(HomePage)),
        (t => Has(t, "Risk"), typeof(RisksPage)),
        (t => Has(t, "Opportun"), typeof(OpportunitiesPage)),
        (t => Has(t, "Lesson"), typeof(LessonsPage)),
        (t => Has(t, "Submittal"), typeof(SubmittalsPage)),
        (t => Has(t, "Earned") || Has(t, "EVM"), typeof(EvmPage)),
        (t => Has(t, "Portfolio"), typeof(PortfolioPage)),
        (t => Has(t, "Productiv"), typeof(ProductivityPage)),
        (t => Has(t, "Process") || Eq(t, "What's next"), typeof(ProcessPage)),
        (t => Has(t, "Chart") || Has(t, "Key Numbers") || Has(t, "Insight"),
            typeof(ChartsPage)),
        (t => Has(t, "Cash") || Has(t, "Payment") || Has(t, "Money")
              || Has(t, "Ageing") || Has(t, "Retention"), typeof(MoneyPage)),
        (t => Has(t, "Capture") || Has(t, "AI Engine") || Has(t, "Assistant"),
            typeof(CapturePage)),
        (t => Has(t, "Import") || Has(t, "Goods Receipt") || Has(t, "BOQ")
              || Has(t, "Requisition") || Has(t, "Sourcing"), typeof(ImportPage)),
        (t => Has(t, "Settings"), typeof(SettingsPage)),
    };

    public static Type Resolve(string? tag)
    {
        var t = tag ?? "";
        foreach (var (match, page) in Routes)
        {
            if (match(t)) return page;
        }
        return typeof(HomePage);
    }

    static bool Eq(string tag, string value) =>
        string.Equals(tag, value, StringComparison.OrdinalIgnoreCase);

    static bool Has(string tag, string fragment) =>
        tag.Contains(fragment, StringComparison.OrdinalIgnoreCase);
}
