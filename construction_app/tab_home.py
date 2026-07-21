"""Home — the morning screen: the whole business, read in a glance.

Four bands, top to bottom:

* **At a glance** — the money and counts a contractor checks first.
* **Insights & advisories** — the same figures, judged and ranked, each with a
  plain-language action and a **confidence** that says how much the data backs
  it (see ``advisory``). This is the "what should I do?" layer, computed on the
  device from the firm's own records — no internet, no model, nothing to leak.
* **Bottlenecks** — where work and money are sitting still, as a scoreboard.
* **Decisions pending** — everything waiting on a signature.

All of it is derived on demand by ``dashboard.collect`` from the tables the rest
of the app writes; nothing here is stored, so it can never drift from the tab it
summarises. The body is rebuilt on refresh because the advisory and bottleneck
lists change length with the data.
"""

from datetime import date
import tkinter as tk
from tkinter import ttk

import advisory
import dashboard
from widgets import ScrollFrame

_WRAP = 720                 # advisory detail wrap width (fits the stage)

_SEV_CAP = {'act': 'Act', 'watch': 'Watch', 'good': 'Good', 'info': 'Info'}
_SEV_ICON = {'act': '⚠', 'watch': '●', 'good': '✓', 'info': 'ℹ'}


def _inr(value):
    return '₹ {:,.0f}'.format(round(float(value or 0)))


