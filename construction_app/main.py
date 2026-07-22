"""Entry point. Initializes the database, builds the ttk.Notebook, and wires
every tab in one place.

Each tab module exposes either a ``build_*_tab(parent, db_getter)`` function
returning a widget, or a class taking ``(parent, db_getter)`` — both are simple
callables ``builder(parent, db_getter)``. To keep the top tab bar from getting
crowded, tabs are grouped into a handful of top-level **sections**; each section
is its own ``ttk.Notebook`` holding the related tabs (``_section`` below). A
builder that already returns a Notebook (e.g. Money) just nests one level
deeper, which is fine.
"""

import os
import tkinter as tk
from tkinter import ttk

import db
import modules
import menu
import assets
import auth
import session
import i18n
import errors
import theme
from shell import RailStage
from tab_login import LoginDialog
from tab_wizard import maybe_run_setup
from tab_home import build_home_tab
from tab_assistant import build_assistant_tab
from tab_aiengine import build_aiengine_tab
from tab_money import build_money_tab
from tab_insight import build_insight_tab
from tab_masters import (build_sites_tab, build_clients_tab,
                         build_materials_tab, build_labor_tab,
                         build_equipment_tab, build_rate_book_tab)
from tab_vendor import build_vendors_tab
from tab_warehouse import build_warehouse_tab
from tab_labor import build_labor_tab as build_labor_ops_tab
from tab_muster import build_muster_tab
from tab_documents import (build_quotations_tab, build_contracts_tab,
                           build_purchase_orders_tab)
from tab_estimate import build_estimate_tab
from tab_bidding import build_bidding_tab
from tab_rateanalysis import build_rate_analysis_tab
from tab_takeoff import build_takeoff_tab
from tab_projects import build_projects_tab
from tab_evm import build_evm_tab
from tab_risk import build_risk_tab
from tab_opportunity import build_opportunity_tab
from tab_lessons_learned import build_lessons_learned_tab
from tab_process import build_process_tab
from tab_sourcing import build_sourcing_tab, build_submittals
from tab_review import build_review_tab
from tab_portfolio import build_portfolio_tab
from tab_productivity import build_productivity_tab
from tab_billing import BillingTab
from tab_tax_invoice import build_tax_invoice_tab
from tab_boq_ra import build_boq_ra_tab
from tab_variations import build_variations_tab
from tab_cashflow import build_cashflow_tab
from tab_grn import build_grn_tab
from tab_retention import build_retention_tab
from tab_quality import build_quality_tab
from tab_planning import build_planning_tab
from tab_kpi import build_kpi_tab
from tab_approvals import build_approvals_tab
from tab_closeout import build_closeout_tab
from tab_hse import build_hse_tab
from tab_consumption import build_consumption_tab
from tab_site_reports import build_site_reports_tab
from tab_vendor_invoice import build_vendor_invoices_tab
from tab_subcontract import build_subcontract_tab
from tab_accounting import build_accounting_tab
from tab_gst import build_gst_tab
from tab_compliance import build_compliance_tab
from tab_equipment_hire import build_equipment_hire_tab
from tab_plant import build_plant_tab
from tab_timeline import build_timeline_tab
from tab_tools import build_tools_tab


