"""Opportunity register persistence (Part 2) — the store over ``opportunity.py``.

DB-only, tkinter-free, so it is testable against a temporary SQLite database the
same way ``risk_store`` is. It mirrors that module deliberately — same
derive-on-save discipline (score/priority/band/expected_value recomputed through
``opportunity.py`` on every write, so a stored value can't drift), same
re-assess-in-summary — because a risk register and an opportunity register are
the same machine pointed at the upside.
"""

from datetime import date

import opportunity

_WRITABLE = (
    'project_id', 'category', 'title', 'description',
    'likelihood', 'impact', 'urgency', 'value', 'response',
    'owner', 'action_plan', 'target_date', 'status', 'reference',
    'source', 'decided_by', 'decided_date', 'created_date', 'remarks',
)

_DERIVED = ('score', 'priority', 'band', 'expected_value')


def _today():
    return date.today().isoformat()


def _derived(fields):
    a = opportunity.assess(
        fields.get('likelihood', 1),
        fields.get('impact', 1),
        value=fields.get('value', 0) or 0,
        urgency=fields.get('urgency'))
    return {
        'score': a['score'],
        'priority': a['priority'],
        'band': a['band'],
        'expected_value': a['expected_value'],
    }


def add(conn, **fields):
    """Insert an opportunity, deriving score/priority/band/expected_value.
    Returns the new row id."""
    row = {k: fields[k] for k in _WRITABLE if k in fields}
    if 'response' in row:
        row['response'] = opportunity.valid_response(row['response'])
    row.setdefault('source', 'manual')
    row.setdefault('status', 'Open')
    row.setdefault('created_date', _today())
    row.update(_derived(row))

    cols = list(row.keys())
    sql = 'INSERT INTO opportunities ({}) VALUES ({})'.format(
        ', '.join(cols), ', '.join('?' for _ in cols))
    cur = conn.execute(sql, [row[c] for c in cols])
    conn.commit()
    return cur.lastrowid


def update(conn, opp_id, **fields):
    existing = get(conn, opp_id)
    if existing is None:
        return False
    merged = {k: existing[k] for k in existing.keys()}
    for k in _WRITABLE:
        if k in fields:
            merged[k] = fields[k]
    if 'response' in fields:
        merged['response'] = opportunity.valid_response(merged.get('response'))
    merged.update(_derived(merged))

    cols = [c for c in _WRITABLE if c in merged] + list(_DERIVED)
    assignments = ', '.join('{} = ?'.format(c) for c in cols)
    conn.execute('UPDATE opportunities SET {} WHERE id = ?'.format(assignments),
                 [merged[c] for c in cols] + [opp_id])
    conn.commit()
    return True


def set_status(conn, opp_id, status, decided_by=None, decided_date=None):
    """Move an opportunity's status (Pursuing / Realized / Declined), stamping
    who decided and when — realising an opportunity is worth a name too."""
    conn.execute(
        'UPDATE opportunities SET status = ?, decided_by = ?, decided_date = ? '
        'WHERE id = ?',
        (status, decided_by, decided_date or _today(), opp_id))
    conn.commit()
    return True


def delete(conn, opp_id):
    conn.execute('DELETE FROM opportunities WHERE id = ?', (opp_id,))
    conn.commit()
    return True


def get(conn, opp_id):
    return conn.execute('SELECT * FROM opportunities WHERE id = ?',
                        (opp_id,)).fetchone()


def list_opportunities(conn, project_id=None, status=None):
    """Opportunity rows, best-first, optionally filtered by project/status."""
    where, params = [], []
    if project_id is not None:
        where.append('project_id = ?')
        params.append(project_id)
    if status is not None:
        where.append('status = ?')
        params.append(status)
    sql = 'SELECT * FROM opportunities'
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY priority DESC, score DESC, expected_value DESC, id'
    return conn.execute(sql, params).fetchall()


def _assess_row(row):
    a = opportunity.assess(row['likelihood'], row['impact'],
                           value=row['value'] or 0, urgency=row['urgency'])
    a['id'] = row['id']
    a['title'] = row['title']
    a['category'] = row['category']
    return a


def summary(conn, project_id=None, top_n=5):
    """Portfolio summary over the stored opportunities, via
    ``opportunity.register_summary`` (re-assessed from raw levels, so a
    hand-edited row still rolls up honestly)."""
    rows = list_opportunities(conn, project_id=project_id)
    return opportunity.register_summary([_assess_row(r) for r in rows],
                                        top_n=top_n)
