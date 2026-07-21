"""Password security primitives (pure, stdlib only).

Salted PBKDF2-HMAC-SHA256 hashing with a constant-time verify — no third-party
crypto, no dependency. Used by ``auth.py`` for the optional login system.

The stored hash is **self-describing** — ``pbkdf2_sha256$<iterations>$<hex>`` —
so the work factor can be raised over time without stranding existing accounts:
a hash written at an older cost still verifies at the cost it records, and
``auth`` transparently re-hashes it at the current cost on the next successful
login (``needs_rehash``). Hashes written before the versioned format (bare hex)
are read as the original 120 000-iteration PBKDF2 and upgraded the same way.

Note: this protects *passwords*, not the SQLite file itself. Stdlib SQLite has
no at-rest encryption (that would need SQLCipher, a native dependency we
deliberately avoid). On-disk protection is the OS user account + the optional
login here; a truly sensitive deployment should sit on an encrypted volume.
"""

import hashlib
import hmac
import os

_ALGO = 'sha256'
_ITERATIONS = 600000           # OWASP 2023 floor for PBKDF2-HMAC-SHA256
_LEGACY_ITERATIONS = 120000    # cost of hashes written before the versioned form
_PREFIX = 'pbkdf2_sha256'


def _derive(password, salt, iterations):
    return hashlib.pbkdf2_hmac(_ALGO, (password or '').encode('utf-8'), salt,
                               iterations).hex()


def hash_password(password, salt=None):
    """Return ``(salt_hex, encoded)``.

    ``encoded`` is ``pbkdf2_sha256$<iterations>$<hash_hex>``. A random 16-byte
    salt is generated when none is given; a hex salt (str) may be passed to
    re-derive at the current cost."""
    if salt is None:
        salt = os.urandom(16)
    elif isinstance(salt, str):
        salt = bytes.fromhex(salt)
    hexhash = _derive(password, salt, _ITERATIONS)
    return salt.hex(), '{}${}${}'.format(_PREFIX, _ITERATIONS, hexhash)


def _parse(stored):
    """``(iterations, hash_hex)`` from a stored value, tolerating the legacy
    bare-hex form. Returns ``(None, None)`` if it can't be understood."""
    if not stored:
        return None, None
    if '$' in stored:
        parts = stored.split('$')
        try:
            return int(parts[-2]), parts[-1]
        except (ValueError, IndexError):
            return None, None
    return _LEGACY_ITERATIONS, stored          # pre-versioned bare hex


def verify_password(password, salt_hex, stored):
    """Constant-time check of a password against a stored salt + encoded hash."""
    if not salt_hex or not stored:
        return False
    iterations, hexhash = _parse(stored)
    if not iterations or not hexhash:
        return False
    try:
        salt = bytes.fromhex(salt_hex)
        calc = _derive(password, salt, iterations)
    except ValueError:
        return False
    return hmac.compare_digest(calc, hexhash)


def needs_rehash(stored):
    """True when a stored hash is weaker than current policy (legacy form, or a
    lower iteration count), so a successful login can upgrade it in place."""
    if not stored or '$' not in stored:
        return True                            # legacy bare hex, or empty
    iterations, hexhash = _parse(stored)
    if not iterations or not hexhash:
        return True
    return iterations < _ITERATIONS


def password_issues(password):
    """Light password policy suited to the audience — return a list of problems
    (empty = acceptable). Not draconian: usable on a shared office PC."""
    password = password or ''
    problems = []
    if len(password.strip()) < 6:
        problems.append('be at least 6 characters')
    if password.isdigit():
        problems.append('not be only digits')
    if password.lower() in ('password', 'passw0rd', '123456', '12345678',
                            'qwerty', 'admin', 'admin123', 'welcome'):
        problems.append('not be a common password')
    return problems