class HomeTab(ttk.Frame):
    def __init__(self, parent, db_getter):
        super().__init__(parent, style='Stage.TFrame')
        self.db_getter = db_getter

        # --- fixed header (identity lives in the rail; Home leads with work)
        header = ttk.Frame(self, style='Stage.TFrame')
        header.pack(fill='x', padx=16, pady=(14, 2))
        left = ttk.Frame(header, style='Stage.TFrame'); left.pack(side='left')
        ttk.Label(left, text='Overview', style='H1.TLabel').pack(anchor='w')
        self.subtitle = tk.StringVar()
        ttk.Label(left, textvariable=self.subtitle,
                  style='Muted.TLabel').pack(anchor='w')
        ttk.Button(header, text='Refresh', command=self.refresh).pack(
            side='right', anchor='n')

        self.headline = ttk.Label(self, text='', style='Section.TLabel')
        self.headline.pack(anchor='w', padx=16, pady=(2, 0))

        # --- scrolling body (rebuilt each refresh)
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=(8, 0), pady=(6, 0))

        self.refresh()

    # ------------------------------------------------------------- rendering
    def refresh(self):
        today = date.today()
        self.subtitle.set('As on {} · computed on this device from your own '
                          'records'.format(today.isoformat()))

        conn = self.db_getter()
        try:
            snap = dashboard.collect(conn)
        finally:
            conn.close()
        cards = advisory.build(snap)
        self._set_headline(cards)

        body = self.scroll.body
        for w in body.winfo_children():
            w.destroy()

        self._render_kpis(body, snap)
        self._render_advisories(body, cards)
        self._render_bottlenecks(body, snap.get('bottlenecks', []))
        self._render_decisions(body, snap.get('decisions', []))
        # a little breathing room at the foot of the scroll
        ttk.Frame(body, style='Stage.TFrame', height=12).pack(fill='x')

    def _set_headline(self, cards):
        c = advisory.counts(cards)
        parts = []
        if c[advisory.ACT]:
            parts.append('{} need an action today'.format(c[advisory.ACT]))
        if c[advisory.WATCH]:
            parts.append('{} to watch'.format(c[advisory.WATCH]))
        if not parts:
            parts.append('Nothing needs an action today')
        self.headline.configure(
            text='  ·  '.join(parts),
            style='SevAct.TLabel' if c[advisory.ACT] else 'SevGood.TLabel')

    def _heading(self, parent, text, hint=''):
        row = ttk.Frame(parent, style='Stage.TFrame')
        row.pack(fill='x', padx=8, pady=(16, 6))
        ttk.Label(row, text=text, style='Section.TLabel').pack(side='left')
        if hint:
            ttk.Label(row, text=hint, style='SectionHint.TLabel').pack(
                side='left', padx=(10, 0))

    # ---- band 1: KPIs
    def _render_kpis(self, parent, s):
        self._heading(parent, 'At a glance')
        grid = ttk.Frame(parent, style='Stage.TFrame')
        grid.pack(fill='x', padx=4)

        cash = s.get('cash', 0)
        net = s.get('net_position', 0)
        r90 = s.get('receivable_90plus', 0)
        rdue = s.get('retention_due_now', 0)
        billed = s.get('billed_month', 0)
        collected = s.get('collected_month', 0)
        ratio = ('{:.0f}% of what was billed'.format(collected / billed * 100)
                 if billed else 'this month')

        tiles = [
            ('Cash in Hand', _inr(cash), '\U0001F4B5',
             'StatGood.TLabel' if cash >= 0 else 'StatWarn.TLabel', ''),
            ('To Collect', _inr(s.get('receivable', 0)), '\U0001F4E5',
             'StatInfo.TLabel',
             '{} past 90 days'.format(_inr(r90)) if r90 > 0 else 'none past 90 days'),
            ('To Pay', _inr(s.get('payable', 0)), '\U0001F4E4',
             'StatWarn.TLabel', 'owed to vendors'),
            ('Net Position', _inr(net), '\U0001F4CA',
             'StatGood.TLabel' if net >= 0 else 'StatWarn.TLabel',
             'to collect − to pay'),
            ('Active Sites', str(s.get('sites', 0)), '\U0001F3D7',
             'StatValue.TLabel', 'running now'),
            ('Billed This Month', _inr(billed), '\U0001F9FE',
             'StatInfo.TLabel', 'approved + paid'),
            ('Collected This Month', _inr(collected), '✅',
             'StatGood.TLabel', ratio),
            ('Retention Held', _inr(s.get('retention_outstanding', 0)),
             '\U0001F512', 'StatInfo.TLabel',
             '{} due now'.format(_inr(rdue)) if rdue > 0 else 'held till DLP'),
        ]
        cols = 4
        for i in range(cols):
            grid.columnconfigure(i, weight=1, uniform='kpi')
        for idx, (label, value, icon, valstyle, meta) in enumerate(tiles):
            r, c = divmod(idx, cols)
            self._kpi_card(grid, r, c, icon, label, value, valstyle, meta)

    def _kpi_card(self, grid, r, c, icon, label, value, valstyle, meta):
        card = ttk.Frame(grid, style='StatCard.TFrame', padding=(14, 12))
        card.grid(row=r, column=c, padx=6, pady=6, sticky='nsew')
        head = ttk.Frame(card, style='Card.TFrame'); head.pack(fill='x')
        ttk.Label(head, text=icon, style='StatIcon.TLabel').pack(side='left')
        ttk.Label(head, text=label, style='StatLabel.TLabel').pack(
            side='left', padx=(8, 0))
        ttk.Label(card, text=value, style=valstyle).pack(anchor='w', pady=(8, 0))
        if meta:
            ttk.Label(card, text=meta, style='StatMeta.TLabel').pack(anchor='w')

    # ---- band 2: advisories
    def _render_advisories(self, parent, cards):
        self._heading(parent, 'Insights & advisories',
                      'ranked by urgency, each with how confident the data is')
        holder = ttk.Frame(parent, style='Stage.TFrame')
        holder.pack(fill='x', padx=8)
        for c in cards:
            self._advisory_card(holder, c)

    def _advisory_card(self, parent, c):
        cap = _SEV_CAP.get(c['severity'], 'Info')
        card = ttk.Frame(parent, style='StatCard.TFrame')
        card.pack(fill='x', pady=4)
        rule = ttk.Frame(card, style='Rule%s.TFrame' % cap, width=4)
        rule.pack(side='left', fill='y')
        rule.pack_propagate(False)
        inner = ttk.Frame(card, style='Card.TFrame')
        inner.pack(side='left', fill='both', expand=True, padx=12, pady=10)

        top = ttk.Frame(inner, style='Card.TFrame'); top.pack(fill='x')
        ttk.Label(top, text=_SEV_ICON.get(c['severity'], 'ℹ'),
                  style='Sev%s.TLabel' % cap).pack(side='left')
        ttk.Label(top, text=c['title'], style='CardTitle.TLabel').pack(
            side='left', padx=(6, 0))
        ttk.Label(top, text=cap.upper(), style='Sev%sMicro.TLabel' % cap).pack(
            side='right')

        ttk.Label(inner, text=c['detail'], style='CardBody.TLabel',
                  wraplength=_WRAP, justify='left').pack(anchor='w', pady=(4, 0))
        if c.get('action'):
            ttk.Label(inner, text='Do:  ' + c['action'], style='CardMeta.TLabel',
                      wraplength=_WRAP, justify='left').pack(anchor='w', pady=(4, 0))

        foot = ttk.Frame(inner, style='Card.TFrame'); foot.pack(fill='x', pady=(6, 0))
        ttk.Label(foot, text='{} confidence  ·  {}'.format(
            c['confidence'], c['basis']), style='CardMeta.TLabel').pack(side='left')
        if c.get('where'):
            ttk.Label(foot, text='→ ' + c['where'],
                      style='CardLink.TLabel').pack(side='right')

    # ---- band 3: bottlenecks
    def _render_bottlenecks(self, parent, items):
        self._heading(parent, 'Bottlenecks — where work is stuck',
                      'queues and stuck money, worst first')
        grid = ttk.Frame(parent, style='Stage.TFrame')
        grid.pack(fill='x', padx=4)
        if not items:
            card = ttk.Frame(grid, style='StatCard.TFrame', padding=(14, 12))
            card.pack(fill='x', padx=6, pady=6)
            ttk.Label(card, text='✓  Nothing is stuck', style='SevGood.TLabel') \
                .pack(anchor='w')
            ttk.Label(card, text='No open queues or aged money on the numbers '
                      'recorded so far.', style='CardBody.TLabel',
                      wraplength=_WRAP, justify='left').pack(anchor='w', pady=(2, 0))
            return
        cols = 3
        for i in range(cols):
            grid.columnconfigure(i, weight=1, uniform='bn')
        for idx, b in enumerate(items):
            r, c = divmod(idx, cols)
            self._bottleneck_chip(grid, r, c, b)

    def _bottleneck_chip(self, grid, r, c, b):
        cap = _SEV_CAP.get(b['severity'], 'Watch')
        chip = ttk.Frame(grid, style='StatCard.TFrame', padding=(12, 10))
        chip.grid(row=r, column=c, padx=6, pady=6, sticky='nsew')
        ttk.Label(chip, text=b['metric'], style='Sev%s.TLabel' % cap).pack(
            anchor='w')
        ttk.Label(chip, text=b['label'], style='CardTitle.TLabel',
                  wraplength=220, justify='left').pack(anchor='w', pady=(3, 0))
        if b.get('detail'):
            ttk.Label(chip, text=b['detail'], style='CardMeta.TLabel',
                      wraplength=220, justify='left').pack(anchor='w')
        ttk.Label(chip, text='→ ' + b['where'], style='CardLink.TLabel').pack(
            anchor='w', pady=(4, 0))

    # ---- band 4: decisions
    def _render_decisions(self, parent, decisions):
        total = sum(d['count'] for d in decisions)
        self._heading(parent, 'Decisions pending',
                      '{} waiting on a signature'.format(total) if total
                      else 'nothing waiting')
        card = ttk.Frame(parent, style='StatCard.TFrame', padding=(16, 12))
        card.pack(fill='x', padx=8)
        if not decisions:
            ttk.Label(card, text='✓  The approvals desk is clear',
                      style='SevGood.TLabel').pack(anchor='w')
            return
        for d in decisions:
            row = ttk.Frame(card, style='Card.TFrame'); row.pack(fill='x', pady=5)
            left = ttk.Frame(row, style='Card.TFrame'); left.pack(side='left')
            ttk.Label(left, text=d['label'], style='CardTitle.TLabel').pack(
                anchor='w')
            ttk.Label(left, text='→ ' + d['where'], style='CardLink.TLabel').pack(
                anchor='w')
            right = ttk.Frame(row, style='Card.TFrame'); right.pack(side='right')
            ttk.Label(right, text='{} item(s)'.format(d['count']),
                      style='CardBody.TLabel').pack(anchor='e')
            if d.get('value'):
                ttk.Label(right, text=_inr(d['value']),
                          style='CardTitle.TLabel').pack(anchor='e')


def build_home_tab(parent, db_getter):
    return HomeTab(parent, db_getter)
