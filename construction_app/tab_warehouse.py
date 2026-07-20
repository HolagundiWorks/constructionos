"""Warehouse tab: material ledger CRUD + a computed stock summary.

The ledger is a flat transaction log (IN/OUT). The stock summary is derived on
the fly per (site, material) as SUM(IN qty) - SUM(OUT qty); it is never stored.
"""

from tkinter import ttk

from crud_frame import CrudFrame, Field, TODAY
from tab_masters import (site_options, material_options, vendor_options,
                         project_options)


def _build_ledger(parent, db_getter):
    fields = [
        Field('txn_date', 'Date', default=TODAY),
        Field('site_id', 'Site', kind='fk', options_func=site_options,
              remember=True),
        # Optional: tag the issue to a project so cost rolls up per project
        # even when a site hosts more than one. Blank = attributed by site.
        Field('project_id', 'Project (optional)', kind='fk',
              options_func=project_options),
        Field('material_id', 'Material', kind='fk',
              options_func=material_options),
        Field('txn_type', 'Type', kind='combo',
              options=['IN', 'OUT'], default='IN'),
        Field('qty', 'Qty', kind='number', default='0'),
        Field('rate', 'Rate', kind='number', default='0'),
        Field('vendor_id', 'Vendor (IN)', kind='fk',
              options_func=vendor_options),
        Field('remarks', 'Remarks', width=160),
    ]
    return CrudFrame(parent, db_getter, 'material_ledger', fields,
                     'Material Ledger', order_by='txn_date DESC, id DESC')


class StockSummary(ttk.Frame):
    """Read-only current stock per site/material, computed from the ledger."""

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter

        ttk.Label(self, text='Stock Summary',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        columns = ('site', 'material', 'in_qty', 'out_qty', 'balance')
        headings = {'site': 'Site', 'material': 'Material', 'in_qty': 'Total In',
                    'out_qty': 'Total Out', 'balance': 'Balance'}
        self.tree = ttk.Treeview(self, columns=columns, show='headings')
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=140, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        ttk.Button(self, text='Refresh', command=self.refresh) \
            .pack(anchor='w', padx=8, pady=(0, 8))
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            sql = (
                "SELECT s.name AS site, m.name AS material, "
                "  SUM(CASE WHEN l.txn_type = 'IN'  THEN l.qty ELSE 0 END) AS in_qty, "
                "  SUM(CASE WHEN l.txn_type = 'OUT' THEN l.qty ELSE 0 END) AS out_qty "
                "FROM material_ledger l "
                "LEFT JOIN sites s ON s.id = l.site_id "
                "LEFT JOIN materials m ON m.id = l.material_id "
                "GROUP BY l.site_id, l.material_id "
                "ORDER BY s.name, m.name")
            for r in conn.execute(sql):
                in_qty = r['in_qty'] or 0
                out_qty = r['out_qty'] or 0
                self.tree.insert('', 'end', values=(
                    r['site'] or '-', r['material'] or '-',
                    '{:.2f}'.format(in_qty), '{:.2f}'.format(out_qty),
                    '{:.2f}'.format(in_qty - out_qty)))
        finally:
            conn.close()


def build_warehouse_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(_build_ledger(nb, db_getter), text='Material Ledger')
    nb.add(StockSummary(nb, db_getter), text='Stock Summary')
    return nb
