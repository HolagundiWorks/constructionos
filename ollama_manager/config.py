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

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'settings.json')

DEFAULTS = {
    'host': '127.0.0.1',
    'port': 11434,
    'model': '',
}

# Construction OS keeps its data file next to its own code, one level up.
_SIBLING_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'construction_app', 'construction.db')


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
    candidate = path or _SIBLING_DB
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
