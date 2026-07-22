"""Weekly Review — the assembled review pack on screen (E4 surfacing).

Read-only. The whole pack is assembled by ``review_assemble.assemble`` (the DB
bridge onto the pure ``review_pack.build``), so this tab is only the rendering:
the plain-language narrative first, then the money at a glance, the advisories,
the risk and opportunity summaries, and the portfolio EVM. It is a **draft to
read, not a decision** — nothing here books, files or pays; that honesty is
stated on screen, not assumed.
"""

import tkinter as tk
from tkinter import ttk

import review_assemble
import theme
from widgets import ScrollFrame

_HEAD = ('TkDefaultFont', 11, 'bold')


def _money(value):
    try:
        return '₹ {:,.0f}'.format(round(float(value or 0)))
    except (TypeError, ValueError):
        return '₹ 0'


class ReviewPackTab(ttk.Frame):
    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._build_ui()
        self.refresh()

    # -------------------------------------------------------------------- UI
    def _build_ui(self):
        pal = theme.palette()
        top = ttk.Frame(self); top.pack(fill='x', padx=12, pady=(12, 2))
        ttk.Label(top, text='Weekly Review',
                  font=('TkDefaultFont', 14, 'bold')).pack(side='left')
        ttk.Button(top, text='Refresh', style='Accent.TButton',
                   command=self.refresh).pack(side='right')
        self.generated_var = tk.StringVar()
        ttk.Label(self, textvariable=self.generated_var, foreground=pal['muted'],
                  wraplength=820, justify='left').pack(anchor='w', padx=12,
                                                       pady=(0, 6))
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=4, pady=4)

    # ---------------------------------------------------------------- render
    def refresh(self):
        conn = self.db_getter()
        try:
            pack = review_assemble.assemble(conn)
        finally:
            conn.close()
        self._render(pack)

    def _section(self, title):
        pal = theme.palette()
        ttk.Frame(self.scroll.body, height=10).pack(fill='x')
        ttk.Label(self.scroll.body, text=title, font=_HEAD).pack(
            anchor='w', padx=8, pady=(4, 2))
        ttk.Frame(self.scroll.body, height=1).pack(fill='x', padx=8)

    def _line(self, text, muted=False, indent=0):
        pal = theme.palette()
        ttk.Label(self.scroll.body, text=text, wraplength=820, justify='left',
                  foreground=pal['muted'] if muted else pal['ink']).pack(
            anchor='w', padx=(8 + indent, 8), pady=1)

    def _render(self, pack):
        for w in self.scroll.body.winfo_children():
            w.destroy()
        self.generated_var.set(
            'Generated {}  ·  a draft to read, not a decision — nothing here '
            'books, files or pays.'.format(pack['generated']))

        # --- Narrative (the plain-language read, first)
        self._section('In plain words')
        for sentence in pack['narrative']['kpi'] or ['Nothing notable to report.']:
            self._line('• ' + sentence)
        risk_text = pack['narrative']['risk']
        if risk_text:
            for ln in risk_text.split('\n'):
                self._line(ln, muted=ln.startswith('•'), indent=8 if ln.startswith('•') else 0)

        # --- Money at a glance
        k = pack['kpis']
        self._section('Money at a glance')
        self._line('Cash in hand: {}    Receivable: {} (past 90 days: {})'.format(
            _money(k['cash']), _money(k['receivable']),
            _money(k['receivable_90plus'])))
        self._line('Payable: {}    This month — billed {}, collected {}'.format(
            _money(k['payable']), _money(k['billed_this_month']),
            _money(k['collected_this_month'])))
        if k['retention_due_now']:
            self._line('Retention due for release now: {}'.format(
                _money(k['retention_due_now'])))

        # --- Portfolio EVM (when there's a project to measure)
        e = pack.get('evm')
        if e:
            self._section('Earned value (portfolio)')
            cpi = '—' if e['cpi'] is None else '{:.2f}'.format(e['cpi'])
            spi = '—' if e['spi'] is None else '{:.2f}'.format(e['spi'])
            self._line('{n} project(s) measured    CPI {cpi}    SPI {spi}    '
                       '{oc} over cost    {bh} behind'.format(
                           n=e['projects'], cpi=cpi, spi=spi,
                           oc=e['over_cost'], bh=e['behind_schedule']))
            if e['worst_cpi']:
                self._line('Worst cost performance: {} (CPI {:.2f}).'.format(
                    e['worst_cpi'], e['worst_cpi_value']), muted=True)

        # --- Advisories
        adv = pack['advisories']
        c = adv['counts']
        self._section('Advisories')
        self._line('{} to act on · {} to watch · {} good · {} info'.format(
            c.get('act', 0), c.get('watch', 0), c.get('good', 0),
            c.get('info', 0)), muted=True)
        for card in adv['cards']:
            self._line('• [{}] {} — {}'.format(
                card['severity'].upper(), card['title'], card['detail']))
            self._line('Do: {}  ({})'.format(
                card['action'], card.get('where', '')), muted=True, indent=12)

        # --- Risks
        r = pack['risks']
        self._section('Risks')
        if not r['count']:
            self._line('No risks flagged on the numbers recorded so far.',
                       muted=True)
        else:
            self._line('{} flagged · {} need action now · total expected '
                       'exposure {}'.format(r['count'], r['needs_action'],
                                            _money(r['total_expected_exposure'])),
                       muted=True)
            for t in r['top']:
                self._line('• [{}] {} — {}'.format(
                    t['band'], t.get('title', 'risk'), t.get('basis', '')))

        # --- Opportunities
        o = pack.get('opportunities')
        if o:
            self._section('Opportunities')
            self._line('{} logged · {} worth pursuing now · total expected '
                       'upside {}'.format(o['count'], o['pursue_now'],
                                          _money(o['total_expected_value'])),
                       muted=True)
            for t in o['top']:
                self._line('• [{}] {} — expected upside {}'.format(
                    t.get('band', 'Low'), t.get('title', 'opportunity'),
                    _money(t.get('expected_value'))))

        ttk.Frame(self.scroll.body, height=16).pack(fill='x')


def build_review_tab(parent, db_getter):
    return ReviewPackTab(parent, db_getter)
