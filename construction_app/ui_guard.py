"""One-line write guard for role-based access control.

Call ``can_write()`` at the top of any method that changes data:

    if not can_write():
        return

When security is off (single-user) or the signed-in user is Admin/Operator,
this returns True. A Viewer is read-only: it shows a plain dialog and returns
False. Kept out of ``session.py`` so that module stays tkinter-free.
"""

from tkinter import messagebox

import session


def can_write():
    if session.can_write():
        return True
    messagebox.showwarning(
        'Read-only',
        'Your account can view but not change data.\n\nAsk an admin for '
        'Operator access to make changes.')
    return False
