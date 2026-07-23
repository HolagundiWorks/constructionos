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

import paths

# The registry of company files. From source it sits beside the code; an
# installed build keeps it in the per-user data folder alongside the databases
# it points at (see paths.py). Not beside any one company file.
REGISTRY_PATH = paths.data_path('companies.json')

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
    # The analyses behind the rate book are a library too — losing them at the
    # year boundary would leave rates nobody can justify. Parent first: ids are
    # copied verbatim, so the child rows still point at the right analysis.
    'rate_analysis',
    'rate_analysis_items',
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


def list_entries(data=None):
    """UI-friendly rows: ``[{name, path, active, exists}, …]``."""
    data = data if data is not None else load()
    active = data.get('active')
    out = []
    for f in data.get('files', []):
        path = f['path']
        out.append({
            'name': f.get('name') or os.path.basename(path),
            'path': path,
            'active': bool(active and _same(active, path)),
            'exists': os.path.exists(path),
        })
    return out


def apply_active(db_module=None, registry_path=None, default_path=None):
    """Point ``db.DB_PATH`` at the registry's active file before ``init_db``.

    If nothing is active (or the file is missing), keeps ``default_path`` /
    the module's current ``DB_PATH`` and ensures that path is registered so
    the next boot has something to select. Returns the path now in use.
    """
    if db_module is None:
        import db as db_module
    reg = registry_path or REGISTRY_PATH
    data = load(reg)
    chosen = active_path(data)
    if chosen is None:
        chosen = default_path or getattr(db_module, 'DB_PATH', None)
    if not chosen:
        return None
    db_module.DB_PATH = chosen
    # Keep the open file on the list (and active) so the login picker sees it.
    name = None
    existing = find(data, chosen)
    if existing is not None:
        name = existing.get('name')
    else:
        name = os.path.splitext(os.path.basename(chosen))[0] or 'Main'
    add(data, name, chosen, make_active=True)
    save(data, reg)
    return chosen


def _audit_in_book(db_module, actor, action, entity_id=None, detail=None):
    """Write an audit row into the currently open company file. Best-effort."""
    if not actor:
        return
    try:
        import auth
        conn = db_module.get_conn()
        try:
            auth.audit(conn, actor, action, 'company', entity_id, detail,
                       origin=auth.ORIGIN_MANUAL)
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def select_company(db_path, name=None, db_module=None, registry_path=None,
                   actor=None):
    """Register (if needed), mark active, and set ``db.DB_PATH``.

    Does not restart the process — callers that already built UI should still
    ask for a reopen. Returns ``(ok, message)``. Viewers may select; create /
    import stay write-gated at the UI/API layer. Audits when ``actor`` is set.
    """
    if db_module is None:
        import db as db_module
    if not db_path:
        return False, 'No company file selected.'
    if not os.path.exists(db_path):
        return False, 'That company file is missing:\n{}'.format(db_path)
    reg = registry_path or REGISTRY_PATH
    data = load(reg)
    label = name or (find(data, db_path) or {}).get('name') \
        or os.path.splitext(os.path.basename(db_path))[0] or 'Company'
    add(data, label, db_path, make_active=True)
    if not save(data, reg):
        return False, 'Could not update the company list.'
    db_module.DB_PATH = db_path
    _audit_in_book(db_module, actor, 'company_select', db_path, label)
    return True, db_path


def export_company(src_path, dest_path):
    """Copy a company SQLite file to ``dest_path``. Returns ``(ok, message)``."""
    import shutil
    if not src_path or not os.path.exists(src_path):
        return False, 'Nothing to export — the company file was not found.'
    if not dest_path:
        return False, 'Choose where to save the export.'
    try:
        # Avoid exporting into the live file.
        if _same(src_path, dest_path):
            return False, 'Pick a different location than the live company file.'
        folder = os.path.dirname(os.path.abspath(dest_path))
        if folder:
            os.makedirs(folder, exist_ok=True)
        shutil.copy2(src_path, dest_path)
    except OSError as exc:
        return False, 'Export failed: {}'.format(exc)
    return True, dest_path


