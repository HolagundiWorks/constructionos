"""Statutory compliance calendar — what is due, when, and whether it is done.

No tkinter, no database. Generates the year's filing obligations for an Indian
contractor from a rule table, works out each one's due date, and reports where
it stands.

Why this earns its place: every other deadline in this app is money the
contractor is *owed*. These are deadlines where being late costs them money
directly — late fees per day, interest on unpaid tax, and in the GST case a
customer's input credit that a late return can hold up. Nobody sends a
reminder, and a small firm without a full-time accountant finds out from a
notice.

**The due dates here are defaults, not law.** They are the standard statutory
dates, but the government moves them: GST deadlines have been extended by
notification many times, and state rules differ for professional tax and
labour cess. Every date is derived from an editable rule rather than
hard-coded, and the UI says plainly that a notification overrides the default.
Presenting these as authoritative would be worse than presenting nothing,
because a contractor would stop checking.

Deliberately **not** included: any penalty or late-fee computation. Those rates
change often and vary by return, turnover and whether the return is nil.
Showing a confident wrong figure for what someone owes is worse than showing
days late and letting their accountant price it.
"""

from datetime import date, timedelta

import isodate

MONTHLY = 'Monthly'
QUARTERLY = 'Quarterly'
ANNUAL = 'Annual'

# Applicability flags — a contractor ticks what applies to them, because a
# calendar full of obligations that do not apply is one nobody reads.
GST = 'gst'
GST_COMPOSITION = 'gst_composition'
GST_QRMP = 'gst_qrmp'
TDS = 'tds'
PF = 'pf'
ESI = 'esi'
CESS = 'cess'
INCOME_TAX = 'income_tax'

# Each rule: due_day / month_offset are counted from the END of the period.
# ``exceptions`` maps a period-ending month to its own (month_offset, day) —
# the March cases are the ones people get wrong, and they are worth the extra
# machinery on their own.
OBLIGATIONS = [
    {'key': 'gstr1', 'name': 'GSTR-1 (outward supplies)', 'authority': 'GST',
     'frequency': MONTHLY, 'month_offset': 1, 'due_day': 11, 'applies': GST,
     'note': 'Your buyer cannot claim input credit until this is filed.'},
    {'key': 'gstr3b', 'name': 'GSTR-3B (summary return and tax payment)',
     'authority': 'GST', 'frequency': MONTHLY, 'month_offset': 1,
     'due_day': 20, 'applies': GST,
     'note': 'Interest runs on tax paid late, separately from the late fee.'},
    {'key': 'gstr1_q', 'name': 'GSTR-1 (quarterly, QRMP scheme)',
     'authority': 'GST', 'frequency': QUARTERLY, 'month_offset': 1,
     'due_day': 13, 'applies': GST_QRMP,
     'note': 'QRMP filers still pay tax monthly by challan (PMT-06).'},
    {'key': 'cmp08', 'name': 'CMP-08 (composition scheme statement)',
     'authority': 'GST', 'frequency': QUARTERLY, 'month_offset': 1,
     'due_day': 18, 'applies': GST_COMPOSITION},
    {'key': 'gstr9', 'name': 'GSTR-9 (annual return)', 'authority': 'GST',
     'frequency': ANNUAL, 'month_offset': 9, 'due_day': 31, 'applies': GST,
     'note': 'For the financial year just ended.'},

    {'key': 'tds_payment', 'name': 'TDS payment (challan ITNS-281)',
     'authority': 'Income Tax', 'frequency': MONTHLY, 'month_offset': 1,
     'due_day': 7, 'applies': TDS,
     'exceptions': {3: (1, 30)},
     'note': 'March deduction is due 30 April, not 7 April — the one most '
             'often missed.'},
    {'key': 'tds_26q', 'name': 'TDS return 26Q', 'authority': 'Income Tax',
     'frequency': QUARTERLY, 'month_offset': 1, 'due_day': 31, 'applies': TDS,
     'exceptions': {3: (2, 31)},
     'note': 'The January-March quarter is due 31 May, not 30 April.'},

    {'key': 'pf_ecr', 'name': 'PF contribution and ECR',
     'authority': 'EPFO', 'frequency': MONTHLY, 'month_offset': 1,
     'due_day': 15, 'applies': PF},
    {'key': 'esi', 'name': 'ESI contribution', 'authority': 'ESIC',
     'frequency': MONTHLY, 'month_offset': 1, 'due_day': 15, 'applies': ESI},
    {'key': 'bocw_cess', 'name': 'Labour welfare cess (BOCW)',
     'authority': 'Labour Dept', 'frequency': MONTHLY, 'month_offset': 1,
     'due_day': 30, 'applies': CESS,
     'note': 'State rules vary — check your own board\'s date.'},

    {'key': 'advance_tax', 'name': 'Advance tax instalment',
     'authority': 'Income Tax', 'frequency': QUARTERLY, 'month_offset': 0,
     'due_day': 15, 'applies': INCOME_TAX,
     'note': 'Due on the 15th of the last month of each quarter.'},
    {'key': 'itr', 'name': 'Income tax return', 'authority': 'Income Tax',
     'frequency': ANNUAL, 'month_offset': 4, 'due_day': 31,
     'applies': INCOME_TAX,
     'note': 'Non-audit case. An audited return is due 31 October.'},
]

BY_KEY = {o['key']: o for o in OBLIGATIONS}

FILED = 'Filed'
OVERDUE = 'OVERDUE'
DUE = 'Due soon'
UPCOMING = 'Upcoming'


