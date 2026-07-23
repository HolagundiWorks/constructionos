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
        (t => Has(t, "GST"), typeof(GstPage)),
        (t => Has(t, "Accounting"), typeof(AccountingPage)),
        (t => Has(t, "Look-ahead") || Has(t, "Lookahead"), typeof(LookaheadPage)),
        // More specific than the broad "Cash"/"Assistant" routes below — must win.
        (t => Has(t, "Cash Flow") || Has(t, "Cashflow"), typeof(CashFlowPage)),
        (t => Has(t, "Assistant"), typeof(AssistantPage)),
        (t => Has(t, "Review"), typeof(ReviewPage)),
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
        (t => Has(t, "Capture") || Has(t, "AI Engine"), typeof(CapturePage)),
        (t => Has(t, "Import") || Has(t, "Goods Receipt") || Has(t, "BOQ")
              || Has(t, "Requisition") || Has(t, "Sourcing"), typeof(ImportPage)),
        (t => Has(t, "Settings"), typeof(SettingsPage)),
        (t => Eq(t, "Tools"), typeof(ToolsPage)),
    };

    public static Type Resolve(string? tag) =>
        TryResolve(tag, out var page) ? page : typeof(HomePage);

    // True + the page when a route matches; false when nothing does (so callers
    // can fall back to a placeholder instead of silently landing on Home).
    public static bool TryResolve(string? tag, out Type page)
    {
        var t = tag ?? "";
        foreach (var (match, p) in Routes)
        {
            if (match(t)) { page = p; return true; }
        }
        page = typeof(HomePage);
        return false;
    }

    static bool Eq(string tag, string value) =>
        string.Equals(tag, value, StringComparison.OrdinalIgnoreCase);

    static bool Has(string tag, string fragment) =>
        tag.Contains(fragment, StringComparison.OrdinalIgnoreCase);
}
