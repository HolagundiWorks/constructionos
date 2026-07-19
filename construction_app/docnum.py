"""Pure document-number series maths (Phase 2 — get paid & submit).

Indian contractors number invoices per financial year (April–March), e.g.
``INV/25-26/007``. These helpers are pure (no tkinter, no database) so the
numbering rule is testable with ``python -c``. The next serial is derived from
the **maximum** existing serial in the series — not a row count — so deleting
an old invoice can never cause a duplicate number.
"""

import re


def fy_label(date_str):
    """Indian financial-year label ('25-26') for a ``YYYY-MM-DD`` date.

    April onward belongs to the FY starting that year; January–March to the
    FY that started the previous April. Returns '' for an unparseable date.
    """
    try:
        year = int(str(date_str)[0:4])
        month = int(str(date_str)[5:7])
    except (TypeError, ValueError, IndexError):
        return ''
    start = year if month >= 4 else year - 1
    return '{:02d}-{:02d}'.format(start % 100, (start + 1) % 100)


def next_doc_no(existing, prefix='INV', fy=''):
    """Next number in a document series.

    With ``fy`` set, the series is ``PREFIX/FY/serial`` (e.g. INV/25-26/007)
    and only numbers in that FY count; without it, ``PREFIX-serial`` (also
    accepting ``PREFIX/serial``). ``existing`` is an iterable of the numbers
    already issued; non-matching or free-typed numbers are ignored. The new
    serial is max(existing serials) + 1, zero-padded to 3 digits.
    """
    if fy:
        pattern = re.compile(r'^{}/{}/(\d+)$'.format(
            re.escape(prefix), re.escape(fy)))
    else:
        pattern = re.compile(r'^{}[-/](\d+)$'.format(re.escape(prefix)))
    top = 0
    for number in existing or []:
        match = pattern.match(str(number or '').strip())
        if match:
            top = max(top, int(match.group(1)))
    if fy:
        return '{}/{}/{:03d}'.format(prefix, fy, top + 1)
    return '{}-{:03d}'.format(prefix, top + 1)
