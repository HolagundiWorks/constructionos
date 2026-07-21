"""Settings for the Ollama Manager, stored as JSON beside the app.

Host, port and the chosen model. Kept deliberately tiny and forgiving: a
missing or corrupt file falls back to defaults rather than raising, because a
settings problem must never be the reason a management tool won't open.

``push_to_construction_os`` is the one piece of integration with the sibling
app: Construction OS reads ``assistant_model`` / ``assistant_host`` from its own
SQLite settings table, so the manager can write the selected model straight
there instead of making the user retype it.
"""

import json
import os
import sqlite3
import sys

# Settings location. From source it sits beside the code, so the manager stays
# self-contained; an installed (frozen) build cannot write to its own folder in
# Program Files, so settings move to a per-user folder under %LOCALAPPDATA%.
APP_DIR_NAME = 'Ollama Manager'


def _here():
    return os.path.dirname(os.path.abspath(__file__))


def _data_dir():
    if not getattr(sys, 'frozen', False):
        return _here()
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    target = os.path.join(base, APP_DIR_NAME)
    try:
        os.makedirs(target, exist_ok=True)
        return target
    except OSError:
        return _here()


CONFIG_PATH = os.path.join(_data_dir(), 'settings.json')

DEFAULTS = {
    'host': '127.0.0.1',
    'port': 11434,
    'model': '',
}


def _construction_os_default_db():
    """Where Construction OS keeps its database.

    Installed, it lives in ``%LOCALAPPDATA%\\Construction OS`` (its own
    ``paths.py`` puts it there); from source it sits next to that app's code,
    one level up from here. Return the first that actually exists, so this
    works whether the sibling app was installed or is being run from source —
    the old hard-coded source path would never find an installed build.
    """
    candidates = []
    base = os.environ.get('LOCALAPPDATA')
    if base:
        candidates.append(os.path.join(base, 'Construction OS', 'construction.db'))
    candidates.append(os.path.join(os.path.dirname(_here()),
                                   'construction_app', 'construction.db'))
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


def load(path=None):
    path = path or CONFIG_PATH
    data = dict(DEFAULTS)
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            for key in DEFAULTS:
                if key in stored and stored[key] not in (None, ''):
                    data[key] = stored[key]
    except (OSError, ValueError):
        pass
    try:
        data['port'] = int(data['port'])
    except (TypeError, ValueError):
        data['port'] = DEFAULTS['port']
    return data


def save(data, path=None):
    path = path or CONFIG_PATH
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=2)
        return True
    except OSError:
        return False


def construction_os_db(path=None):
    """Path to the sibling app's data file if it exists, else None."""
    candidate = path or _construction_os_default_db()
    return candidate if os.path.exists(candidate) else None


def push_to_construction_os(model, host_url, path=None):
    """Write the chosen model/host into Construction OS's settings.

    Returns (ok, message). Fails soft: the sibling app may not be installed,
    may be an older build without the settings table, or may have the file
    open — none of which should be more than a message here.
    """
    db_path = construction_os_db(path)
    if not db_path:
        return False, 'Construction OS data file not found next to this app.'
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        try:
            conn.execute('CREATE TABLE IF NOT EXISTS app_settings '
                         '(key TEXT PRIMARY KEY, value TEXT)')
            for key, value in (('assistant_model', model),
                               ('assistant_host', host_url)):
                conn.execute(
                    'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                    'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                    (key, value))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return False, 'Could not update Construction OS: {}'.format(exc)
    return True, 'Construction OS will now use "{}".'.format(model)
