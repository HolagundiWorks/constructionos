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

        # Logo and the developer credit now live in the rail (identity belongs
        # there, per the HCW spatial model); Home leads straight with the work.
        header = ttk.Frame(self); header.pack(fill='x', padx=12, pady=(12, 4))
        ttk.Label(header, text='Overview', style='H1.TLabel').pack(side='left')
        ttk.Button(header, text='Refresh', command=self.refresh).pack(side='right')

        self.subtitle = tk.StringVar()
        ttk.Label(self, textvariable=self.subtitle,
                  style='Muted.TLabel').pack(anchor='w', padx=12)

        self.grid_frame = ttk.Frame(self)
        self.grid_frame.pack(fill='both', expand=True, padx=8, pady=10)

        # (title, key, pictogram, value-style). The colour carries meaning:
        # green = money you hold or have brought in, red = money you owe,
        # slate (info) = money in motion, ink = a plain count.
        self._tiles = [
            ('Cash in Hand', 'cash', '\U0001F4B5', 'StatGood.TLabel'),
            ('To Collect', 'receivable', '\U0001F4E5', 'StatInfo.TLabel'),
            ('To Pay', 'payable', '\U0001F4E4', 'StatWarn.TLabel'),
            ('Active Sites', 'sites', '\U0001F3D7', 'StatValue.TLabel'),
            ('Billed This Month', 'billed_month', '\U0001F9FE', 'StatInfo.TLabel'),
            ('Collected This Month', 'collected_month', '✅', 'StatGood.TLabel'),
        ]
        self._vars = {}
        for idx, (title, key, icon, valstyle) in enumerate(self._tiles):
            r, c = divmod(idx, 3)
            card = ttk.Frame(self.grid_frame, style='StatCard.TFrame',
                             padding=(16, 14))
            card.grid(row=r, column=c, padx=8, pady=8, sticky='nsew')
            self.grid_frame.columnconfigure(c, weight=1, uniform='stat')
            self.grid_frame.rowconfigure(r, weight=1)
            head = ttk.Frame(card, style='Card.TFrame')
            head.pack(fill='x', anchor='w')
            ttk.Label(head, text=icon, style='StatIcon.TLabel').pack(side='left')
            ttk.Label(head, text=title, style='StatLabel.TLabel') \
                .pack(side='left', padx=(8, 0))
            var = tk.StringVar(value='—')
            self._vars[key] = var
            ttk.Label(card, textvariable=var, style=valstyle) \
                .pack(anchor='w', pady=(10, 0))

        ttk.Label(self, text='Tip: use Money > Cash Book for the day book, and '
                             'Money > Party Balances to see who owes whom.',
                  style='Muted.TLabel') \
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
