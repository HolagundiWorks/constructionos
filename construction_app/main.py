"""Entry point. Initializes the database, builds the ttk.Notebook, and wires
every tab in one place.

Each tab module exposes either a ``build_*_tab(parent, db_getter)`` function
returning a widget, or a class taking ``(parent, db_getter)``. Both are added
the same way: ``nb.add(widget_or_builder(nb, db.get_conn), text=...)``.
"""

import tkinter as tk
from tkinter import ttk

import db
from tab_home import build_home_tab
from tab_money import build_money_tab
from tab_insight import build_insight_tab
from tab_masters import (build_sites_tab, build_clients_tab,
                         build_materials_tab, build_labor_tab,
                         build_equipment_tab)
from tab_vendor import build_vendors_tab
from tab_warehouse import build_warehouse_tab
from tab_labor import build_labor_tab as build_labor_ops_tab
from tab_muster import build_muster_tab
from tab_documents import (build_quotations_tab, build_contracts_tab,
                           build_purchase_orders_tab)
from tab_estimate import build_estimate_tab
from tab_billing import BillingTab
from tab_tax_invoice import build_tax_invoice_tab
from tab_boq_ra import build_boq_ra_tab
from tab_consumption import build_consumption_tab
from tab_site_reports import build_site_reports_tab
from tab_vendor_invoice import build_vendor_invoices_tab
from tab_accounting import build_accounting_tab
from tab_gst import build_gst_tab
from tab_equipment_hire import build_equipment_hire_tab
from tab_timeline import build_timeline_tab
from tab_tools import build_tools_tab


def main():
    db.init_db()

    root = tk.Tk()
    root.title('Contractor-OS — Construction Management')
    root.geometry('1100x720')

    nb = ttk.Notebook(root)
    nb.pack(fill='both', expand=True)

    get = db.get_conn

    # Home
    nb.add(build_home_tab(nb, get), text='Home')

    # Masters
    nb.add(build_sites_tab(nb, get), text='Sites')
    nb.add(build_clients_tab(nb, get), text='Clients')
    nb.add(build_vendors_tab(nb, get), text='Vendors')
    nb.add(build_materials_tab(nb, get), text='Materials')
    nb.add(build_labor_tab(nb, get), text='Labor Master')
    nb.add(build_equipment_tab(nb, get), text='Equipment')

    # Operations
    nb.add(build_warehouse_tab(nb, get), text='Warehouse')
    nb.add(build_labor_ops_tab(nb, get), text='Labor Ops')
    nb.add(build_muster_tab(nb, get), text='Muster & Wages')
    nb.add(build_equipment_hire_tab(nb, get), text='Equipment Hire')

    # Procurement
    nb.add(build_purchase_orders_tab(nb, get), text='Purchase Orders')
    nb.add(build_vendor_invoices_tab(nb, get), text='Vendor Invoices')

    # Documents & commercial
    nb.add(build_quotations_tab(nb, get), text='Quotations')
    nb.add(build_estimate_tab(nb, get), text='Estimates')
    nb.add(build_contracts_tab(nb, get), text='Contracts')
    nb.add(build_boq_ra_tab(nb, get), text='BOQ / RA Bills')
    nb.add(BillingTab(nb, get), text='Bills')
    nb.add(build_tax_invoice_tab(nb, get), text='Tax Invoice')

    # Site execution & quality
    nb.add(build_consumption_tab(nb, get), text='Consumption')
    nb.add(build_site_reports_tab(nb, get), text='Site Reports')

    # Money (cash-first)
    nb.add(build_money_tab(nb, get), text='Money')

    # Insight (profitability & outstanding)
    nb.add(build_insight_tab(nb, get), text='Insight')

    # Compliance & accounting
    nb.add(build_gst_tab(nb, get), text='GST & TDS')
    nb.add(build_accounting_tab(nb, get), text='Accounting')

    # Planning
    nb.add(build_timeline_tab(nb, get), text='Timeline')

    # Tools (backup & restore)
    nb.add(build_tools_tab(nb, get), text='Tools')

    root.mainloop()


if __name__ == '__main__':
    main()
