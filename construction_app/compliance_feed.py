"""Compliance due-date → follow-up drafts (E4).

Tkinter-free. Given overdue / upcoming filing rows (from ``compliance.overdue``
/ ``upcoming``), return ``event_hooks.react(FILING_DUE, …)`` drafts. Nothing
is auto-filed — every follow-up stays gated where the rule says so.
"""

import event_hooks
import followups


def filing_events(rows):
    """One react() result per filing row that needs attention."""
    out = []
    for r in rows or []:
        payload = {
            'name': r.get('name') or 'Filing',
            'due_date': r.get('due_date') or '',
            'period': r.get('period') or '',
        }
        out.append(event_hooks.react(followups.FILING_DUE, payload=payload))
    return out
