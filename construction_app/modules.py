"""Module catalog + on/off toggles.

Every optional tab is a "module" the contractor can switch off to declutter the
UI (a T2/T3 outfit may never touch Accounting or Timeline). The catalog here —
section title -> ordered tab labels — is the single source of truth for both the
UI layout (``main.py`` supplies a builder per label) and the toggle settings
panel (``tab_tools.py`` renders a checkbox per label).

State lives in ``app_settings`` under ``module:<label>`` (``'1'``/``'0'``);
absent means enabled. ``Home`` and ``Tools`` are always on and not listed here.
Toggles apply on the next app start (the Notebook is built once).
"""

SECTIONS_CATALOG = [
    ('Masters', ['Sites', 'Clients', 'Vendors', 'Materials', 'Labour',
                 'Equipment']),
    # Project Management is the planning + programme workspace, kept apart from
    # daily site execution (Operations): "how is the project doing?" — the
    # portfolio, the programme (Gantt/CPM/baseline/LD) and the weekly plan —
    # rather than "what happened on site today".
    ('Project Management', ['Projects', 'Timeline', 'Look-ahead']),
    ('Operations', ['Warehouse', 'Muster & Wages', 'Labour Ops',
                    'Equipment Hire', 'Plant', 'Consumption', 'Site Reports',
                    'Quality', 'Safety', 'Closeout']),
    ('Billing', ['Rate Book', 'Rate Analysis', 'Takeoff', 'Bid / No Bid',
                 'Quotations', 'Estimates', 'Contracts',
                 'BOQ / RA Bills', 'Variations', 'Running Bills',
                 'Tax Invoice']),
    ('Purchases', ['Sourcing', 'Purchase Orders', 'Goods Receipt',
                   'Vendor Invoices', 'Subcontractors']),
    ('Money', ['Key Numbers', 'Approvals', 'Cash & Parties', 'Cash Flow',
               'Retention', 'Insight']),
    ('Accounts', ['GST & TDS', 'Compliance', 'Accounting']),
]

# Flat list of every toggleable module label, in catalog order.
ALL_MODULES = [label for _title, labels in SECTIONS_CATALOG for label in labels]


def _key(label):
    return 'module:' + label


def enabled_map(conn):
    """Return ``{label: bool}`` for every module (absent setting = enabled)."""
    saved = {r['key']: r['value'] for r in conn.execute(
        "SELECT key, value FROM app_settings WHERE key LIKE 'module:%'")}
    return {label: saved.get(_key(label), '1') != '0' for label in ALL_MODULES}


def is_enabled(conn, label):
    row = conn.execute('SELECT value FROM app_settings WHERE key = ?',
                       (_key(label),)).fetchone()
    return row is None or row['value'] != '0'


def set_states(conn, states):
    """Persist a ``{label: bool}`` mapping."""
    for label, on in states.items():
        conn.execute(
            'INSERT INTO app_settings (key, value) VALUES (?, ?) '
            'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
            (_key(label), '1' if on else '0'))
    conn.commit()
