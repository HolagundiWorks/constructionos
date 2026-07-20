"""Pure cash-flow forecast maths (Phase 8, Wave 1).

No tkinter, no database.

Contracting businesses fail on **liquidity, not profitability**. A job can be
profitable on paper and still sink the firm because ₹8 lakh of wages fall due
in week 3 and the client's certified bill lands in week 6. The P&L will not
show that; only a dated view of money in against money out will.

So this projects **expected** cash, not accounting revenue:

* **Inflows** — what is open on client bills, expected on a lag. Contractors
  are paid late as a matter of routine, so a bill is assumed to arrive
  ``receipt_lag_days`` after its date rather than on it. A forecast that
  assumes prompt payment is worse than none.
* **Outflows** — open vendor/subcontractor payables (also lagged), plus the
  recurring costs that do not wait: **wages**, which in this trade are weekly
  and in cash.

Buckets are weekly or monthly. The output carries a **running balance** from
today's cash, because the number that matters is not any single week's net —
it is the first week the running balance goes negative.
"""

from datetime import date, timedelta

import isodate

BUCKET_WEEK = 'week'
BUCKET_MONTH = 'month'


def money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _parse(d):
    return isodate.parse(d)


def expected_date(doc_date, lag_days, today=None):
    """When a dated document is expected to turn into cash.

    Never earlier than today: a bill that was due last month is not money you
    already have, it is money you are still waiting for — so it lands in the
    first bucket rather than silently dropping out of the forecast.
    """
    today = _parse(today) or date.today()
    base = _parse(doc_date)
    if base is None:
        return today
    due = base + timedelta(days=int(lag_days or 0))
    return max(due, today)


def bucket_start(d, mode=BUCKET_WEEK):
    """Start of the bucket a date falls in (Monday, or the 1st)."""
    d = _parse(d) or date.today()
    if mode == BUCKET_MONTH:
        return date(d.year, d.month, 1)
    return d - timedelta(days=d.weekday())


def _advance(start, mode):
    if mode == BUCKET_MONTH:
        return date(start.year + (start.month == 12),
                    1 if start.month == 12 else start.month + 1, 1)
    return start + timedelta(days=7)


def build_buckets(today=None, periods=8, mode=BUCKET_WEEK):
    """The forecast horizon as a list of bucket-start dates."""
    start = bucket_start(_parse(today) or date.today(), mode)
    out, cur = [], start
    for _ in range(max(1, int(periods))):
        out.append(cur)
        cur = _advance(cur, mode)
    return out


def forecast(inflows, outflows, opening_balance=0, today=None, periods=8,
             mode=BUCKET_WEEK):
    """Project cash over the horizon.

    ``inflows``/``outflows`` are iterables of ``(expected_date, amount, label)``.
    Anything falling beyond the horizon is folded into the **last** bucket, so
    the totals still reconcile to the full open position rather than quietly
    losing money off the end of the table.

    Returns a list of bucket dicts (start, in, out, net, balance) plus totals
    and ``first_negative`` — the first bucket where the running balance goes
    below zero, which is the whole point of the exercise.
    """
    today = _parse(today) or date.today()
    buckets = build_buckets(today, periods, mode)
    rows = [{'start': b, 'in': 0.0, 'out': 0.0} for b in buckets]

    def place(when):
        when = _parse(when) or today
        target = bucket_start(max(when, today), mode)
        for i, b in enumerate(buckets):
            nxt = _advance(b, mode)
            if target < nxt:
                return i
        return len(buckets) - 1          # beyond the horizon -> last bucket

    for when, amount, _label in inflows or []:
        rows[place(when)]['in'] += money(amount)
    for when, amount, _label in outflows or []:
        rows[place(when)]['out'] += money(amount)

    balance = money(opening_balance)
    first_negative = None
    for row in rows:
        row['in'] = money(row['in'])
        row['out'] = money(row['out'])
        row['net'] = money(row['in'] - row['out'])
        balance = money(balance + row['net'])
        row['balance'] = balance
        if balance < 0 and first_negative is None:
            first_negative = row['start']

    return {
        'buckets': rows,
        'opening_balance': money(opening_balance),
        'total_in': money(sum(r['in'] for r in rows)),
        'total_out': money(sum(r['out'] for r in rows)),
        'closing_balance': balance,
        'first_negative': first_negative,
        'mode': mode,
    }


def wage_outflows(weekly_wage_bill, today=None, periods=8, mode=BUCKET_WEEK):
    """Recurring wage cost across the horizon.

    Wages are the outflow that cannot be deferred — labour walks off site. A
    weekly figure is spread per week, or multiplied out for a monthly bucket.
    """
    weekly = money(weekly_wage_bill)
    if weekly <= 0:
        return []
    out = []
    for start in build_buckets(today, periods, mode):
        amount = weekly if mode == BUCKET_WEEK else money(weekly * 52 / 12.0)
        out.append((start, amount, 'Wages'))
    return out
