"""Revision-delta maths over drawing elements (pure, Phase D T4).

Align → match by ``ref`` (preferred) or by type+nearest centroid → classify
added / removed / modified / unchanged → quantify with ``takeoff.measure``.

No tkinter, no DB. Alignment helpers accept optional scale/offset so a future
UI can register sheets; default is identity. See ``docs/AI-DRAWING-TAKEOFF.md``.
"""

import math

import drawing_geometry as geom
import takeoff


ADDED, REMOVED, MODIFIED, UNCHANGED = (
    'added', 'removed', 'modified', 'unchanged')
CHANGE_KINDS = (ADDED, REMOVED, MODIFIED, UNCHANGED)


def centroid(points):
    pts = list(points or [])
    if not pts:
        return (0.0, 0.0)
    return (
        sum(p[0] for p in pts) / len(pts),
        sum(p[1] for p in pts) / len(pts),
    )


def transform_points(points, scale=1.0, offset=(0.0, 0.0)):
    """Apply uniform scale about origin then offset. Identity by default."""
    try:
        s = float(scale if scale is not None else 1.0)
    except (TypeError, ValueError):
        s = 1.0
    if s == 0:
        s = 1.0
    ox, oy = offset or (0.0, 0.0)
    try:
        ox, oy = float(ox), float(oy)
    except (TypeError, ValueError):
        ox, oy = 0.0, 0.0
    out = []
    for p in points or []:
        try:
            out.append((float(p[0]) * s + ox, float(p[1]) * s + oy))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def align_elements(elements, scale=1.0, offset=(0.0, 0.0),
                   measure_scale=0.0, linear_unit='m'):
    """Return normalized elements with points transformed for comparison."""
    aligned = []
    for raw in elements or []:
        pts = transform_points(
            geom.normalize_points(raw.get('points')),
            scale=scale, offset=offset)
        copy = dict(raw)
        copy['points'] = pts
        aligned.append(geom.normalize_element(
            copy, scale=measure_scale, linear_unit=linear_unit,
            default_source=raw.get('source') or 'manual'))
    return aligned


def _match_key(el):
    ref = (el.get('ref') or '').strip()
    if ref:
        return ('ref', ref)
    return None


def _nearest(candidates, target, max_dist):
    """Pick nearest candidate of same type by centroid; None if none in range."""
    tx, ty = centroid(target.get('points'))
    ttype = (target.get('type') or '').lower()
    best, best_d = None, None
    for c in candidates:
        if (c.get('type') or '').lower() != ttype:
            continue
        cx, cy = centroid(c.get('points'))
        d = math.hypot(cx - tx, cy - ty)
        if max_dist is not None and d > max_dist:
            continue
        if best_d is None or d < best_d:
            best, best_d = c, d
    return best


def _qty_delta(before, after):
    try:
        a = float((after or {}).get('quantity') or 0)
        b = float((before or {}).get('quantity') or 0)
    except (TypeError, ValueError):
        return 0.0
    return round(a - b, 4)


def _same_geometry(a, b, eps=0.5):
    """True if point lists match within ``eps`` pixel tolerance (order-sensitive)."""
    pa = list(a.get('points') or [])
    pb = list(b.get('points') or [])
    if len(pa) != len(pb):
        return False
    for p, q in zip(pa, pb):
        if math.hypot(p[0] - q[0], p[1] - q[1]) > eps:
            return False
    return True


