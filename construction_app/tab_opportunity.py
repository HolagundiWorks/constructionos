"""Opportunity Register — the on-screen register over ``opportunity_store`` (E5).

The upside twin of the Risk tab. The maths lives in ``opportunity.py``
(likelihood × impact → score/band, probability-weighted **expected upside**,
urgency-driven priority) and the persistence in ``opportunity_store.py``
(derive-on-save, so a stored band can never disagree with the scoring) — the
same machine as the risk register, pointed at the good news. This tab is only the
GUI: a best-first list (the opportunity to pursue hardest on top), and a form
whose **score / band / expected upside are computed live and never typed**.

Statuses record a decision (Open → Pursuing → Realized / Declined); the derived
figures are display-only. Writes are gated for Viewers via ``ui_guard``.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import opportunity
import opportunity_store
import theme
from ui_guard import can_write
from widgets import make_sortable
from tab_masters import project_options

_STATUSES = ['Open', 'Pursuing', 'Realized', 'Declined']
_CATEGORIES = ['Cost', 'Schedule', 'Procurement', 'Quality', 'Commercial',
               'Resource', 'Design', 'Client', 'Other']
_LK = ['{} — {}'.format(n, opportunity.LIKELIHOOD_LABELS[n]) for n in range(1, 6)]
_IM = ['{} — {}'.format(n, opportunity.IMPACT_LABELS[n]) for n in range(1, 6)]
_URG = [''] + ['{}'.format(n) for n in range(1, 6)]


def _lvl(text):
    """Pull the leading 1..5 out of a 'N — Label' combo value (0/'' → None)."""
    text = (text or '').strip()
    if not text:
        return None
    try:
        return int(text.split('—')[0].strip().split()[0])
    except (ValueError, IndexError):
        return None


class OpportunityRegisterTab(ttk.Frame):
    COLS = ('title', 'category', 'li', 'band', 'upside', 'response',
            'owner', 'status')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self._proj_map = {}
        self.vars = {}
        self._build_ui()
        self.refresh()

    # -------------------------------------------------------------------- UI
    def _build_ui(self):
        pal = theme.palette()
        ttk.Label(self, text='Opportunity Register',
                  font=('TkDefaultFont', 14, 'bold')).pack(
            anchor='w', padx=12, pady=(12, 2))
        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var, foreground=pal['muted'],
                  wraplength=760, justify='left').pack(anchor='w', padx=12,
                                                       pady=(0, 6))

        # --- filters
        bar = ttk.Frame(self); bar.pack(fill='x', padx=12, pady=2)
        ttk.Label(bar, text='Project').pack(side='left')
        self.filter_proj = ttk.Combobox(bar, width=20, state='readonly')
        self.filter_proj.pack(side='left', padx=(4, 10))
        self.filter_proj.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Label(bar, text='Status').pack(side='left')
        self.filter_status = ttk.Combobox(bar, width=12, state='readonly',
                                          values=['All'] + _STATUSES)
        self.filter_status.set('All')
        self.filter_status.pack(side='left', padx=(4, 10))
        self.filter_status.bind('<<ComboboxSelected>>', lambda e: self.refresh())

        # --- list
        lf = ttk.Frame(self); lf.pack(fill='both', expand=True, padx=12, pady=4)
        self.tree = ttk.Treeview(lf, columns=self.COLS, show='headings',
                                 height=9)
        heads = {'title': 'Opportunity', 'category': 'Category', 'li': 'L×I',
                 'band': 'Priority', 'upside': 'Expected upside',
                 'response': 'Response', 'owner': 'Owner', 'status': 'Status'}
        widths = {'title': 240, 'category': 90, 'li': 50, 'band': 70,
                  'upside': 120, 'response': 80, 'owner': 100, 'status': 80}
        for c in self.COLS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor='w')
        vsb = ttk.Scrollbar(lf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        # A strong opportunity is good news — the best are washed green (go get
        # it), the middling grey; nothing shouts red.
        self.tree.tag_configure('pursue', background=theme.wash('good'))
        self.tree.tag_configure('watch', background=theme.wash('muted'))
        self._resort = make_sortable(self.tree)     # click-to-sort headers

        # --- form
        form = ttk.LabelFrame(self, text='Details')
        form.pack(fill='x', padx=12, pady=4)
        fields = [
            ('title', 'Opportunity', 'entry'),
            ('category', 'Category', _CATEGORIES),
            ('owner', 'Owner', 'entry'),
            ('likelihood', 'Likelihood', _LK), ('impact', 'Impact', _IM),
            ('urgency', 'Urgency (1-5)', _URG),
            ('value', 'Upside value ₹', 'entry'),
            ('response', 'Response', list(opportunity.RESPONSES)),
            ('status', 'Status', _STATUSES),
            ('target_date', 'Target date', 'entry'),
            ('action_plan', 'Action / plan', 'entry'),
            ('remarks', 'Remarks', 'entry'),
        ]
        for idx, (key, label, kind) in enumerate(fields):
            cell = ttk.Frame(form)
            cell.grid(row=idx // 3, column=idx % 3, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=14).pack(side='left')
            var = tk.StringVar()
            self.vars[key] = var
            if isinstance(kind, list):
                w = ttk.Combobox(cell, textvariable=var, width=18,
                                 state='readonly', values=kind)
            else:
                w = ttk.Entry(cell, textvariable=var, width=20)
            w.pack(side='left')
        self.vars['status'].set('Open')
        for k in ('likelihood', 'impact', 'urgency', 'value'):
            self.vars[k].trace_add('write', lambda *_a: self._reassess())
        self.assess_var = tk.StringVar()
        ttk.Label(form, textvariable=self.assess_var,
                  font=('TkDefaultFont', 10, 'bold')).grid(
            row=4, column=0, columnspan=3, padx=6, pady=(2, 6), sticky='w')

        btns = ttk.Frame(self); btns.pack(fill='x', padx=12, pady=(2, 10))
        ttk.Button(btns, text='Add', command=self.add).pack(side='left', padx=3)
        ttk.Button(btns, text='Update', command=self.update).pack(side='left', padx=3)
        ttk.Button(btns, text='Delete', command=self.delete).pack(side='left', padx=3)
        ttk.Button(btns, text='Clear', command=self.clear).pack(side='left', padx=3)
        ttk.Button(btns, text='Refresh', command=self.refresh).pack(side='left', padx=3)

    # ---------------------------------------------------------------- helpers
    def _reassess(self):
        lk, im = _lvl(self.vars['likelihood'].get()), _lvl(self.vars['impact'].get())
        if not lk or not im:
            self.assess_var.set('')
            return
        try:
            val = float(self.vars['value'].get() or 0)
        except ValueError:
            val = 0
        a = opportunity.assess(lk, im, value=val,
                               urgency=_lvl(self.vars['urgency'].get()))
        self.assess_var.set(
            'Assessment:  score {}  ·  {}  ·  expected upside ₹ {:,.0f}'.format(
                a['score'], a['band'], a['expected_value']))

    def _collect(self):
        lk, im = _lvl(self.vars['likelihood'].get()), _lvl(self.vars['impact'].get())
        if not self.vars['title'].get().strip():
            messagebox.showinfo('Opportunity', 'An opportunity needs a title.')
            return None
        if not lk or not im:
            messagebox.showinfo('Opportunity',
                                'Choose a likelihood and an impact.')
            return None
        try:
            val = float(self.vars['value'].get() or 0)
        except ValueError:
            messagebox.showerror('Opportunity', 'Upside value must be a number.')
            return None
        return {
            'project_id': self._proj_map.get(self.filter_proj.get()),
            'title': self.vars['title'].get().strip(),
            'category': self.vars['category'].get().strip(),
            'owner': self.vars['owner'].get().strip(),
            'likelihood': lk, 'impact': im,
            'urgency': _lvl(self.vars['urgency'].get()),
            'value': val,
            'response': self.vars['response'].get().strip() or None,
            'status': self.vars['status'].get().strip() or 'Open',
            'target_date': self.vars['target_date'].get().strip(),
            'action_plan': self.vars['action_plan'].get().strip(),
            'remarks': self.vars['remarks'].get().strip(),
        }

    # ----------------------------------------------------------------- data
    def refresh(self):
        conn = self.db_getter()
        try:
            self._proj_map = {'{} - {}'.format(i, n): i
                              for i, n in project_options(conn)}
            self.filter_proj['values'] = ['All projects'] + list(self._proj_map)
            if not self.filter_proj.get():
                self.filter_proj.set('All projects')
            pid = self._proj_map.get(self.filter_proj.get())
            st = self.filter_status.get()
            rows = opportunity_store.list_opportunities(
                conn, project_id=pid, status=(None if st == 'All' else st))
            summ = opportunity_store.summary(conn, project_id=pid)
        finally:
            conn.close()

        self.tree.delete(*self.tree.get_children())
        for r in rows:
            band = r['band'] or 'Low'
            tag = 'pursue' if band in ('Critical', 'High') else (
                'watch' if band == 'Medium' else '')
            self.tree.insert('', 'end', iid=str(r['id']), tags=(tag,), values=(
                r['title'], r['category'] or '',
                '{}×{}'.format(r['likelihood'], r['impact']), band,
                '₹ {:,.0f}'.format(r['expected_value'] or 0),
                r['response'] or '', r['owner'] or '', r['status'] or ''))
        bb = summ['by_band']
        self.summary_var.set(
            '{c} opportunity(ies)  ·  {n} worth pursuing now  ·  total expected '
            'upside ₹ {e:,.0f}     Critical {cr} · High {hi} · Medium {me} · '
            'Low {lo}'.format(
                c=summ['count'], n=summ['pursue_now'],
                e=summ['total_expected_value'], cr=bb['Critical'],
                hi=bb['High'], me=bb['Medium'], lo=bb['Low']))
        self._resort()          # keep the chosen sort after a reload

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = opportunity_store.get(conn, self.selected_id)
        finally:
            conn.close()
        if not r:
            return
        self.vars['title'].set(r['title'] or '')
        self.vars['category'].set(r['category'] or '')
        self.vars['owner'].set(r['owner'] or '')
        self.vars['likelihood'].set(
            _LK[r['likelihood'] - 1] if r['likelihood'] else '')
        self.vars['impact'].set(_IM[r['impact'] - 1] if r['impact'] else '')
        self.vars['urgency'].set(str(r['urgency']) if r['urgency'] else '')
        self.vars['value'].set('' if not r['value'] else str(r['value']))
        self.vars['response'].set(r['response'] or '')
        self.vars['status'].set(r['status'] or 'Open')
        self.vars['target_date'].set(r['target_date'] or '')
        self.vars['action_plan'].set(r['action_plan'] or '')
        self.vars['remarks'].set(r['remarks'] or '')

    # --------------------------------------------------------------- actions
    def add(self):
        if not can_write():
            return
        vals = self._collect()
        if vals is None:
            return
        conn = self.db_getter()
        try:
            opportunity_store.add(conn, source='manual', **vals)
        finally:
            conn.close()
        self.refresh()
        self.clear()

    def update(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('Opportunity', 'Select one to update.')
            return
        vals = self._collect()
        if vals is None:
            return
        conn = self.db_getter()
        try:
            opportunity_store.update(conn, self.selected_id, **vals)
        finally:
            conn.close()
        self.refresh()

    def delete(self):
        if not can_write():
            return
        if self.selected_id is None:
            return
        if not messagebox.askyesno('Delete opportunity',
                                   'Delete the selected opportunity?'):
            return
        conn = self.db_getter()
        try:
            opportunity_store.delete(conn, self.selected_id)
        finally:
            conn.close()
        self.refresh()
        self.clear()

    def clear(self):
        self.selected_id = None
        for k, v in self.vars.items():
            v.set('Open' if k == 'status' else '')
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self.assess_var.set('')


def build_opportunity_tab(parent, db_getter):
    return OpportunityRegisterTab(parent, db_getter)
