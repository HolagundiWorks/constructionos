"""Pure closeout maths: snag list and handover readiness (Phase 8, Wave 4).

No tkinter, no database.

The end of a job is where money quietly goes missing. The work is finished, the
site is emptying, attention has moved to the next project — and the last
payment plus the whole retention balance are still outstanding, waiting on a
snag list nobody is tracking.

So the number here is **readiness**: what proportion of the punch list is
actually cleared, and what specifically is standing between the contractor and
handover. Handover matters beyond tidiness — it starts the defect-liability
clock, and the DLP is what releases retention (see ``retention.py``). A week
of delay at handover is a week added to getting the retention back.

A snag moves Open → Fixed → Verified. **Fixed is the contractor's claim;
Verified is the client's agreement**, and only the second one counts toward
readiness. Marking your own work complete has never convinced anybody.
"""

from datetime import date

import finance
import isodate

OPEN = 'Open'
FIXED = 'Fixed'
VERIFIED = 'Verified'
STATUSES = [OPEN, FIXED, VERIFIED]

MINOR = 'Minor'
MAJOR = 'Major'
BLOCKER = 'Blocker'          # stops handover on its own
SEVERITIES = [MINOR, MAJOR, BLOCKER]


def money(value):
    return finance.money(value)


def _parse(d):
    return isodate.parse(d)


def _get(row, key, default=''):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _status(row):
    return (str(_get(row, 'status', OPEN)).strip() or OPEN)


def is_overdue(snag, as_on=None):
    """Past its target date and not yet verified."""
    if _status(snag) == VERIFIED:
        return False
    target = _parse(_get(snag, 'target_date', None))
    if target is None:
        return False
    return (_parse(as_on) or date.today()) > target


def readiness(snags):
    """Share of the punch list actually verified, as a percentage.

    Counts **Verified** only. A snag the contractor has marked Fixed is a
    claim, not a clearance, so counting it would let a job report itself ready
    while the client still disagrees — which is precisely the argument that
    delays handover and holds up retention.

    None when there are no snags at all, rather than 100%: an empty list may
    mean a perfect job or an inspection nobody has done yet, and those should
    not look identical.
    """
    rows = list(snags or [])
    if not rows:
        return None
    verified = sum(1 for s in rows if _status(s) == VERIFIED)
    return money(verified / len(rows) * 100.0)


def blockers(snags):
    """Snags that stop handover on their own — Blocker severity, not verified."""
    return [s for s in snags or []
            if str(_get(s, 'severity', MINOR)).strip() == BLOCKER
            and _status(s) != VERIFIED]


def may_hand_over(snags):
    """The closeout gate: ``(allowed, reason)``.

    Blocked by any unverified Blocker, or by anything still Open. Snags marked
    Fixed but not yet Verified do **not** block — they are waiting on the
    client's walk-round, which is a scheduling matter rather than a defect,
    and refusing to let the contractor request handover would be backwards.
    """
    rows = list(snags or [])
    if not rows:
        return True, 'No snags recorded.'
    blocking = blockers(rows)
    if blocking:
        return False, ('{} blocker(s) outstanding — these stop handover on '
                       'their own.'.format(len(blocking)))
    still_open = [s for s in rows if _status(s) == OPEN]
    if still_open:
        return False, ('{} snag(s) not yet fixed.'.format(len(still_open)))
    awaiting = [s for s in rows if _status(s) == FIXED]
    if awaiting:
        return True, ('All snags fixed; {} awaiting the client\'s '
                      'verification.'.format(len(awaiting)))
    return True, 'All snags verified.'


def summarise(snags, as_on=None):
    """Counts by status and severity, plus overdue and readiness."""
    rows = list(snags or [])
    by_status = {s: 0 for s in STATUSES}
    by_severity = {s: 0 for s in SEVERITIES}
    overdue = 0
    for s in rows:
        st = _status(s)
        by_status[st] = by_status.get(st, 0) + 1
        sev = str(_get(s, 'severity', MINOR)).strip() or MINOR
        by_severity[sev] = by_severity.get(sev, 0) + 1
        if is_overdue(s, as_on):
            overdue += 1
    allowed, reason = may_hand_over(rows)
    return {
        'total': len(rows),
        'by_status': by_status,
        'by_severity': by_severity,
        'open': by_status.get(OPEN, 0),
        'overdue': overdue,
        'blockers': len(blockers(rows)),
        'readiness': readiness(rows),
        'may_hand_over': allowed,
        'reason': reason,
    }


def by_trade(snags):
    """Open snags grouped by trade, worst first — who to chase.

    A punch list of forty items is not forty conversations; it is usually
    three, one per trade.
    """
    counts = {}
    for s in snags or []:
        if _status(s) == VERIFIED:
            continue
        trade = str(_get(s, 'trade', '') or 'Not stated').strip() or 'Not stated'
        counts[trade] = counts.get(trade, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
