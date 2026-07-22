"""Menu model (E7.1) — personas → visible sections, and a 3rd-level grouping.

No tkinter, no database. (Target home: ``config/menu.py`` — see
``docs/APP-ARCHITECTURE.md`` §5/§3.2.) This is the *pure model* behind an
enterprise, role-aware menu; the on-screen rail filtering (E7.3/E7.4) renders it.

Two ideas, both data-driven and testable:

* **Personas.** A persona is the *job* a user does (Owner, Commercial/QS, Site
  Engineer, Accountant, Storekeeper) — distinct from the permission *role*
  (Admin/Operator/Viewer, which governs what they may *change*). A persona
  decides *what menu they see*, so a storekeeper is not handed the accounting
  sections and a site engineer is not lost among invoices.
* **Grouping.** A crowded section (Billing already holds 11 tabs) can present its
  tabs in named groups — a third hierarchy level — *without changing which tabs
  exist*. ``flatten(groups_for(...))`` equals the section's original tab list,
  and a test asserts it against the live catalog, so the overlay can never drift.

The one new register home this phase introduces — a **Controls** section for the
Part 2 registers — is modelled here (``CONTROLS_SECTION`` / ``proposed_catalog``)
so personas can already grant it once the tabs are wired (E7.3).

Exercised with ``python -c``.
"""

import modules

# --- personas (the "what menu do I see" axis)
OWNER = 'Owner'
COMMERCIAL = 'Commercial / QS'
SITE = 'Site Engineer'
ACCOUNTS = 'Accountant'
STORE = 'Storekeeper'
PERSONAS = (OWNER, COMMERCIAL, SITE, ACCOUNTS, STORE)

# Rail entries shown to every persona, outside SECTIONS_CATALOG.
ALWAYS_ON = ('Home', 'Assistant', 'Process', 'Tools')

# Controls section for the Part 2 registers (wired in SECTIONS_CATALOG / E7.3).
CONTROLS_SECTION = ('Controls', ['Risk Register', 'Opportunity Register',
                                 'Lessons Learned', 'Submittals'])


# Persona → the set of section titles they see. ``None`` = every section (Owner).
# Titles must match SECTIONS_CATALOG (+ 'Controls'); a test guards that.
_PERSONA_SECTIONS = {
    OWNER: None,
    COMMERCIAL: {'Masters', 'Project Management', 'Billing', 'Purchases',
                 'Money', 'Controls'},
    SITE: {'Masters', 'Project Management', 'Operations', 'Controls'},
    ACCOUNTS: {'Billing', 'Purchases', 'Money', 'Accounts'},
    STORE: {'Masters', 'Operations', 'Purchases'},
}

# Optional 3rd-level grouping for crowded sections: section title → ordered
# [(group_label, [tab_labels])]. A section absent here is one implicit flat
# group. This is an OVERLAY — it only regroups existing tabs, never adds/removes.
GROUPS = {
    'Billing': [
        ('Pre-construction', ['Rate Book', 'Rate Analysis', 'Takeoff',
                              'Bid / No Bid', 'Quotations', 'Estimates']),
        ('Contract billing', ['Contracts', 'BOQ / RA Bills', 'Variations',
                              'Running Bills']),
        ('Invoicing', ['Tax Invoice']),
    ],
    'Operations': [
        ('Site work', ['Warehouse', 'Muster & Wages', 'Labour Ops',
                       'Equipment Hire', 'Plant']),
        ('Records', ['Consumption', 'Site Reports']),
        ('Assurance', ['Quality', 'Safety', 'Closeout']),
    ],
}


def _catalog(catalog=None):
    return catalog if catalog is not None else modules.SECTIONS_CATALOG


def proposed_catalog():
    """Full menu including Controls. Once Controls ships in ``SECTIONS_CATALOG``
    this is the live catalog (no duplicate append)."""
    titles = {t for t, _ in modules.SECTIONS_CATALOG}
    if 'Controls' in titles:
        return list(modules.SECTIONS_CATALOG)
    return list(modules.SECTIONS_CATALOG) + [CONTROLS_SECTION]


def search_tabs(query, catalog=None):
    """Command-palette hits: sections/tabs whose names match ``query``.

    Empty query returns every tab. Matching is case-insensitive substring on
    ``section``, ``tab``, or ``section › tab``. Returns
    ``[{section, tab, label}, ...]`` in catalog order.
    """
    catalog = _catalog(catalog)
    q = (query or '').strip().lower()
    hits = []
    for title, tabs in catalog:
        for tab in tabs:
            label = '{} › {}'.format(title, tab)
            hay = (title + ' ' + tab + ' ' + label).lower()
            if not q or q in hay:
                hits.append({'section': title, 'tab': tab, 'label': label})
    return hits



def visible_sections(persona, catalog=None):
    """Ordered section titles a persona sees, in catalog order. An unknown
    persona, or ``Owner``, sees every section (safe default: show, don't hide)."""
    catalog = _catalog(catalog)
    allowed = _PERSONA_SECTIONS.get(persona, None)
    titles = [t for t, _ in catalog]
    if allowed is None:
        return titles
    return [t for t in titles if t in allowed]


def resolve(persona, is_enabled=None, catalog=None):
    """The final visible menu for a persona: sections the persona sees, each
    holding only its **enabled** tabs.

    ``is_enabled`` is an optional predicate ``label -> bool`` (the module
    feature-flags; default all-on). A section whose tabs are all disabled drops
    out entirely, so the rail never shows an empty section. Returns
    ``[(title, [tabs])]`` in catalog order.
    """
    catalog = _catalog(catalog)
    vis = set(visible_sections(persona, catalog))
    out = []
    for title, tabs in catalog:
        if title not in vis:
            continue
        shown = [t for t in tabs if is_enabled is None or is_enabled(t)]
        if shown:
            out.append((title, shown))
    return out


def groups_for(title, tabs):
    """The grouped view of a section's tabs: ``[(group_label, [labels])]``.

    A section with no grouping overlay returns a single implicit group
    (``group_label`` is None) holding all its tabs — so a caller can iterate
    groups uniformly whether or not a section is grouped."""
    grouping = GROUPS.get(title)
    if not grouping:
        return [(None, list(tabs))]
    return [(g, list(labels)) for g, labels in grouping]


def flatten(grouped):
    """Flatten ``[(group, [labels])]`` back to a flat ``[labels]``. Must equal
    the section's original tab list — the invariant that proves grouping is a
    pure overlay (a test asserts it against the live catalog)."""
    out = []
    for _group, labels in grouped:
        out.extend(labels)
    return out
