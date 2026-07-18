"""Pure estimate roll-up (ported from Construction-Billing-System).

Mirrors CBS's ``EstimateCalculator::totals`` exactly:

    items_subtotal = Sum(rate * qty)
    contingency    = items_subtotal * contingency%
    taxable        = items_subtotal + contingency
    gst            = taxable * gst%
    grand_total    = taxable + gst

No tkinter, no database — testable with ``python -c``.
"""


def _money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def item_amount(rate, qty):
    return _money(float(rate or 0) * float(qty or 0))


def estimate_totals(items, contingency_pct=0.0, gst_pct=0.0):
    """Roll estimate items up to the grand total.

    ``items`` is an iterable of mappings/rows with ``rate`` and ``qty`` (or an
    ``amount``); contingency and GST are percentages. Returns subtotal,
    contingency, taxable, gst, and grand_total (all rounded).
    """
    subtotal = 0.0
    for it in items:
        try:
            amt = it['amount']
        except (KeyError, IndexError, TypeError):
            amt = None
        if amt is None:
            amt = item_amount(_get(it, 'rate'), _get(it, 'qty'))
        subtotal += float(amt or 0)
    subtotal = _money(subtotal)
    contingency = _money(subtotal * float(contingency_pct or 0) / 100.0)
    taxable = _money(subtotal + contingency)
    gst = _money(taxable * float(gst_pct or 0) / 100.0)
    grand = _money(taxable + gst)
    return {'subtotal': subtotal, 'contingency': contingency,
            'taxable': taxable, 'gst': gst, 'grand_total': grand}


def _get(row, key, default=0):
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val
