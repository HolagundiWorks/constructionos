"""Muster / attendance draft from a name list (E1 muster OCR floor).

No tkinter. Turns free-text name lines (typed or from an OCR sidecar) into
attendance draft rows via ``labor_match`` + ``capture``. Nothing is written —
a confirm path (API or GUI) must apply the draft.
"""

import capture
import labor_match

STATUSES = ('Present', 'Absent', 'Half Day', 'Overtime')


def parse_name_lines(text):
    """Split pasted / OCR text into candidate labour names.

    One name per non-empty line. Leading serial numbers (``1.``, ``1)``,
    ``1 -``) are stripped. Comma-separated single lines are also split.
    """
    names = []
    for raw in (text or '').splitlines():
        line = raw.strip()
        if not line:
            continue
        # Strip leading "1." / "1)" / "1 -"
        i = 0
        while i < len(line) and line[i].isdigit():
            i += 1
        if i and i < len(line) and line[i] in '.)-–—:':
            line = line[i + 1:].strip()
        if ',' in line and ' ' not in line.split(',')[0].strip():
            # Unlikely; keep whole line as one name.
            pass
        if line:
            names.append(line)
    return names


def draft_from_names(names, labor_rows, att_date, default_status='Present',
                     hours=8.0, threshold=0.55):
    """Build per-name attendance drafts with match confidence.

    Returns::

        {
          'att_date': str,
          'rows': [{
              'query', 'labor_id', 'matched_name', 'status', 'hours',
              'confidence', 'needs_review', 'candidates'
          }, ...],
          'matched': int,
          'unmatched': int,
        }
    """
    status = default_status if default_status in STATUSES else 'Present'
    try:
        hrs = float(hours)
    except (TypeError, ValueError):
        hrs = 8.0
    rows = []
    matched = unmatched = 0
    for name in names or []:
        m = labor_match.match_one(name, labor_rows, threshold=threshold)
        conf = m['confidence']
        needs = m['labor_id'] is None or conf < capture.REVIEW_THRESHOLD
        if m['labor_id'] is None:
            unmatched += 1
        else:
            matched += 1
        rows.append({
            'query': m['query'],
            'labor_id': m['labor_id'],
            'matched_name': m['matched_name'],
            'status': status,
            'hours': hrs,
            'confidence': conf,
            'needs_review': needs,
            'candidates': m['candidates'],
        })
    return {
        'att_date': att_date or '',
        'rows': rows,
        'matched': matched,
        'unmatched': unmatched,
    }


def draft_from_text(text, labor_rows, att_date, **kwargs):
    """Convenience: parse text then ``draft_from_names``."""
    return draft_from_names(parse_name_lines(text), labor_rows, att_date,
                            **kwargs)


def capture_fields_for_row(row):
    """One attendance row as a ``capture`` field bag (for per-row review UI)."""
    fields = {
        'labor_id': row.get('labor_id'),
        'matched_name': row.get('matched_name') or '',
        'status': row.get('status') or 'Present',
        'hours': row.get('hours') if row.get('hours') is not None else 8.0,
        'query': row.get('query') or '',
    }
    conf = {
        'labor_id': float(row.get('confidence') or 0),
        'matched_name': float(row.get('confidence') or 0),
        'status': 1.0,
        'hours': 1.0,
        'query': 1.0,
    }
    return capture.build_draft(fields, confidence=conf)
