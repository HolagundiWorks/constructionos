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
  narrows a datetime to its date instead — always, in both modes.
* ``muster``'s copy stripped whitespace but parsed the *whole* string, so it
  accepted ``' 2026-01-01 '`` (which the others rejected) and rejected
  ``'2026-01-01T10:30:00'`` (which the others accepted). Whitespace tolerance
  is plainly right and is now shared; the time-part tolerance is a genuine
  policy difference, so it is a parameter — see ``strict`` below — rather than
  something silently decided for every caller.
"""

from datetime import date, datetime


def parse(value, strict=False):
    """Tolerant ISO-date parse: ``date`` on success, ``None`` on anything else.

    Accepts a ``date`` or a ``datetime`` (narrowed to its date) unconditionally.
    For a string, leading/trailing whitespace is always stripped; ``strict``
    then decides what a *string with more than a date in it* means:

    * ``strict=False`` (default) takes the leading ten characters, so a full
      timestamp ``'2026-01-01T10:30:00'`` parses to the day it falls on. This is
      what nine of the ten modules did and want — dates arriving from mixed
      sources may carry a time part.
    * ``strict=True`` parses the whole stripped string, so anything beyond a
      bare ``YYYY-MM-DD`` is rejected as ``None``. ``muster`` uses this: a muster
      roll is keyed by day, and a value that smuggled in a time would be a data
      error worth refusing rather than quietly truncating.

    Blank, ``None``, and unparseable input all give ``None``; nothing raises.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text if strict else text[:10])
    except (ValueError, TypeError):
        return None
