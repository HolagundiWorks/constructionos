"""Baseline-versus-actual programme, delay attribution, and LD exposure.

No tkinter, no database.

The timeline let dates be edited in place, which means the original plan was
gone the first time anything moved. That is the expensive gap: when a job
finishes late the contractor is asked to prove *what* slipped and *whose fault
it was*, and "we remember it was the drawings" is not evidence. A baseline is
simply the plan frozen at a moment, so the comparison can be made later.

Two numbers come out of that comparison, and both are money:

**Liquidated damages exposure.** A PWD contract typically charges a percentage
of contract value per week of delay, capped at a percentage of the whole. Knowing
that figure mid-job is what makes acceleration a decision rather than a panic.

**Extension of time.** Delay caused by the employer — late drawings, late site
access, a variation, exceptional weather — is normally excusable, and days
granted reduce the delay LDs are computed on. The claim has to name the cause
and the dates, which is exactly what per-task attribution produces.

Three honesty constraints, all load-bearing:

* The LD figure is an **exposure estimate on the terms entered**, never a
  statement of what will be charged. Contracts differ, and departments remit.
* Days are **claimable**, not granted. Only the employer grants an extension;
  the app reports what the record supports asking for.
* **Re-baselining destroys the evidence.** Overwriting the frozen plan with
  today's dates makes the slip vanish, and with it any EOT claim. The module
  will do it, but the caller has to ask explicitly.
"""

from datetime import date

# Who caused the delay. The split that matters is whether it supports an
# extension of time, not who is to blame in conversation.
OWN = 'Own'                     # contractor's own resources, method, labour
CLIENT = 'Client'               # late drawings, access, decisions, payment
VARIATION = 'Variation'         # extra or changed work instructed
WEATHER = 'Weather'             # exceptional, beyond what was foreseeable
STATUTORY = 'Statutory'         # permits, utility shifting, authority delay
SUBCONTRACTOR = 'Subcontractor'  # a domestic sub — normally the main's risk

CAUSES = [OWN, CLIENT, VARIATION, WEATHER, STATUTORY, SUBCONTRACTOR]

# Causes that normally support an extension of time. Weather and statutory
# delay are the arguable ones — many contracts allow them, some do not — so
# they are included by default but the caller can override the set rather than
# the module pretending the answer is universal.
EXCUSABLE = frozenset({CLIENT, VARIATION, WEATHER, STATUTORY})

DEFAULT_LD_PCT_PER_WEEK = 0.5
DEFAULT_LD_CAP_PCT = 10.0


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


def _num(value, default=0.0):
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def slip_days(baseline, actual):
    """Days later than baseline. Negative means early. ``None`` if unknowable.

    Returning None rather than 0 for a missing date matters: "no baseline" and
    "on time" are different states, and reporting the first as the second
    would make an unbaselined programme look perfectly healthy.
    """
    b, a = _parse(baseline), _parse(actual)
    if b is None or a is None:
        return None
    return (a - b).days


def has_baseline(task):
    """True once a task's plan has been frozen."""
    return _parse(_g(task, 'baseline_end')) is not None


def effective_finish(task):
    """The date this task is expected to finish — actual if it has, else planned."""
    return _parse(_g(task, 'actual_end')) or _parse(_g(task, 'end_date'))


def task_variance(task):
    """One task's baseline-versus-current position."""
    b_start = _parse(_g(task, 'baseline_start'))
    b_end = _parse(_g(task, 'baseline_end'))
    finish = effective_finish(task)
    start = _parse(_g(task, 'actual_start')) or _parse(_g(task, 'start_date'))
    cause = str(_g(task, 'delay_cause', '') or '').strip()
    finish_slip = slip_days(b_end, finish)
    return {
        'id': _g(task, 'id'),
        'task_name': _g(task, 'task_name', ''),
        'baseline_start': b_start.isoformat() if b_start else '',
        'baseline_finish': b_end.isoformat() if b_end else '',
        'start': start.isoformat() if start else '',
        'finish': finish.isoformat() if finish else '',
        'actual_finish': _g(task, 'actual_end', '') or '',
        'start_slip': slip_days(b_start, start),
        'finish_slip': finish_slip,
        'status': _g(task, 'status', ''),
        'cause': cause,
        'note': _g(task, 'delay_note', '') or '',
        'complete': bool(_parse(_g(task, 'actual_end'))),
        'baselined': b_end is not None,
    }


def programme_finish(tasks, key='end_date'):
    """The programme's finish date: the latest task finish on that basis."""
    dates = []
    for t in tasks or []:
        d = effective_finish(t) if key == 'effective' else _parse(_g(t, key))
        if d is not None:
            dates.append(d)
    return max(dates) if dates else None


