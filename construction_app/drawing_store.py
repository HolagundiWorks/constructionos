"""Drawing elements + revision-delta persistence (Phase D store).

No tkinter. Pure scoring/geometry stays in ``drawing_geometry`` /
``revision_delta``; this module is the SQL bridge. AI proposes elements;
confirm endpoints write only after a human calls them.
"""

import json
from datetime import date

import drawing_geometry as geom
import revision_delta as delta


def _today():
    return date.today().isoformat()


def _points_json(points):
    return json.dumps([[p[0], p[1]] for p in (points or [])])


def _parse_points(raw):
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return geom.normalize_points(raw)
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return geom.normalize_points(data)


def list_elements(conn, drawing_id, reviewed_only=False):
    """Return element rows for a drawing (dicts with parsed points)."""
    sql = 'SELECT * FROM drawing_elements WHERE drawing_id = ?'
    params = [drawing_id]
    if reviewed_only:
        sql += " AND reviewed_at IS NOT NULL AND reviewed_at != ''"
    sql += ' ORDER BY id'
    rows = []
    for r in conn.execute(sql, params):
        d = dict(r)
        d['points'] = _parse_points(d.get('points'))
        rows.append(d)
    return rows


def replace_elements(conn, drawing_id, elements, scale=0.0, linear_unit='m',
                     reviewed_by=None, mark_reviewed=False):
    """Replace all elements on a drawing with normalized ``elements``.

    Returns ``{count, totals, ids}``. Does **not** auto-review unless
    ``mark_reviewed`` (manual confirm path).
    """
    drawing_id = int(drawing_id)
    normalized = geom.normalize_elements(
        elements, scale=scale, linear_unit=linear_unit or 'm')
    conn.execute('DELETE FROM drawing_elements WHERE drawing_id = ?',
                 (drawing_id,))
    ids = []
    reviewed_at = _today() if mark_reviewed else None
    reviewer = reviewed_by if mark_reviewed else None
    for el in normalized:
        cur = conn.execute(
            'INSERT INTO drawing_elements ('
            'drawing_id, element_ref, element_type, name, layer, kind, '
            'unit, depth, quantity, points, confidence, source, '
            'reviewed_by, reviewed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (
                drawing_id,
                el.get('ref') or '',
                el.get('type') or '',
                el.get('name') or '',
                el.get('layer') or '',
                el.get('kind') or '',
                el.get('unit') or '',
                el.get('depth') or 0,
                el.get('quantity') or 0,
                _points_json(el.get('points')),
                el.get('confidence') if el.get('confidence') is not None else 1.0,
                el.get('source') or 'ai',
                reviewer,
                reviewed_at,
            ))
        ids.append(cur.lastrowid)
    conn.commit()
    return {
        'ok': True,
        'drawing_id': drawing_id,
        'count': len(ids),
        'ids': ids,
        'totals': geom.totals(normalized),
        'elements': normalized,
    }


def elements_as_normalized(conn, drawing_id):
    """Load stored rows reshaped for ``revision_delta`` / geometry."""
    out = []
    for row in list_elements(conn, drawing_id):
        out.append({
            'type': row.get('element_type') or '',
            'name': row.get('name') or '',
            'layer': row.get('layer') or '',
            'points': row.get('points') or [],
            'depth': row.get('depth') or 0,
            'confidence': row.get('confidence') if row.get('confidence') is not None
            else 1.0,
            'source': row.get('source') or 'manual',
            'ref': row.get('element_ref') or '',
            'quantity': row.get('quantity') or 0,
            'unit': row.get('unit') or '',
            'kind': row.get('kind') or '',
        })
    return out


