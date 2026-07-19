"""Material consumption reconciliation.

Civil sites care about theoretical vs actual material consumption: a bag-per-cum
norm times the executed quantity of an activity gives the *theoretical*
requirement, which is compared against what was actually issued from the
material ledger. The gap is wastage (or pilferage) to investigate.

- Norms: ``consumption_norms`` — material consumed per unit of an activity
  (e.g. 6.0 bags of cement per cum of 'M20 Concrete').
- Work done: ``work_done_entries`` — executed activity quantities per site.
- Reconciliation view: for a site, theoretical = SUM(work.qty x norm.qty_per_unit)
  grouped by material (activities matched by name), actual = SUM of OUT ledger
  qty per material; variance & wastage% via ``civil.reconcile_consumption``.
"""

import tkinter as tk
from tkinter import ttk

import civil
from crud_frame import CrudFrame, Field, TODAY
from tab_masters import material_options, site_options


def _build_norms(parent, db_getter):
    fields = [
        Field('activity', 'Activity'),
        Field('unit', 'Unit'),
        Field('material_id', 'Material', kind='fk', options_func=material_options),
        Field('qty_per_unit', 'Qty / Unit', kind='number', default='0'),
        Field('remarks', 'Remarks', width=160),
    ]
    return CrudFrame(parent, db_getter, 'consumption_norms', fields,
                     'Consumption Norms', order_by='activity')


def _build_work_done(parent, db_getter):
    fields = [
        Field('entry_date', 'Date', default=TODAY),
        Field('site_id', 'Site', kind='fk', options_func=site_options,
              remember=True),
        Field('activity', 'Activity'),
        Field('unit', 'Unit'),
        Field('qty', 'Qty Executed', kind='number', default='0'),
        Field('remarks', 'Remarks', width=160),
    ]
    return CrudFrame(parent, db_getter, 'work_done_entries', fields,
                     'Work Done (executed quantities)',
                     order_by='entry_date DESC, id DESC')


class ReconciliationView(ttk.Frame):
    COLUMNS = ('material', 'theoretical', 'actual', 'variance', 'wastage')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._site_map = {}
        self.site_var = tk.StringVar()

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Site', font=('TkDefaultFont', 11, 'bold')).pack(side='left')
        self.site_combo = ttk.Combobox(top, textvariable=self.site_var,
                                       width=24, state='readonly')
        self.site_combo.pack(side='left', padx=6)
        self.site_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Button(top, text='Refresh', command=self.reload).pack(side='left')

        headings = {'material': 'Material', 'theoretical': 'Theoretical',
                    'actual': 'Actual Issued', 'variance': 'Variance',
                    'wastage': 'Wastage %'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=150 if col == 'material' else 120, anchor='w')
        self.tree.tag_configure('over', background='#ffebee')
        self.tree.tag_configure('ok', background='#e8f5e9')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.reload()

    def reload(self):
        conn = self.db_getter()
        try:
            opts = [(s['id'], s['name'])
                    for s in conn.execute('SELECT id, name FROM sites ORDER BY name')]
        finally:
            conn.close()
        self._site_map = {'{} - {}'.format(i, n): i for i, n in opts}
        self.site_combo['values'] = ['{} - {}'.format(i, n) for i, n in opts]
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        raw = self.site_var.get().strip()
        if not raw:
            return
        site_id = self._site_map.get(raw, raw.split(' - ')[0])
        conn = self.db_getter()
        try:
            theoretical = {}
            for r in conn.execute(
                    "SELECT n.material_id AS mid, m.name AS name, "
                    "SUM(w.qty * n.qty_per_unit) AS theo "
                    "FROM work_done_entries w "
                    "JOIN consumption_norms n ON n.activity = w.activity "
                    "JOIN materials m ON m.id = n.material_id "
                    "WHERE w.site_id = ? GROUP BY n.material_id", (site_id,)):
                theoretical[r['mid']] = (r['name'], r['theo'] or 0)
            actual = {}
            for r in conn.execute(
                    "SELECT l.material_id AS mid, m.name AS name, "
                    "SUM(l.qty) AS act FROM material_ledger l "
                    "JOIN materials m ON m.id = l.material_id "
                    "WHERE l.site_id = ? AND l.txn_type = 'OUT' "
                    "GROUP BY l.material_id", (site_id,)):
                actual[r['mid']] = (r['name'], r['act'] or 0)
        finally:
            conn.close()

        for mid in sorted(set(theoretical) | set(actual),
                          key=lambda k: (theoretical.get(k) or actual.get(k))[0]):
            name = (theoretical.get(mid) or actual.get(mid))[0]
            theo = theoretical.get(mid, (name, 0))[1]
            act = actual.get(mid, (name, 0))[1]
            rec = civil.reconcile_consumption(theo, act)
            pct = '-' if rec['wastage_pct'] is None else '{:.1f}%'.format(rec['wastage_pct'])
            tag = 'over' if rec['variance'] > 0 else 'ok'
            self.tree.insert('', 'end', values=(
                name, '{:.3f}'.format(rec['theoretical']),
                '{:.3f}'.format(rec['actual']), '{:.3f}'.format(rec['variance']),
                pct), tags=(tag,))


def build_consumption_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(_build_norms(nb, db_getter), text='Norms')
    nb.add(_build_work_done(nb, db_getter), text='Work Done')
    nb.add(ReconciliationView(nb, db_getter), text='Reconciliation')
    return nb
