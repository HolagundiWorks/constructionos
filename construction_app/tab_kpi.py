"""KPI dashboard — the whole business on one screen (Phase 8, Wave 3).

Every number here already exists somewhere in the app. The value of collecting
them is that a contractor will not open eight tabs each morning, and the
figures that matter most are the ones nobody goes looking for: money agreed but
never billed, invoices with no goods receipt behind them, retention long past
its release date.

Each KPI carries a **verdict** — good, watch, or act — so the screen can be
read in five seconds rather than interpreted. Where there is no data the KPI
says so instead of showing a confident zero, because "0%" and "nothing recorded
yet" mean very different things.
"""

import tkinter as tk
from datetime import date
from tkinter import ttk

import ageing
import allocation
import bill_export
import planning
import procurement
import quality
import report_open
import retention
import variation
from tab_allocate import party_documents

GOOD, WATCH, ACT, NONE = 'good', 'watch', 'act', 'none'


class KPIDashboard(ttk.Frame):
    COLUMNS = ('kpi', 'value', 'verdict', 'meaning')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self.headline_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Key numbers',
                  font=('TkDefaultFont', 13, 'bold')) \
            .pack(anchor='w', padx=8, pady=(10, 2))
        ttk.Label(self, text='Everything worth checking daily, in one place. '
                             'Red lines are money or risk that needs an action '
                             'today.',
                  wraplength=720, justify='left', foreground='#555') \
            .pack(anchor='w', padx=8, pady=(0, 6))

        ttk.Label(self, textvariable=self.headline_var, foreground='#a4343a',
                  font=('TkDefaultFont', 12, 'bold'), wraplength=720,
                  justify='left').pack(anchor='w', padx=8, pady=(0, 6))

        heads = {'kpi': 'Indicator', 'value': 'Now', 'verdict': '',
                 'meaning': 'What it means'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=16)
        self.tree.heading('kpi', text=heads['kpi'])
        self.tree.heading('value', text=heads['value'])
        self.tree.heading('verdict', text=heads['verdict'])
        self.tree.heading('meaning', text=heads['meaning'])
        self.tree.column('kpi', width=220, anchor='w')
        self.tree.column('value', width=130, anchor='e')
        self.tree.column('verdict', width=60, anchor='center')
        self.tree.column('meaning', width=340, anchor='w')
        self.tree.tag_configure(ACT, background='#ffe3e3')
        self.tree.tag_configure(WATCH, background='#fff4e5')
        self.tree.tag_configure(GOOD, background='#e4f1e8')
        self.tree.tag_configure(NONE, foreground='#888')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 10))
        ttk.Button(btns, text='Refresh', command=self.refresh).pack(side='left')
        ttk.Button(btns, text='Print / Export', command=self.export).pack(side='left', padx=6)

    # ------------------------------------------------------------ gathering
    def _collect(self, conn):
        """Every KPI as (name, value_text, verdict, meaning)."""
        out = []
        today = date.today().isoformat()

        # --- unbilled variations: agreed work nobody has asked to be paid for
        vars_all = conn.execute('SELECT * FROM variations').fetchall()
        vsum = variation.summarise(vars_all)
        unbilled = vsum['approved_unbilled']
        out.append(('Variations approved, not billed', '{:,.2f}'.format(unbilled),
                    ACT if unbilled > 0 else GOOD,
                    'Work the client agreed to pay for that has not been billed.'
                    if unbilled else 'Nothing agreed is waiting to be billed.'))

        # --- over-invoiced purchases: paying for goods never received
        pos = conn.execute('SELECT id, total_amount FROM purchase_orders').fetchall()
        recv, inv = {}, {}
        for r in conn.execute(
                'SELECT g.purchase_order_id AS pid, SUM(gi.amount) AS a '
                'FROM grn_items gi JOIN goods_receipts g ON g.id = gi.grn_id '
                "WHERE g.status = 'Posted' GROUP BY g.purchase_order_id"):
            recv[r['pid']] = r['a'] or 0
        for r in conn.execute(
                'SELECT purchase_order_id AS pid, SUM(subtotal) AS a '
                'FROM vendor_invoices WHERE purchase_order_id IS NOT NULL '
                'GROUP BY purchase_order_id'):
            inv[r['pid']] = r['a'] or 0
        matches = [procurement.three_way(p['total_amount'], recv.get(p['id'], 0),
                                         inv.get(p['id'], 0), 100) for p in pos]
        psum = procurement.summarise(matches)
        out.append(('Invoiced without a goods receipt',
                    '{:,.2f}'.format(psum['at_risk']),
                    ACT if psum['at_risk'] > 0 else GOOD,
                    'Vendor value billed with no receipt behind it — check '
                    'before paying.' if psum['at_risk'] else
                    'Every vendor invoice is backed by a receipt.'))

        # --- spend under PO: how much buying is controlled at all
        po_total = sum(float(p['total_amount'] or 0) for p in pos)
        all_purchases = conn.execute(
            'SELECT COALESCE(SUM(subtotal), 0) FROM vendor_invoices').fetchone()[0] or 0
        under_po = conn.execute(
            'SELECT COALESCE(SUM(subtotal), 0) FROM vendor_invoices '
            'WHERE purchase_order_id IS NOT NULL').fetchone()[0] or 0
        if all_purchases:
            pct = round(under_po / all_purchases * 100.0, 1)
            out.append(('Purchases made under a PO', '{:.1f}%'.format(pct),
                        GOOD if pct >= 80 else WATCH if pct >= 50 else ACT,
                        'Buying without a PO is the classic leak; aim high.'))
        else:
            out.append(('Purchases made under a PO', '—', NONE,
                        'No vendor invoices recorded yet.'))

        # --- receivables and the oldest slab
        docs, allocs, settled = [], [], 0.0
        for c in conn.execute('SELECT id FROM clients'):
            docs += party_documents(conn, 'Client', c['id'])
        for r in conn.execute(
                'SELECT pa.doc_type, pa.doc_id, pa.amount FROM payment_allocations pa '
                "JOIN payments p ON p.id = pa.payment_id WHERE p.party_type = 'Client'"):
            allocs.append({'doc_type': r['doc_type'], 'doc_id': r['doc_id'],
                           'amount': r['amount']})
        settled = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payments WHERE direction='Receipt' "
            "AND party_type='Client'").fetchone()[0] or 0
        used = sum(allocation.money(a['amount']) for a in allocs)
        unalloc = max(allocation.money(settled) - allocation.money(used), 0.0)
        aged = ageing.age_open_items(
            allocation.open_items_for_ageing(docs, allocs, unalloc))
        out.append(('Receivables outstanding', '{:,.2f}'.format(aged['total']),
                    WATCH if aged['total'] > 0 else GOOD,
                    'Money owed to you across all clients.'))
        old = aged['90+']
        out.append(('  of which over 90 days', '{:,.2f}'.format(old),
                    ACT if old > 0 else GOOD,
                    'The hardest money to collect. Chase before it ages further.'
                    if old else 'Nothing has aged past 90 days.'))

        # --- retention due for release
        from tab_retention import retention_lines
        rlines = retention_lines(conn, 12)
        rsum = retention.summarise(rlines)
        out.append(('Retention due for release', '{:,.2f}'.format(rsum['due_now']),
                    ACT if rsum['due_now'] > 0 else GOOD,
                    'Past its defect-liability date and still held{}.'.format(
                        ' — oldest by {} days'.format(rsum['max_overdue_days'])
                        if rsum['max_overdue_days'] else '')
                    if rsum['due_now'] else 'Nothing is overdue for release.'))
        out.append(('Retention still held (total)',
                    '{:,.2f}'.format(rsum['outstanding']), NONE,
                    'Earned money held by others until the DLP expires.'))

        # --- plan reliability
        commits = conn.execute('SELECT * FROM commitments').fetchall()
        weeks = {}
        for r in commits:
            weeks.setdefault(r['week_start'] or '?', []).append(r)
        trend = planning.ppc_trend(weeks)
        if trend['average'] is None:
            out.append(('Plan reliability (PPC)', '—', NONE,
                        'No weekly commitments recorded yet.'))
        else:
            avg = trend['average']
            out.append(('Plan reliability (PPC)', '{:.0f}%'.format(avg),
                        GOOD if avg >= 80 else WATCH if avg >= 60 else ACT,
                        'Share of weekly promises actually finished.'))
            worst = planning.reasons_for_misses(commits)
            if worst:
                out.append(('  biggest cause of misses', worst[0][0], WATCH,
                            'Fix this and reliability moves more than any '
                            'amount of chasing.'))

        # --- quality
        insp = conn.execute('SELECT * FROM inspections').fetchall()
        ftp = quality.first_time_pass_rate(insp)
        if ftp is None:
            out.append(('Inspections passed first time', '—', NONE,
                        'No inspections recorded yet.'))
        else:
            out.append(('Inspections passed first time', '{:.0f}%'.format(ftp),
                        GOOD if ftp >= 90 else WATCH if ftp >= 75 else ACT,
                        'Rework is the most expensive way to build.'))
        ncrs = conn.execute('SELECT * FROM ncrs').fetchall()
        nsum = quality.ncr_summary(ncrs)
        out.append(('Open non-conformances', str(nsum['open']),
                    ACT if nsum['oldest_open_days'] > 30 else
                    WATCH if nsum['open'] else GOOD,
                    'Oldest open {} days — a logged defect left open is worse '
                    'than one never found.'.format(nsum['oldest_open_days'])
                    if nsum['open'] else 'Nothing outstanding.'))
        return out

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            rows = self._collect(conn)
        finally:
            conn.close()
        self._rows = []
        marks = {GOOD: '✓', WATCH: '!', ACT: '✗', NONE: '·'}
        actions = 0
        for name, value, verdict, meaning in rows:
            if verdict == ACT:
                actions += 1
            values = (name, value, marks.get(verdict, ''), meaning)
            self._rows.append((name, value, meaning))
            self.tree.insert('', 'end', values=values, tags=(verdict,))
        self.headline_var.set(
            '{} indicator(s) need an action today.'.format(actions) if actions
            else 'Nothing needs action today.')

    def export(self):
        html = bill_export.build_statement_html(
            'Key numbers', [self.headline_var.get(),
                            'As at {}'.format(date.today().isoformat())],
            ['Indicator', 'Now', 'What it means'], self._rows,
            summary=self.headline_var.get())
        report_open.save_and_open_html(html, 'kpi_dashboard.html')


def build_kpi_tab(parent, db_getter):
    return KPIDashboard(parent, db_getter)
