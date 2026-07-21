"""Insight — the honest numbers a contractor checks (Phase 6).

- **Site Profitability**: per site, revenue (Approved/Paid bills + RA bills on
  that site's contracts) vs cost (material issued from the ledger + labour cash
  paid + equipment hire), giving profit and margin %.
- **Receivables** / **Payables**: who still owes us, and whom we still owe,
  per client / vendor.

All figures are computed on demand and printable. These are approximations, not
a reconciled ledger (e.g. receipts aren't linked to specific bills — see
docs/ROADMAP.md Phase 6 for ageing, which needs that link).
"""

import tkinter as tk
from tkinter import ttk
import theme

import ageing
import allocation
import analytics
import money as m
import bill_export
from tab_money import _save_and_open_html


def _sum_map(conn, sql):
    """Run a `SELECT key, value` grouped query -> {key: value}."""
    return {r[0]: (r[1] or 0) for r in conn.execute(sql)}


class SiteProfitability(ttk.Frame):
    COLUMNS = ('site', 'revenue', 'material', 'labour', 'hire', 'cost',
               'profit', 'margin')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Site Profitability',
                  font=('TkDefaultFont', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='right', padx=2)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='right', padx=2)

        heads = {'site': 'Site', 'revenue': 'Revenue', 'material': 'Material',
                 'labour': 'Labour', 'hire': 'Equip Hire', 'cost': 'Total Cost',
                 'profit': 'Profit', 'margin': 'Margin %'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=130 if col == 'site' else 100, anchor='w')
        self.tree.tag_configure('loss', background=theme.wash('bad'))
        self.tree.tag_configure('profit', background=theme.wash('good'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            rev_bills = _sum_map(conn,
                "SELECT c.site_id, SUM(b.net_payable) FROM bills b "
                "JOIN contracts c ON c.id = b.contract_id "
                "WHERE b.status IN ('Approved','Paid') GROUP BY c.site_id")
            rev_ra = _sum_map(conn,
                "SELECT c.site_id, SUM(r.net_payable) FROM ra_bills r "
                "JOIN contracts c ON c.id = r.contract_id "
                "WHERE r.status IN ('Approved','Paid') GROUP BY c.site_id")
            material = _sum_map(conn,
                "SELECT site_id, SUM(qty * rate) FROM material_ledger "
                "WHERE txn_type = 'OUT' GROUP BY site_id")
            labour = _sum_map(conn,
                "SELECT site_id, SUM(amount) FROM payments "
                "WHERE direction = 'Payment' AND party_type = 'Labour' GROUP BY site_id")
            hire = _sum_map(conn,
                "SELECT site_id, SUM(total_amount) FROM equipment_hire GROUP BY site_id")
            sites = conn.execute('SELECT id, name FROM sites ORDER BY name').fetchall()
        finally:
            conn.close()

        self._rows = []
        for s in sites:
            sid = s['id']
            revenue = (rev_bills.get(sid, 0) or 0) + (rev_ra.get(sid, 0) or 0)
            mat = material.get(sid, 0) or 0
            lab = labour.get(sid, 0) or 0
            hr = hire.get(sid, 0) or 0
            cost = mat + lab + hr
            if revenue == 0 and cost == 0:
                continue
            pm = m.profit_margin(revenue, cost)
            margin = '-' if pm['margin_pct'] is None else '{:.1f}%'.format(pm['margin_pct'])
            row = (s['name'], '{:.2f}'.format(pm['revenue']), '{:.2f}'.format(mat),
                   '{:.2f}'.format(lab), '{:.2f}'.format(hr),
                   '{:.2f}'.format(pm['cost']), '{:.2f}'.format(pm['profit']), margin)
            tag = 'loss' if pm['profit'] < 0 else 'profit'
            self.tree.insert('', 'end', values=row, tags=(tag,))
            self._rows.append(row)

    def export(self):
        html = bill_export.build_statement_html(
            'Site Profitability', ['As on today'],
            ['Site', 'Revenue', 'Material', 'Labour', 'Equip Hire', 'Total Cost',
             'Profit', 'Margin %'], self._rows)
        _save_and_open_html(html, 'site_profitability.html')


class Outstanding(ttk.Frame):
    """Receivables (clients) or payables (vendors)."""

    def __init__(self, parent, db_getter, mode):
        super().__init__(parent)
        self.db_getter = db_getter
        self.mode = mode          # 'Receivable' or 'Payable'
        self._rows = []

        label = 'Receivables (clients owe us)' if mode == 'Receivable' \
            else 'Payables (we owe vendors)'
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text=label, font=('TkDefaultFont', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='right', padx=2)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='right', padx=2)

        billed_h = 'Billed' if mode == 'Receivable' else 'Invoiced'
        settled_h = 'Received' if mode == 'Receivable' else 'Paid'
        self._headers = ['Party', billed_h, settled_h, 'Outstanding']
        self.tree = ttk.Treeview(self, columns=('party', 'billed', 'settled', 'out'),
                                 show='headings')
        for col, h in zip(('party', 'billed', 'settled', 'out'), self._headers):
            self.tree.heading(col, text=h)
            self.tree.column(col, width=180 if col == 'party' else 120, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=4)
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            if self.mode == 'Receivable':
                parties = conn.execute('SELECT id, name FROM clients ORDER BY name').fetchall()
                billed = _sum_map(conn,
                    "SELECT c.client_id, SUM(b.net_payable) FROM bills b "
                    "JOIN contracts c ON c.id = b.contract_id "
                    "WHERE b.status IN ('Approved','Paid') GROUP BY c.client_id")
                billed_ra = _sum_map(conn,
                    "SELECT c.client_id, SUM(r.net_payable) FROM ra_bills r "
                    "JOIN contracts c ON c.id = r.contract_id "
                    "WHERE r.status IN ('Approved','Paid') GROUP BY c.client_id")
                for k, v in billed_ra.items():
                    billed[k] = (billed.get(k, 0) or 0) + (v or 0)
                settled = _sum_map(conn,
                    "SELECT party_id, SUM(amount) FROM payments "
                    "WHERE direction = 'Receipt' AND party_type = 'Client' "
                    "AND party_id IS NOT NULL GROUP BY party_id")
            else:
                parties = conn.execute('SELECT id, name FROM vendors ORDER BY name').fetchall()
                billed = _sum_map(conn,
                    "SELECT vendor_id, SUM(net_payable) FROM vendor_invoices "
                    "GROUP BY vendor_id")
                settled = _sum_map(conn,
                    "SELECT party_id, SUM(amount) FROM payments "
                    "WHERE direction = 'Payment' AND party_type = 'Vendor' "
                    "AND party_id IS NOT NULL GROUP BY party_id")
        finally:
            conn.close()

        self._rows = []
        total_out = 0.0
        for p in parties:
            b = billed.get(p['id'], 0) or 0
            s = settled.get(p['id'], 0) or 0
            if b == 0 and s == 0:
                continue
            out = m.party_outstanding(b, s)
            total_out += out
            row = (p['name'], '{:.2f}'.format(b), '{:.2f}'.format(s), '{:.2f}'.format(out))
            self.tree.insert('', 'end', values=row)
            self._rows.append(row)
        noun = 'receivable' if self.mode == 'Receivable' else 'payable'
        self.summary_var.set('Total {}: {:.2f}'.format(noun, round(total_out, 2)))

    def export(self):
        title = 'Receivables' if self.mode == 'Receivable' else 'Payables'
        html = bill_export.build_statement_html(
            title, ['As on today'], self._headers, self._rows,
            summary=self.summary_var.get())
        _save_and_open_html(html, title.lower() + '.html')


class Ageing(ttk.Frame):
    """Age each party's outstanding into 0-30 / 30-60 / 60-90 / 90+ slabs.

    Where a receipt has been **allocated** to specific bills (Money > Payments >
    Allocate to Bills), that allocation is used — this is reconciled ageing.
    Anything still unallocated falls back to settling oldest-first, so a
    part-migrated ledger keeps adding up (`allocation.open_items_for_ageing`).

    The document set comes from ``tab_allocate.party_documents`` so this view
    and the allocation dialog can never disagree about what a party owes:
    client bills + RA bills + tax invoices, vendor invoices at net payable.
    """

    COLUMNS = ('party', '0-30', '30-60', '60-90', '90+', 'total')

    def __init__(self, parent, db_getter, mode):
        super().__init__(parent)
        self.db_getter = db_getter
        self.mode = mode          # 'Receivable' or 'Payable'
        self._rows = []

        label = ('Receivables ageing (clients)' if mode == 'Receivable'
                 else 'Payables ageing (vendors)')
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text=label, font=('TkDefaultFont', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='right', padx=2)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='right', padx=2)

        heads = {'party': 'Party', '0-30': '0-30 d', '30-60': '30-60 d',
                 '60-90': '60-90 d', '90+': '90+ d', 'total': 'Total'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=180 if col == 'party' else 95, anchor='w')
        self.tree.tag_configure('overdue', background=theme.wash('bad'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=4)
        self.refresh()

    def _party_data(self, conn):
        """(parties, settled-by-party) for this side of the ledger."""
        if self.mode == 'Receivable':
            parties = conn.execute(
                'SELECT id, name FROM clients ORDER BY name').fetchall()
            settled = _sum_map(conn,
                "SELECT party_id, SUM(amount) FROM payments "
                "WHERE direction = 'Receipt' AND party_type = 'Client' "
                "AND party_id IS NOT NULL GROUP BY party_id")
        else:
            parties = conn.execute(
                'SELECT id, name FROM vendors ORDER BY name').fetchall()
            settled = _sum_map(conn,
                "SELECT party_id, SUM(amount) FROM payments "
                "WHERE direction = 'Payment' AND party_type = 'Vendor' "
                "AND party_id IS NOT NULL GROUP BY party_id")
        return parties, settled

    def refresh(self):
        from tab_allocate import party_documents
        party_type = 'Client' if self.mode == 'Receivable' else 'Vendor'
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            parties, settled = self._party_data(conn)
            docs_by_party, allocs_by_party = {}, {}
            for p in parties:
                docs_by_party[p['id']] = party_documents(conn, party_type, p['id'])
            for r in conn.execute(
                    'SELECT p.party_id AS pid, pa.doc_type, pa.doc_id, pa.amount '
                    'FROM payment_allocations pa '
                    'JOIN payments p ON p.id = pa.payment_id '
                    'WHERE p.party_type = ? AND p.party_id IS NOT NULL',
                    (party_type,)):
                allocs_by_party.setdefault(r['pid'], []).append(
                    {'doc_type': r['doc_type'], 'doc_id': r['doc_id'],
                     'amount': r['amount']})
        finally:
            conn.close()

        self._rows = []
        totals = {b: 0.0 for b in ageing.BUCKETS}
        for p in parties:
            docs = docs_by_party.get(p['id']) or []
            if not docs:
                continue
            allocs = allocs_by_party.get(p['id'], [])
            # Receipts not tied to any bill still reduce the balance, oldest
            # first — otherwise allocating one receipt would make the rest of
            # a party's payments vanish from the ageing.
            allocated = sum(allocation.money(a['amount']) for a in allocs)
            unallocated = max(allocation.money(settled.get(p['id'], 0) or 0)
                              - allocation.money(allocated), 0.0)
            aged = ageing.age_open_items(
                allocation.open_items_for_ageing(docs, allocs, unallocated))
            if aged['total'] == 0:
                continue
            for b in ageing.BUCKETS:
                totals[b] += aged[b]
            row = (p['name'],) + tuple('{:.2f}'.format(aged[b])
                                       for b in ageing.BUCKETS) + \
                  ('{:.2f}'.format(aged['total']),)
            tag = 'overdue' if (aged['60-90'] + aged['90+']) > 0 else ''
            self.tree.insert('', 'end', values=row, tags=(tag,))
            self._rows.append(row)
        grand = round(sum(totals.values()), 2)
        self.summary_var.set(
            'Total {:.2f}  |  0-30: {:.2f}   30-60: {:.2f}   60-90: {:.2f}   '
            '90+: {:.2f}'.format(grand, totals['0-30'], totals['30-60'],
                                 totals['60-90'], totals['90+']))

    def export(self):
        title = ('Receivables Ageing' if self.mode == 'Receivable'
                 else 'Payables Ageing')
        html = bill_export.build_statement_html(
            title, ['As on today (FIFO-settled, aged by bill date)'],
            ['Party', '0-30 d', '30-60 d', '60-90 d', '90+ d', 'Total'],
            self._rows, summary=self.summary_var.get())
        _save_and_open_html(html, title.lower().replace(' ', '_') + '.html')


class ContractProgress(ttk.Frame):
    """Physical progress per contract: measured value vs BOQ value.

    BOQ value = SUM(boq_items.amount); measured value = SUM(measurement.quantity
    x its boq_item.rate). Progress % = measured / BOQ (uncapped, so a deviation
    over 100% is visible). Contracts with no BOQ are skipped.
    """

    COLUMNS = ('contract', 'site', 'boq', 'measured', 'progress', 'balance')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Contract / BOQ Progress',
                  font=('TkDefaultFont', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='right', padx=2)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='right', padx=2)

        heads = {'contract': 'Contract', 'site': 'Site', 'boq': 'BOQ Value',
                 'measured': 'Measured', 'progress': 'Progress %',
                 'balance': 'Balance'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=140 if col in ('contract', 'site') else 100,
                             anchor='w')
        self.tree.tag_configure('over', background=theme.wash('warn'))
        self.tree.tag_configure('done', background=theme.wash('good'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            boq = _sum_map(conn,
                "SELECT contract_id, SUM(amount) FROM boq_items GROUP BY contract_id")
            measured = _sum_map(conn,
                "SELECT b.contract_id, SUM(msr.quantity * b.rate) "
                "FROM measurements msr JOIN boq_items b ON b.id = msr.boq_item_id "
                "GROUP BY b.contract_id")
            contracts = conn.execute(
                "SELECT c.id, c.contract_no, s.name AS site FROM contracts c "
                "LEFT JOIN sites s ON s.id = c.site_id ORDER BY c.contract_no").fetchall()
        finally:
            conn.close()

        self._rows = []
        for c in contracts:
            boq_val = boq.get(c['id'], 0) or 0
            if boq_val == 0:
                continue
            pr = analytics.contract_progress(boq_val, measured.get(c['id'], 0) or 0)
            ppct = '-' if pr['progress_pct'] is None else \
                '{:.1f}%'.format(pr['progress_pct'])
            row = (c['contract_no'] or '-', c['site'] or '-',
                   '{:.2f}'.format(pr['boq_value']),
                   '{:.2f}'.format(pr['measured_value']), ppct,
                   '{:.2f}'.format(pr['balance_value']))
            tag = ''
            if pr['progress_pct'] is not None:
                tag = 'over' if pr['progress_pct'] > 100 else \
                    ('done' if pr['progress_pct'] >= 99.5 else '')
            self.tree.insert('', 'end', values=row, tags=(tag,))
            self._rows.append(row)

    def export(self):
        html = bill_export.build_statement_html(
            'Contract / BOQ Progress', ['As on today'],
            ['Contract', 'Site', 'BOQ Value', 'Measured', 'Progress %',
             'Balance'], self._rows)
        _save_and_open_html(html, 'contract_progress.html')


class MaterialBudget(ttk.Frame):
    """Money view of material consumption for a site: theoretical requirement
    (norm x work done) valued at the material's rate, vs actual issued value."""

    COLUMNS = ('material', 'budget', 'actual', 'variance', 'overspend')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._site_map = {}
        self._rows = []
        self.site_var = tk.StringVar()

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Material Budget vs Actual (value)',
                  font=('TkDefaultFont', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='right', padx=2)
        ttk.Button(top, text='Refresh', command=self.reload).pack(side='right', padx=2)

        sel = ttk.Frame(self); sel.pack(fill='x', padx=8, pady=(0, 4))
        ttk.Label(sel, text='Site').pack(side='left')
        self.site_combo = ttk.Combobox(sel, textvariable=self.site_var,
                                       width=24, state='readonly')
        self.site_combo.pack(side='left', padx=6)
        self.site_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())

        heads = {'material': 'Material', 'budget': 'Budget Value',
                 'actual': 'Actual Value', 'variance': 'Variance',
                 'overspend': 'Overspend %'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=160 if col == 'material' else 110, anchor='w')
        self.tree.tag_configure('over', background=theme.wash('bad'))
        self.tree.tag_configure('ok', background=theme.wash('good'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=4)
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
        if opts and not self.site_var.get():
            self.site_var.set('{} - {}'.format(opts[0][0], opts[0][1]))
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        raw = self.site_var.get().strip()
        if not raw:
            return
        site_id = self._site_map.get(raw, raw.split(' - ')[0])
        conn = self.db_getter()
        try:
            theo = {}
            for r in conn.execute(
                    "SELECT n.material_id AS mid, m.name AS name, "
                    "COALESCE(m.rate, 0) AS rate, "
                    "SUM(w.qty * n.qty_per_unit) AS theo "
                    "FROM work_done_entries w "
                    "JOIN consumption_norms n ON n.activity = w.activity "
                    "JOIN materials m ON m.id = n.material_id "
                    "WHERE w.site_id = ? GROUP BY n.material_id", (site_id,)):
                theo[r['mid']] = (r['name'], r['rate'] or 0, r['theo'] or 0)
            actual = {}
            for r in conn.execute(
                    "SELECT l.material_id AS mid, m.name AS name, "
                    "COALESCE(m.rate, 0) AS rate, SUM(l.qty) AS act "
                    "FROM material_ledger l JOIN materials m ON m.id = l.material_id "
                    "WHERE l.site_id = ? AND l.txn_type = 'OUT' "
                    "GROUP BY l.material_id", (site_id,)):
                actual[r['mid']] = (r['name'], r['rate'] or 0, r['act'] or 0)
        finally:
            conn.close()

        tot_b = tot_a = 0.0
        for mid in sorted(set(theo) | set(actual),
                          key=lambda k: (theo.get(k) or actual.get(k))[0]):
            name, rate, tq = theo.get(mid, (None, 0, 0))
            name2, rate2, aq = actual.get(mid, (None, 0, 0))
            name = name or name2
            rate = rate or rate2
            mb = analytics.material_budget(tq, aq, rate)
            tot_b += mb['budget_value']; tot_a += mb['actual_value']
            osp = '-' if mb['overspend_pct'] is None else \
                '{:.1f}%'.format(mb['overspend_pct'])
            tag = 'over' if mb['variance_value'] > 0 else 'ok'
            row = (name, '{:.2f}'.format(mb['budget_value']),
                   '{:.2f}'.format(mb['actual_value']),
                   '{:.2f}'.format(mb['variance_value']), osp)
            self.tree.insert('', 'end', values=row, tags=(tag,))
            self._rows.append(row)
        self.summary_var.set(
            'Budget {:.2f}  |  Actual {:.2f}  |  Variance {:.2f}'.format(
                round(tot_b, 2), round(tot_a, 2), round(tot_a - tot_b, 2)))

    def export(self):
        html = bill_export.build_statement_html(
            'Material Budget vs Actual', ['Site: {}'.format(self.site_var.get())],
            ['Material', 'Budget Value', 'Actual Value', 'Variance',
             'Overspend %'], self._rows, summary=self.summary_var.get())
        _save_and_open_html(html, 'material_budget.html')


def build_insight_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(SiteProfitability(nb, db_getter), text='Site Profitability')
    nb.add(ContractProgress(nb, db_getter), text='Contract Progress')
    nb.add(MaterialBudget(nb, db_getter), text='Material Budget')
    nb.add(Outstanding(nb, db_getter, 'Receivable'), text='Receivables')
    nb.add(Outstanding(nb, db_getter, 'Payable'), text='Payables')
    nb.add(Ageing(nb, db_getter, 'Receivable'), text='Receivables Ageing')
    nb.add(Ageing(nb, db_getter, 'Payable'), text='Payables Ageing')
    return nb