def diff_elements(from_elements, to_elements, match_radius=50.0, geom_eps=0.5):
    """Element-diff two normalized lists.

    Returns ``{changes: [...], summary: {added, removed, modified, unchanged},
    quantity_deltas: {unit: net}}``.
    """
    fro = list(from_elements or [])
    to = list(to_elements or [])
    from_by_ref = {}
    for el in fro:
        k = _match_key(el)
        if k:
            from_by_ref[k[1]] = el
    to_by_ref = {}
    for el in to:
        k = _match_key(el)
        if k:
            to_by_ref[k[1]] = el

    used_from = set()
    used_to = set()
    changes = []

    # Ref-matched pairs first.
    for ref, tel in to_by_ref.items():
        fel = from_by_ref.get(ref)
        if fel is None:
            continue
        used_from.add(id(fel))
        used_to.add(id(tel))
        if _same_geometry(fel, tel, eps=geom_eps) and (
                float(fel.get('quantity') or 0) == float(tel.get('quantity') or 0)):
            kind = UNCHANGED
        else:
            kind = MODIFIED
        changes.append({
            'change': kind,
            'element_ref': ref,
            'type': tel.get('type') or fel.get('type'),
            'from': fel,
            'to': tel,
            'quantity_delta': _qty_delta(fel, tel),
            'unit': tel.get('unit') or fel.get('unit') or '',
        })

    remaining_from = [el for el in fro if id(el) not in used_from]
    remaining_to = [el for el in to if id(el) not in used_to]

    # Nearest-type match for leftovers without refs.
    still_from = list(remaining_from)
    for tel in list(remaining_to):
        if _match_key(tel):
            # Has ref but no from partner → added
            continue
        match = _nearest(still_from, tel, max_dist=match_radius)
        if match is None:
            continue
        still_from.remove(match)
        remaining_to.remove(tel)
        remaining_from = [el for el in remaining_from if el is not match]
        if _same_geometry(match, tel, eps=geom_eps) and (
                float(match.get('quantity') or 0) == float(tel.get('quantity') or 0)):
            kind = UNCHANGED
        else:
            kind = MODIFIED
        changes.append({
            'change': kind,
            'element_ref': '',
            'type': tel.get('type') or match.get('type'),
            'from': match,
            'to': tel,
            'quantity_delta': _qty_delta(match, tel),
            'unit': tel.get('unit') or match.get('unit') or '',
        })

    for tel in remaining_to:
        changes.append({
            'change': ADDED,
            'element_ref': (tel.get('ref') or ''),
            'type': tel.get('type'),
            'from': None,
            'to': tel,
            'quantity_delta': round(float(tel.get('quantity') or 0), 4),
            'unit': tel.get('unit') or '',
        })

    for fel in remaining_from:
        # Skip those already consumed by nearest match
        if any(c.get('from') is fel for c in changes):
            continue
        changes.append({
            'change': REMOVED,
            'element_ref': (fel.get('ref') or ''),
            'type': fel.get('type'),
            'from': fel,
            'to': None,
            'quantity_delta': round(-float(fel.get('quantity') or 0), 4),
            'unit': fel.get('unit') or '',
        })

    summary = {k: 0 for k in CHANGE_KINDS}
    qty_by_unit = {}
    for c in changes:
        summary[c['change']] = summary.get(c['change'], 0) + 1
        if c['change'] == UNCHANGED:
            continue
        u = c.get('unit') or ''
        try:
            qty_by_unit[u] = round(
                qty_by_unit.get(u, 0.0) + float(c.get('quantity_delta') or 0), 4)
        except (TypeError, ValueError):
            continue

    return {
        'changes': changes,
        'summary': summary,
        'quantity_deltas': qty_by_unit,
        'count': len(changes),
    }


def variation_draft_lines(diff_result, rate=0.0):
    """Build **draft** variation line dicts from a diff (human still confirms).

    Amount is qty_delta × rate (default 0 — QS prices later). Skips unchanged.
    """
    lines = []
    try:
        rate_f = float(rate or 0)
    except (TypeError, ValueError):
        rate_f = 0.0
    for c in (diff_result or {}).get('changes') or []:
        if c.get('change') == UNCHANGED:
            continue
        qty = float(c.get('quantity_delta') or 0)
        if qty == 0 and c.get('change') not in (ADDED, REMOVED, MODIFIED):
            continue
        desc = '{} {} ({})'.format(
            (c.get('change') or '').title(),
            c.get('type') or 'element',
            c.get('element_ref') or 'unmatched')
        lines.append({
            'description': desc,
            'reason': 'Design change',
            'reference': c.get('element_ref') or '',
            'unit': c.get('unit') or '',
            'qty': qty,
            'rate': rate_f,
            'amount': round(qty * rate_f, 2),
            'gated': True,
            'change': c.get('change'),
        })
    return {
        'ok': True,
        'gated': True,
        'lines': lines,
        'count': len(lines),
        'note': 'Draft only — human must raise / approve in Billing › Variations',
    }


def compare_drawings(from_elements, to_elements, align=None, measure_scale=0.0,
                     linear_unit='m', match_radius=50.0):
    """Full compare with optional alignment on the *to* sheet.

    ``align`` is ``{scale, offset: [dx,dy]}`` applied to ``to_elements`` only.
    """
    align = align or {}
    to_aligned = align_elements(
        to_elements,
        scale=align.get('scale', 1.0),
        offset=tuple(align.get('offset') or (0.0, 0.0)),
        measure_scale=measure_scale,
        linear_unit=linear_unit)
    from_norm = [
        geom.normalize_element(e, scale=measure_scale, linear_unit=linear_unit,
                               default_source=(e or {}).get('source') or 'manual')
        for e in (from_elements or [])
    ]
    return diff_elements(from_norm, to_aligned, match_radius=match_radius)
