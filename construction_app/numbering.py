"""Pure document-numbering helpers (Phase 2 — configurable invoice series).

No tkinter, no database. A contractor wants tidy, sequential invoice numbers
that optionally carry the financial year and reset each April — e.g.
``INV/2026-27/001``. These helpers compute the Indian financial year, format a
number from a series config, and derive the next serial by inspecting the
numbers already in use (so deletes and manual numbers don't desync a stored
counter). The DB glue that reads the config and the existing numbers lives in
the calling tab; everything here is exercised with ``python -c``.
"""

from datetime import date


def financial_year(d):
    """Indian financial year label (Apr-Mar) for an ISO date or ``date``.

    ``2026-07-19`` -> ``'2026-27'``; ``2026-02-10`` -> ``'2025-26'``. A
    blank/invalid date falls back to today's financial year.
    """
    if not isinstance(d, date):
        try:
            d = date.fromisoformat(str(d)[:10])
        except (ValueError, TypeError):
            d = date.today()
    start = d.year if d.month >= 4 else d.year - 1
    return '{}-{:02d}'.format(start, (start + 1) % 100)


def build_number(prefix, serial, fy=None, width=3, include_fy=True):
    """Format a document number from its parts.

    With a financial year: ``PREFIX/FY/serial`` (``INV/2026-27/001``); without:
    ``PREFIX-serial`` (``INV-001``). ``width`` zero-pads the serial.
    """
    prefix = (prefix or 'INV').strip()
    ser = '{:0{w}d}'.format(int(serial), w=max(1, int(width)))
    if include_fy and fy:
        return '{}/{}/{}'.format(prefix, fy, ser)
    return '{}-{}'.format(prefix, ser)


def _trailing_int(s):
    """Trailing run of digits in a string as int, or None."""
    digits = ''
    for ch in reversed(str(s)):
        if ch.isdigit():
            digits = ch + digits
        else:
            break
    return int(digits) if digits else None


def next_serial(existing_numbers, prefix, fy=None, include_fy=True):
    """Next serial (max in-use + 1, min 1) for a prefix / FY scope.

    Only numbers whose stem matches the same ``prefix`` (and ``fy`` when
    ``include_fy``) are considered, so switching the FY naturally restarts the
    count at 1. Numbers that don't fit the pattern are ignored.
    """
    prefix = (prefix or 'INV').strip()
    stem = '{}/{}/'.format(prefix, fy) if (include_fy and fy) else '{}-'.format(prefix)
    highest = 0
    for num in existing_numbers or []:
        if not num or not str(num).startswith(stem):
            continue
        n = _trailing_int(num)
        if n is not None and n > highest:
            highest = n
    return highest + 1


def next_number(existing_numbers, prefix='INV', doc_date=None, width=3,
                fy_reset=True):
    """Convenience: compute FY from ``doc_date`` and return the next formatted
    number for a series, scanning ``existing_numbers`` for the current serial."""
    fy = financial_year(doc_date) if fy_reset else None
    ser = next_serial(existing_numbers, prefix, fy, include_fy=fy_reset)
    return build_number(prefix, ser, fy, width, include_fy=fy_reset)