# One builder per module label. The section grouping and order live in
# modules.SECTIONS_CATALOG (the single source of truth, shared with the toggle
# settings panel); this map just supplies the widget for each label.
BUILDERS = {
    'Sites': build_sites_tab,
    'Clients': build_clients_tab,
    'Vendors': build_vendors_tab,
    'Materials': build_materials_tab,
    'Labour': build_labor_tab,
    'Equipment': build_equipment_tab,
    'Projects': build_projects_tab,
    'Earned Value': build_evm_tab,
    'Risk Register': build_risk_tab,
    'Opportunity Register': build_opportunity_tab,
    'Lessons Learned': build_lessons_learned_tab,
    'Submittals': build_submittals,
    # Legacy aliases (pre-Controls rename) — keep callable for old bookmarks.
    'Risks': build_risk_tab,
    'Opportunities': build_opportunity_tab,
    'Warehouse': build_warehouse_tab,
    'Muster & Wages': build_muster_tab,
    'Labour Ops': build_labor_ops_tab,
    'Equipment Hire': build_equipment_hire_tab,
    'Plant': build_plant_tab,
    'Productivity': build_productivity_tab,
    'Consumption': build_consumption_tab,
    'Site Reports': build_site_reports_tab,
    'Quality': build_quality_tab,
    'Look-ahead': build_planning_tab,
    'Safety': build_hse_tab,
    'Closeout': build_closeout_tab,
    'Timeline': build_timeline_tab,
    'Rate Book': build_rate_book_tab,
    'Rate Analysis': build_rate_analysis_tab,
    'Takeoff': build_takeoff_tab,
    'Bid / No Bid': build_bidding_tab,
    'Quotations': build_quotations_tab,
    'Estimates': build_estimate_tab,
    'Contracts': build_contracts_tab,
    'BOQ / RA Bills': build_boq_ra_tab,
    'Variations': build_variations_tab,
    'Running Bills': BillingTab,
    'Tax Invoice': build_tax_invoice_tab,
    'Sourcing': build_sourcing_tab,
    'Purchase Orders': build_purchase_orders_tab,
    'Goods Receipt': build_grn_tab,
    'Vendor Invoices': build_vendor_invoices_tab,
    'Subcontractors': build_subcontract_tab,
    'Key Numbers': build_kpi_tab,
    'Approvals': build_approvals_tab,
    'Cash & Parties': build_money_tab,
    'Cash Flow': build_cashflow_tab,
    'Retention': build_retention_tab,
    'Insight': build_insight_tab,
    'Review': build_review_tab,
    'Portfolio': build_portfolio_tab,
    'GST & TDS': build_gst_tab,
    'Compliance': build_compliance_tab,
    'Accounting': build_accounting_tab,
}


# A pictogram per module — so a sub-tab inside a section is found by shape
# before its word is read, echoing the rail. Kept distinct within each section.
MODULE_ICONS = {
    # Masters
    'Sites': '\U0001F4CD', 'Clients': '\U0001F91D', 'Vendors': '\U0001F3ED',
    'Materials': '\U0001F9F1', 'Labour': '\U0001F477', 'Equipment': '\U0001F69C',
    # Projects + Controls
    'Projects': '\U0001F3D7', 'Earned Value': '\U0001F4C8',
    'Risk Register': '⚠', 'Opportunity Register': '\U0001F31F',
    'Lessons Learned': '\U0001F4D3', 'Submittals': '\U0001F4E4',
    'Risks': '⚠', 'Opportunities': '\U0001F31F',
    # Operations
    'Warehouse': '\U0001F4E6', 'Muster & Wages': '\U0001F4CB',
    'Labour Ops': '\U0001F477', 'Equipment Hire': '\U0001F69C', 'Plant': '⚙',
    'Productivity': '\U0001F4C8',
    'Consumption': '\U0001F6E2', 'Site Reports': '\U0001F4DD', 'Quality': '✅',
    'Look-ahead': '\U0001F4C5', 'Safety': '\U0001F9BA', 'Closeout': '\U0001F3C1',
    'Timeline': '\U0001F4C6',
    # Billing
    'Rate Book': '\U0001F4D6', 'Rate Analysis': '\U0001F9EE',
    'Takeoff': '\U0001F4CF', 'Bid / No Bid': '⚖',
    'Quotations': '\U0001F4C4', 'Estimates': '\U0001F4D0', 'Contracts': '\U0001F4DC',
    'BOQ / RA Bills': '\U0001F4D1', 'Variations': '\U0001F500',
    'Running Bills': '\U0001F9FE', 'Tax Invoice': '\U0001F4C3',
    # Purchases
    'Sourcing': '\U0001F50E', 'Purchase Orders': '\U0001F6D2',
    'Goods Receipt': '\U0001F4E5', 'Vendor Invoices': '\U0001F9FE',
    'Subcontractors': '\U0001F91D',
    # Money
    'Key Numbers': '\U0001F511', 'Approvals': '✔', 'Cash & Parties': '\U0001F4B0',
    'Cash Flow': '\U0001F4B8', 'Retention': '\U0001F512', 'Insight': '\U0001F4A1',
    'Review': '\U0001F5DE', 'Portfolio': '\U0001F4CA',
    # Accounts
    'GST & TDS': '\U0001F3DB', 'Compliance': '\U0001F5D3', 'Accounting': '\U0001F4CA',
}