def delay_summary(tasks, excusable=EXCUSABLE):
    """Programme-level delay, split by whether it supports an EOT claim.

    ``claimable_days`` is the largest excusable finish-slip on the programme,
    **not** the sum. Delays overlap in time — three tasks each a fortnight late
    because the same drawings were late is a fortnight of delay, not six weeks.
    Summing them is the most common way an EOT claim is inflated to the point
    of being rejected whole.
    """
    variances = [task_variance(t) for t in tasks or []]
    baselined = [v for v in variances if v['baselined']]
    baseline_finish = programme_finish(tasks, 'baseline_end')
    forecast_finish = programme_finish(tasks, 'effective')
    total = slip_days(baseline_finish, forecast_finish)

    late = [v for v in baselined if (v['finish_slip'] or 0) > 0]
    claimable = 0
    for v in late:
        if v['cause'] in excusable:
            claimable = max(claimable, v['finish_slip'])
    unattributed = [v for v in late if not v['cause']]

    return {
        'tasks': len(variances),
        'baselined': len(baselined),
        'unbaselined': len(variances) - len(baselined),
        'baseline_finish': baseline_finish.isoformat() if baseline_finish else '',
        'forecast_finish': forecast_finish.isoformat() if forecast_finish else '',
        'total_delay_days': total,
        'late_tasks': len(late),
        'claimable_days': claimable,
        'unattributed_tasks': len(unattributed),
        'worst': max(late, key=lambda v: v['finish_slip']) if late else None,
    }


def net_delay(total_delay_days, eot_granted_days=0):
    """Delay left after the extension actually granted. Never negative."""
    total = int(_num(total_delay_days))
    return max(total - int(_num(eot_granted_days)), 0)


def ld_exposure(contract_value, net_delay_days,
                pct_per_week=DEFAULT_LD_PCT_PER_WEEK,
                cap_pct=DEFAULT_LD_CAP_PCT):
    """Liquidated-damages exposure on the terms entered.

    Part weeks count as whole weeks, which is how these clauses usually read
    and is the conservative direction for a contractor to plan against. The cap
    is applied last, because a capped figure that ignores the cap is the one
    number that would actually mislead.

    This is an estimate on the entered terms, not a statement of what will be
    charged: contracts differ and departments remit.
    """
    value = _num(contract_value)
    days = max(int(_num(net_delay_days)), 0)
    weeks = -(-days // 7)                      # ceiling division: part week = week
    raw = value * _num(pct_per_week) / 100.0 * weeks
    cap = value * _num(cap_pct) / 100.0
    capped = min(raw, cap) if cap > 0 else raw
    return {
        'delay_days': days,
        'weeks_charged': weeks,
        'pct_per_week': _num(pct_per_week),
        'cap_pct': _num(cap_pct),
        'raw': round(raw, 2),
        'cap_amount': round(cap, 2),
        'exposure': round(capped, 2),
        'at_cap': cap > 0 and raw >= cap,
    }


def position(tasks, contract_value=0, eot_granted_days=0,
             pct_per_week=DEFAULT_LD_PCT_PER_WEEK,
             cap_pct=DEFAULT_LD_CAP_PCT, excusable=EXCUSABLE):
    """The whole programme position: delay, what is claimable, what it costs."""
    summary = delay_summary(tasks, excusable)
    total = summary['total_delay_days'] or 0
    net = net_delay(total, eot_granted_days)
    ld = ld_exposure(contract_value, net, pct_per_week, cap_pct)
    summary.update({
        'eot_granted_days': int(_num(eot_granted_days)),
        'net_delay_days': net,
        'ld': ld,
        # What the exposure would fall to if the claimable days were granted.
        'exposure_if_claim_succeeds': ld_exposure(
            contract_value,
            net_delay(total, int(_num(eot_granted_days))
                      + summary['claimable_days']),
            pct_per_week, cap_pct)['exposure'],
    })
    return summary


def baseline_payload(tasks):
    """``[(id, start, end)]`` for tasks that can be frozen.

    A task with no planned dates is skipped rather than frozen empty — an empty
    baseline would later read as "no baseline" anyway, and writing one would
    only make the count of baselined tasks lie.
    """
    out = []
    for t in tasks or []:
        start = _g(t, 'start_date', '') or ''
        end = _g(t, 'end_date', '') or ''
        if _parse(end) is None:
            continue
        out.append((_g(t, 'id'), start, end))
    return out


def rebaseline_warning(tasks):
    """What would be lost by re-freezing the baseline over existing slip.

    Called before overwriting, so the warning can quote the real figure rather
    than a generic caution nobody reads.
    """
    summary = delay_summary(tasks)
    return {
        'already_baselined': summary['baselined'],
        'delay_days_erased': summary['total_delay_days'] or 0,
        'claimable_days_erased': summary['claimable_days'],
    }
