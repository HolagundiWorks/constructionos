"""Multi-firm / multi-year company files (Phase 7).

The app is one SQLite file. A contractor who runs two entities, or who wants a
clean file each financial year, needs **several** — and a way to move between
them without touching the filesystem.

This module owns:

- a small **registry** of known company files (name + path), kept as JSON next
  to the code so it survives switching between files (it cannot live *inside*
  a company file, or you could never find the others);
- **carry-forward**, which copies the masters — sites, clients, vendors,
  materials, labour, the chart of accounts, the rate book, firm settings — from
  last year's file into a fresh one, so starting a new year doesn't mean
  retyping everything.

No tkinter here: the registry is plain JSON and carry-forward takes two open
connections, so both are testable headlessly.

Switching the active file sets ``db.DB_PATH``. Connections in this app are
short-lived (opened and closed per operation), so the next operation simply
opens the new file — but open views still show the old data, which is why the
UI asks for a restart after a switch, exactly like Restore does.
"""

import json
import os
import re
import sqlite3

# Registry lives beside the code, not beside any one company file.
REGISTRY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'companies.json')

# Masters worth carrying into a new year / new firm. Ordered so that parents
# land before anything that references them. Deliberately excludes every
# transaction table (bills, payments, measurements, the journal…) — a new year
# starts with an empty ledger.
MASTER_TABLES = [
    'app_settings',       # firm name/GSTIN, invoice series, language
    'accounts',           # chart of accounts, including any custom heads
    'sites',
    'clients',
    'vendors',
    'materials',
    'labor',
    'equipment',
    'thekedars',
    'consumption_norms',
    'rate_book',
]

# Not carried by default: 'users' (a different firm usually means different
# people, and copying password hashes across entities is a choice, not a
# default). Pass it explicitly if an office wants the same logins.


def _blank():
    return {'active': None, 'files': []}


def load(path=None):
    """Read the registry. A missing or corrupt file yields an empty registry
    rather than raising — this must never block the app from starting."""
    path = path or REGISTRY_PATH
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return _blank()
    if not isinstance(data, dict):
        return _blank()
    files = data.get('files')
    if not isinstance(files, list):
        files = []
    clean = []
    for f in files:
        if isinstance(f, dict) and f.get('path'):
            clean.append({'name': str(f.get('name') or ''), 'path': str(f['path'])})
    return {'active': data.get('active'), 'files': clean}


def save(data, path=None):
    """Write the registry. Returns True on success, False if it couldn't be
    written (a read-only folder shouldn't crash the app)."""
    path = path or REGISTRY_PATH
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=2)
        return True
    except OSError:
        return False


def _same(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def find(data, db_path):
    """The registry entry for a path, or None."""
    for f in data.get('files', []):
        if _same(f['path'], db_path):
            return f
    return None


def add(data, name, db_path, make_active=False):
    """Register a company file. Re-registering a known path renames it rather
    than creating a duplicate entry."""
    existing = find(data, db_path)
    if existing is not None:
        if name:
            existing['name'] = name
    else:
        data.setdefault('files', []).append(
            {'name': name or os.path.basename(db_path), 'path': db_path})
    if make_active:
        data['active'] = db_path
    return data


def remove(data, db_path):
    """Forget a company file. Only drops it from the list — never deletes the
    file itself, which is the user's business data."""
    data['files'] = [f for f in data.get('files', [])
                     if not _same(f['path'], db_path)]
    if data.get('active') and _same(data['active'], db_path):
        data['active'] = None
    return data


def set_active(data, db_path):
    data['active'] = db_path
    return data


def active_path(data):
    """The active file if it is still registered and present on disk."""
    p = data.get('active')
    if p and os.path.exists(p):
        return p
    return None


def safe_filename(name):
    """Turn a firm/year label into a portable .db filename.

    'Sharma Constructions 25-26' -> 'sharma_constructions_25-26.db'

    Hyphens are kept: financial-year labels ('25-26') read wrong without them.
    """
    slug = re.sub(r'[^A-Za-z0-9-]+', '_', str(name or ''))
    slug = re.sub(r'_{2,}', '_', slug).strip('_-').lower()
    return (slug or 'company') + '.db'


def suggest_path(folder, name):
    """A non-clashing path for a new company file in ``folder``."""
    base = safe_filename(name)
    path = os.path.join(folder, base)
    if not os.path.exists(path):
        return path
    stem = base[:-3]
    for n in range(2, 100):
        candidate = os.path.join(folder, '{}_{}.db'.format(stem, n))
        if not os.path.exists(candidate):
            return candidate
    return path


def next_year_label(fy_label):
    """'2025-26' -> '2026-27'. Returns '' if it can't be parsed."""
    m = re.match(r'^(\d{4})-(\d{2})$', str(fy_label or '').strip())
    if not m:
        return ''
    start = int(m.group(1)) + 1
    return '{}-{:02d}'.format(start, (start + 1) % 100)


def _columns(conn, table):
    cur = conn.execute('SELECT * FROM {} LIMIT 0'.format(table))
    return [d[0] for d in cur.description]


def carry_forward(src_conn, dst_conn, tables=None):
    """Copy master rows from one company file into another.

    ``dst_conn`` should already have the schema (call ``db.init_db()`` first).
    Seeded defaults in the destination — notably the chart of accounts — are
    cleared for each carried table so the source is reproduced exactly rather
    than duplicated. Returns ``{table: rows_copied}``.

    Only transaction-free masters are copied, so the new file opens with the
    same setup and an empty ledger. Table names come from ``MASTER_TABLES``
    (hardcoded, never user input), so the f-string SQL is safe.
    """
    tables = list(tables or MASTER_TABLES)
    copied = {}
    for table in tables:
        try:
            rows = src_conn.execute('SELECT * FROM {}'.format(table)).fetchall()
        except sqlite3.Error:
            continue          # table absent in an older source file — skip it
        try:
            cols = _columns(dst_conn, table)
        except sqlite3.Error:
            continue          # absent in the destination — skip it
        src_cols = _columns(src_conn, table)
        use = [c for c in cols if c in src_cols]
        if not use:
            continue
        dst_conn.execute('DELETE FROM {}'.format(table))
        if rows:
            dst_conn.executemany(
                'INSERT INTO {} ({}) VALUES ({})'.format(
                    table, ', '.join(use), ', '.join(['?'] * len(use))),
                [tuple(r[c] for c in use) for r in rows])
        copied[table] = len(rows)
    dst_conn.commit()
    return copied
