"""Closeout — the snag list and whether the job can be handed over (Wave 4).

Two views:

* **Snag List** — the punch list, per site. Raise, assign to a trade, set a
  target date, then mark Fixed and finally Verified.
* **Handover** — readiness per site: what proportion is verified, what is
  overdue, which trades are holding it up, and a plain answer to *can this be
  handed over?*

Why this earns its place in an app for a small contractor: handover starts the
defect-liability clock, and the DLP is what releases retention. Every week the
punch list drifts is a week added to getting that money back — which the
Retention register will then dutifully report as "still held".
"""

import tkinter as tk
import theme
from datetime import date
from tkinter import ttk, messagebox

import bill_export
import closeout
import report_open
import retention
from crud_frame import CrudFrame, Field
from tab_masters import site_options
from tab_boq_ra import contract_options
from ui_guard import can_write


def build_snag_list(parent, db_getter):
    fields = [
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('contract_id', 'Contract', kind='fk', options_func=contract_options),
        Field('snag_no', 'Snag No'),
        Field('raised_date', 'Raised', default='TODAY'),
        Field('location', 'Location / element'),
        Field('description', 'Defect'),
        Field('trade', 'Trade'),
        Field('severity', 'Severity', kind='combo', options=closeout.SEVERITIES,
              default=closeout.MINOR),
        Field('assigned_to', 'Assigned to'),
        Field('target_date', 'Fix by'),
        Field('status', 'Status', kind='combo', options=closeout.STATUSES,
              default=closeout.OPEN),
        Field('fixed_date', 'Fixed on'),
        Field('verified_date', 'Verified on'),
        Field('verified_by', 'Verified by'),
        Field('remarks', 'Remarks'),
    ]
    return CrudFrame(parent, db_getter, 'snags', fields,
                     'Snag / punch list — Verified is the client agreeing, '
                     'not you claiming', order_by='status, severity DESC, id DESC')


class HandoverView(ttk.Frame):
    COLUMNS = ('site', 'total', 'open', 'fixed', 'verified', 'overdue',
               'ready', 'verdict')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self.headline_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Handover readiness',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='Handover starts the defect-liability clock, and '
                             'that clock is what releases your retention. A '
                             'punch list left drifting is retention left '
                             'uncollected.',
                  wraplength=700, justify='left', foreground='#555') \
            .pack(anchor='w', padx=8, pady=(0, 6))

        ttk.Label(self, textvariable=self.headline_var, foreground='#a4343a',
                  font=('TkDefaultFont', 11, 'bold'), wraplength=700,
                  justify='left').pack(anchor='w', padx=8, pady=(0, 4))

        heads = {'site': 'Site', 'total': 'Snags', 'open': 'Open',
                 'fixed': 'Fixed', 'verified': 'Verified', 'overdue': 'Overdue',
                 'ready': 'Verified %', 'verdict': 'Handover'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=8)
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=190 if c == 'verdict' else
                             (150 if c == 'site' else 80),
                             anchor='w' if c in ('site', 'verdict') else 'e')
        self.tree.tag_configure('blocked', background=theme.wash('bad'))
        self.tree.tag_configure('ready', background=theme.wash('good'))
        self.tree.pack(fill='x', padx=8, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        ttk.Label(self, text='Who is holding it up',
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=(8, 2))
        self.trade_tree = ttk.Treeview(self, columns=('trade', 'count'),
                                       show='headings', height=6)
        self.trade_tree.heading('trade', text='Trade')
        self.trade_tree.heading('count', text='Snags outstanding')
        self.trade_tree.column('trade', width=300, anchor='w')
        self.trade_tree.column('count', width=140, anchor='e')
        self.trade_tree.pack(fill='both', expand=True, padx=8, pady=4)

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 10))
        ttk.Button(btns, text='Refresh', command=self.refresh).pack(side='left')
        ttk.Button(btns, text='Print / Export', command=self.export).pack(side='left', padx=6)
        ttk.Label(btns, text='Select a site to see its trades.',
                  foreground='#777').pack(side='left', padx=10)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in self.trade_tree.get_children():
            self.trade_tree.delete(item)
        conn = self.db_getter()
        try:
            sites = conn.execute('SELECT id, name FROM sites ORDER BY name').fetchall()
            snags = conn.execute('SELECT * FROM snags').fetchall()
        finally:
            conn.close()

        self._by_site = {}
        for s in snags:
            self._by_site.setdefault(s['site_id'], []).append(s)

        self._rows = []
        blocked_sites = 0
        for site in sites:
            rows = self._by_site.get(site['id'], [])
            if not rows:
                continue
            s = closeout.summarise(rows)
            if not s['may_hand_over']:
                blocked_sites += 1
            values = (
                site['name'], str(s['total']),
                str(s['by_status'].get(closeout.OPEN, 0)),
                str(s['by_status'].get(closeout.FIXED, 0)),
                str(s['by_status'].get(closeout.VERIFIED, 0)),
                str(s['overdue']),
                '-' if s['readiness'] is None else '{:.0f}%'.format(s['readiness']),
                s['reason'])
            self._rows.append(values)
            self.tree.insert('', 'end', iid=str(site['id']), values=values,
                             tags=('ready',) if s['may_hand_over'] else ('blocked',))

        if not self._rows:
            self.headline_var.set('No snags recorded yet.')
        elif blocked_sites:
            self.headline_var.set(
                '{} site(s) cannot be handed over yet — every week of delay is '
                'a week before retention starts running down.'.format(blocked_sites))
        else:
            self.headline_var.set('All sites with snags are clear for handover.')

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        for item in self.trade_tree.get_children():
            self.trade_tree.delete(item)
        if not sel:
            return
        rows = self._by_site.get(int(sel[0]), [])
        for trade, count in closeout.by_trade(rows):
            self.trade_tree.insert('', 'end', values=(trade, count))

    def export(self):
        html = bill_export.build_statement_html(
            'Handover readiness', [self.headline_var.get()],
            ['Site', 'Snags', 'Open', 'Fixed', 'Verified', 'Overdue',
             'Verified %', 'Handover'], self._rows,
            summary=self.headline_var.get())
        report_open.save_and_open_html(html, 'handover_readiness.html')


def build_closeout_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(build_snag_list(nb, db_getter), text='Snag List')
    nb.add(HandoverView(nb, db_getter), text='Handover')
    return nb
