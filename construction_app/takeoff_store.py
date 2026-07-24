"""Takeoff persistence + draft-estimate bridge (Phase D API half).

No tkinter. Mirrors the save / load / send-to-estimate path in
``tab_takeoff.py`` so WinUI and agents share one store. Geometry stays in
``takeoff.py``.
"""

import json
from datetime import date, datetime

import takeoff as takeoff_math


def _points_json(points):
    return json.dumps([[float(p[0]), float(p[1])] for p in (points or [])])


def _parse_points(raw):
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return [(float(p[0]), float(p[1])) for p in raw
                if isinstance(p, (list, tuple)) and len(p) >= 2]
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    out = []
    for p in data or []:
        try:
            out.append((float(p[0]), float(p[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def list_takeoffs(conn, project_id=None, site_id=None, limit=50):
    sql = ('SELECT id, project_id, site_id, name, source, page, scale, unit, '
           'notes, created_at FROM takeoffs WHERE 1=1')
    params = []
    if project_id not in (None, ''):
        sql += ' AND project_id = ?'
        params.append(int(project_id))
    if site_id not in (None, ''):
        sql += ' AND site_id = ?'
        params.append(int(site_id))
    sql += ' ORDER BY id DESC LIMIT ?'
    params.append(int(limit))
    return [dict(r) for r in conn.execute(sql, params)]


def get_takeoff(conn, takeoff_id):
    row = conn.execute(
        'SELECT * FROM takeoffs WHERE id = ?', (int(takeoff_id),)).fetchone()
    if row is None:
        return None
    header = dict(row)
    items = []
    for r in conn.execute(
            'SELECT * FROM takeoff_items WHERE takeoff_id = ? ORDER BY id',
            (int(takeoff_id),)):
        it = dict(r)
        it['points'] = _parse_points(it.get('points'))
        items.append(it)
    header['items'] = items
    header['totals'] = takeoff_math.totals_by_unit(items)
    return header


def save(conn, header, items, takeoff_id=None):
    """Insert or replace a takeoff + items. Recomputes quantity via takeoff.measure."""
    header = header or {}
    name = (header.get('name') or 'Takeoff').strip() or 'Takeoff'
    scale = float(header.get('scale') or 0)
    unit = header.get('unit') or 'm'
    page = int(header.get('page') or 1)
    created = header.get('created_at') or datetime.now().isoformat(
        timespec='seconds')
    if takeoff_id:
        conn.execute(
            'UPDATE takeoffs SET project_id=?, site_id=?, name=?, source=?, '
            'page=?, scale=?, unit=?, notes=? WHERE id=?',
            (
                header.get('project_id'), header.get('site_id'), name,
                header.get('source') or '', page, scale, unit,
                header.get('notes') or '', int(takeoff_id),
            ))
        conn.execute('DELETE FROM takeoff_items WHERE takeoff_id=?',
                     (int(takeoff_id),))
        tid = int(takeoff_id)
    else:
        cur = conn.execute(
            'INSERT INTO takeoffs (project_id, site_id, name, source, page, '
            'scale, unit, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?)',
            (
                header.get('project_id'), header.get('site_id'), name,
                header.get('source') or '', page, scale, unit,
                header.get('notes') or '', created,
            ))
        tid = cur.lastrowid

    for it in items or []:
        kind = (it.get('kind') or takeoff_math.LENGTH).strip().lower()
        points = it.get('points') or []
        if isinstance(points, str):
            points = _parse_points(points)
        depth = float(it.get('depth') or 0)
        qty = takeoff_math.measure(kind, points, scale=scale, depth=depth)
        item_unit = it.get('unit') or takeoff_math.unit_for(kind, unit)
        conn.execute(
            'INSERT INTO takeoff_items (takeoff_id, name, category, kind, '
            'unit, depth, quantity, points) VALUES (?,?,?,?,?,?,?,?)',
            (
                tid,
                it.get('name') or '',
                it.get('category') or '',
                kind,
                item_unit,
                depth,
                qty,
                _points_json(points),
            ))
    conn.commit()
    return tid


def to_estimate(conn, takeoff_id, title=None):
    """Create a **Draft** estimate from takeoff items (rates 0 — QS prices).

    Returns ``{ok, estimate_id, item_count}``.
    """
    data = get_takeoff(conn, takeoff_id)
    if not data:
        return {'ok': False, 'reason': 'takeoff not found'}
    items = data.get('items') or []
    if not items:
        return {'ok': False, 'reason': 'takeoff has no items'}
    n = conn.execute('SELECT COUNT(*) AS c FROM estimates').fetchone()['c']
    est_title = title or ('Takeoff: ' + (data.get('name') or ''))
    cur = conn.execute(
        'INSERT INTO estimates (est_number, title, site_id, estimate_date, '
        "status, contingency_pct, gst_pct) VALUES (?, ?, ?, ?, 'Draft', 0, 18)",
        (
            'EST-{}'.format(n + 1),
            est_title,
            data.get('site_id'),
            date.today().isoformat(),
        ))
    eid = cur.lastrowid
    for it in items:
        conn.execute(
            'INSERT INTO estimate_items (estimate_id, item_code, description, '
            'unit, qty, rate, amount) VALUES (?, ?, ?, ?, ?, 0, 0)',
            (eid, '', it.get('name') or '', it.get('unit') or '',
             float(it.get('quantity') or 0)))
    conn.commit()
    return {
        'ok': True,
        'estimate_id': eid,
        'item_count': len(items),
        'gated': False,
        'note': 'Draft estimate — open Billing › Estimates to price',
    }


def delete_takeoff(conn, takeoff_id):
    conn.execute('DELETE FROM takeoffs WHERE id = ?', (int(takeoff_id),))
    conn.commit()
    return True