def compute_revision_delta(conn, from_drawing_id, to_drawing_id, align=None,
                           measure_scale=0.0, linear_unit='m'):
    """Diff two drawings' stored elements (read-only — does not persist)."""
    fro = elements_as_normalized(conn, from_drawing_id)
    to = elements_as_normalized(conn, to_drawing_id)
    # Prefer scale/unit from the *to* drawing header when present.
    row = conn.execute(
        'SELECT scale, unit FROM drawings WHERE id = ?',
        (to_drawing_id,)).fetchone()
    if row is not None:
        if measure_scale in (None, 0, 0.0) and row['scale']:
            try:
                measure_scale = float(row['scale'] or 0)
            except (TypeError, ValueError):
                measure_scale = 0.0
        if not linear_unit and row['unit']:
            linear_unit = row['unit'] or 'm'
    result = delta.compare_drawings(
        fro, to, align=align, measure_scale=measure_scale,
        linear_unit=linear_unit or 'm')
    result['from_drawing_id'] = int(from_drawing_id)
    result['to_drawing_id'] = int(to_drawing_id)
    result['ok'] = True
    return result


def save_element_changes(conn, from_drawing_id, to_drawing_id, diff_result,
                         variation_id=None, accepted_by=None):
    """Persist ``element_changes`` from a diff result. Returns inserted ids."""
    ids = []
    accepted_at = _today()
    for c in (diff_result or {}).get('changes') or []:
        if c.get('change') == delta.UNCHANGED:
            continue
        cur = conn.execute(
            'INSERT INTO element_changes ('
            'from_drawing_id, to_drawing_id, element_ref, change_kind, '
            'element_type, quantity_delta, unit, variation_id, '
            'accepted_by, accepted_at, detail_json) VALUES '
            '(?,?,?,?,?,?,?,?,?,?,?)',
            (
                int(from_drawing_id),
                int(to_drawing_id),
                c.get('element_ref') or '',
                c.get('change') or '',
                c.get('type') or '',
                float(c.get('quantity_delta') or 0),
                c.get('unit') or '',
                variation_id,
                accepted_by,
                accepted_at,
                json.dumps({
                    'from_qty': (c.get('from') or {}).get('quantity'),
                    'to_qty': (c.get('to') or {}).get('quantity'),
                }),
            ))
        ids.append(cur.lastrowid)
    conn.commit()
    return {'ok': True, 'ids': ids, 'count': len(ids)}


def list_changes(conn, from_drawing_id=None, to_drawing_id=None, limit=100):
    sql = 'SELECT * FROM element_changes WHERE 1=1'
    params = []
    if from_drawing_id is not None:
        sql += ' AND from_drawing_id = ?'
        params.append(from_drawing_id)
    if to_drawing_id is not None:
        sql += ' AND to_drawing_id = ?'
        params.append(to_drawing_id)
    sql += ' ORDER BY id DESC LIMIT ?'
    params.append(int(limit))
    return [dict(r) for r in conn.execute(sql, params)]


def sync_elements_to_takeoff(conn, drawing_id, takeoff_id=None, name=None):
    """Create/update a takeoff from reviewed (or all) drawing elements.

    Returns takeoff id. Quantities come from stored measured columns.
    """
    from datetime import datetime

    import takeoff_store

    els = elements_as_normalized(conn, drawing_id)
    if not els:
        return {'ok': False, 'reason': 'no elements on drawing'}
    drow = conn.execute(
        'SELECT * FROM drawings WHERE id = ?', (drawing_id,)).fetchone()
    if drow is None:
        return {'ok': False, 'reason': 'drawing not found'}
    d = dict(drow)
    scale = float(d.get('scale') or 0)
    unit = d.get('unit') or 'm'
    items = geom.to_takeoff_items(
        geom.normalize_elements(els, scale=scale, linear_unit=unit))
    header = {
        'project_id': d.get('project_id'),
        'site_id': d.get('site_id'),
        'name': name or ('Drawing {} {}'.format(
            d.get('drawing_no') or drawing_id, d.get('revision') or '')).strip(),
        'source': d.get('source_file') or '',
        'page': int(d.get('page') or 1),
        'scale': scale,
        'unit': unit,
        'notes': 'Synced from drawing_elements id={}'.format(drawing_id),
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }
    if takeoff_id:
        tid = takeoff_store.save(conn, header, items, takeoff_id=takeoff_id)
    else:
        tid = takeoff_store.save(conn, header, items)
    conn.execute(
        'UPDATE drawings SET takeoff_id = ? WHERE id = ?', (tid, drawing_id))
    conn.commit()
    return {'ok': True, 'takeoff_id': tid, 'item_count': len(items)}
