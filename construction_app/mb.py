"""Measurement Book structure, integrity checks, and CMB eligibility.

No tkinter, no database. ``civil.py`` computes a single measurement's quantity
(Nos x L x B x D); this module deals with the *book* around those entries — how
they group into pages, whether the record satisfies the CPWD Works Manual's
integrity rules, and what the totals come to.

Why this exists: for works of Rs 15 lakh and above the CPWD Works Manual
(Para 7.12) lets the contractor submit a **Computerised Measurement Book** in
place of the conventional hand-written MB, on machine-numbered A-4 pages in the
same format. That makes MB-format output from this app an accepted departmental
deliverable rather than a convenience, so it is worth getting the record rules
right rather than just dumping rows into a table.

The checks in ``integrity_issues`` follow Para 7.5 and CPWA Form 23: every set
carries a page reference, a date and the particulars of what was measured; no
blank or void entries; and nothing may be counted twice. The duplicate check is
the one with money attached — a measurement entered twice is billed twice.
"""

# Works of this value and above may use a contractor-prepared Computerised
# Measurement Book (CPWD Works Manual Para 7.12). Rupees.
CMB_THRESHOLD = 1500000.0

UNNUMBERED = '(unnumbered)'


def _g(row, key, default=None):
    """Read ``key`` from a sqlite3.Row or dict, tolerating absent columns."""
    if row is None:
        return default
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


def _txt(row, key):
    return str(_g(row, key, '') or '').strip()


def cmb_eligible(contract_value):
    """True when the work qualifies for a contractor-prepared computerised MB."""
    try:
        return float(contract_value or 0) >= CMB_THRESHOLD
    except (TypeError, ValueError):
        return False


def page_ref(row):
    """The MB page a measurement belongs to; blanks group under UNNUMBERED."""
    return _txt(row, 'mb_ref') or UNNUMBERED


def group_pages(rows):
    """Group measurements into ``[(page_ref, [rows]), ...]``.

    Pages come out in order of first appearance rather than sorted, because MB
    references are free text ('12', '12A', 'Vol II p.7') and sorting them
    lexically would reorder the book. Entry order is the book's own order.
    """
    order = []
    pages = {}
    for row in rows or []:
        ref = page_ref(row)
        if ref not in pages:
            pages[ref] = []
            order.append(ref)
        pages[ref].append(row)
    return [(ref, pages[ref]) for ref in order]


def page_total(rows):
    """Total measured content on one page."""
    return round(sum(float(_g(r, 'quantity', 0) or 0) for r in rows or []), 3)


def item_totals(rows):
    """Cumulative measured quantity per BOQ item -> ``{boq_item_id: qty}``."""
    totals = {}
    for row in rows or []:
        key = _g(row, 'boq_item_id')
        totals[key] = round(totals.get(key, 0.0)
                            + float(_g(row, 'quantity', 0) or 0), 3)
    return totals


def _dedupe_key(row):
    return (page_ref(row), _g(row, 'boq_item_id'),
            _txt(row, 'description').lower(),
            _g(row, 'nos'), _g(row, 'length'),
            _g(row, 'breadth'), _g(row, 'depth'))


def integrity_issues(rows):
    """Check the book against the Works Manual record rules.

    Returns ``[{'id', 'severity', 'issue'}, ...]`` in row order, then duplicate
    findings. ``severity`` is ``'error'`` for anything that makes the entry
    unfit to bill against, ``'warning'`` for a record-keeping lapse that does
    not by itself invalidate the measurement.
    """
    issues = []
    for row in rows or []:
        rid = _g(row, 'id')
        if not _txt(row, 'mb_ref'):
            issues.append({'id': rid, 'severity': 'warning',
                           'issue': 'No MB page reference — the bill certificate '
                                    'must cite an MB number and page.'})
        if not _txt(row, 'mb_date'):
            issues.append({'id': rid, 'severity': 'error',
                           'issue': 'No measurement date.'})
        if not _txt(row, 'description'):
            issues.append({'id': rid, 'severity': 'warning',
                           'issue': 'No particulars / location recorded.'})
        qty = float(_g(row, 'quantity', 0) or 0)
        if qty == 0:
            issues.append({'id': rid, 'severity': 'error',
                           'issue': 'Zero quantity — blank entries are not '
                                    'permitted in a measurement book.'})
        elif qty < 0:
            issues.append({'id': rid, 'severity': 'error',
                           'issue': 'Negative quantity.'})

    seen = {}
    for row in rows or []:
        key = _dedupe_key(row)
        if key[1] is None and not key[2]:
            continue          # too little to judge; the blank checks cover it
        if key in seen:
            issues.append({
                'id': _g(row, 'id'), 'severity': 'error',
                'issue': 'Identical to measurement #{} on the same page — '
                         'would be billed twice.'.format(seen[key])})
        else:
            seen[key] = _g(row, 'id')
    return issues


def blocking_issues(rows):
    """Only the issues that should stop the book being certified."""
    return [i for i in integrity_issues(rows) if i['severity'] == 'error']


def may_certify(rows):
    """True when the book is fit to sign off and bill against."""
    return not blocking_issues(rows)


def date_range(rows):
    """``(first, last)`` measurement date present, or ``(None, None)``."""
    dates = sorted(d for d in (_txt(r, 'mb_date') for r in rows or []) if d)
    return (dates[0], dates[-1]) if dates else (None, None)


def summarise(rows):
    """Headline figures for the book."""
    rows = list(rows or [])
    first, last = date_range(rows)
    issues = integrity_issues(rows)
    return {
        'entries': len(rows),
        'pages': len(group_pages(rows)),
        'items': len([k for k in item_totals(rows) if k is not None]),
        'total_quantity': page_total(rows),
        'first_date': first,
        'last_date': last,
        'errors': len([i for i in issues if i['severity'] == 'error']),
        'warnings': len([i for i in issues if i['severity'] == 'warning']),
    }


def certificate_text(measured_by, measured_on, entries):
    """The dated 'Measured by me' certificate that closes an MB set."""
    who = (measured_by or '').strip() or '________________'
    when = (measured_on or '').strip() or '____________'
    return ('Measured by me on {date}. The above {n} measurement{s} '
            'were taken at site in my presence and are correct. — {who}'
            .format(date=when, n=entries, s='' if entries == 1 else 's',
                    who=who))
