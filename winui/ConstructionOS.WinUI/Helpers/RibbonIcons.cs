namespace ConstructionOS.WinUI.Helpers;

/// <summary>
/// Resolves a ribbon command's icon from its tab label. Keyword substring match
/// (first hit wins) maps to a <b>Segoe MDL2 Assets</b> glyph — the WinUI
/// <c>FontIcon</c> default font on Windows 10/11, so no extra font assets are
/// needed. Product docs target Segoe Fluent Icons longer-term
/// (<c>docs/UI-PRINCIPLES-AND-GUIDELINES.md</c> §11); until the Fluent font is
/// set explicitly, keep these MDL2 code points. The label always shows beneath
/// the icon, so an approximate glyph still reads correctly; unmatched labels
/// fall back to a neutral document glyph. Glyphs are written as \u escapes (not
/// pasted private-use characters) so the source stays reviewable.
/// </summary>
public static class RibbonIcons
{
    // Order matters: first substring match wins, so put specific keys before
    // generic ones ("cash flow" before "cash", "purchase order" before "order").
    private static readonly (string Key, string Glyph)[] Map =
    {
        ("home", ""),                                  // Home
        ("assistant", ""), ("chat", ""),         // Message
        ("process", ""), ("what's next", ""), ("workflow", ""),
        ("tool", ""),                                  // Repair
        // Masters / parties
        ("client", ""), ("customer", ""),        // Contact
        ("vendor", ""), ("supplier", ""),        // Shop
        ("subcontractor", ""), ("sourcing", ""),
        ("labour", ""), ("labor", ""), ("muster", ""),
        ("wage", ""), ("thekedar", ""), ("people", ""),
        ("part", ""),                                  // party / parties
        ("site", ""),                                  // MapPin
        ("warehouse", ""), ("store", ""), ("material", ""),
        ("stock", ""), ("consumption", ""), ("goods receipt", ""),
        ("purchase order", ""), ("requisition", ""),  // Package
        ("equipment", ""), ("plant", ""), ("hire", ""),
        // Project management
        ("milestone", ""),                             // Flag
        ("earned value", ""), ("evm", ""),       // Calculator
        ("project", ""),
        ("risk", ""), ("safety", ""),            // Important
        ("opportunit", ""),                            // FavoriteStar
        // Billing / commercial
        ("rate", ""), ("estimate", ""), ("quotation", ""),
        ("boq", ""), ("takeoff", ""), ("bid", ""),
        ("contract", ""), ("variation", ""), ("lesson", ""),
        ("submittal", ""), ("approval", ""), ("quality", ""),
        ("closeout", ""),                              // Accept
        // Money
        ("cash flow", ""),                             // report (before "cash")
        ("invoice", ""), ("bill", ""),
        ("payment", ""), ("cash", ""), ("money", ""),
        ("retention", ""), ("account", ""),
        ("gst", ""), ("tax", ""), ("tds", ""),
        ("compliance", ""),                            // Calendar
        // Dashboards / reports
        ("key number", ""), ("insight", ""), ("chart", ""),
        ("kpi", ""), ("dashboard", ""), ("ageing", ""),
        ("portfolio", ""), ("productiv", ""), ("report", ""),
        ("review", ""),
        ("capture", ""),                               // Camera
        ("import", ""),                                // Download
        ("setting", ""),                               // Setting (gear)
    };

    private const string Default = "";                 // Document

    public static string Glyph(string? label)
    {
        var l = (label ?? "").ToLowerInvariant();
        foreach (var (key, glyph) in Map)
            if (l.Contains(key)) return glyph;
        return Default;
    }
}
