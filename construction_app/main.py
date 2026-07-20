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
import assets
import auth
import session
import i18n
import errors
from tab_login import LoginDialog
from tab_wizard import maybe_run_setup
from tab_home import build_home_tab
from tab_assistant import build_assistant_tab
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
from tab_rateanalysis import build_rate_analysis_tab
from tab_projects import build_projects_tab
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
from tab_sourcing import build_sourcing_tab
from tab_consumption import build_consumption_tab
from tab_site_reports import build_site_reports_tab
from tab_vendor_invoice import build_vendor_invoices_tab
from tab_subcontract import build_subcontract_tab
from tab_accounting import build_accounting_tab
from tab_gst import build_gst_tab
from tab_equipment_hire import build_equipment_hire_tab
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
    'Warehouse': build_warehouse_tab,
    'Muster & Wages': build_muster_tab,
    'Labour Ops': build_labor_ops_tab,
    'Equipment Hire': build_equipment_hire_tab,
    'Consumption': build_consumption_tab,
    'Site Reports': build_site_reports_tab,
    'Quality': build_quality_tab,
    'Look-ahead': build_planning_tab,
    'Safety': build_hse_tab,
    'Closeout': build_closeout_tab,
    'Timeline': build_timeline_tab,
    'Rate Book': build_rate_book_tab,
    'Rate Analysis': build_rate_analysis_tab,
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
    'GST & TDS': build_gst_tab,
    'Accounting': build_accounting_tab,
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


def _section(parent, get, items):
    """Build a sub-notebook holding a group of related tabs."""
    sub = ttk.Notebook(parent)
    for label, builder in items:
        sub.add(builder(sub, get), text=i18n.t(label))
    return sub


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

    nb = ttk.Notebook(root)
    nb.pack(fill='both', expand=True)

    conn = get()
    try:
        enabled = modules.enabled_map(conn)
        i18n.load(conn)                    # active language for tab/section labels
    finally:
        conn.close()

    nb.add(build_home_tab(nb, get), text=i18n.t('Home'))          # always on
    nb.add(build_assistant_tab(nb, get), text=i18n.t('Assistant'))  # always on
    for title, labels in modules.SECTIONS_CATALOG:
        items = [(label, BUILDERS[label]) for label in labels
                 if enabled.get(label, True)]
        if not items:
            continue   # whole section switched off
        nb.add(_section(nb, get, items), text=i18n.t(title))
    nb.add(build_tools_tab(nb, get), text=i18n.t('Tools'))  # always on (holds the toggles)

    root.mainloop()


if __name__ == '__main__':
    main()
