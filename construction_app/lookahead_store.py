"""Look-ahead / PPC assembly over ``commitments`` (CT-9).

Pure maths lives in ``planning.py``. This module loads commitments from SQLite
(optionally scoped by project→site or site) and returns planned-vs-done rows
plus PPC figures for the JSON API.

No tkinter.
"""

import planning


def _site_for_project(conn, project_id):
    if not project_id:
        return None
    row = conn.execute(
        'SELECT site_id FROM projects WHERE id = ?', (project_id,)
    ).fetchone()
    return row['site_id'] if row else None


def load_commitments(conn, project_id=None, site_id=None, weeks=None):
    """Return commitment rows (sqlite Row / dict-like), newest week first.

    ``weeks`` limits to the N most recent distinct ``week_start`` values when
    set to a positive int.
    """
    if project_id and not site_id:
        site_id = _site_for_project(conn, int(project_id))
    where, params = [], []
    if site_id:
        where.append('site_id = ?')
        params.append(int(site_id))
    sql = 'SELECT * FROM commitments'
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY week_start DESC, id DESC'
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    if weeks:
        try:
            n = int(weeks)
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            seen, keep = [], set()
            for r in rows:
                ws = r.get('week_start') or ''
                if ws not in keep:
                    if len(seen) >= n:
                        continue
                    keep.add(ws)
                    seen.append(ws)
            rows = [r for r in rows if (r.get('week_start') or '') in keep]
    return rows


def lookahead(conn, project_id=None, site_id=None, weeks=None):
    """Assemble look-ahead payload: items, PPC overall, per-week trend, misses."""
    items = load_commitments(conn, project_id=project_id, site_id=site_id,
                             weeks=weeks)
    # Resolve site names for display.
    site_ids = {r.get('site_id') for r in items if r.get('site_id')}
    names = {}
    if site_ids:
        placeholders = ','.join('?' * len(site_ids))
        for r in conn.execute(
                'SELECT id, name FROM sites WHERE id IN ({})'.format(
                    placeholders), list(site_ids)):
            names[r['id']] = r['name']
    for r in items:
        r['site'] = names.get(r.get('site_id'))
        r['done'] = (r.get('status') or '') == planning.DONE

    by_week = {}
    for r in items:
        by_week.setdefault(r.get('week_start') or '', []).append(r)
    trend = planning.ppc_trend(by_week)
    overall = planning.ppc(items)
    misses = planning.reasons_for_misses(items)
    cols = [
        {'key': 'week_start', 'label': 'Week'},
        {'key': 'task', 'label': 'Task'},
        {'key': 'site', 'label': 'Site'},
        {'key': 'responsible', 'label': 'Responsible'},
        {'key': 'planned_qty', 'label': 'Planned qty', 'align': 'right'},
        {'key': 'unit', 'label': 'Unit'},
        {'key': 'status', 'label': 'Status'},
        {'key': 'reason', 'label': 'Miss reason'},
    ]
    return {
        'project_id': int(project_id) if project_id else None,
        'site_id': int(site_id) if site_id else (
            _site_for_project(conn, int(project_id)) if project_id else None),
        'cols': cols,
        'items': items,
        'ppc': overall,
        'weeks': [{'week': w, 'ppc': p} for w, p in trend['weeks']],
        'ppc_average': trend['average'],
        'miss_reasons': [{'reason': r, 'count': c} for r, c in misses],
        'promised': len(items),
        'done': sum(1 for r in items if r.get('done')),
    }
