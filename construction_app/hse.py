"""Pure health & safety maths: permits, incidents, LTIFR (Phase 8, Wave 4).

No tkinter, no database.

Safety at this scale is mostly informal, and pretending otherwise produces a
module nobody fills in. So this is deliberately small and aimed at the two
things that actually bite a small contractor:

* **Permits to work** for the jobs that kill people in this trade — working at
  height, excavation, hot work, confined space, lifting. A permit is only
  meaningful while it is *open and in date*, so the useful question is not
  "is there a permit" but "is this permit valid right now".
* **Incidents**, including near misses. Recording a near miss is the cheapest
  safety measure there is — it is the same event as an injury with the outcome
  changed by luck, and it costs nothing but the writing down.

``LTIFR`` (lost-time injury frequency rate) is included because clients and
tenders ask for it. It is stated per **200,000 hours** worked, the common
convention, and returns None below a threshold of hours rather than a wild
number — one injury in a fortnight's work would otherwise produce a rate that
looks catastrophic and means nothing.
"""

from datetime import date

import finance

# Permit types that matter on an Indian civil site.
PERMIT_TYPES = ['Work at height', 'Excavation', 'Hot work', 'Confined space',
                'Lifting / crane', 'Electrical', 'Demolition', 'Other']

OPEN = 'Open'
CLOSED = 'Closed'
CANCELLED = 'Cancelled'

NEAR_MISS = 'Near miss'
FIRST_AID = 'First aid'
LOST_TIME = 'Lost time'
REPORTABLE = 'Reportable'
SEVERITIES = [NEAR_MISS, FIRST_AID, LOST_TIME, REPORTABLE]

# Injuries that cost time away from work — the numerator of LTIFR.
LOST_TIME_KINDS = (LOST_TIME, REPORTABLE)

# Below this, a frequency rate is noise rather than information.
_MIN_HOURS_FOR_RATE = 10000


def money(value):
    return finance.money(value)


def _parse(d):
    if isinstance(d, date):
        return d
    if not d:
        return None
    try:
        return date.fromisoformat(str(d)[:10])
    except (ValueError, TypeError):
        return None


def _get(row, key, default=''):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def permit_valid(permit, as_on=None):
    """Is this permit open and within its dates? ``(valid, reason)``.

    A permit that has expired is not a lesser permit — it is no permit, and
    saying so plainly is the whole point of issuing one.
    """
    status = str(_get(permit, 'status', OPEN)).strip() or OPEN
    if status != OPEN:
        return False, 'Permit is {}.'.format(status.lower())
    today = _parse(as_on) or date.today()
    start = _parse(_get(permit, 'valid_from', None))
    end = _parse(_get(permit, 'valid_to', None))
    if start and today < start:
        return False, 'Permit does not start until {}.'.format(start.isoformat())
    if end and today > end:
        return False, 'Permit expired on {}.'.format(end.isoformat())
    return True, 'Valid.'


def expiring_permits(permits, within_days=2, as_on=None):
    """Open permits expiring within ``within_days`` — renew before work stops."""
    today = _parse(as_on) or date.today()
    out = []
    for p in permits or []:
        if str(_get(p, 'status', OPEN)).strip() != OPEN:
            continue
        end = _parse(_get(p, 'valid_to', None))
        if end is None:
            continue
        days = (end - today).days
        if 0 <= days <= int(within_days or 0):
            out.append((p, days))
    return sorted(out, key=lambda pd: pd[1])


def ltifr(incidents, hours_worked):
    """Lost-time injuries per 200,000 hours worked.

    None below ``_MIN_HOURS_FOR_RATE``: a rate computed over a fortnight is
    arithmetic, not a safety record, and quoting it would mislead in both
    directions.
    """
    hours = float(hours_worked or 0)
    if hours < _MIN_HOURS_FOR_RATE:
        return None
    lost = sum(1 for i in incidents or []
               if str(_get(i, 'severity', '')).strip() in LOST_TIME_KINDS)
    return money(lost / hours * 200000.0)


def summarise(incidents, permits=None, hours_worked=0, as_on=None):
    """The safety picture: incidents by severity, open permits, LTIFR.

    ``near_miss_ratio`` is worth watching for a reason that is not obvious: a
    site reporting *no* near misses is almost never a safe site, it is a site
    where nobody is writing them down. A healthy ratio is high.
    """
    rows = list(incidents or [])
    by_severity = {s: 0 for s in SEVERITIES}
    lost_days = 0
    for i in rows:
        sev = str(_get(i, 'severity', NEAR_MISS)).strip() or NEAR_MISS
        by_severity[sev] = by_severity.get(sev, 0) + 1
        try:
            lost_days += int(float(_get(i, 'lost_days', 0) or 0))
        except (TypeError, ValueError):
            pass
    near = by_severity.get(NEAR_MISS, 0)
    ratio = money(near / len(rows) * 100.0) if rows else None
    open_permits = [p for p in permits or []
                    if permit_valid(p, as_on)[0]]
    invalid = [p for p in permits or []
               if str(_get(p, 'status', OPEN)).strip() == OPEN
               and not permit_valid(p, as_on)[0]]
    return {
        'total': len(rows),
        'by_severity': by_severity,
        'lost_time': sum(by_severity.get(k, 0) for k in LOST_TIME_KINDS),
        'lost_days': lost_days,
        'near_miss_ratio': ratio,
        'ltifr': ltifr(rows, hours_worked),
        'open_permits': len(open_permits),
        'expired_permits': len(invalid),
    }
