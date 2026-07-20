"""Pure retention / defect-liability maths (Phase 8, Wave 2).

No tkinter, no database.

Retention is money already earned and already withheld — typically 5% of every
bill, held until the defect-liability period expires. Two things make it leak:

* On the **client side** it is a receivable nobody chases, because it never
  appears on an invoice. A contractor with twenty bills behind them can be owed
  a substantial sum and have no single figure for it.
* On the **subcontractor side** it is a payable that must eventually be
  released, and forgetting is how disputes start.

So this module answers: how much is held, how much has been released, what is
still outstanding, and — the part that turns a register into an action —
**which of it is now due for release**.

The defect-liability period runs from the *completion* date, not the bill date;
a bill raised early in a job is released on the same day as the last one.
"""

from datetime import date, timedelta

import finance
import isodate

CLIENT = 'Client'          # they hold our money — a receivable
SUB = 'Subcontractor'      # we hold theirs — a payable


def money(value):
    return finance.money(value)


def _parse(d):
    return isodate.parse(d)


def release_due_date(completion_date, dlp_months=12):
    """When retention becomes releasable: completion + the DLP.

    Months are added calendar-wise (12 months from 15 Mar is 15 Mar next year)
    rather than as 30-day blocks, because that is how a contract reads.
    Returns None when there is no completion date — work that has not finished
    cannot have a release date, and guessing one would be worse than silence.
    """
    start = _parse(completion_date)
    if start is None:
        return None
    months = int(dlp_months or 0)
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = start.day
    # Clamp for short months: 31 Aug + 6 months is the end of February.
    while day > 1:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, 1)


def outstanding(withheld, released):
    """Retention still held — never negative, even on an over-release."""
    return money(max(money(withheld) - money(released), 0.0))


def is_due(due_date, as_on=None):
    """True once the release date has arrived. No date means not due."""
    due = _parse(due_date)
    if due is None:
        return False
    return (_parse(as_on) or date.today()) >= due


def line_status(withheld, released, due_date, as_on=None):
    """Where one retention line stands: Released / Due / Held / Not started."""
    left = outstanding(withheld, released)
    if money(withheld) <= 0:
        return 'None'
    if left <= 0:
        return 'Released'
    if due_date is None:
        return 'Held (no completion date)'
    return 'DUE for release' if is_due(due_date, as_on) else 'Held'


def summarise(lines, as_on=None):
    """Roll up a set of retention lines.

    ``due_now`` is the number worth acting on: money whose defect-liability
    period has expired and which is still sitting with the other side.
    """
    withheld = released = left = due_now = 0.0
    overdue_days = 0
    for ln in lines or []:
        w = money(ln.get('withheld'))
        r = money(ln.get('released'))
        o = outstanding(w, r)
        withheld = money(withheld + w)
        released = money(released + r)
        left = money(left + o)
        if o > 0 and is_due(ln.get('due_date'), as_on):
            due_now = money(due_now + o)
            due = _parse(ln.get('due_date'))
            if due:
                days = ((_parse(as_on) or date.today()) - due).days
                overdue_days = max(overdue_days, days)
    return {
        'withheld': withheld,
        'released': released,
        'outstanding': left,
        'due_now': due_now,
        'max_overdue_days': overdue_days,
        'count': len(lines or []),
    }


# --------------------------------------------------------------- CPWD regime
#
# A CPWD contract secures performance twice over, and the two are separate
# money with separate release rules — conflating them is how a contractor
# loses track of what they are owed:
#
#   * a **performance guarantee** of 5% of the tendered value, furnished
#     *before* work starts (Works Manual Para 21.1), and
#   * a **security deposit** of 2.5% deducted from the gross of every running
#     and final bill as the work proceeds (Para 21.2).
#
# Once the accumulated security deposit reaches Rs 5 lakh it may be released
# against a bank guarantee — worth surfacing, because it converts dead cash
# into working capital and nobody sends a reminder.
#
# All three are defaults, not constants. State PWDs differ sharply: Arunachal
# deducts 10% per bill against CPWD's 2.5%.

PERFORMANCE_GUARANTEE_PCT = 5.0
SECURITY_DEPOSIT_PCT = 2.5
BG_RELEASE_THRESHOLD = 500000.0


def performance_guarantee(tendered_value, pct=PERFORMANCE_GUARANTEE_PCT):
    """The guarantee furnished up front, on the tendered value."""
    return money(money(tendered_value) * float(pct or 0) / 100.0)


def deposit_accrual(bills, pct=SECURITY_DEPOSIT_PCT):
    """Security deposit accumulating bill by bill.

    Each row carries its own deduction and the running total, because the
    question a contractor actually asks is "how much of mine is sitting with
    them *now*", which no single bill answers.

    A bill that already records a deducted amount is trusted over the
    percentage: a part-rate or a departmental adjustment can make the actual
    deduction differ from the nominal rate, and the register should show what
    was really withheld, not what the formula says.
    """
    rows, running = [], 0.0
    for b in bills or []:
        gross = money(b.get('value'))
        stated = b.get('deducted')
        amount = money(stated) if stated is not None else money(
            gross * float(pct or 0) / 100.0)
        running = money(running + amount)
        rows.append({
            'bill_no': b.get('bill_no', ''),
            'bill_date': b.get('bill_date', ''),
            'value': gross,
            'deducted': amount,
            'cumulative': running,
        })
    return rows


def bg_release(accumulated, threshold=BG_RELEASE_THRESHOLD):
    """Whether the accrued deposit may be swapped for a bank guarantee."""
    accumulated = money(accumulated)
    return {
        'accumulated': accumulated,
        'threshold': money(threshold),
        'eligible': accumulated >= money(threshold),
        'shortfall': money(max(money(threshold) - accumulated, 0.0)),
    }


def deposit_position(tendered_value, bills, pg_furnished=0, released=0,
                     sd_pct=SECURITY_DEPOSIT_PCT,
                     pg_pct=PERFORMANCE_GUARANTEE_PCT,
                     threshold=BG_RELEASE_THRESHOLD):
    """The whole security position on one contract.

    ``total_secured`` deliberately adds the performance guarantee to the
    deposit still held: both are the contractor's money tied up against the
    same work, and seeing them apart is what makes people forget the guarantee
    exists long after the job closed.
    """
    rows = deposit_accrual(bills, sd_pct)
    accrued = rows[-1]['cumulative'] if rows else 0.0
    held = outstanding(accrued, released)
    required_pg = performance_guarantee(tendered_value, pg_pct)
    furnished = money(pg_furnished)
    return {
        'rows': rows,
        'sd_pct': float(sd_pct or 0),
        'sd_accrued': money(accrued),
        'sd_released': money(released),
        'sd_held': held,
        'pg_required': required_pg,
        'pg_furnished': furnished,
        'pg_shortfall': money(max(required_pg - furnished, 0.0)),
        'total_secured': money(held + furnished),
        'bg': bg_release(held, threshold),
        'bills': len(rows),
    }


def upcoming(lines, within_days=60, as_on=None):
    """Lines whose release falls inside the next ``within_days``.

    Lets a contractor raise the claim *before* the date rather than noticing it
    months later.
    """
    today = _parse(as_on) or date.today()
    horizon = today + timedelta(days=int(within_days or 0))
    out = []
    for ln in lines or []:
        if outstanding(ln.get('withheld'), ln.get('released')) <= 0:
            continue
        due = _parse(ln.get('due_date'))
        if due is not None and today <= due <= horizon:
            out.append(ln)
    return out
