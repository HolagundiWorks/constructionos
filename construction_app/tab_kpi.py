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
import theme
from datetime import date
from tkinter import ttk

import ageing
import allocation
import bill_export
import planning
import procurement
import projectcost
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
                  wraplength=720, justify='left',
                  foreground=theme.palette()['muted']) \
            .pack(anchor='w', padx=8, pady=(0, 6))

        ttk.Label(self, textvariable=self.headline_var,
                  foreground=theme.palette()['error'],
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
        self.tree.tag_configure(ACT, background=theme.wash('bad'))
        self.tree.tag_configure(WATCH, background=theme.wash('warn'))
        self.tree.tag_configure(GOOD, background=theme.wash('good'))
        self.tree.tag_configure(NONE, foreground=theme.palette()['helper'])
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

        # --- project margin: a job running at a loss is the thing you most
        # want to know before the final account, not after.
        from project_rollup import project_cost_rollup
        rolls = []
        for r in conn.execute("SELECT id, name FROM projects "
                              "WHERE status != 'Cancelled'"):
            rolls.append((r['name'], project_cost_rollup(conn, r['id'])))
        if rolls:
            port = projectcost.portfolio(rolls)
            if port['at_a_loss']:
                out.append(('Projects running at a loss', str(port['at_a_loss']),
                            ACT, 'Worst is {} at {:,.2f}. Costs have overtaken '
                            'what is billed — before the final account, not '
                            'after.'.format(port['worst'], port['worst_margin'])))
            elif port['over_budget']:
                out.append(('Projects over budget', str(port['over_budget']),
                            WATCH, 'Cost has passed the budget on {}.'.format(
                                ', '.join(port['over_budget_names'][:3]))))
            if port['unattributed_total']:
                out.append(('Untagged cost on shared sites',
                            '{:,.2f}'.format(port['unattributed_total']), WATCH,
                            'Cost on sites with more than one project, not yet '
                            'tagged — tag it for a true per-project margin.'))

        # --- schedule contradictions: a dependency loop silently disables the
        # critical path, so it is worth surfacing on its own.
        from tab_timeline import project_schedule, worst_delay
        looped = sum(1 for r in conn.execute(
            "SELECT id FROM projects WHERE status != 'Closed'")
            if project_schedule(conn, r['id']).get('cycle'))
        if looped:
            out.append(('Programmes with a dependency loop', str(looped), ACT,
                        'Tasks that wait on each other in a circle — the '
                        'critical path cannot be computed until it is fixed.'))

        # --- programme delay
        wd = worst_delay(conn)
        if wd is None:
            out.append(('Programme delay', '—', NONE,
                        'No project has a frozen baseline yet '
                        '(Timeline > Baseline vs Actual).'))
        else:
            days = wd['net_delay_days']
            out.append(('Worst programme delay',
                        '{} day(s)'.format(days) if days else 'On time',
                        ACT if days > 0 else GOOD,
                        '{} — exposure {:,.2f} in liquidated damages on the '
                        'terms recorded. {} day(s) of it may support an '
                        'extension claim.'.format(
                            wd['project'], wd['ld']['exposure'],
                            wd['claimable_days'])
                        if days else 'Nothing running late against baseline.'))

        # --- plant
        from tab_plant import open_plant_alerts
        psum = open_plant_alerts(conn)
        if not psum['machines']:
            out.append(('Plant due for service', '—', NONE,
                        'No machines in the equipment master.'))
        else:
            need = psum['overdue'] + psum['due']
            out.append(('Plant due for service', str(need),
                        ACT if psum['overdue'] else
                        WATCH if psum['due'] else GOOD,
                        '{} overdue. A seizure mid-pour costs the machine, the '
                        'pour and the day.'.format(psum['overdue'])
                        if psum['overdue'] else
                        'Due soon — order the parts before it bites.'
                        if psum['due'] else 'Nothing overdue.'))
            if psum['fuel_flags']:
                out.append(('Fuel days above the usual rate',
                            str(psum['fuel_flags']), WATCH,
                            'About {:,.0f} litres more than those machines '
                            'normally use. Questions to ask, not '
                            'findings.'.format(psum['excess_litres'])))

        # --- statutory filings
        # Function-local import for the same reason as retention_lines above:
        # a tab module importing another tab module at module scope loops.
        from tab_compliance import open_obligations
        csum = open_obligations(conn)
        if not csum['total']:
            out.append(('Statutory filings due', '—', NONE,
                        'No compliance calendar built yet (Accounts > '
                        'Compliance).'))
        else:
            out.append(('Statutory filings overdue', str(csum['overdue']),
                        ACT if csum['overdue'] else GOOD,
                        'Late by up to {} days. Late fees and interest run '
                        'per day, and a late GSTR-1 holds up your customer\'s '
                        'input credit.'.format(csum['max_days_late'])
                        if csum['overdue'] else 'Nothing has slipped.'))
            nxt = csum['next']
            out.append(('  next filing due',
                        '{} on {}'.format(nxt['name'], nxt['due_date'])
                        if nxt else '—',
                        WATCH if csum['due_soon'] else NONE,
                        '{} due in the next 30 days.'.format(csum['due_soon'])
                        if nxt else 'Nothing due in the next 30 days.'))

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

        # --- productivity (crew / plant)
        import productivity_store
        prod = productivity_store.firm_summary(conn)
        uph = prod.get('units_per_hour')
        if uph is None:
            out.append(('Crew output per labour-hour', '—', NONE,
                        'Need work-done qty and attendance to compute.'))
        else:
            out.append(('Crew output per labour-hour', '{:,.3f}'.format(uph),
                        WATCH, 'Work-done quantity divided by muster hours.'))
        putil = prod.get('plant_util_pct')
        if putil is None:
            out.append(('Plant utilisation', '—', NONE,
                        'Need plant log hours to compute.'))
        else:
            out.append(('Plant utilisation', '{:.0f}%'.format(putil),
                        GOOD if putil >= 70 else WATCH if putil >= 40 else ACT,
                        'Hours run ÷ (hours run + downtime) from plant logs.'))

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