def import_company(src_path, name=None, folder=None, make_active=False,
                   db_module=None, registry_path=None, actor=None):
    """Copy an external ``.db`` into the data folder and register it.

    Returns ``(ok, message, new_path)``. Never overwrites an existing book —
    ``suggest_path`` picks a free name. When ``actor`` is set, audits into the
    imported book.
    """
    import shutil
    if db_module is None:
        import db as db_module
    if not src_path or not os.path.exists(src_path):
        return False, 'That file was not found.', None
    # Cheap SQLite sniff — refuse obvious non-DB uploads.
    try:
        with open(src_path, 'rb') as fh:
            head = fh.read(16)
    except OSError as exc:
        return False, 'Could not read that file: {}'.format(exc), None
    if not head.startswith(b'SQLite format 3'):
        import branding
        return False, 'That does not look like an {} company file (.db).'.format(
            branding.APP_NAME), None
    folder = folder or os.path.dirname(os.path.abspath(
        getattr(db_module, 'DB_PATH', paths.data_path('construction.db'))))
    label = (name or '').strip() or os.path.splitext(os.path.basename(src_path))[0] \
        or 'Imported'
    dest = suggest_path(folder, label)
    try:
        shutil.copy2(src_path, dest)
    except OSError as exc:
        return False, 'Import failed: {}'.format(exc), None
    reg = registry_path or REGISTRY_PATH
    data = load(reg)
    add(data, label, dest, make_active=make_active)
    save(data, reg)
    prev = getattr(db_module, 'DB_PATH', None)
    db_module.DB_PATH = dest
    _audit_in_book(db_module, actor, 'company_import', dest,
                   'from={} name={}'.format(src_path, label))
    if not make_active and prev is not None:
        db_module.DB_PATH = prev
    return True, dest, dest


def create_company(name, folder=None, carry_from=None, make_active=True,
                   db_module=None, registry_path=None, actor=None):
    """Create a fresh company book, optionally carrying masters forward.

    Returns ``(ok, message, new_path)``. When ``actor`` is set, audits create
    (and carry-forward) into the new book.
    """
    import sqlite3
    if db_module is None:
        import db as db_module
    name = (name or '').strip()
    if not name:
        return False, 'Enter a name for the new company.', None
    folder = folder or os.path.dirname(os.path.abspath(
        getattr(db_module, 'DB_PATH', paths.data_path('construction.db'))))
    path = suggest_path(folder, name)
    prev = getattr(db_module, 'DB_PATH', None)
    try:
        db_module.DB_PATH = path
        db_module.init_db()
        if carry_from and os.path.exists(carry_from):
            src = sqlite3.connect(carry_from)
            src.row_factory = sqlite3.Row
            dst = db_module.get_conn()
            try:
                carry_forward(src, dst, actor=actor, source_path=carry_from)
            finally:
                src.close()
                dst.close()
    except Exception as exc:  # noqa: BLE001 — surfaced to the caller
        if prev is not None:
            db_module.DB_PATH = prev
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
        return False, 'Could not create the company file: {}'.format(exc), None
    reg = registry_path or REGISTRY_PATH
    data = load(reg)
    add(data, name, path, make_active=make_active)
    save(data, reg)
    _audit_in_book(db_module, actor, 'company_create', path, name)
    if not make_active and prev is not None:
        db_module.DB_PATH = prev
    return True, path, path


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


def carry_forward(src_conn, dst_conn, tables=None, actor=None, source_path=None):
    """Copy master rows from one company file into another.

    ``dst_conn`` should already have the schema (call ``db.init_db()`` first).
    Seeded defaults in the destination — notably the chart of accounts — are
    cleared for each carried table so the source is reproduced exactly rather
    than duplicated. Returns ``{table: rows_copied}``.

    Only transaction-free masters are copied, so the new file opens with the
    same setup and an empty ledger. Table names come from ``MASTER_TABLES``
    (hardcoded, never user input), so the f-string SQL is safe.

    When ``actor`` is set, appends an audit row on ``dst_conn`` noting
    ``source_path``.
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
    if actor:
        try:
            import auth
            auth.audit(
                dst_conn, actor, 'company_carry_forward', 'company',
                source_path, 'tables={}'.format(','.join(sorted(copied))),
                origin=auth.ORIGIN_MANUAL)
        except Exception:
            pass
    dst_conn.commit()
    return copied