def _apply_app_icon(root):
    """Set the window/taskbar icon from the bundled logo. Fails soft."""
    try:
        icon = tk.PhotoImage(file=assets.LOGO_SQUARE)   # Tk 8.6+ reads PNG
        root.iconphoto(True, icon)
        root._app_icon = icon                            # keep a reference
    except Exception:
        pass
    if os.name == 'nt':
        try:
            root.iconbitmap(assets.APP_ICON)
        except Exception:
            pass


def _section(parent, get, title, items):
    """Build a sub-notebook holding a group of related tabs.

    When ``menu.GROUPS`` defines a 3rd-level overlay for ``title``, render an
    outer notebook of named groups, each holding its tabs — otherwise a flat
    notebook (the historical behaviour).
    """
    builders = {label: builder for label, builder in items}
    tabs = [label for label, _ in items]
    groups = menu.groups_for(title, tabs)

    def _add_tabs(nb, labels):
        for label in labels:
            builder = builders.get(label)
            if builder is None:
                continue
            icon = MODULE_ICONS.get(label, '')
            text = ('{}  {}'.format(icon, i18n.t(label)) if icon
                    else i18n.t(label))
            nb.add(builder(nb, get), text=text)

    # One implicit group → flat section notebook.
    if len(groups) == 1 and groups[0][0] is None:
        sub = ttk.Notebook(parent)
        _add_tabs(sub, groups[0][1])
        return sub

    outer = ttk.Notebook(parent)
    for group_label, labels in groups:
        shown = [t for t in labels if t in builders]
        if not shown:
            continue
        inner = ttk.Notebook(outer)
        _add_tabs(inner, shown)
        outer.add(inner, text=group_label or i18n.t(title))
    return outer