def _parse(value):
    """Tolerant ISO-date parse; ``None`` on anything unusable."""
    return isodate.parse(value)


def _clamped(year, month, day):
    """A date in (year, month), pulling `day` back to the month's last day.

    Statutory dates are routinely quoted as the 30th or 31st; February needs
    the clamp, and silently rolling into March would move a deadline.
    """
    while day > 1:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, 1)


def _add_months(year, month, offset):
    total = (year * 12 + (month - 1)) + int(offset or 0)
    return total // 12, total % 12 + 1


def fy_label(fy_start_year):
    """'FY 2026-27' for the year beginning April `fy_start_year`."""
    return 'FY {}-{:02d}'.format(fy_start_year, (fy_start_year + 1) % 100)


def current_fy(as_on=None):
    """The financial year containing `as_on` — April to March."""
    today = _parse(as_on) or date.today()
    return today.year if today.month >= 4 else today.year - 1


def periods_for_fy(frequency, fy_start_year):
    """``[(label, end_year, end_month), ...]`` for one financial year.

    Periods are identified by the month they *end* in, because every due date
    is expressed as an offset from the period end.
    """
    out = []
    if frequency == MONTHLY:
        for i in range(12):
            y, m = _add_months(fy_start_year, 4, i)
            out.append(('{}-{:02d}'.format(y, m), y, m))
    elif frequency == QUARTERLY:
        for q in range(4):
            y, m = _add_months(fy_start_year, 6, q * 3)   # Jun, Sep, Dec, Mar
            out.append(('Q{} {}'.format(q + 1, fy_label(fy_start_year)), y, m))
    elif frequency == ANNUAL:
        out.append((fy_label(fy_start_year), fy_start_year + 1, 3))
    return out


def due_date(obligation, end_year, end_month):
    """When a period's filing is due."""
    if isinstance(obligation, str):
        obligation = BY_KEY.get(obligation)
    if not obligation:
        return None
    offset = obligation.get('month_offset', 1)
    day = obligation.get('due_day', 1)
    exceptions = obligation.get('exceptions') or {}
    if end_month in exceptions:
        offset, day = exceptions[end_month]
    y, m = _add_months(end_year, end_month, offset)
    return _clamped(y, m, day)


def calendar_for_fy(fy_start_year, applicable=None):
    """Every filing due in one financial year, in due-date order.

    ``applicable`` is the set of flags the firm has ticked; with none given
    nothing is returned rather than everything, because a calendar showing a
    sole proprietor their ESI obligations trains them to ignore it.
    """
    flags = set(applicable or ())
    rows = []
    for ob in OBLIGATIONS:
        if ob['applies'] not in flags:
            continue
        for label, ey, em in periods_for_fy(ob['frequency'], fy_start_year):
            rows.append({
                'obligation': ob['key'],
                'name': ob['name'],
                'authority': ob['authority'],
                'frequency': ob['frequency'],
                'period': label,
                'due_date': due_date(ob, ey, em).isoformat(),
                'note': ob.get('note', ''),
            })
    rows.sort(key=lambda r: (r['due_date'], r['name']))
    return rows


def status(due, filed_date=None, as_on=None, warn_days=7):
    """Where one filing stands.

    A filing is Filed the moment a date is recorded, late or not — the history
    of *when* it was filed is preserved in the row, but the calendar's job is
    to show what still needs doing.
    """
    if _parse(filed_date) is not None:
        return FILED
    due_d = _parse(due)
    if due_d is None:
        return UPCOMING
    today = _parse(as_on) or date.today()
    if today > due_d:
        return OVERDUE
    if (due_d - today).days <= int(warn_days or 0):
        return DUE
    return UPCOMING


def days_late(due, filed_date=None, as_on=None):
    """Days past the due date — of the filing if filed, else of today.

    Returns 0 when on time and None when there is nothing to measure, so a
    caller can tell "on time" from "unknown".
    """
    due_d = _parse(due)
    if due_d is None:
        return None
    reference = _parse(filed_date) or _parse(as_on) or date.today()
    return max((reference - due_d).days, 0)


def upcoming(rows, within_days=30, as_on=None):
    """Unfiled obligations due inside the window, soonest first."""
    today = _parse(as_on) or date.today()
    horizon = today + timedelta(days=int(within_days or 0))
    out = []
    for r in rows or []:
        if _parse(r.get('filed_date')) is not None:
            continue
        due_d = _parse(r.get('due_date'))
        if due_d is not None and today <= due_d <= horizon:
            out.append(r)
    return sorted(out, key=lambda r: r['due_date'])


def overdue(rows, as_on=None):
    """Unfiled obligations whose date has passed, oldest first."""
    today = _parse(as_on) or date.today()
    out = [r for r in rows or []
           if _parse(r.get('filed_date')) is None
           and (_parse(r.get('due_date')) or today) < today]
    return sorted(out, key=lambda r: r['due_date'])


def summarise(rows, as_on=None, within_days=30):
    """Headline counts for the calendar and the KPI feed."""
    rows = list(rows or [])
    late = overdue(rows, as_on)
    soon = upcoming(rows, within_days, as_on)
    worst = 0
    for r in late:
        worst = max(worst, days_late(r.get('due_date'), as_on=as_on) or 0)
    return {
        'total': len(rows),
        'filed': len([r for r in rows if _parse(r.get('filed_date'))]),
        'overdue': len(late),
        'due_soon': len(soon),
        'max_days_late': worst,
        'next': soon[0] if soon else None,
    }
