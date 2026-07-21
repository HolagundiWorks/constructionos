"""Lessons-learned register persistence (Part 2) — the store over ``lessons``.

DB-only, tkinter-free, testable against a temporary SQLite database like the
risk and opportunity stores. It normalises the vocabulary on save (outcome and
source coerced to known values through ``lessons``), so a stored row always
speaks the register's language, and it can seed a lesson **straight from a risk
or opportunity** (``from_risk`` / ``from_opportunity``) so the source that taught
the lesson is linked, not retyped.
"""

from datetime import date

import lessons

_WRITABLE = (
    'project_id', 'category', 'title', 'description', 'outcome',
    'root_cause', 'recommendation', 'source', 'source_id', 'impact_value',
    'tags', 'status', 'owner', 'created_date', 'remarks',
)


def _today():
    return date.today().isoformat()


def add(conn, **fields):
    """Insert a lesson, normalising outcome/source. Returns the new row id."""
    row = {k: fields[k] for k in _WRITABLE if k in fields}
    row['outcome'] = lessons.normalize_outcome(row.get('outcome'))
    row['source'] = lessons.normalize_source(row.get('source'))
    row.setdefault('status', lessons.OPEN)
    row.setdefault('created_date', _today())

    cols = list(row.keys())
    sql = 'INSERT INTO lessons_learned ({}) VALUES ({})'.format(
        ', '.join(cols), ', '.join('?' for _ in cols))
    cur = conn.execute(sql, [row[c] for c in cols])
    conn.commit()
    return cur.lastrowid


def from_risk(conn, risk_row, recommendation='', **overrides):
    """Capture a lesson from a risk that materialised — carrying its project,
    category and title, and linking back by ``source_id``. The negative-outcome
    default reflects that a realised risk is usually a 'what went wrong'."""
    fields = {
        'project_id': risk_row['project_id'],
        'category': risk_row['category'],
        'title': risk_row['title'],
        'description': risk_row['description'] if 'description'
        in risk_row.keys() else '',
        'outcome': lessons.NEGATIVE,
        'recommendation': recommendation,
        'source': lessons.RISK,
        'source_id': risk_row['id'],
    }
    fields.update(overrides)
    return add(conn, **fields)


def from_opportunity(conn, opp_row, recommendation='', **overrides):
    """Capture a lesson from an opportunity — a realised one is a 'what went
    well' worth repeating; a missed one, a recommendation for next time."""
    fields = {
        'project_id': opp_row['project_id'],
        'category': opp_row['category'],
        'title': opp_row['title'],
        'outcome': lessons.POSITIVE,
        'recommendation': recommendation,
        'source': lessons.OPPORTUNITY,
        'source_id': opp_row['id'],
    }
    fields.update(overrides)
    return add(conn, **fields)


def update(conn, lesson_id, **fields):
    existing = get(conn, lesson_id)
    if existing is None:
        return False
    merged = {k: existing[k] for k in existing.keys()}
    for k in _WRITABLE:
        if k in fields:
            merged[k] = fields[k]
    merged['outcome'] = lessons.normalize_outcome(merged.get('outcome'))
    merged['source'] = lessons.normalize_source(merged.get('source'))

    cols = [c for c in _WRITABLE if c in merged]
    assignments = ', '.join('{} = ?'.format(c) for c in cols)
    conn.execute('UPDATE lessons_learned SET {} WHERE id = ?'.format(assignments),
                 [merged[c] for c in cols] + [lesson_id])
    conn.commit()
    return True


def set_status(conn, lesson_id, status):
    """Move a lesson's status. Setting it to 'Applied' is how the register
    records that the insight was actually carried into future planning."""
    conn.execute('UPDATE lessons_learned SET status = ? WHERE id = ?',
                 (status, lesson_id))
    conn.commit()
    return True


def delete(conn, lesson_id):
    conn.execute('DELETE FROM lessons_learned WHERE id = ?', (lesson_id,))
    conn.commit()
    return True


def get(conn, lesson_id):
    return conn.execute('SELECT * FROM lessons_learned WHERE id = ?',
                        (lesson_id,)).fetchone()


def list_lessons(conn, project_id=None, category=None, status=None):
    """Lesson rows, newest first, optionally filtered by project/category/status."""
    where, params = [], []
    if project_id is not None:
        where.append('project_id = ?')
        params.append(project_id)
    if category is not None:
        where.append('category = ?')
        params.append(category)
    if status is not None:
        where.append('status = ?')
        params.append(status)
    sql = 'SELECT * FROM lessons_learned'
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY created_date DESC, id DESC'
    return conn.execute(sql, params).fetchall()


def feed_forward(conn, project_id=None):
    """The lessons still to be applied — recommendations captured but not yet
    carried into future planning. The register's actionable queue."""
    rows = list_lessons(conn, project_id=project_id)
    return [r for r in rows if lessons.is_feed_forward(r)]


def summary(conn, project_id=None):
    """Roll the stored lessons up via ``lessons.summary`` (counts by category and
    outcome, how many applied, and the feed-forward queue)."""
    return lessons.summary(list_lessons(conn, project_id=project_id))
