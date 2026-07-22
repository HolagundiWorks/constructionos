"""Rate Realisation — the closeout lessons-learned loop (feeds the rate library).

For each material, the **achieved** purchase rate (quantity-weighted, from the
material-ledger IN rows) is set beside its **standard/reference** rate
(`materials.rate`). Where the two have drifted, one click writes the achieved
rate back as the new standard — so the next estimate, rate analysis and material
budget are priced on what things actually cost, not last year's guess.

Scope can be a single site (a finished job's lessons) or all sites (a periodic
refresh of the standard rates). Nothing is auto-applied: the achieved figure is
shown with the number of purchases behind it, and the person decides — a one-off
panic-buy shouldn't silently reset a good standard rate.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import theme

import lessons
import bill_export
import report_open
from ui_guard import can_write
from tab_masters import site_options


class RateRealisation(ttk.Frame):
    COLUMNS = ('material', 'unit', 'reference', 'achieved', 'delta', 'pct',
               'n', 'latest')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._site_map = {}
        self._rows = []                 # (material_id, achieved) for apply
        self.site_var = tk.StringVar()

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Rate Realisation — achieved vs standard',
                  font=('TkDefaultFont', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='right', padx=2)
        ttk.Button(top, text='Refresh', command=self.reload).pack(side='right', padx=2)

        ttk.Label(self, text='The achieved rate is what you actually paid '
                            '(quantity-weighted, from goods received). Applying '
                            'it updates the material’s standard rate, which '
                            'feeds estimates, rate analysis and the material '
                            'budget.', foreground=theme.palette()['muted'],
                  wraplength=680, justify='left').pack(anchor='w', padx=8, pady=(0, 6))

        sel = ttk.Frame(self); sel.pack(fill='x', padx=8, pady=(0, 4))
        ttk.Label(sel, text='Scope').pack(side='left')
        self.site_combo = ttk.Combobox(sel, textvariable=self.site_var,
                                       width=26, state='readonly')
        self.site_combo.pack(side='left', padx=6)
        self.site_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())

        heads = {'material': 'Material', 'unit': 'Unit', 'reference': 'Standard',
                 'achieved': 'Achieved', 'delta': 'Delta', 'pct': 'Var %',
                 'n': 'Buys', 'latest': 'Latest'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 selectmode='extended')
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=150 if col == 'material' else 85, anchor='w')
        self.tree.tag_configure('over', background=theme.wash('bad'))
        self.tree.tag_configure('under', background=theme.wash('good'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btns, text='Apply Achieved → Standard (selected)',
                   command=self.apply_selected).pack(side='left', padx=(0, 6))
        ttk.Button(btns, text='Apply All Drifted',
                   command=self.apply_all_drifted).pack(side='left')
        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var,
                  foreground=theme.palette()['muted']).pack(anchor='w', padx=8, pady=(0, 6))
        self.reload()

    def reload(self):
        conn = self.db_getter()
        try:
            opts = site_options(conn)
        finally:
            conn.close()
        self._site_map = {'{} - {}'.format(i, n): i for i, n in opts}
        self.site_combo['values'] = ['All sites'] + \
            ['{} - {}'.format(i, n) for i, n in opts]
        if not self.site_var.get():
            self.site_var.set('All sites')
        self.refresh()

    def _site_id(self):
        raw = self.site_var.get().strip()
        if not raw or raw == 'All sites':
            return None
        return self._site_map.get(raw, raw.split(' - ')[0])

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        site_id = self._site_id()
        where = "l.txn_type = 'IN' AND l.qty > 0"
        params = []
        if site_id is not None:
            where += ' AND l.site_id = ?'
            params.append(site_id)
        conn = self.db_getter()
        try:
            rows = conn.execute(
                "SELECT m.id, m.name, m.unit, COALESCE(m.rate, 0) AS ref, "
                "SUM(l.qty) AS tq, SUM(l.qty * l.rate) AS tv, COUNT(*) AS n, "
                "MAX(l.txn_date) AS latest "
                "FROM material_ledger l JOIN materials m ON m.id = l.material_id "
                "WHERE " + where + " GROUP BY m.id ORDER BY m.name", params
            ).fetchall()
        finally:
            conn.close()

        for r in rows:
            res = lessons.realise(r['ref'], r['tq'], r['tv'], r['n'])
            if res['achieved'] is None:
                continue
            row = (r['name'], r['unit'] or '', '{:.2f}'.format(res['reference']),
                   '{:.2f}'.format(res['achieved']), '{:+.2f}'.format(res['delta']),
                   '-' if res['pct'] is None else '{:+.1f}%'.format(res['pct']),
                   str(res['n']), r['latest'] or '')
            tag = res['direction'] if res['direction'] in ('over', 'under') else ''
            self.tree.insert('', 'end', iid=str(r['id']), values=row, tags=(tag,))
            self._rows.append((r['id'], res['achieved'], res['delta']))
        self.status_var.set(
            '{} material(s) with purchase history in scope.'.format(len(self._rows)))

    def _apply(self, pairs):
        """Write achieved -> materials.rate for (material_id, achieved) pairs."""
        if not can_write():
            return 0
        if not pairs:
            return 0
        conn = self.db_getter()
        try:
            for mid, achieved in pairs:
                conn.execute('UPDATE materials SET rate = ? WHERE id = ?',
                             (achieved, mid))
            conn.commit()
        finally:
            conn.close()
        return len(pairs)

    def apply_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Nothing selected',
                                'Select one or more materials to update.')
            return
        chosen = {int(i) for i in sel}
        pairs = [(mid, ach) for (mid, ach, _d) in self._rows if mid in chosen]
        if not messagebox.askyesno(
                'Update standard rates',
                'Set the standard rate to the achieved rate for {} material(s)?\n'
                'This affects future estimates and budgets, not past records.'
                .format(len(pairs))):
            return
        n = self._apply(pairs)
        if n:
            self.status_var.set('Updated {} standard rate(s).'.format(n))
            self.refresh()

    def apply_all_drifted(self):
        """Apply every material whose achieved rate differs from the standard."""
        pairs = [(mid, ach) for (mid, ach, delta) in self._rows if delta]
        if not pairs:
            messagebox.showinfo('Nothing to apply',
                                'No material has drifted from its standard rate.')
            return
        if not messagebox.askyesno(
                'Update all drifted rates',
                'Update the standard rate of {} material(s) to their achieved '
                'rate?'.format(len(pairs))):
            return
        n = self._apply(pairs)
        if n:
            self.status_var.set('Updated {} standard rate(s).'.format(n))
            self.refresh()

    def export(self):
        html = bill_export.build_statement_html(
            'Rate Realisation', ['Scope: {}'.format(self.site_var.get())],
            ['Material', 'Unit', 'Standard', 'Achieved', 'Delta', 'Var %',
             'Buys', 'Latest'],
            [self.tree.item(i, 'values') for i in self.tree.get_children()])
        report_open.save_and_open_html(html, 'rate_realisation.html')