def main():
    db.init_db()

    get = db.get_conn

    # Optional login gate: only when security is enabled and users exist.
    conn = get()
    try:
        require_login = auth.security_enabled(conn) and auth.user_count(conn) > 0
    finally:
        conn.close()

    root = tk.Tk()
    root.title('Construction OS — Construction Management')
    root.geometry('1180x760')
    _apply_app_icon(root)
    errors.install(root)   # no stack trace ever reaches the user

    # HCW theme, before any UI is built so classic-widget defaults take effect.
    conn = get()
    try:
        theme.apply(root, theme.load_mode(conn))
    finally:
        conn.close()

    if require_login:
        root.withdraw()                      # hide until authenticated
        dialog = LoginDialog(root, get)
        if not dialog.ok:
            root.destroy()
            return
        root.deiconify()
        root.title('Construction OS — {} ({})'.format(
            session.username(), session.role()))

    # First-run wizard on a fresh book (empty masters, not previously done).
    maybe_run_setup(root, get)

    conn = get()
    try:
        enabled = modules.enabled_map(conn)
        i18n.load(conn)                    # active language for tab/section labels
        persona = modules.get_persona(conn)
        if persona not in menu.PERSONAS:
            persona = menu.OWNER
    finally:
        conn.close()

    def toggle_theme():
        new = 'dark' if theme.mode() == 'light' else 'light'
        c = get()
        try:
            theme.save_mode(c, new)
        finally:
            c.close()
        theme.apply(root, new)

    # A pictogram per rail row — the eye finds a section by shape before it
    # reads the word. Keyed by the always-on screens and by section title.
    icons = {
        'home': '\U0001F3E0',        # house
        'assistant': '\U0001F4AC',   # speech balloon
        'process': '\U0001F9ED',     # compass — guided what's-next
        'aiengine': '\U0001F916',    # robot — the local AI engine (Foundry Local)
        'tools': '⚙',           # gear
        'Masters': '\U0001F5C2',            # card index dividers
        'Project Management': '\U0001F3D7',  # building construction
        'Controls': '\U0001F6E1',           # shield — registers
        'Operations': '\U0001F6E0',         # hammer and wrench
        'Billing': '\U0001F9FE',     # receipt
        'Purchases': '\U0001F6D2',   # shopping trolley
        'Money': '\U0001F4B0',       # money bag
        'Accounts': '\U0001F4CA',    # bar chart
    }

    # Persona-scoped sections (E7.3) compose with module feature-flags.
    resolved = menu.resolve(
        persona, is_enabled=lambda label: enabled.get(label, True))

    # shell is filled after entries are built; goto closes over it.
    shell_holder = {'shell': None}

    def goto(section, tab):
        sh = shell_holder['shell']
        if sh is None:
            return
        key = 'sec:' + section
        if key not in {e['key'] for e in sh.entries}:
            return
        sh.select(key)
        root_nb = sh._built.get(key)
        if not isinstance(root_nb, ttk.Notebook):
            return

        def _select_tab(nb, name):
            try:
                end = nb.index('end')
            except Exception:
                return False
            for i in range(end):
                text = nb.tab(i, 'text') or ''
                child = nb.nametowidget(nb.tabs()[i])
                if name in text or text.strip().endswith(name):
                    nb.select(i)
                    return True
                # Nested group notebook (E7.3 3rd level).
                if isinstance(child, ttk.Notebook) and _select_tab(child, name):
                    nb.select(i)
                    return True
            return False

        _select_tab(root_nb, tab)

    # One rail entry per always-on screen and per enabled section; each section
    # keeps its sub-notebook, built lazily the first time the row is opened.
    entries = [
        {'key': 'home', 'label': i18n.t('Home'), 'icon': icons['home'],
         'build': lambda p: build_home_tab(p, get)},
        {'key': 'assistant', 'label': i18n.t('Assistant'),
         'icon': icons['assistant'],
         'build': lambda p: build_assistant_tab(p, get)},
        {'key': 'process', 'label': 'Process', 'icon': icons['process'],
         'build': lambda p: build_process_tab(p, get, on_goto=goto)},
        # The local AI engine (Foundry Local) as its own rail row — start/stop
        # the on-device daemon and set up the one built-in model — so it is found
        # at a glance rather than buried as a sub-tab.
        {'key': 'aiengine', 'label': 'AI Engine', 'icon': icons['aiengine'],
         'build': lambda p: build_aiengine_tab(p, get)},
    ]
    for title, labels in resolved:
        items = [(label, BUILDERS[label]) for label in labels]
        if not items:
            continue
        entries.append({'key': 'sec:' + title, 'label': i18n.t(title),
                        'icon': icons.get(title, '◆'),
                        'build': (lambda p, t=title, it=items:
                                  _section(p, get, t, it))})
    entries.append({'key': 'tools', 'label': i18n.t('Tools'),
                    'icon': icons['tools'],
                    'build': lambda p: build_tools_tab(p, get)})

    subtitle = persona
    try:
        if session.username():
            subtitle = '{} · {} · {}'.format(
                session.username(), session.role(), persona)
    except Exception:
        pass

    shell = RailStage(root, entries, subtitle=subtitle,
                      on_toggle_theme=toggle_theme)
    shell_holder['shell'] = shell
    shell.pack(fill='both', expand=True)

    root.mainloop()


if __name__ == '__main__':
    main()
