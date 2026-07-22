"""Fuzzy material-name matching (stdlib ``difflib``) — GRN / OCR floor.

No tkinter, no DB. Mirrors ``labor_match`` for the materials master so a
challan line description can resolve to ``materials.id`` with an honest
confidence. Never writes a GRN on its own.
"""

import difflib
import re

_SPACE = re.compile(r'\s+')
_NON_WORD = re.compile(r'[^a-z0-9\s]')


def normalize_name(value):
    s = _NON_WORD.sub(' ', (value or '').lower())
    return _SPACE.sub(' ', s).strip()


def _score(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    if ta and ta <= tb:
        return 0.92
    if tb and tb <= ta:
        return 0.90
    return difflib.SequenceMatcher(None, a, b).ratio()


def match_one(description, material_rows, threshold=0.55, top_n=3):
    """Best material match for a free-text description / OCR line."""
    q = normalize_name(description)
    scored = []
    for row in material_rows or []:
        try:
            mid = int(row['id'])
        except (KeyError, TypeError, ValueError):
            continue
        name = normalize_name(row['name'] if 'name' in row.keys() else '')
        cat = ''
        try:
            cat = normalize_name(row['category'] or '')
        except (KeyError, IndexError, TypeError):
            cat = ''
        conf = _score(q, name)
        if cat:
            conf = max(conf, _score(q, name + ' ' + cat) * 0.97)
        display = (row['name'] if 'name' in row.keys() else '') or ''
        unit = ''
        try:
            unit = row['unit'] or ''
        except (KeyError, IndexError, TypeError):
            unit = ''
        scored.append({
            'material_id': mid,
            'name': display,
            'unit': unit,
            'confidence': round(conf, 3),
        })
    scored.sort(key=lambda c: c['confidence'], reverse=True)
    top = scored[: max(1, int(top_n))]
    best = top[0] if top and top[0]['confidence'] >= threshold else None
    return {
        'query': description or '',
        'material_id': best['material_id'] if best else None,
        'matched_name': best['name'] if best else None,
        'unit': best['unit'] if best else None,
        'confidence': best['confidence'] if best else 0.0,
        'candidates': top,
    }


def match_many(descriptions, material_rows, threshold=0.55):
    return [match_one(d, material_rows, threshold=threshold)
            for d in (descriptions or [])]
