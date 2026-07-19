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

import ageing
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
        self.tree.tag_configure('loss', background='#ffebee')
        self.tree.tag_configure('profit', background='#e8f5e9')
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

    Receipts/payments aren't linked to specific bills, so we settle a party's
    dated bills oldest-first (FIFO) by their total received/paid, then age
    whatever is still open (`ageing.party_ageing`). Receivables age client
    bills + RA bills by bill date; payables age vendor invoices by invoice date.
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
        self.tree.tag_configure('overdue', background='#ffebee')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=4)
        self.refresh()

    def _bills_by_party(self, conn):
        """Return {party_id: [(date, amount), ...]} and {party_id: settled}."""
        bills = {}
        if self.mode == 'Receivable':
            parties = conn.execute(
                'SELECT id, name FROM clients ORDER BY name').fetchall()
            rows = conn.execute(
                "SELECT c.client_id AS pid, b.bill_date AS d, b.net_payable AS a "
                "FROM bills b JOIN contracts c ON c.id = b.contract_id "
                "WHERE b.status IN ('Approved','Paid') "
                "UNION ALL "
                "SELECT c.client_id AS pid, r.bill_date AS d, r.net_payable AS a "
                "FROM ra_bills r JOIN contracts c ON c.id = r.contract_id "
                "WHERE r.status IN ('Approved','Paid')").fetchall()
            settled = _sum_map(conn,
                "SELECT party_id, SUM(amount) FROM payments "
                "WHERE direction = 'Receipt' AND party_type = 'Client' "
                "AND party_id IS NOT NULL GROUP BY party_id")
        else:
            parties = conn.execute(
                'SELECT id, name FROM vendors ORDER BY name').fetchall()
            rows = conn.execute(
                "SELECT vendor_id AS pid, invoice_date AS d, net_payable AS a "
                "FROM vendor_invoices").fetchall()
            settled = _sum_map(conn,
                "SELECT party_id, SUM(amount) FROM payments "
                "WHERE direction = 'Payment' AND party_type = 'Vendor' "
                "AND party_id IS NOT NULL GROUP BY party_id")
        for r in rows:
            if r['pid'] is None:
                continue
            bills.setdefault(r['pid'], []).append((r['d'], r['a'] or 0))
        return parties, bills, settled

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            parties, bills, settled = self._bills_by_party(conn)
        finally:
            conn.close()

        self._rows = []
        totals = {b: 0.0 for b in ageing.BUCKETS}
        for p in parties:
            party_bills = bills.get(p['id'])
            if not party_bills:
                continue
            aged = ageing.party_ageing(party_bills, settled.get(p['id'], 0) or 0)
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


def build_insight_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(SiteProfitability(nb, db_getter), text='Site Profitability')
    nb.add(Outstanding(nb, db_getter, 'Receivable'), text='Receivables')
    nb.add(Outstanding(nb, db_getter, 'Payable'), text='Payables')
    nb.add(Ageing(nb, db_getter, 'Receivable'), text='Receivables Ageing')
    nb.add(Ageing(nb, db_getter, 'Payable'), text='Payables Ageing')
    return nb
