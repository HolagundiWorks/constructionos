"""Plant maintenance and fuel analysis.

No tkinter, no database. The daily plant log already captured hours run,
diesel issued and downtime; nothing ever computed anything from them. This
module turns that log into the two answers that carry money:

**Is a machine burning more diesel than it should?** Fuel is the classic leak
on a small site — drawn against a machine that did not run, or topped up twice
against one entry. The baseline here is deliberately **each machine's own
median litres per hour**, not a fleet average and not a manufacturer figure. A
JCB and a needle vibrator have nothing to say to each other, and a spec sheet
describes a new machine in a laboratory. The median rather than the mean
because the outliers are exactly what is being hunted, and a mean quietly
absorbs them.

**Is a machine due for service?** On hours run or on elapsed days, whichever
falls first, because a mixer that sat idle through the monsoon still needs its
oil changed. A seizure mid-pour costs the machine, the pour, and the day.

Two honesty constraints:

* Nothing is called theft. The module reports *unusual* consumption and leaves
  the conclusion to the person who knows whether the machine spent Tuesday
  idling on standby. Accusing a named operator on arithmetic alone would be
  both wrong and, on a small site, unforgivable.
* No outlier is reported until a machine has enough history to have a norm.
  With three logs "unusual" means nothing, and crying wolf early is how a
  useful signal gets ignored.
"""

from datetime import date
from statistics import median

# A machine needs this many usable logs before its own median means anything.
MIN_SAMPLE = 5

# Consumption above baseline x (1 + this) is worth a look.
DEFAULT_TOLERANCE_PCT = 30.0

OK = 'OK'
DUE = 'Due'
OVERDUE = 'OVERDUE'
UNKNOWN = 'Not scheduled'


def _num(value, default=0.0):
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _g(row, key, default=None):
    if row is None:
        return default
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


def _parse(value):
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def machine_key(row):
    """Group logs by equipment id when present, else by trimmed name.

    Older logs predate the link to the equipment master and carry only free
    text, so both have to work. Names are lower-cased because 'JCB' and 'jcb'
    are one machine to everyone except a GROUP BY.
    """
    eid = _g(row, 'equipment_id')
    if eid:
        return ('id', eid)
    return ('name', str(_g(row, 'equipment', '') or '').strip().lower())


def litres_per_hour(hours, diesel):
    """Fuel burn rate. ``None`` when the machine did not run.

    Dividing by zero hours would be infinite, and reporting a machine that sat
    still as infinitely thirsty is noise — that case is handled separately by
    ``fuel_without_work``, where it means something specific.
    """
    hours = _num(hours)
    if hours <= 0:
        return None
    return round(_num(diesel) / hours, 2)


def availability(hours_run, downtime_hrs):
    """Share of engaged time the machine was actually working, as a percent."""
    run = _num(hours_run)
    down = _num(downtime_hrs)
    engaged = run + down
    if engaged <= 0:
        return None
    return round(run / engaged * 100.0, 1)


def summarise_machine(logs):
    """Totals and burn rate for one machine's logs."""
    logs = list(logs or [])
    hours = round(sum(_num(_g(l, 'hours_run')) for l in logs), 2)
    diesel = round(sum(_num(_g(l, 'diesel_ltr')) for l in logs), 2)
    downtime = round(sum(_num(_g(l, 'downtime_hrs')) for l in logs), 2)
    rates = [r for r in (litres_per_hour(_g(l, 'hours_run'), _g(l, 'diesel_ltr'))
                         for l in logs) if r is not None]
    return {
        'logs': len(logs),
        'hours': hours,
        'diesel': diesel,
        'downtime': downtime,
        'litres_per_hour': round(diesel / hours, 2) if hours > 0 else None,
        'median_lph': round(median(rates), 2) if rates else None,
        'availability': availability(hours, downtime),
        'samples': len(rates),
    }


def group_by_machine(logs):
    """``{machine_key: [logs]}`` preserving input order within each machine."""
    out = {}
    for row in logs or []:
        out.setdefault(machine_key(row), []).append(row)
    return out


def fuel_without_work(logs):
    """Diesel issued on a day the machine recorded no hours.

    The cleanest signal in the log: fuel left the store and no work came back.
    It has innocent explanations — a tank filled the evening before a job, a
    genset run not metered — so it is reported, not judged.
    """
    return [l for l in logs or []
            if _num(_g(l, 'diesel_ltr')) > 0 and _num(_g(l, 'hours_run')) <= 0]


