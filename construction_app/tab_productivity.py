"""Crew / plant productivity KPIs — Operations › Productivity.

Read-only view over ``productivity_store`` (muster + plant logs + work done).
Pure ratios stay in ``productivity.py``; this tab only displays.
"""

import tkinter as tk
from tkinter import ttk

import productivity_store
import theme


class ProductivityTab(ttk.Frame):
    COLS = ('site', 'qty', 'labour_hours', 'units_per_hour', 'hours_per_unit',
            'plant_util_pct')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.from_var = tk.StringVar()
        self.to_var = tk.StringVar()
        self.summary_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        pal = theme.palette()
        ttk.Label(self, text='Productivity',
                  font=('TkDefaultFont', 14, 'bold')).pack(
            anchor='w', padx=12, pady=(12, 2))
        ttk.Label(
            self,
            text='Labour output (units/hour) and plant utilisation from muster, '
                 'work-done and plant logs. Blank dates = all history.',
            foreground=pal['muted'], wraplength=760, justify='left'
        ).pack(anchor='w', padx=12, pady=(0, 6))

        bar = ttk.Frame(self)
        bar.pack(fill='x', padx=12, pady=4)
        ttk.Label(bar, text='From').pack(side='left')
        ttk.Entry(bar, textvariable=self.from_var, width=12).pack(
            side='left', padx=4)
        ttk.Label(bar, text='To').pack(side='left')
        ttk.Entry(bar, textvariable=self.to_var, width=12).pack(
            side='left', padx=4)
        ttk.Button(bar, text='Refresh', command=self.refresh).pack(
            side='left', padx=8)

        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold'), wraplength=760,
                  justify='left').pack(anchor='w', padx=12, pady=4)

        lf = ttk.Frame(self)
        lf.pack(fill='both', expand=True, padx=12, pady=4)
        self.tree = ttk.Treeview(lf, columns=self.COLS, show='headings',
                                 height=12)
        heads = {
            'site': 'Site', 'qty': 'Qty done', 'labour_hours': 'Labour hrs',
            'units_per_hour': 'Units / hr', 'hours_per_unit': 'Hrs / unit',
            'plant_util_pct': 'Plant util %',
        }
        for c in self.COLS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=110 if c != 'site' else 160, anchor='w')
        self.tree.pack(fill='both', expand=True)

    def refresh(self):
        from_d = self.from_var.get().strip() or None
        to_d = self.to_var.get().strip() or None
        conn = self.db_getter()
        try:
            summary = productivity_store.firm_summary(conn, from_d, to_d)
        finally:
            conn.close()
        uph = summary.get('units_per_hour')
        util = summary.get('plant_util_pct')
        self.summary_var.set(
            'Firm: {uph} units/hr · plant util {util}% · '
            'qty {qty:,.1f} · labour {hrs:,.1f} h'.format(
                uph=('—' if uph is None else '{:.2f}'.format(uph)),
                util=('—' if util is None else '{:.0f}'.format(util)),
                qty=summary.get('qty') or 0,
                hrs=summary.get('labour_hours') or 0,
            ))
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in summary.get('sites') or []:
            uph_r = r.get('units_per_hour')
            hpu = r.get('hours_per_unit')
            util_r = r.get('plant_util_pct')
            self.tree.insert('', 'end', values=(
                r.get('site') or '',
                '{:.1f}'.format(r.get('qty') or 0),
                '{:.1f}'.format(r.get('labour_hours') or 0),
                '—' if uph_r is None else '{:.2f}'.format(uph_r),
                '—' if hpu is None else '{:.2f}'.format(hpu),
                '—' if util_r is None else '{:.0f}'.format(util_r),
            ))


def build_productivity_tab(parent, db_getter):
    return ProductivityTab(parent, db_getter)
