"""Pure receivable / payable ageing helpers (Phase 6).

No tkinter, no database. A contractor wants to know not just *how much* is
outstanding but *how old* it is — a 90-day-old receivable is a different worry
from a fresh one. These helpers take a party's dated bills and total receipts,
apply the receipts to the **oldest bills first** (FIFO — the natural assumption
when payments aren't linked to specific bills), and bucket whatever remains open
by age into 0-30 / 30-60 / 60-90 / 90+ day slabs.

Everything is a plain function so the maths can be exercised with ``python -c``.
Dates are ISO ``YYYY-MM-DD`` strings; a blank/None or unparseable date is
treated as *today* (age 0) rather than raising.
"""

from datetime import date

import isodate

BUCKETS = ('0-30', '30-60', '60-90', '90+')
_EDGES = (30, 60, 90)


def money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _parse(d):
    """ISO date string -> ``date``; blank/garbage -> None."""
    return isodate.parse(d)


def days_between(bill_date, as_on):
    """Age in days of ``bill_date`` as at ``as_on`` (both ISO or ``date``).

    A missing/invalid bill date ages to 0 (treated as today). Negative ages
    (future-dated bills) clamp to 0.
    """
    as_on = _parse(as_on) or date.today() if not isinstance(as_on, date) else as_on
    bd = bill_date if isinstance(bill_date, date) else _parse(bill_date)
    if bd is None:
        return 0
    return max(0, (as_on - bd).days)


def bucket_for_days(days):
    """Map an age in days to one of the four bucket labels."""
    for edge, label in zip(_EDGES, BUCKETS):
        if days < edge:
            return label
    return BUCKETS[-1]


def apply_receipts_fifo(bills, receipts_total):
    """Reduce dated bills by a lump receipts total, oldest bill first.

    ``bills`` is an iterable of ``(date, amount)``; the result is a list of
    ``(date, open_amount)`` in the same (oldest-first) order, dropping bills
    that are fully settled. ``receipts_total`` in excess of all bills is simply
    exhausted (an over-received party shows nothing outstanding).
    """
    remaining = money(receipts_total)
    ordered = sorted(bills, key=lambda b: (_parse(b[0]) or date.min))
    out = []
    for d, amt in ordered:
        amt = money(amt)
        if remaining >= amt:
            remaining = money(remaining - amt)
            continue
        open_amt = money(amt - remaining)
        remaining = 0.0
        out.append((d, open_amt))
    return out


def age_open_items(open_items, as_on=None):
    """Bucket ``(date, open_amount)`` items by age. Returns a dict of the four
    bucket labels plus ``total`` (all rounded)."""
    as_on = _parse(as_on) or date.today()
    result = {b: 0.0 for b in BUCKETS}
    for d, amt in open_items:
        label = bucket_for_days(days_between(d, as_on))
        result[label] = money(result[label] + money(amt))
    result['total'] = money(sum(result[b] for b in BUCKETS))
    return result


def party_ageing(bills, receipts_total, as_on=None):
    """Convenience: FIFO-settle a party's ``bills`` by ``receipts_total`` then
    age the remainder. Returns the same dict shape as :func:`age_open_items`."""
    return age_open_items(apply_receipts_fifo(bills, receipts_total), as_on)
