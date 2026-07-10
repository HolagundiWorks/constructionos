"""Entry point. Initializes the database, builds the ttk.Notebook, and wires
every tab in one place.

Each tab module exposes either a ``build_*_tab(parent, db_getter)`` function
returning a widget, or a class taking ``(parent, db_getter)``. Both are added
the same way: ``nb.add(widget_or_builder(nb, db.get_conn), text=...)``.
"""

import tkinter as tk
from tkinter import ttk

import db
from tab_masters import (build_sites_tab, build_clients_tab,
                         build_materials_tab, build_labor_tab,
                         build_equipment_tab)
from tab_vendor import build_vendors_tab
from tab_warehouse import build_warehouse_tab
from tab_labor import build_labor_tab as build_labor_ops_tab
from tab_documents import (build_quotations_tab, build_estimates_tab,
                           build_contracts_tab)
from tab_billing import BillingTab
from tab_equipment_hire import build_equipment_hire_tab
from tab_timeline import build_timeline_tab


def main():
    db.init_db()

    root = tk.Tk()
    root.title('Contractor-OS — Construction Management')
    root.geometry('1100x720')

    nb = ttk.Notebook(root)
    nb.pack(fill='both', expand=True)

    get = db.get_conn

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
    nb.add(build_equipment_hire_tab(nb, get), text='Equipment Hire')

    # Documents & commercial
    nb.add(build_quotations_tab(nb, get), text='Quotations')
    nb.add(build_estimates_tab(nb, get), text='Estimates')
    nb.add(build_contracts_tab(nb, get), text='Contracts')
    nb.add(BillingTab(nb, get), text='Bills')

    # Planning
    nb.add(build_timeline_tab(nb, get), text='Timeline')

    root.mainloop()


if __name__ == '__main__':
    main()
