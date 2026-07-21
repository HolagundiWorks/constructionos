"""User accounts, authentication, and audit logging (DB layer).

Login is **opt-in**: with security disabled (the default) the app opens straight
in, single-user, exactly as before. An admin turns it on from Tools, which
requires at least one Admin user to exist. All functions take a live connection
so they are testable without any GUI.

Roles: Admin (full, incl. user management), Operator (day-to-day), Viewer
(read-only, enforced in the UI via ``session.can_write``).
"""

from datetime import datetime

import security

MAX_FAILED = 5                 # lock the account after this many bad passwords
SECURITY_KEY = 'security_enabled'


# ------------------------------------------------------------------ settings
def security_enabled(conn):
    row = conn.execute('SELECT value FROM app_settings WHERE key = ?',
                       (SECURITY_KEY,)).fetchone()
    return bool(row) and row['value'] == '1'


def set_security_enabled(conn, on, actor=None):
    conn.execute(
        'INSERT INTO app_settings (key, value) VALUES (?, ?) '
        'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
        (SECURITY_KEY, '1' if on else '0'))
    audit(conn, actor, 'security_' + ('enabled' if on else 'disabled'))
    conn.commit()


# --------------------------------------------------------------------- users
def user_count(conn):
    return conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']


def admin_count(conn):
    return conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE role = 'Admin' AND is_active = 1"
    ).fetchone()['c']


def list_users(conn):
    return conn.execute(
        'SELECT id, username, role, is_active, locked, failed_attempts, '
        'created_at FROM users ORDER BY username').fetchall()


def get_user(conn, username):
    return conn.execute('SELECT * FROM users WHERE username = ?',
                        (username,)).fetchone()


def create_user(conn, username, password, role='Operator', actor=None):
    """Create a user. Returns (ok, message)."""
    username = (username or '').strip()
    if not username:
        return False, 'Username is required.'
    if role not in session_roles():
        return False, 'Invalid role.'
    if get_user(conn, username):
        return False, 'That username already exists.'
    issues = security.password_issues(password)
    if issues:
        return False, 'Password must ' + ', and '.join(issues) + '.'
    if (password or '').strip().lower() == username.lower():
        return False, 'Password must not be the same as the username.'
    salt, pw_hash = security.hash_password(password)
    conn.execute(
        'INSERT INTO users (username, password_hash, salt, role, is_active, '
        'created_at) VALUES (?, ?, ?, ?, 1, ?)',
        (username, pw_hash, salt, role, datetime.now().isoformat(timespec='seconds')))
    audit(conn, actor, 'create_user', 'users', username, 'role=' + role)
    conn.commit()
    return True, 'User created.'


def change_password(conn, username, new_password, actor=None):
    issues = security.password_issues(new_password)
    if issues:
        return False, 'Password must ' + ', and '.join(issues) + '.'
    if (new_password or '').strip().lower() == (username or '').lower():
        return False, 'Password must not be the same as the username.'
    salt, pw_hash = security.hash_password(new_password)
    conn.execute(
        'UPDATE users SET password_hash = ?, salt = ?, failed_attempts = 0, '
        'locked = 0 WHERE username = ?', (pw_hash, salt, username))
    audit(conn, actor, 'change_password', 'users', username)
    conn.commit()
    return True, 'Password updated.'


def set_role(conn, username, role, actor=None):
    if role not in session_roles():
        return False, 'Invalid role.'
    # Don't strand the system with zero admins.
    target = get_user(conn, username)
    if target and target['role'] == 'Admin' and role != 'Admin' and admin_count(conn) <= 1:
        return False, 'Cannot demote the last active admin.'
    conn.execute('UPDATE users SET role = ? WHERE username = ?', (role, username))
    audit(conn, actor, 'set_role', 'users', username, 'role=' + role)
    conn.commit()
    return True, 'Role updated.'


def set_active(conn, username, active, actor=None):
    target = get_user(conn, username)
    if target and target['role'] == 'Admin' and not active and admin_count(conn) <= 1:
        return False, 'Cannot deactivate the last active admin.'
    conn.execute('UPDATE users SET is_active = ? WHERE username = ?',
                 (1 if active else 0, username))
    audit(conn, actor, 'activate' if active else 'deactivate', 'users', username)
    conn.commit()
    return True, 'Updated.'


def unlock(conn, username, actor=None):
    conn.execute(
        'UPDATE users SET locked = 0, failed_attempts = 0 WHERE username = ?',
        (username,))
    audit(conn, actor, 'unlock', 'users', username)
    conn.commit()
    return True, 'Account unlocked.'


def authenticate(conn, username, password):
    """Verify a login. Returns (ok, message, user_row_or_None).

    On failure the message is deliberately generic (no user enumeration).
    Increments failed_attempts and locks the account past MAX_FAILED.
    """
    user = get_user(conn, username)
    generic = 'Invalid username or password.'
    if user is None or not user['is_active']:
        return False, generic, None
    if user['locked']:
        return False, 'Account is locked. Ask an admin to unlock it.', None
    if security.verify_password(password, user['salt'], user['password_hash']):
        conn.execute('UPDATE users SET failed_attempts = 0 WHERE id = ?',
                     (user['id'],))
        # Transparently upgrade an old/weaker hash to the current work factor
        # now that we hold the plaintext — the login the user just did.
        if security.needs_rehash(user['password_hash']):
            salt, pw_hash = security.hash_password(password)
            conn.execute('UPDATE users SET salt = ?, password_hash = ? '
                         'WHERE id = ?', (salt, pw_hash, user['id']))
        audit(conn, username, 'login')
        conn.commit()
        return True, '', user
    attempts = (user['failed_attempts'] or 0) + 1
    locked = 1 if attempts >= MAX_FAILED else 0
    conn.execute('UPDATE users SET failed_attempts = ?, locked = ? WHERE id = ?',
                 (attempts, locked, user['id']))
    audit(conn, username, 'login_failed', detail='attempt {}'.format(attempts))
    conn.commit()
    if locked:
        return False, 'Too many attempts — account locked.', None
    return False, generic, None


# ------------------------------------------------------------------- audit
def audit(conn, username, action, entity=None, entity_id=None, detail=None):
    """Append an audit-log row. Best-effort — never raises into the caller."""
    try:
        conn.execute(
            'INSERT INTO audit_log (ts, username, action, entity, entity_id, '
            'detail) VALUES (?, ?, ?, ?, ?, ?)',
            (datetime.now().isoformat(timespec='seconds'), username or '-',
             action, entity, str(entity_id) if entity_id is not None else None,
             detail))
    except Exception:
        pass


def recent_audit(conn, limit=200):
    return conn.execute(
        'SELECT ts, username, action, entity, entity_id, detail FROM audit_log '
        'ORDER BY id DESC LIMIT ?', (limit,)).fetchall()


def session_roles():
    import session
    return session.ROLES