def fuel_outliers(logs, tolerance_pct=DEFAULT_TOLERANCE_PCT,
                  min_sample=MIN_SAMPLE):
    """Days a machine burned notably more per hour than it usually does.

    Each machine is judged against its own median, and only once it has
    ``min_sample`` usable days. Returns one dict per flagged day with the
    baseline it was judged against, so the reader can disagree with the call
    rather than having to trust it.
    """
    flagged = []
    for _key, rows in group_by_machine(logs).items():
        rates = [(l, litres_per_hour(_g(l, 'hours_run'), _g(l, 'diesel_ltr')))
                 for l in rows]
        usable = [(l, r) for l, r in rates if r is not None and r > 0]
        if len(usable) < int(min_sample or 0):
            continue
        baseline = median([r for _l, r in usable])
        if baseline <= 0:
            continue
        threshold = baseline * (1 + _num(tolerance_pct) / 100.0)
        for log, rate in usable:
            if rate > threshold:
                flagged.append({
                    'log_date': _g(log, 'log_date', ''),
                    'equipment': _g(log, 'equipment', ''),
                    'operator': _g(log, 'operator', ''),
                    'hours_run': _num(_g(log, 'hours_run')),
                    'diesel_ltr': _num(_g(log, 'diesel_ltr')),
                    'litres_per_hour': rate,
                    'baseline': round(baseline, 2),
                    'excess_pct': round((rate / baseline - 1) * 100.0, 1),
                })
    return sorted(flagged, key=lambda f: f['excess_pct'], reverse=True)


def excess_litres(flagged):
    """Litres above baseline across flagged days — the size of the question.

    Not a loss figure. It is what the extra consumption came to if the
    baseline was right, which is the number worth asking about.
    """
    total = 0.0
    for f in flagged or []:
        total += (f['litres_per_hour'] - f['baseline']) * f['hours_run']
    return round(max(total, 0.0), 2)


# ------------------------------------------------------------ maintenance
def hours_since_service(logs, last_service_date=None):
    """Hours run since the last service (all logged hours if never serviced).

    A log whose date will not parse is **counted**, not skipped. It cannot be
    placed either side of the service, and the two failure directions are not
    equal: counting it may service a machine early, skipping it may leave a
    seizure to happen. Oil is cheaper than a crankshaft.
    """
    since = _parse(last_service_date)
    total = 0.0
    for l in logs or []:
        when = _parse(_g(l, 'log_date'))
        if since is not None and when is not None and when <= since:
            continue
        total += _num(_g(l, 'hours_run'))
    return round(total, 2)


def service_status(machine, logs, as_on=None):
    """Where one machine stands against its service schedule.

    Checks hours and days independently and reports the more urgent, because
    a machine that sat idle all season still needs its oil changed and one
    that ran flat out for a fortnight needs it early.

    A machine with no interval set is ``Not scheduled`` rather than OK — the
    app does not know it is fine, and saying OK would be a claim it cannot
    support.
    """
    today = _parse(as_on) or date.today()
    interval_h = _num(_g(machine, 'service_interval_hours'))
    interval_d = _num(_g(machine, 'service_interval_days'))
    last_date = _parse(_g(machine, 'last_service_date'))
    run = hours_since_service(logs, _g(machine, 'last_service_date'))

    hours_left = interval_h - run if interval_h > 0 else None
    days_left = None
    if interval_d > 0 and last_date is not None:
        days_left = int(interval_d) - (today - last_date).days

    # Either measure can trigger, and the more urgent one wins. "Due" means
    # inside the last tenth of the hours interval, or inside a week of the
    # date — enough warning to order the oil and pick a slack day.
    candidates = [v for v in (hours_left, days_left) if v is not None]
    hours_warn = max(interval_h * 0.1, 1) if interval_h > 0 else 0
    if not candidates:
        status = UNKNOWN
    elif min(candidates) < 0:
        status = OVERDUE
    elif (hours_left is not None and hours_left <= hours_warn) or \
         (days_left is not None and days_left <= 7):
        status = DUE
    else:
        status = OK

    return {
        'name': _g(machine, 'name', ''),
        'equipment_id': _g(machine, 'id'),
        'hours_since_service': run,
        'interval_hours': interval_h or None,
        'hours_left': round(hours_left, 2) if hours_left is not None else None,
        'interval_days': int(interval_d) if interval_d else None,
        'days_left': days_left,
        'last_service_date': _g(machine, 'last_service_date', '') or '',
        'status': status,
    }


def due_for_service(statuses):
    """Machines needing attention, most overdue first."""
    ranked = [s for s in statuses or [] if s['status'] in (DUE, OVERDUE)]

    def urgency(s):
        vals = [v for v in (s['hours_left'], s['days_left']) if v is not None]
        return min(vals) if vals else 0
    return sorted(ranked, key=urgency)


def fleet_summary(statuses, flagged=None, logs=None):
    """Headline counts for the fleet view and the KPI feed."""
    statuses = list(statuses or [])
    flagged = list(flagged or [])
    return {
        'machines': len(statuses),
        'overdue': len([s for s in statuses if s['status'] == OVERDUE]),
        'due': len([s for s in statuses if s['status'] == DUE]),
        'unscheduled': len([s for s in statuses if s['status'] == UNKNOWN]),
        'fuel_flags': len(flagged),
        'excess_litres': excess_litres(flagged),
        'fuel_without_work': len(fuel_without_work(logs)),
    }
