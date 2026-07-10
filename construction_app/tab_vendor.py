"""Vendor tab: a vendor master (CrudFrame) plus a read-only spend/hire rollup.

The rollup is computed on the fly from ``material_ledger`` (IN transactions,
``qty * rate``) and ``equipment_hire`` (``total_amount``), grouped per vendor.
It is display-only — no editing.
"""

import tkinter as tk
from tkinter import ttk

from crud_frame import CrudFrame, Field


def _build_vendor_master(parent, db_getter):
    fields = [
        Field('name', 'Name'),
        Field('contact_person', 'Contact'),
        Field('phone', 'Phone'),
        Field('email', 'Email'),
        Field('gst_no', 'GST No'),
        Field('address', 'Address', width=180),
    ]
    return CrudFrame(parent, db_getter, 'vendors', fields, 'Vendors')


class VendorRollup(ttk.Frame):
    """Read-only per-vendor material spend + equipment hire totals."""

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter

        ttk.Label(self, text='Vendor Spend & Hire Rollup',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        columns = ('vendor', 'material_spend', 'hire_spend', 'total')
        self.tree = ttk.Treeview(self, columns=columns, show='headings')
        headings = {'vendor': 'Vendor', 'material_spend': 'Material Spend',
                    'hire_spend': 'Equipment Hire', 'total': 'Total'}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=160, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        ttk.Button(self, text='Refresh', command=self.refresh) \
            .pack(anchor='w', padx=8, pady=(0, 8))
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            material = {r['vendor_id']: r['spend'] for r in conn.execute(
                "SELECT vendor_id, SUM(qty * rate) AS spend "
                "FROM material_ledger "
                "WHERE txn_type = 'IN' AND vendor_id IS NOT NULL "
                "GROUP BY vendor_id")}
            hire = {r['vendor_id']: r['spend'] for r in conn.execute(
                "SELECT vendor_id, SUM(total_amount) AS spend "
                "FROM equipment_hire WHERE vendor_id IS NOT NULL "
                "GROUP BY vendor_id")}
            for v in conn.execute('SELECT id, name FROM vendors ORDER BY name'):
                m = material.get(v['id'], 0) or 0
                h = hire.get(v['id'], 0) or 0
                self.tree.insert('', 'end', values=(
                    v['name'], '{:.2f}'.format(m), '{:.2f}'.format(h),
                    '{:.2f}'.format(m + h)))
        finally:
            conn.close()


def build_vendors_tab(parent, db_getter):
    """Inner notebook: Vendors master + Spend Rollup."""
    nb = ttk.Notebook(parent)
    nb.add(_build_vendor_master(nb, db_getter), text='Vendors')
    nb.add(VendorRollup(nb, db_getter), text='Spend Rollup')
    return nb
