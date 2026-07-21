"""Pure quality-gate maths: hold points, inspections, NCRs (Phase 8, Wave 3).

No tkinter, no database.

The cube-test and material-test registers already record *results*. What was
missing is the **gate**: the rule that concrete does not get poured, and
reinforcement does not get covered, until someone has signed the inspection
off. An Inspection & Test Plan makes that explicit by marking certain checks as:

* **Hold**    — work stops until this is passed. The gate.
* **Witness** — the engineer is invited; work may continue if they do not come.
* **Record**  — evidence to be filed, no stoppage either way.

So the question this module answers is not "did it pass" but **"may the work
proceed"**, and those are different: an unfinished Hold point blocks even
though nothing has failed. A blank check is not a pass.

It also tracks non-conformances, because finding a defect matters far less than
closing it — an NCR left open is a defect still in the building.
"""

from datetime import date

import finance
import isodate

HOLD = 'Hold'
WITNESS = 'Witness'
RECORD = 'Record'
CHECK_TYPES = [HOLD, WITNESS, RECORD]

PASS = 'Pass'
FAIL = 'Fail'
PENDING = 'Pending'
NA = 'N/A'
RESULTS = [PENDING, PASS, FAIL, NA]

OPEN = 'Open'
CLOSED = 'Closed'


def money(value):
    return finance.money(value)


def _parse(d):
    return isodate.parse(d)


def _result(row):
    try:
        return (row['result'] or '').strip() or PENDING
    except (KeyError, IndexError, TypeError):
        return PENDING


def _check_type(row):
    try:
        return (row['check_type'] or '').strip() or RECORD
    except (KeyError, IndexError, TypeError):
        return RECORD


def inspection_result(items):
    """Overall result of one inspection.

    Any failure fails the inspection. Otherwise it only passes once every
    Hold and Witness point has been answered — a blank check is Pending, not a
    pass, because unrecorded is exactly how an inspection gets skipped.
    """
    items = list(items or [])
    if not items:
        return PENDING
    if any(_result(i) == FAIL for i in items):
        return FAIL
    for i in items:
        if _check_type(i) in (HOLD, WITNESS) and _result(i) == PENDING:
            return PENDING
    return PASS


def blocking_holds(items):
    """Hold points not yet passed — the reasons work may not proceed."""
    out = []
    for i in items or []:
        if _check_type(i) != HOLD:
            continue
        if _result(i) in (PASS, NA):
            continue
        out.append(i)
    return out


def may_proceed(items):
    """The gate. ``(allowed, reason)``.

    Work proceeds only when no Hold point is outstanding or failed. Witness
    points deliberately do not block: the engineer was invited, and a
    contractor cannot be held hostage by someone who did not attend.
    """
    blockers = blocking_holds(items)
    if not blockers:
        return True, ''
    failed = [b for b in blockers if _result(b) == FAIL]
    if failed:
        return False, ('{} hold point(s) FAILED — fix and re-inspect before '
                       'proceeding.'.format(len(failed)))
    return False, ('{} hold point(s) not yet signed off — work must not '
                   'proceed.'.format(len(blockers)))


def first_time_pass_rate(inspections):
    """Percentage of inspections passed without a re-inspection.

    ``inspections`` are mappings with ``result`` and optional ``reinspection``
    (truthy when this is a repeat of an earlier failure). The KPI a client
    cares about: how much work is right first time. None when nothing has been
    inspected, rather than a misleading 0% or 100%.
    """
    rows = [i for i in inspections or [] if _result(i) in (PASS, FAIL)]
    if not rows:
        return None
    def _repeat(row):
        try:
            return bool(row['reinspection'])
        except (KeyError, IndexError, TypeError):
            return False
    first_time = [r for r in rows if _result(r) == PASS and not _repeat(r)]
    return money(len(first_time) / len(rows) * 100.0)


def ncr_age_days(raised_date, closed_date=None, as_on=None):
    """How long a non-conformance has been open (or took to close)."""
    start = _parse(raised_date)
    if start is None:
        return 0
    end = _parse(closed_date) or _parse(as_on) or date.today()
    return max(0, (end - start).days)


def ncr_summary(ncrs, as_on=None):
    """Open vs closed, and how long the oldest open one has been sitting.

    ``oldest_open_days`` is the number worth showing: a defect logged and
    forgotten is worse than one never logged, because the record proves it
    was known about.
    """
    open_rows, closed_rows, oldest = [], [], 0
    for n in ncrs or []:
        try:
            status = (n['status'] or '').strip() or OPEN
        except (KeyError, IndexError, TypeError):
            status = OPEN
        if status == CLOSED:
            closed_rows.append(n)
            continue
        open_rows.append(n)
        try:
            raised = n['raised_date']
        except (KeyError, IndexError, TypeError):
            raised = None
        oldest = max(oldest, ncr_age_days(raised, None, as_on))
    total = len(open_rows) + len(closed_rows)
    return {
        'open': len(open_rows),
        'closed': len(closed_rows),
        'total': total,
        'oldest_open_days': oldest,
        'closure_rate': money(len(closed_rows) / total * 100.0) if total else None,
    }
