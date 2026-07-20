"""Muster roll structure in CPWA Form 21 shape.

No tkinter, no database. ``wages.py`` computes what one worker earns; this
module arranges those workers into the roll the department expects — a nominal
roll with a day-by-day attendance grid (Part I), and a reconciliation of wages
paid against the value of work measured in the same period (Part II).

Two things drive the design:

**The payee acknowledgement is the point of Part I.** CPWA Form 21 is not a
timesheet; it is proof that named people received named amounts. That is why
the printed roll carries a signature / thumb-impression column per worker.
Most site labour in this market is paid in cash without a payslip, so the
signed muster is often the only evidence a payment happened at all — which
matters to the contractor under a labour inspection, not just to the clerk.

**Unpaid wages do not simply vanish.** When a worker is not present at payment
their entry is struck off the roll and carried to a Register of Unpaid Wages
(Form 21A), so the liability stays visible instead of disappearing when the
next roll is drawn. Here that register is *derived*: anyone on the roll with
no recorded payment for the period is unpaid, so it cannot drift out of step
with what was actually disbursed.

Part II is an honest approximation, and worth being explicit about. The
statutory form reconciles the work done *by that labour* against the
measurement book. This app does not record which worker executed which BOQ
item, so ``work_reconciliation`` compares the period's total wage cost against
the value of work measured in the same period. That answers the question the
form exists to ask — is the wage bill proportionate to what got built — without
pretending to a per-worker attribution the data cannot support.
"""

from datetime import date, timedelta

import isodate
import wages


def _g(row, key, default=None):
    """Read ``key`` from a sqlite3.Row or dict, tolerating absent columns."""
    if row is None:
        return default
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


def _d(value):
    """Parse an ISO date; returns None rather than raising."""
    return isodate.parse(value)


def period_dates(start, end):
    """Every calendar date in the wage period, inclusive.

    Returns [] when either end is unparseable or the range is inverted, so a
    mistyped date produces an empty roll rather than a runaway loop.
    """
    s, e = _d(start), _d(end)
    if s is None or e is None or e < s:
        return []
    return [s + timedelta(days=i) for i in range((e - s).days + 1)]


# Single-letter marks for the printed grid; a full status word per cell would
# make a 7-day roll unreadable on one page.
MARKS = {'Present': 'P', 'Half Day': '½', 'Overtime': 'O', 'Absent': 'A'}


def mark(status):
    return MARKS.get(status, '-')


def attendance_index(attendance_rows):
    """``{(labor_id, iso_date): row}`` for quick per-cell lookup."""
    index = {}
    for row in attendance_rows or []:
        key = (_g(row, 'labor_id'), str(_g(row, 'att_date', '')))
        index[key] = row
    return index


def roll_lines(labour_rows, attendance_rows, start, end, advances=None):
    """Build the nominal roll: one line per worker, with the day grid.

    ``advances`` is ``{labor_id: open balance}``; the deduction is capped at
    gross by ``wages.wage_net`` so a large advance never produces negative pay.
    Workers with no attendance in the period are still listed, with zero days —
    dropping them would silently hide someone who should have been paid.
    """
    index = attendance_index(attendance_rows)
    advances = advances or {}
    dates = period_dates(start, end)
    lines = []
    for worker in labour_rows or []:
        wid = _g(worker, 'id')
        cells, days = [], 0.0
        for day in dates:
            row = index.get((wid, day.isoformat()))
            status = _g(row, 'status', '') if row is not None else ''
            cells.append(mark(status) if row is not None else '-')
            if row is not None:
                days += wages.day_fraction(status, _g(row, 'hours', 8))
        days = round(days, 2)
        amounts = wages.wage_net(days, _g(worker, 'daily_wage', 0),
                                 advances.get(wid, 0))
        lines.append({
            'labor_id': wid,
            'name': _g(worker, 'name', '') or '',
            'father_name': _g(worker, 'father_name', '') or '',
            'skill': _g(worker, 'skill', '') or '',
            'daily_wage': round(float(_g(worker, 'daily_wage', 0) or 0), 2),
            'cells': cells,
            'days': days,
            'gross': amounts['gross'],
            'deduction': amounts['deduction'],
            'net': amounts['net'],
        })
    return lines


def summarise_roll(lines):
    """Totals for the foot of the roll."""
    lines = list(lines or [])
    return {
        'workers': len(lines),
        'days': round(sum(l['days'] for l in lines), 2),
        'gross': round(sum(l['gross'] for l in lines), 2),
        'deduction': round(sum(l['deduction'] for l in lines), 2),
        'net': round(sum(l['net'] for l in lines), 2),
    }


def unpaid_lines(lines, paid_ids):
    """Form 21A: roll entries with no recorded payment for the period.

    Zero-net entries are excluded — a worker who was absent all period is not
    an unpaid wage, just an absence, and listing them would bury the real
    liability in noise.
    """
    paid = {str(p) for p in (paid_ids or [])}
    return [l for l in (lines or [])
            if l['net'] > 0 and str(l['labor_id']) not in paid]


def unpaid_total(lines, paid_ids):
    return round(sum(l['net'] for l in unpaid_lines(lines, paid_ids)), 2)


def work_reconciliation(wage_total, measured_value, threshold_pct=60.0):
    """Part II: is the period's wage bill proportionate to what was built?

    ``ratio_pct`` is labour cost as a percentage of the value of work measured
    in the same period. ``needs_explanation`` is True when it exceeds
    ``threshold_pct`` — high labour against low measured output means either
    work was done but not measured, or wages were paid for work that did not
    happen. Both need an answer written on the roll, which is what the
    statutory form's excess/saving column is for.

    With no measured value the ratio is undefined rather than infinite: an
    unmeasured period is a measurement gap, not a 100% labour ratio.
    """
    wage_total = round(float(wage_total or 0), 2)
    measured_value = round(float(measured_value or 0), 2)
    ratio = (round(wage_total / measured_value * 100.0, 2)
             if measured_value else None)
    return {
        'wage_total': wage_total,
        'measured_value': measured_value,
        'ratio_pct': ratio,
        'difference': round(measured_value - wage_total, 2),
        'needs_explanation': ratio is not None and ratio > threshold_pct,
        'unmeasured': measured_value == 0 and wage_total > 0,
    }
