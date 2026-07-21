"""Lightweight vernacular string table (Phase 4 — trust & ease).

Non-technical T2/T3 users are far more comfortable in Hindi / Hinglish than in
English accounting jargon. Full localisation of every widget would be brittle;
instead this translates the **navigation layer** — section titles, the always-on
tabs, and module/tab labels — which is what a user reads to find their way
around. Anything without a translation falls back to the English key, so the app
is always usable and translations can be filled in incrementally.

The active language is read once at startup from ``app_settings.language``
(``en`` / ``hi`` / ``hi_en``); ``t(key)`` returns the localised label. No
tkinter, no live DB — ``load(conn)`` sets the module language, ``t`` is pure.
"""

LANGUAGES = [('en', 'English'), ('hi', 'हिन्दी'), ('hi_en', 'Hinglish')]

# key -> {lang: label}. Missing lang (or key) falls back to the English key.
STRINGS = {
    # Always-on tabs
    'Home': {'hi': 'मुख्य पृष्ठ', 'hi_en': 'Home'},
    'Assistant': {'hi': 'सहायक', 'hi_en': 'Sahayak'},
    'Tools': {'hi': 'औज़ार', 'hi_en': 'Tools'},
    # Sections
    'Masters': {'hi': 'मास्टर', 'hi_en': 'Masters'},
    'Project Management': {'hi': 'परियोजना प्रबंधन', 'hi_en': 'Project Mgmt'},
    'Projects': {'hi': 'परियोजनाएँ', 'hi_en': 'Projects'},
    'Operations': {'hi': 'कार्य', 'hi_en': 'Kaam'},
    'Billing': {'hi': 'बिलिंग', 'hi_en': 'Billing'},
    'Purchases': {'hi': 'खरीद', 'hi_en': 'Kharid'},
    'Money': {'hi': 'पैसा', 'hi_en': 'Paisa'},
    'Accounts': {'hi': 'खाता', 'hi_en': 'Accounts'},
    # Common module / tab labels
    'Sites': {'hi': 'साइट', 'hi_en': 'Sites'},
    'Clients': {'hi': 'ग्राहक', 'hi_en': 'Clients'},
    'Vendors': {'hi': 'विक्रेता', 'hi_en': 'Vendors'},
    'Materials': {'hi': 'सामग्री', 'hi_en': 'Maal'},
    'Labour': {'hi': 'मज़दूर', 'hi_en': 'Mazdoor'},
    'Equipment': {'hi': 'उपकरण', 'hi_en': 'Machine'},
    'Warehouse': {'hi': 'गोदाम', 'hi_en': 'Godown'},
    'Muster & Wages': {'hi': 'हाज़िरी और मज़दूरी', 'hi_en': 'Hazri & Wages'},
    'Labour Ops': {'hi': 'मज़दूर कार्य', 'hi_en': 'Mazdoor Kaam'},
    'Equipment Hire': {'hi': 'मशीन किराया', 'hi_en': 'Machine Kiraya'},
    'Consumption': {'hi': 'खपत', 'hi_en': 'Khapat'},
    'Site Reports': {'hi': 'साइट रिपोर्ट', 'hi_en': 'Site Report'},
    'Timeline': {'hi': 'समय-सारणी', 'hi_en': 'Timeline'},
    'Rate Book': {'hi': 'दर सूची', 'hi_en': 'Rate Book'},
    'Takeoff': {'hi': 'मात्रा माप', 'hi_en': 'Takeoff'},
    'Quotations': {'hi': 'कोटेशन', 'hi_en': 'Quotation'},
    'Estimates': {'hi': 'अनुमान', 'hi_en': 'Estimate'},
    'Contracts': {'hi': 'ठेका', 'hi_en': 'Theka'},
    'BOQ / RA Bills': {'hi': 'BOQ / RA बिल', 'hi_en': 'BOQ / RA Bill'},
    'Running Bills': {'hi': 'चालू बिल', 'hi_en': 'Running Bill'},
    'Tax Invoice': {'hi': 'टैक्स बिल', 'hi_en': 'Tax Invoice'},
    'Purchase Orders': {'hi': 'खरीद आदेश', 'hi_en': 'Purchase Order'},
    'Vendor Invoices': {'hi': 'विक्रेता बिल', 'hi_en': 'Vendor Bill'},
    'Subcontractors': {'hi': 'उप-ठेकेदार', 'hi_en': 'Petti Theka'},
    'Cash & Parties': {'hi': 'नकद और पार्टी', 'hi_en': 'Cash & Party'},
    'Insight': {'hi': 'जानकारी', 'hi_en': 'Insight'},
    'GST & TDS': {'hi': 'GST और TDS', 'hi_en': 'GST & TDS'},
    'Accounting': {'hi': 'लेखा', 'hi_en': 'Accounting'},
}

_current = 'en'


def valid(lang):
    return lang in {code for code, _name in LANGUAGES}


def set_language(lang):
    global _current
    _current = lang if valid(lang) else 'en'


def get_language():
    return _current


def load(conn):
    """Set the active language from app_settings (defaults to English)."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'language'").fetchone()
    set_language(row['value'] if row and row['value'] else 'en')
    return _current


def t(key, lang=None):
    """Localised label for ``key``; falls back to English (the key itself)."""
    lang = lang or _current
    if lang == 'en':
        return key
    return STRINGS.get(key, {}).get(lang, key)
