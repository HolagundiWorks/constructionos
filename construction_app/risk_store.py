"""Risk register persistence (E0 foundation) — the store over ``risk.py``.

DB-only: every function takes an open connection and does **no tkinter**, so the
register is testable against a real temporary SQLite database exactly the way
``journal_post.py`` is. The pure scoring stays in ``risk.py``; this module is the
thin, honest bridge between it and the ``risks`` table.

The one rule that earns the module: **derive on save.** Every write routes
likelihood / impact / impact_value through ``risk.assess`` and writes back the
resulting ``score``, ``band`` and ``expected_exposure``. So a stored derived
value can never disagree with the scoring module — the same discipline the
variations register uses for its amount. And ``summary`` re-assesses from the
stored raw levels rather than trusting the stored derived columns, so even a
hand-edited row rolls up consistently.
"""

from datetime import date

import risk

# Columns a caller may set; everything else on the row is derived or defaulted.
_WRITABLE = (
    'project_id', 'category', 'title', 'description',
    'likelihood', 'impact', 'impact_value', 'owner', 'mitigation',
    'residual_likelihood', 'residual_impact', 'status', 'reference',
    'source', 'decided_by', 'decided_date', 'created_date', 'remarks',
)


def _today():
    return date.today().isoformat()


def _derived(fields):
    """The (score, band, expected_exposure) for a set of fields, via risk.assess.

    Single-sources the scoring so the table and ``risk.py`` cannot disagree."""
    a = risk.assess(
        fields.get('likelihood', 1),
        fields.get('impact', 1),
        value=fields.get('impact_value', 0) or 0,
        residual_likelihood=fields.get('residual_likelihood'),
        residual_impact=fields.get('residual_impact'),
    )
    return {
        'score': a['score'],
        'band': a['band'],
        'expected_exposure': a['expected_exposure'],
    }


def add(conn, **fields):
    """Insert a risk, deriving score/band/exposure. Returns the new row id.

    Unknown keyword fields are ignored (so a caller can pass a whole form dict
    without curating it). ``created_date`` defaults to today; ``source`` to
    'manual'."""
    row = {k: fields[k] for k in _WRITABLE if k in fields}
    row.setdefault('source', 'manual')
    row.setdefault('status', 'Open')
    row.setdefault('created_date', _today())
    row.update(_derived(row))

    cols = list(row.keys())
    placeholders = ', '.join('?' for _ in cols)
    sql = 'INSERT INTO risks ({}) VALUES ({})'.format(
        ', '.join(cols), placeholders)
    cur = conn.execute(sql, [row[c] for c in cols])
    conn.commit()
    return cur.lastrowid


def update(conn, risk_id, **fields):
    """Update the given fields of a risk and re-derive score/band/exposure.

    The derived columns are recomputed from the *merged* row (existing values
    plus the changes), so changing only the impact still rolls the band and
    exposure forward correctly.
    """
    existing = get(conn, risk_id)
    if existing is None:
        return False
    merged = {k: existing[k] for k in existing.keys()}
    for k in _WRITABLE:
        if k in fields:
            merged[k] = fields[k]
    merged.update(_derived(merged))

    cols = [c for c in _WRITABLE if c in merged] + [
        'score', 'band', 'expected_exposure']
    assignments = ', '.join('{} = ?'.format(c) for c in cols)
    conn.execute('UPDATE risks SET {} WHERE id = ?'.format(assignments),
                 [merged[c] for c in cols] + [risk_id])
    conn.commit()
    return True


def set_status(conn, risk_id, status, decided_by=None, decided_date=None):
    """Move a risk's status, stamping who decided and when (the audit the
    roadmap asks for). Accepting or closing a risk is a decision worth a name."""
    conn.execute(
        'UPDATE risks SET status = ?, decided_by = ?, decided_date = ? '
        'WHERE id = ?',
        (status, decided_by, decided_date or _today(), risk_id))
    conn.commit()
    return True


def delete(conn, risk_id):
    conn.execute('DELETE FROM risks WHERE id = ?', (risk_id,))
    conn.commit()
    return True


def get(conn, risk_id):
    """One risk row (sqlite3.Row) or None."""
    cur = conn.execute('SELECT * FROM risks WHERE id = ?', (risk_id,))
    return cur.fetchone()


def list_risks(conn, project_id=None, status=None):
    """Risk rows, optionally filtered by project and/or status, worst-first.

    Ordered by the derived score then exposure so the top of the list is the
    thing to act on first — the same ordering ``risk.rank`` gives in memory."""
    where, params = [], []
    if project_id is not None:
        where.append('project_id = ?')
        params.append(project_id)
    if status is not None:
        where.append('status = ?')
        params.append(status)
    sql = 'SELECT * FROM risks'
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY score DESC, expected_exposure DESC, id'
    return conn.execute(sql, params).fetchall()


def _assess_row(row):
    """Re-assess a stored row from its raw levels, carrying id/title/category.

    Used by ``summary`` so the roll-up rests on ``risk.assess`` again rather than
    trusting the stored derived columns — a hand-edited score can't skew it."""
    a = risk.assess(
        row['likelihood'], row['impact'],
        value=row['impact_value'] or 0,
        residual_likelihood=row['residual_likelihood'],
        residual_impact=row['residual_impact'])
    a['id'] = row['id']
    a['title'] = row['title']
    a['category'] = row['category']
    return a


def summary(conn, project_id=None, top_n=5):
    """Portfolio summary over the stored risks (optionally for one project).

    Delegates the counting/ranking to ``risk.register_summary`` so the register
    and the pure scoring share one definition of 'the top risks'."""
    rows = list_risks(conn, project_id=project_id)
    assessed = [_assess_row(r) for r in rows]
    return risk.register_summary(assessed, top_n=top_n)
