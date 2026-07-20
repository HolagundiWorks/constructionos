"""Pure sourcing maths: quote comparison and vendor rating (Wave 4).

No tkinter, no database.

Two small things that make buying less expensive.

**Quote comparison.** The three-quote rule exists because a single quotation is
not a price, it is an opening position. Comparing them is trivial arithmetic;
the value is in doing it at all, and in recording that it was done.

Cheapest is offered as a *recommendation*, not a decision. Lowest price with a
six-week delivery on a job that needs material next Tuesday is not the best
quote, and software that pretends otherwise trains people to ignore it. So the
comparison also surfaces delivery and the spread.

**Vendor rating.** A simple average across quality, delivery and price, kept to
three factors because a ten-factor scorecard for a firm with eleven suppliers
is a form nobody fills in twice.
"""

import finance

RATING_FACTORS = ('quality', 'delivery', 'price')


def money(value):
    return finance.money(value)


def _get(row, key, default=None):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _amount(q):
    try:
        return money(_get(q, 'amount', 0))
    except (TypeError, ValueError):
        return 0.0


def compare_quotes(quotes):
    """Rank quotes cheapest-first and quantify the spread.

    ``saving_vs_highest`` is the number that justifies the exercise: what the
    comparison is worth in rupees. ``spread_pct`` against the cheapest shows
    whether the market is tight (and the cheapest is probably fair) or wide
    (and somebody is guessing).

    Zero-amount quotes are excluded from the ranking — a quote with no price
    is an enquiry, not an offer — but still counted so the caller can see
    responses are outstanding.
    """
    rows = list(quotes or [])
    priced = [q for q in rows if _amount(q) > 0]
    if not priced:
        return {'ranked': [], 'count': len(rows), 'priced': 0,
                'cheapest': None, 'highest': None, 'saving_vs_highest': 0.0,
                'spread_pct': None}
    ranked = sorted(priced, key=_amount)
    low, high = _amount(ranked[0]), _amount(ranked[-1])
    return {
        'ranked': ranked,
        'count': len(rows),
        'priced': len(priced),
        'cheapest': ranked[0],
        'highest': ranked[-1],
        'saving_vs_highest': money(high - low),
        'spread_pct': money((high - low) / low * 100.0) if low else None,
    }


def recommendation(quotes, needed_by=None):
    """A recommendation with its reasoning, never a silent auto-pick.

    Returns ``(quote, note)``. Where the cheapest cannot meet ``needed_by``,
    the next quote that can is recommended instead and the note says why —
    because the cheapest price on material that arrives too late has cost more
    than the difference, in idle labour.
    """
    result = compare_quotes(quotes)
    if not result['ranked']:
        return None, 'No priced quotes yet.'
    cheapest = result['ranked'][0]
    if not needed_by:
        return cheapest, 'Lowest price of {} quote(s).'.format(result['priced'])
    on_time = [q for q in result['ranked']
               if not _get(q, 'delivery_date') or
               str(_get(q, 'delivery_date')) <= str(needed_by)]
    if not on_time:
        return cheapest, ('No quote meets the required date of {} — lowest '
                          'price shown; expect to negotiate delivery.'.format(needed_by))
    best = on_time[0]
    if best is cheapest:
        return best, 'Lowest price, and meets the required date.'
    return best, ('Not the cheapest, but the lowest that can deliver by {}. '
                  'Late material costs more in idle labour than the '
                  'difference.'.format(needed_by))


def vendor_score(ratings):
    """Average a vendor's scores across the rating factors.

    ``ratings`` maps factor -> score out of 5. Missing factors are skipped
    rather than counted as zero: an unrated factor is unknown, not bad.
    Returns None when nothing has been rated.
    """
    values = []
    for factor in RATING_FACTORS:
        value = ratings.get(factor) if hasattr(ratings, 'get') else None
        if value in (None, ''):
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return money(sum(values) / len(values))


def rank_vendors(vendors):
    """Vendors best-rated first; unrated ones last rather than assumed poor."""
    scored, unscored = [], []
    for v in vendors or []:
        score = vendor_score(v)
        if score is None:
            unscored.append((v, None))
        else:
            scored.append((v, score))
    scored.sort(key=lambda vs: -vs[1])
    return scored + unscored
