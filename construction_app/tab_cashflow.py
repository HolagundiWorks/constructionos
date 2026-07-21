"""Cash-flow forecast (Phase 8, Wave 1).

Projects money in against money out over the coming weeks or months, starting
from cash in hand, and says the one thing a contractor needs to hear early:
**the first week you run out**.

Inflows are what is still open on client bills; outflows are open vendor and
subcontractor payables plus the weekly wage bill. Both sides are lagged,
because being paid on the due date is not how this trade works — the lags are
editable, since a contractor knows their own client better than any default.

Open positions come from ``tab_allocate.party_documents`` and the recorded
allocations, so the forecast agrees with the ageing view rather than
re-deriving "what is owed" a second, different way.
"""

import tkinter as tk
import theme
from datetime import date
from tkinter import ttk

import allocation
import bill_export
import cashflow
import money as m
import report_open
from tab_allocate import party_documents


class CashFlowForecast(ttk.Frame):
    COLUMNS = ('period', 'inflow', 'outflow', 'net', 'balance')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self.mode_var = tk.StringVar(value='Weekly')
        self.periods_var = tk.StringVar(value='8')
        self.in_lag_var = tk.StringVar(value='45')
        self.out_lag_var = tk.StringVar(value='30')
        self.wages_var = tk.StringVar(value='0')
        self.summary_var = tk.StringVar()
        self.warn_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Cash-flow forecast',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='Contracting fails on running out of cash, not on '
                             'being unprofitable. This projects what is still '
                             'open on your bills against what you owe and must '
                             'pay, starting from cash in hand.',
                  wraplength=700, justify='left', foreground='#555') \
            .pack(anchor='w', padx=8, pady=(0, 6))

        ctl = ttk.LabelFrame(self, text='Assumptions')
        ctl.pack(fill='x', padx=8, pady=4)
        row = ttk.Frame(ctl); row.pack(fill='x', padx=8, pady=6)
        ttk.Label(row, text='Buckets').pack(side='left')
        ttk.Combobox(row, textvariable=self.mode_var, width=8, state='readonly',
                     values=['Weekly', 'Monthly']).pack(side='left', padx=(4, 12))
        ttk.Label(row, text='Periods').pack(side='left')
        ttk.Entry(row, textvariable=self.periods_var, width=5).pack(side='left', padx=(4, 12))
        ttk.Label(row, text='Client pays after (days)').pack(side='left')
        ttk.Entry(row, textvariable=self.in_lag_var, width=5).pack(side='left', padx=(4, 12))
        ttk.Label(row, text='We pay after (days)').pack(side='left')
        ttk.Entry(row, textvariable=self.out_lag_var, width=5).pack(side='left', padx=(4, 12))
        row2 = ttk.Frame(ctl); row2.pack(fill='x', padx=8, pady=(0, 6))
        ttk.Label(row2, text='Weekly wage bill').pack(side='left')
        ttk.Entry(row2, textvariable=self.wages_var, width=12).pack(side='left', padx=4)
        ttk.Label(row2, text='(the outflow that cannot wait — labour walks off site)',
                  foreground='#777').pack(side='left', padx=6)
        ttk.Button(row2, text='Recalculate', command=self.refresh).pack(side='right')

        heads = {'period': 'Period from', 'inflow': 'Money in',
                 'outflow': 'Money out', 'net': 'Net', 'balance': 'Running balance'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=10)
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=140 if c == 'period' else 120,
                             anchor='w' if c == 'period' else 'e')
        self.tree.tag_configure('short', background=theme.wash('bad'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        ttk.Label(self, textvariable=self.warn_var, foreground='#a4343a',
                  font=('TkDefaultFont', 11, 'bold'), wraplength=700,
                  justify='left').pack(anchor='w', padx=8, pady=(4, 0))
        ttk.Label(self, textvariable=self.summary_var,
                  foreground='#555').pack(anchor='w', padx=8, pady=(2, 4))
        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btns, text='Refresh', command=self.refresh).pack(side='left')
        ttk.Button(btns, text='Print / Export', command=self.export).pack(side='left', padx=6)

    def _num(self, var, default):
        try:
            return float(str(var.get()).strip() or default)
        except ValueError:
            return float(default)

    def _open_by_party(self, conn, party_type):
        """Open documents for every party of a type, allocation-aware."""
        table = 'clients' if party_type == 'Client' else 'vendors'
        direction = 'Receipt' if party_type == 'Client' else 'Payment'
        parties = conn.execute(
            'SELECT id, name FROM {} ORDER BY name'.format(table)).fetchall()
        settled = {}
        for r in conn.execute(
                'SELECT party_id, SUM(amount) AS s FROM payments '
                'WHERE direction = ? AND party_type = ? AND party_id IS NOT NULL '
                'GROUP BY party_id', (direction, party_type)):
            settled[r['party_id']] = r['s'] or 0
        allocs = {}
        for r in conn.execute(
                'SELECT p.party_id AS pid, pa.doc_type, pa.doc_id, pa.amount '
                'FROM payment_allocations pa JOIN payments p ON p.id = pa.payment_id '
                'WHERE p.party_type = ? AND p.party_id IS NOT NULL', (party_type,)):
            allocs.setdefault(r['pid'], []).append(
                {'doc_type': r['doc_type'], 'doc_id': r['doc_id'],
                 'amount': r['amount']})
        items = []
        for p in parties:
            docs = party_documents(conn, party_type, p['id'])
            if not docs:
                continue
            a = allocs.get(p['id'], [])
            used = sum(allocation.money(x['amount']) for x in a)
            unallocated = max(allocation.money(settled.get(p['id'], 0)) -
                              allocation.money(used), 0.0)
            for when, amount in allocation.open_items_for_ageing(docs, a, unallocated):
                items.append((when, amount, p['name']))
        return items

    def refresh(self):
        mode = (cashflow.BUCKET_MONTH if self.mode_var.get() == 'Monthly'
                else cashflow.BUCKET_WEEK)
        periods = int(self._num(self.periods_var, 8))
        in_lag = self._num(self.in_lag_var, 45)
        out_lag = self._num(self.out_lag_var, 30)
        today = date.today()

        conn = self.db_getter()
        try:
            receivable = self._open_by_party(conn, 'Client')
            payable = self._open_by_party(conn, 'Vendor')
            # Cash in hand is the honest starting point: the forecast is only
            # useful relative to what is actually in the tin today.
            rows = conn.execute(
                'SELECT direction, amount FROM payments '
                "WHERE mode = 'Cash'").fetchall()
            opening = m.closing_balance(
                [m.signed_cash(r['direction'], r['amount']) for r in rows], 0)
            sub = conn.execute(
                "SELECT bill_date, net_payable FROM sub_bills "
                "WHERE status IN ('Approved','Paid')").fetchall()
        finally:
            conn.close()

        inflows = [(cashflow.expected_date(d, in_lag, today), a, n)
                   for d, a, n in receivable]
        outflows = [(cashflow.expected_date(d, out_lag, today), a, n)
                    for d, a, n in payable]
        outflows += [(cashflow.expected_date(r['bill_date'], out_lag, today),
                      r['net_payable'], 'Subcontractor') for r in sub]
        outflows += cashflow.wage_outflows(self._num(self.wages_var, 0),
                                           today, periods, mode)

        result = cashflow.forecast(inflows, outflows, opening, today,
                                   periods, mode)
        self._render(result)

    def _render(self, result):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        for b in result['buckets']:
            values = (b['start'].isoformat(), '{:,.2f}'.format(b['in']),
                      '{:,.2f}'.format(b['out']), '{:,.2f}'.format(b['net']),
                      '{:,.2f}'.format(b['balance']))
            self._rows.append(values)
            self.tree.insert('', 'end', values=values,
                             tags=('short',) if b['balance'] < 0 else ())
        if result['first_negative']:
            self.warn_var.set(
                'Cash runs out in the period beginning {} — arrange collection '
                'or defer payments before then.'.format(
                    result['first_negative'].isoformat()))
        else:
            self.warn_var.set('')
        self.summary_var.set(
            'Opening {:,.2f}   ·   in {:,.2f}   ·   out {:,.2f}   ·   '
            'closing {:,.2f}'.format(
                result['opening_balance'], result['total_in'],
                result['total_out'], result['closing_balance']))

    def export(self):
        html = bill_export.build_statement_html(
            'Cash-flow forecast',
            [self.warn_var.get() or 'No shortfall projected in this horizon.',
             self.summary_var.get()],
            ['Period from', 'Money in', 'Money out', 'Net', 'Running balance'],
            self._rows, summary=self.summary_var.get())
        report_open.save_and_open_html(html, 'cashflow_forecast.html')


def build_cashflow_tab(parent, db_getter):
    return CashFlowForecast(parent, db_getter)
