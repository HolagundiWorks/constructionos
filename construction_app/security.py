"""Password security primitives (pure, stdlib only).

Salted PBKDF2-HMAC-SHA256 hashing with a constant-time verify — no third-party
crypto, no dependency. Used by ``auth.py`` for the optional login system.

Note: this protects *passwords*, not the SQLite file itself. Stdlib SQLite has
no at-rest encryption (that would need SQLCipher, a native dependency we
deliberately avoid). On-disk protection is the OS user account + the optional
login here; a truly sensitive deployment should sit on an encrypted volume.
"""

import hashlib
import hmac
import os

_ITERATIONS = 120000
_ALGO = 'sha256'


def hash_password(password, salt=None):
    """Return ``(salt_hex, hash_hex)``. Generates a random 16-byte salt if none
    is given; accepts a hex salt (str) to re-derive for verification."""
    if salt is None:
        salt = os.urandom(16)
    elif isinstance(salt, str):
        salt = bytes.fromhex(salt)
    dk = hashlib.pbkdf2_hmac(_ALGO, (password or '').encode('utf-8'), salt,
                             _ITERATIONS)
    return salt.hex(), dk.hex()


def verify_password(password, salt_hex, hash_hex):
    """Constant-time check of a password against a stored salt+hash."""
    if not salt_hex or not hash_hex:
        return False
    try:
        _, calc = hash_password(password, salt_hex)
    except ValueError:
        return False
    return hmac.compare_digest(calc, hash_hex)


def password_issues(password):
    """Light password policy suited to the audience — return a list of problems
    (empty = acceptable). Not draconian: usable on a shared office PC."""
    password = password or ''
    problems = []
    if len(password) < 6:
        problems.append('be at least 6 characters')
    if password.isdigit():
        problems.append('not be only digits')
    if password.lower() in ('password', '123456', 'admin', 'admin123'):
        problems.append('not be a common password')
    return problems
