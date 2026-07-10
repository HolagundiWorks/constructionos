"""Home — the plain-language landing screen (Phase 1).

What a contractor wants to see the moment they open the app: how much cash is in
hand, how much is still to be collected, how much they owe, and this month's
billing and collection. No jargon, no charts — big numbers.

All figures are computed on demand from the same tables the rest of the app
writes; nothing here is stored.
"""

from datetime import date
import tkinter as tk
from tkinter import ttk

import money as m


class HomeTab(ttk.Frame):
    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter

        header = ttk.Frame(self); header.pack(fill='x', padx=12, pady=(12, 4))
        ttk.Label(header, text='Contractor-OS',
                  font=('TkDefaultFont', 16, 'bold')).pack(side='left')
        ttk.Button(header, text='Refresh', command=self.refresh).pack(side='right')

        self.subtitle = tk.StringVar()
        ttk.Label(self, textvariable=self.subtitle,
                  font=('TkDefaultFont', 10)).pack(anchor='w', padx=12)

        self.grid_frame = ttk.Frame(self)
        self.grid_frame.pack(fill='both', expand=True, padx=8, pady=10)

        # (title, key, accent) — accent used only as a hint colour.
        self._tiles = [
            ('Cash in Hand', 'cash', '#2e7d32'),
            ('To Collect (Receivables)', 'receivable', '#1565c0'),
            ('To Pay (Payables)', 'payable', '#c62828'),
            ('Active Sites', 'sites', '#5d4037'),
            ('Billed This Month', 'billed_month', '#00695c'),
            ('Collected This Month', 'collected_month', '#6a1b9a'),
        ]
        self._vars = {}
        for idx, (title, key, accent) in enumerate(self._tiles):
            r, c = divmod(idx, 3)
            card = ttk.LabelFrame(self.grid_frame, text=title)
            card.grid(row=r, column=c, padx=8, pady=8, sticky='nsew')
            self.grid_frame.columnconfigure(c, weight=1)
            self.grid_frame.rowconfigure(r, weight=1)
            var = tk.StringVar(value='—')
            self._vars[key] = var
            ttk.Label(card, textvariable=var, foreground=accent,
                      font=('TkDefaultFont', 20, 'bold')) \
                .pack(padx=16, pady=16, anchor='w')

        ttk.Label(self, text='Tip: use Money > Cash Book for the day book, and '
                             'Money > Party Balances to see who owes whom.',
                  font=('TkDefaultFont', 9), foreground='#777') \
            .pack(anchor='w', padx=12, pady=(0, 10))
        self.refresh()

    def _fmt(self, value):
        """Indian-ish grouped rupee formatting."""
        return '₹ {:,.0f}'.format(round(float(value or 0)))

    def refresh(self):
        today = date.today()
        ym = today.strftime('%Y-%m')
        self.subtitle.set('As on {}'.format(today.isoformat()))
        conn = self.db_getter()
        try:
            # Cash in hand = opening + signed cash movements.
            row = conn.execute("SELECT value FROM app_settings WHERE key = 'cash_opening'").fetchone()
            opening = float(row['value']) if row and row['value'] else 0.0
            cash_moves = conn.execute(
                "SELECT direction, amount FROM payments WHERE mode = 'Cash'").fetchall()
            cash = m.closing_balance(
                [m.signed_cash(r['direction'], r['amount']) for r in cash_moves], opening)

            billed = conn.execute(
                "SELECT COALESCE(SUM(net_payable), 0) AS v FROM bills "
                "WHERE status IN ('Approved', 'Paid')").fetchone()['v']
            billed += conn.execute(
                "SELECT COALESCE(SUM(net_payable), 0) AS v FROM ra_bills "
                "WHERE status IN ('Approved', 'Paid')").fetchone()['v']
            received = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS v FROM payments "
                "WHERE direction = 'Receipt' AND party_type = 'Client'").fetchone()['v']
            receivable = m.party_outstanding(billed, received)

            invoiced = conn.execute(
                "SELECT COALESCE(SUM(net_payable), 0) AS v FROM vendor_invoices").fetchone()['v']
            paid = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS v FROM payments "
                "WHERE direction = 'Payment' AND party_type = 'Vendor'").fetchone()['v']
            payable = m.party_outstanding(invoiced, paid)

            sites = conn.execute(
                "SELECT COUNT(*) AS c FROM sites WHERE status = 'Active'").fetchone()['c']

            billed_month = conn.execute(
                "SELECT COALESCE(SUM(net_payable), 0) AS v FROM bills "
                "WHERE status IN ('Approved','Paid') AND substr(bill_date,1,7) = ?",
                (ym,)).fetchone()['v']
            billed_month += conn.execute(
                "SELECT COALESCE(SUM(net_payable), 0) AS v FROM ra_bills "
                "WHERE status IN ('Approved','Paid') AND substr(bill_date,1,7) = ?",
                (ym,)).fetchone()['v']
            collected_month = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS v FROM payments "
                "WHERE direction = 'Receipt' AND substr(pay_date,1,7) = ?",
                (ym,)).fetchone()['v']
        finally:
            conn.close()

        self._vars['cash'].set(self._fmt(cash))
        self._vars['receivable'].set(self._fmt(receivable))
        self._vars['payable'].set(self._fmt(payable))
        self._vars['sites'].set(str(sites))
        self._vars['billed_month'].set(self._fmt(billed_month))
        self._vars['collected_month'].set(self._fmt(collected_month))


def build_home_tab(parent, db_getter):
    return HomeTab(parent, db_getter)
