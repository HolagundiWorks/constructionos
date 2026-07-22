"""Earned Value — SPI/CPI/EAC surfaced per project and rolled up (E0.1).

Read-only. The maths is pure in ``earnedvalue.py``; ``evm.py`` bridges it to the
app's own figures (BAC = contract value/budget, AC = cost to date, EV = billed
value, PV = time-scheduled). This tab renders one worst-first line per measured
project — the two indices, percent complete, the forecast (EAC/VAC) and a plain
health verdict — over a portfolio roll-up that is value-weighted, not a naive
average, so a big overrunning job cannot hide behind small tidy ones.

Two honest caveats are footnoted on screen rather than buried: EV tracks
*certified/billed* value (so measured-but-unbilled work reads low), and PV is the
elapsed fraction of the project window (a baseline S-curve would be truer). Both
are the correct fallbacks when there's no separate baseline programme.
"""

import tkinter as tk
from tkinter import ttk

import evm
import theme
from widgets import make_sortable


def _money(value):
    return '₹ {:,.0f}'.format(value or 0)


def _index(value):
    """A performance index to 2dp, or an em-dash when it's undefined."""
    return '—' if value is None else '{:.2f}'.format(value)


def _pct(value):
    return '—' if value is None else '{:.0f}%'.format(value)


def _verdict(row):
    """Plain-language health + the row-tint key, from the on_budget/schedule flags."""
    on_budget, on_schedule = row.get('on_budget'), row.get('on_schedule')
    if on_budget is None and on_schedule is None:
        return '—', 'muted'
    bad = []
    if on_budget is False:
        bad.append('over cost')
    if on_schedule is False:
        bad.append('behind')
    if not bad:
        return 'On track', 'good'
    return ' & '.join(bad).capitalize(), ('bad' if len(bad) == 2 else 'warn')


class EarnedValueTab(ttk.Frame):
    COLS = ('name', 'bac', 'pv', 'ev', 'ac', 'spi', 'cpi', 'pct', 'eac',
            'vac', 'health')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._build_ui()
        self.refresh()

    # -------------------------------------------------------------------- UI
    def _build_ui(self):
        pal = theme.palette()
        ttk.Label(self, text='Earned Value',
                  font=('TkDefaultFont', 14, 'bold')).pack(
            anchor='w', padx=12, pady=(12, 2))
        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var, foreground=pal['muted'],
                  wraplength=820, justify='left').pack(anchor='w', padx=12,
                                                       pady=(0, 6))

        bar = ttk.Frame(self); bar.pack(fill='x', padx=12, pady=2)
        ttk.Button(bar, text='Refresh', style='Accent.TButton',
                   command=self.refresh).pack(side='right')

        lf = ttk.Frame(self); lf.pack(fill='both', expand=True, padx=12, pady=4)
        self.tree = ttk.Treeview(lf, columns=self.COLS, show='headings',
                                 height=12)
        heads = {'name': 'Project', 'bac': 'BAC', 'pv': 'PV (planned)',
                 'ev': 'EV (earned)', 'ac': 'AC (actual)', 'spi': 'SPI',
                 'cpi': 'CPI', 'pct': '% complete', 'eac': 'EAC (forecast)',
                 'vac': 'VAC', 'health': 'Health'}
        widths = {'name': 200, 'bac': 110, 'pv': 110, 'ev': 110, 'ac': 110,
                  'spi': 60, 'cpi': 60, 'pct': 90, 'eac': 120, 'vac': 110,
                  'health': 130}
        aligns = {'name': 'w', 'health': 'w'}
        for c in self.COLS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor=aligns.get(c, 'e'))
        vsb = ttk.Scrollbar(lf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        for key in ('good', 'warn', 'bad', 'muted'):
            self.tree.tag_configure(key, background=theme.wash(key))
        self._resort = make_sortable(self.tree)     # click-to-sort headers

        # The two honest caveats, on screen rather than buried in a docstring.
        note = ('EV is billed/certified value — work measured but not yet '
                'billed reads low.   PV is the elapsed fraction of each '
                'project’s start→end window; a baseline programme would give a '
                'truer schedule.   SPI/CPI blank = no PV/AC yet.')
        ttk.Label(self, text=note, foreground=pal['muted'], wraplength=820,
                  justify='left', font=('TkDefaultFont', 9)).pack(
            anchor='w', padx=12, pady=(2, 12))

    # ----------------------------------------------------------------- data
    def refresh(self):
        conn = self.db_getter()
        try:
            rows, port = evm.portfolio_evm(conn)
        finally:
            conn.close()

        self.tree.delete(*self.tree.get_children())
        # Worst cost performance first — the jobs that need attention on top.
        rows = sorted(
            rows, key=lambda r: (r['cpi'] is None, r.get('cpi') or 0))
        for r in rows:
            verdict, tag = _verdict(r)
            self.tree.insert('', 'end', iid=str(r['id']), tags=(tag,), values=(
                r['name'], _money(r['bac']), _money(r['pv']), _money(r['ev']),
                _money(r['ac']), _index(r['spi']), _index(r['cpi']),
                _pct(r['percent_complete']), _money(r['eac']['default']),
                _money(r['vac']), verdict))

        self.summary_var.set(self._summary_text(port))
        self._resort()          # keep the chosen sort after a reload

    def _summary_text(self, port):
        if not port['projects']:
            return ('No projects with a contract value or budget yet — add one '
                    'to measure earned value against it.')
        worst = ''
        if port['worst_cpi']:
            worst = '   ·   worst CPI: {} ({:.2f})'.format(
                port['worst_cpi'], port['worst_cpi_value'])
        return (
            '{n} project(s) measured   ·   portfolio CPI {cpi}   ·   SPI {spi}'
            '   ·   {oc} over cost   ·   {bh} behind   ·   EV {ev} of BAC {bac}'
            '{worst}'.format(
                n=port['projects'], cpi=_index(port['cpi']),
                spi=_index(port['spi']), oc=port['over_cost'],
                bh=port['behind_schedule'], ev=_money(port['ev']),
                bac=_money(port['bac']), worst=worst))


def build_evm_tab(parent, db_getter):
    return EarnedValueTab(parent, db_getter)
