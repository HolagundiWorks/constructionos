"""Process-wide current-user session for the optional login system.

A desktop app is a single process with one signed-in user, so a module-level
holder is sufficient. When security is disabled there is no session and
``is_authenticated()`` is False; callers should treat "no session" as full
access (single-user mode) — gating only kicks in once login is enabled.
"""

ROLES = ('Admin', 'Operator', 'Viewer')

_current = {'username': None, 'role': None}


def login(username, role):
    _current['username'] = username
    _current['role'] = role


def logout():
    _current['username'] = None
    _current['role'] = None


def username():
    return _current['username']


def role():
    return _current['role']


def is_authenticated():
    return _current['username'] is not None


def is_admin():
    return _current['role'] == 'Admin'


def can_write():
    """Viewers are read-only; everyone else (incl. single-user mode) may write."""
    return _current['role'] != 'Viewer'
