"""Indian Rupee display formatting: the rupee symbol and lakh/crore grouping.

Pure, stdlib. The app coerces money with ``finance.money`` (a float); this module
turns that number into the string a user reads, using the **Indian numbering
system** -- the last three digits, then groups of two (``1,00,000`` = one lakh,
``1,00,00,000`` = one crore) -- rather than the Western thousands grouping, with
the rupee sign. ``compact`` gives the short lakh/crore form for dashboards.

    rupees(100000)   -> 'Rs 1,00,000.00'   (RUPEE symbol in place of 'Rs')
    rupees(-2500, paise=False) -> '-Rs 2,500'
    compact(15000000) -> 'Rs 1.5 Cr'
    compact(45000)    -> 'Rs 45,000'
"""

RUPEE = '₹'          # the Indian Rupee sign


def group_digits(intstr):
    """Indian-group a run of digits: last three, then twos.

    ``'100000' -> '1,00,000'``; ``'10000000' -> '1,00,00,000'``. Leading zeros
    are dropped (``'007' -> '7'``); a non-digit input yields it back unchanged.
    """
    s = ''.join(ch for ch in str(intstr) if ch.isdigit())
    if not s:
        return str(intstr)
    s = s.lstrip('0') or '0'
    if len(s) <= 3:
        return s
    tail, head = s[-3:], s[:-3]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ','.join(parts) + ',' + tail


def _as_float(value):
    try:
        return float(value if value not in (None, '') else 0)
    except (TypeError, ValueError):
        return 0.0


def rupees(value, paise=True, symbol=True):
    """``Rs 1,00,000.00`` (Indian grouping). None/blank -> zero; sign kept.

    ``paise=False`` drops the decimals; ``symbol=False`` drops the rupee sign
    (for columns that show the sign in a header instead).
    """
    v = _as_float(value)
    neg = v < 0
    s = '{:.2f}'.format(abs(v))
    intpart, dec = s.split('.')
    body = group_digits(intpart)
    if paise:
        body += '.' + dec
    out = (RUPEE if symbol else '') + body
    return ('-' + out) if neg else out


def _trim(x):
    """Two decimals, trailing zeros stripped: 1.50 -> '1.5', 2.00 -> '2'."""
    return '{:.2f}'.format(x).rstrip('0').rstrip('.')


def compact(value, symbol=True):
    """Abbreviated: ``Rs 1.5 Cr`` / ``Rs 12.3 L`` / ``Rs 45,000`` (< 1 lakh)."""
    v = _as_float(value)
    neg = v < 0
    a = abs(v)
    if a >= 1e7:
        body = _trim(a / 1e7) + ' Cr'
    elif a >= 1e5:
        body = _trim(a / 1e5) + ' L'
    else:
        body = group_digits('{:.0f}'.format(a))
    out = (RUPEE if symbol else '') + body
    return ('-' + out) if neg else out
