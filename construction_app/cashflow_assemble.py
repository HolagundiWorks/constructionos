"""Assemble a cash-flow forecast from the live book (stdlib, no tkinter).

Used by ``GET /api/cashflow`` so WinUI Charts can bind series without C#
maths. Mirrors the desktop Cash Flow tab's inputs at a firm level: open
client bills → lagged inflows; open vendor invoices + sub bills → lagged
outflows; optional weekly wage bill.
"""

from datetime import date

import cashflow
import isodate


def _money(x):
    try:
        return round(float(x or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _setting(conn, key, default='0'):
    row = conn.execute(
        'SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


def assemble(conn, periods=8, mode=None, receipt_lag_days=45,
             payment_lag_days=15, weekly_wages=0, today=None):
    """Build ``cashflow.forecast`` inputs from open documents + cash opening."""
    today = isodate.parse(today) or date.today()
    mode = mode or cashflow.BUCKET_WEEK
    if mode not in (cashflow.BUCKET_WEEK, cashflow.BUCKET_MONTH):
        mode = cashflow.BUCKET_WEEK
    try:
        periods = max(1, min(int(periods or 8), 52))
    except (TypeError, ValueError):
        periods = 8
    try:
        receipt_lag_days = int(receipt_lag_days)
    except (TypeError, ValueError):
        receipt_lag_days = 45
    try:
        payment_lag_days = int(payment_lag_days)
    except (TypeError, ValueError):
        payment_lag_days = 15

    opening = _money(_setting(conn, 'cash_opening', '0'))

    inflows = []
    for r in conn.execute(
            "SELECT bill_date, net_payable FROM bills "
            "WHERE status IN ('Approved', 'Paid')"):
        if r['bill_date']:
            inflows.append((
                cashflow.expected_date(r['bill_date'], receipt_lag_days, today),
                _money(r['net_payable']), 'Running bill'))
    for r in conn.execute(
            "SELECT bill_date, net_payable FROM ra_bills "
            "WHERE status IN ('Approved', 'Paid')"):
        if r['bill_date']:
            inflows.append((
                cashflow.expected_date(r['bill_date'], receipt_lag_days, today),
                _money(r['net_payable']), 'RA bill'))
    for r in conn.execute(
            "SELECT invoice_date, total_amount FROM tax_invoices "
            "WHERE status != 'Cancelled'"):
        if r['invoice_date']:
            inflows.append((
                cashflow.expected_date(
                    r['invoice_date'], receipt_lag_days, today),
                _money(r['total_amount']), 'Tax invoice'))

    outflows = []
    for r in conn.execute(
            "SELECT invoice_date, net_payable FROM vendor_invoices "
            "WHERE status != 'Paid'"):
        if r['invoice_date']:
            outflows.append((
                cashflow.expected_date(
                    r['invoice_date'], payment_lag_days, today),
                _money(r['net_payable']), 'Vendor invoice'))
    for r in conn.execute(
            "SELECT bill_date, net_payable FROM sub_bills "
            "WHERE status IN ('Approved', 'Submitted')"):
        if r['bill_date']:
            outflows.append((
                cashflow.expected_date(r['bill_date'], payment_lag_days, today),
                _money(r['net_payable']), 'Sub bill'))

    wages = _money(weekly_wages)
    if wages > 0:
        outflows.extend(cashflow.wage_outflows(wages, today, periods, mode))

    result = cashflow.forecast(
        inflows, outflows, opening, today, periods, mode)
    # JSON-friendly dates
    for b in result.get('buckets') or []:
        if hasattr(b.get('start'), 'isoformat'):
            b['start'] = b['start'].isoformat()
    fn = result.get('first_negative')
    if hasattr(fn, 'isoformat'):
        result['first_negative'] = fn.isoformat()
    result['receipt_lag_days'] = receipt_lag_days
    result['payment_lag_days'] = payment_lag_days
    result['weekly_wages'] = wages
    return result
