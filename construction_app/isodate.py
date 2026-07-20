"""PURE tolerant ISO-date parsing, shared by every dated pure module.

No tkinter, no database, no dependencies — not even on ``finance``.

Dates in this app are plain ``TEXT`` ``YYYY-MM-DD`` (see AGENTS.md §11): typed
by hand, imported from elsewhere, sometimes left blank. So every module that
reasons about dates needs the same question answered the same way — *give me a
``date`` if this is usable, and ``None`` if it is not* — without raising, because
a blank target date on one snag must not take down a whole readiness report.

Ten modules had each grown their own copy of that function, and the copies had
quietly drifted apart. Two differences were real:

* Most copies short-circuited on ``isinstance(value, date)`` and returned the
  input untouched. ``datetime`` **is** a ``date``, so a datetime came back as a
  datetime, and the caller's next line — ``today > target`` — raised
  ``TypeError: can't compare datetime.datetime to datetime.date``. ``parse``
  narrows a datetime to its date instead.
* ``muster``'s copy stripped whitespace but parsed the *whole* string, so it
  accepted ``' 2026-01-01 '`` (which the others rejected) and rejected
  ``'2026-01-01T10:30:00'`` (which the others accepted). ``parse`` does both:
  strip first, then take the leading ten characters.

The result is a superset of what every copy accepted, minus the datetime trap.
"""

from datetime import date, datetime


def parse(value):
    """Tolerant ISO-date parse: ``date`` on success, ``None`` on anything else.

    Accepts a ``date``, a ``datetime`` (narrowed to its date), or a string whose
    first ten characters after stripping are an ISO date — so a full timestamp
    ``'2026-01-01T10:30:00'`` parses to the day it falls on. Blank, ``None``,
    and unparseable input all give ``None``; nothing here raises.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (ValueError, TypeError):
        return None
