"""App-wide safety net so no stack trace ever reaches the user (Phase 4).

Tk routes every exception raised inside a widget callback (a button command, an
event binding) through ``Tk.report_callback_exception``. By default that dumps a
traceback to the console — invisible and alarming to a non-technical user on a
single PC. ``install(root)`` replaces it with a friendly dialog that names the
problem in plain language, while still printing the full traceback to stderr so
a support person can diagnose from the log.

This complements the local guards (e.g. CrudFrame's IntegrityError dialog): those
give a specific message for an expected case; this catches everything else.
"""

import sqlite3
import traceback
from tkinter import messagebox


def _friendly(exc_value):
    """A plain-language sentence for the most common failure kinds."""
    if isinstance(exc_value, sqlite3.IntegrityError):
        return ('That change conflicts with existing data (a linked or duplicate '
                'record). Nothing was saved. Check the entry and try again.')
    if isinstance(exc_value, sqlite3.OperationalError):
        return ('The data file is busy or locked right now. Wait a moment and '
                'try again; if it persists, close and reopen the app.')
    if isinstance(exc_value, (ValueError, TypeError)):
        return ('Something in the form didn\'t look right (perhaps a number or '
                'date field). Please check your entries and try again.')
    return ('Something went wrong with that action. Nothing may have been saved '
            '— please try again. If it keeps happening, take a backup and note '
            'what you were doing.')


def install(root):
    """Route uncaught callback exceptions to a friendly dialog + stderr log."""
    def handler(exc_type, exc_value, exc_tb):
        traceback.print_exception(exc_type, exc_value, exc_tb)   # for the log
        try:
            messagebox.showerror('Something went wrong', _friendly(exc_value))
        except Exception:
            pass   # never let the error handler itself crash the app
    root.report_callback_exception = handler
