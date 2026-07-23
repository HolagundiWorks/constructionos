"""Weekly commitments CRUD + reason-code enrichment for look-ahead.

No tkinter. PPC stays binary (Done / Not done); miss reasons come from
``planning.REASONS``.
"""

import planning


_FIELDS = (
    'site_id', 'week_start', 'task', 'responsible', 'planned_qty',
    'unit', 'status', 'reason', 'remarks',
)


def _i(v):
    if v is None or v == '':
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _f(v, default=0.0):
    try:
        return float(v if v is not None else default)
    except (TypeError, ValueError):
        return default


def _norm_status(value):
    raw = (value or '').strip() or planning.NOT_DONE
    if raw.lower() in ('done', 'complete', 'completed', 'yes'):
        return planning.DONE
    if raw.lower() in ('partial', 'part'):
        # Binary honesty: Partial is a miss for PPC.
        return planning.NOT_DONE
    return planning.DONE if raw == planning.DONE else planning.NOT_DONE


def _norm_reason(value, status):
    reason = (value or '').strip()
    if status == planning.DONE:
        return ''
    if reason and reason not in planning.REASONS:
        # Allow free text but prefer catalogue; keep as-is under Other bucket.
        return reason
    return reason


def reasons():
    return list(planning.REASONS)


def get(conn, commitment_id):
    row = conn.execute(
        'SELECT * FROM commitments WHERE id = ?', (int(commitment_id),)
    ).fetchone()
    return dict(row) if row else None


def create(conn, body):
    body = dict(body or {})
    status = _norm_status(body.get('status'))
    reason = _norm_reason(body.get('reason'), status)
    if status != planning.DONE and not reason:
        # Soft default — client should send a reason; empty is allowed so a
        # mid-week plan can be saved before the miss is explained.
        reason = ''
    cur = conn.execute(
        'INSERT INTO commitments (site_id, week_start, task, responsible, '
        'planned_qty, unit, status, reason, remarks) '
        'VALUES (?,?,?,?,?,?,?,?,?)',
        (
            _i(body.get('site_id')),
            str(body.get('week_start') or ''),
            str(body.get('task') or ''),
            str(body.get('responsible') or ''),
            _f(body.get('planned_qty')),
            str(body.get('unit') or ''),
            status,
            reason,
            str(body.get('remarks') or ''),
        ))
    conn.commit()
    return get(conn, cur.lastrowid)


def update(conn, commitment_id, body):
    existing = get(conn, commitment_id)
    if existing is None:
        return None
    body = dict(body or {})
    merged = dict(existing)
    for k in _FIELDS:
        if k in body:
            merged[k] = body[k]
    status = _norm_status(merged.get('status'))
    reason = _norm_reason(merged.get('reason'), status)
    conn.execute(
        'UPDATE commitments SET site_id=?, week_start=?, task=?, responsible=?, '
        'planned_qty=?, unit=?, status=?, reason=?, remarks=? WHERE id=?',
        (
            _i(merged.get('site_id')),
            str(merged.get('week_start') or ''),
            str(merged.get('task') or ''),
            str(merged.get('responsible') or ''),
            _f(merged.get('planned_qty')),
            str(merged.get('unit') or ''),
            status,
            reason,
            str(merged.get('remarks') or ''),
            int(commitment_id),
        ))
    conn.commit()
    return get(conn, commitment_id)


def delete(conn, commitment_id):
    conn.execute('DELETE FROM commitments WHERE id = ?', (int(commitment_id),))
    conn.commit()
    return True


def mark_done(conn, commitment_id, done=True, reason=''):
    """Binary Done / Not done toggle; clears reason when done."""
    existing = get(conn, commitment_id)
    if existing is None:
        return None
    status = planning.DONE if done else planning.NOT_DONE
    reason = '' if done else _norm_reason(reason or existing.get('reason'), status)
    return update(conn, commitment_id, {'status': status, 'reason': reason})


def enrich_lookahead(payload):
    """Add reason catalogue + binary Done hint to a lookahead payload."""
    out = dict(payload or {})
    out['reasons'] = reasons()
    out['statuses'] = [planning.DONE, planning.NOT_DONE]
    out['ppc_note'] = (
        'PPC is binary: only Done counts. A part-finished task is a miss — '
        'name the constraint in reason.'
    )
    return out
