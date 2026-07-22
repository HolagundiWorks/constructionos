"""Pure lessons-learned maths: achieved rate vs the standard rate.

No tkinter, no database. The closeout loop the roadmap asks for is "feed what
things actually cost back into the rate library, so the next estimate is priced
on reality, not the last guess." The one achieved rate the app has as *ground
truth* is the material purchase rate — every ledger IN row carries the quantity
and the price actually paid. These helpers turn those into a quantity-weighted
achieved rate and compare it with the material's standard/reference rate.

Quantity-weighted (not a plain average) on purpose: a 500-bag order at ₹402 and
a 5-bag top-up at ₹450 should land near ₹402, not midway. Exercised with
``python -c``.
"""


def money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def weighted_rate(total_qty, total_value):
    """Achieved unit rate = total value paid / total quantity bought.

    ``total_value`` is SUM(qty x rate) over the purchases, ``total_qty`` is
    SUM(qty). Returns None when nothing was bought (no basis for an average) —
    None means "no data", which is different from a rate of 0.
    """
    tq = float(total_qty or 0)
    if tq <= 0:
        return None
    return money(float(total_value or 0) / tq)


def realise(reference_rate, total_qty, total_value, n_purchases=0):
    """Compare the standard/reference rate against the achieved rate.

        achieved   = weighted_rate(total_qty, total_value)   (None if no data)
        delta      = achieved - reference   (+ = paid more than the standard)
        pct        = delta / reference * 100 (None if the reference is 0)
        direction  = 'over' / 'under' / 'on' / 'no-data'

    A None achieved (no purchases) yields a 'no-data' row rather than a
    misleading 0, so the caller can skip it instead of zeroing a good rate.
    """
    ref = money(reference_rate)
    achieved = weighted_rate(total_qty, total_value)
    if achieved is None:
        return {'reference': ref, 'achieved': None, 'delta': None,
                'pct': None, 'n': int(n_purchases or 0), 'direction': 'no-data'}
    delta = money(achieved - ref)
    pct = round(delta / ref * 100.0, 1) if ref else None
    direction = 'on' if delta == 0 else ('over' if delta > 0 else 'under')
    return {'reference': ref, 'achieved': achieved, 'delta': delta,
            'pct': pct, 'n': int(n_purchases or 0), 'direction': direction}


def apply_rates(conn, pairs):
    """Write achieved rates back to ``materials.rate`` for ``(id, rate)`` pairs.

    Returns how many rows were updated. Does **not** check roles — the GUI /
    API caller gates writes (``can_write``) before calling this. Empty ``pairs``
    is a no-op that returns 0.
    """
    if not pairs:
        return 0
    for mid, achieved in pairs:
        conn.execute('UPDATE materials SET rate = ? WHERE id = ?',
                     (achieved, mid))
    conn.commit()
    return len(pairs)

