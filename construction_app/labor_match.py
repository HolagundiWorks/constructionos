"""Fuzzy labour-name matching (stdlib ``difflib``) — muster / OCR floor.

No tkinter, no DB. Given a free-typed or OCR'd name and a labour master list,
return the best match with an honest confidence (0..1). Used by muster draft
capture; never writes attendance on its own.
"""

import difflib
import re

_SPACE = re.compile(r'\s+')
_NON_WORD = re.compile(r'[^a-z0-9\s]')


def normalize_name(value):
    """Lowercase, strip punctuation, collapse spaces. Empty → ''."""
    s = _NON_WORD.sub(' ', (value or '').lower())
    return _SPACE.sub(' ', s).strip()


def _score(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Exact token containment (OCR often drops a middle name).
    ta, tb = set(a.split()), set(b.split())
    if ta and ta <= tb:
        return 0.92
    if tb and tb <= ta:
        return 0.90
    return difflib.SequenceMatcher(None, a, b).ratio()


def match_one(name, labor_rows, threshold=0.55, top_n=3):
    """Best labour match for ``name``.

    ``labor_rows`` is an iterable of mapping-like rows with at least
    ``id`` and ``name`` (optional ``father_name``). Returns::

        {
          'query': str,
          'labor_id': int|None,
          'matched_name': str|None,
          'confidence': float,
          'candidates': [{labor_id, name, confidence}, ...],
        }
    """
    q = normalize_name(name)
    scored = []
    for row in labor_rows or []:
        try:
            lid = int(row['id'])
        except (KeyError, TypeError, ValueError):
            continue
        primary = normalize_name(row['name'] if 'name' in row.keys() else '')
        father = ''
        try:
            father = normalize_name(row['father_name'] or '')
        except (KeyError, IndexError, TypeError):
            father = ''
        # Score against name; boost slightly when father also overlaps.
        conf = _score(q, primary)
        if father and q:
            conf = max(conf, _score(q, primary + ' ' + father) * 0.98)
        display = (row['name'] if 'name' in row.keys() else '') or ''
        scored.append({
            'labor_id': lid,
            'name': display,
            'confidence': round(conf, 3),
        })
    scored.sort(key=lambda c: c['confidence'], reverse=True)
    top = scored[: max(1, int(top_n))]
    best = top[0] if top and top[0]['confidence'] >= threshold else None
    return {
        'query': name or '',
        'labor_id': best['labor_id'] if best else None,
        'matched_name': best['name'] if best else None,
        'confidence': best['confidence'] if best else 0.0,
        'candidates': top,
    }


def match_many(names, labor_rows, threshold=0.55):
    """Match an ordered list of names. Returns a list of ``match_one`` results."""
    return [match_one(n, labor_rows, threshold=threshold) for n in (names or [])]
