"""Drawing element → takeoff quantity (pure, Phase D deterministic half).

AI / vector sidecars propose *points and classes*; this module turns them into
the same ``takeoff.measure`` quantities the manual canvas uses. No tkinter, no
DB, no model. See ``docs/AI-DRAWING-TAKEOFF.md``.
"""

import takeoff

# Element type (AI / CAD) → measurement kind consumed by takeoff.py.
TYPE_KIND = {
    'wall': takeoff.LENGTH,
    'line': takeoff.LENGTH,
    'length': takeoff.LENGTH,
    'slab': takeoff.AREA,
    'floor': takeoff.AREA,
    'area': takeoff.AREA,
    'polygon': takeoff.AREA,
    'door': takeoff.COUNT,
    'window': takeoff.COUNT,
    'count': takeoff.COUNT,
    'point': takeoff.COUNT,
    'volume': takeoff.VOLUME,
    'excavation': takeoff.VOLUME,
    'room': takeoff.VOLUME,
}

SOURCES = ('ai', 'manual', 'vector')


def kind_for(element_type):
    """Map an element type string to a takeoff kind (default length)."""
    key = (element_type or '').strip().lower()
    return TYPE_KIND.get(key, takeoff.LENGTH)


def normalize_points(points):
    """Coerce ``[[x,y], …]`` / ``[(x,y), …]`` to a list of ``(float, float)``.

    Bad points are skipped; never raises.
    """
    out = []
    for p in points or []:
        try:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                out.append((float(p[0]), float(p[1])))
        except (TypeError, ValueError):
            continue
    return out


def normalize_element(raw, scale=0.0, linear_unit='m', default_source='ai'):
    """Normalize one element dict and attach measured quantity / unit.

    Expected keys (all optional except enough geometry for the kind)::

        type / element_type, points, layer, confidence, source,
        name, depth, ref (stable id across revisions)

    Returns a plain dict ready for store / revision_delta. Quantity is always
    from ``takeoff.measure`` — never an AI-supplied number.
    """
    raw = raw or {}
    etype = (raw.get('type') or raw.get('element_type') or 'wall').strip()
    kind = kind_for(etype)
    points = normalize_points(raw.get('points'))
    try:
        depth = float(raw.get('depth') or 0)
    except (TypeError, ValueError):
        depth = 0.0
    try:
        scale_f = float(scale if scale is not None else raw.get('scale') or 0)
    except (TypeError, ValueError):
        scale_f = 0.0
    unit = takeoff.unit_for(kind, linear_unit or 'm')
    qty = takeoff.measure(kind, points, scale=scale_f, depth=depth)
    try:
        conf = float(raw.get('confidence') if raw.get('confidence') is not None
                     else 1.0)
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    source = (raw.get('source') or default_source or 'ai').strip().lower()
    if source not in SOURCES:
        source = 'ai'
    name = (raw.get('name') or etype or '').strip()
    ref = (raw.get('ref') or raw.get('element_ref') or '').strip()
    return {
        'type': etype,
        'kind': kind,
        'name': name,
        'layer': (raw.get('layer') or '').strip(),
        'points': points,
        'depth': depth,
        'quantity': qty,
        'unit': unit,
        'confidence': conf,
        'source': source,
        'ref': ref,
        'measurable': len(points) >= takeoff.min_points(kind),
    }


def normalize_elements(raw_list, scale=0.0, linear_unit='m', default_source='ai'):
    """Normalize a list of elements; drop empties with no points."""
    out = []
    for raw in raw_list or []:
        el = normalize_element(raw, scale=scale, linear_unit=linear_unit,
                               default_source=default_source)
        if el['points'] or el['kind'] == takeoff.COUNT:
            out.append(el)
    return out


def to_takeoff_items(elements):
    """Shape normalized elements as ``takeoff_items``-like dicts."""
    items = []
    for el in elements or []:
        items.append({
            'name': el.get('name') or el.get('type') or '',
            'category': el.get('type') or '',
            'kind': el.get('kind') or takeoff.LENGTH,
            'unit': el.get('unit') or '',
            'depth': el.get('depth') or 0,
            'quantity': el.get('quantity') or 0,
            'points': list(el.get('points') or []),
        })
    return items


def totals(elements):
    """Footing by unit via ``takeoff.totals_by_unit``."""
    return takeoff.totals_by_unit(to_takeoff_items(elements))


def ingest_vector_payload(payload, scale=0.0, linear_unit='m'):
    """Accept an already-parsed vector JSON payload (future DXF sidecar).

    ``payload`` may be ``{elements: [...], scale?, unit?}`` or a bare list.
    No DXF/DWG parsing in-core (stdlib / no-pip) — the sidecar does that.
    """
    if isinstance(payload, list):
        elements = payload
        scale_f, unit = scale, linear_unit
    else:
        payload = payload or {}
        elements = payload.get('elements') or payload.get('features') or []
        try:
            scale_f = float(payload.get('scale') if payload.get('scale') is not None
                            else scale or 0)
        except (TypeError, ValueError):
            scale_f = float(scale or 0)
        unit = payload.get('unit') or linear_unit or 'm'
    normalized = normalize_elements(
        elements, scale=scale_f, linear_unit=unit, default_source='vector')
    return {
        'ok': True,
        'scale': scale_f,
        'unit': unit,
        'elements': normalized,
        'totals': totals(normalized),
        'count': len(normalized),
        'note': 'Parsed JSON only — DXF/DWG weights stay in a local sidecar',
    }
