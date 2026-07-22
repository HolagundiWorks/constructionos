"""Assemble each project's four base EVM numbers from the app's own figures.

The maths lives in :mod:`earnedvalue` (pure, unit-tested). This is the thin DB
bridge that decides where BAC/PV/EV/AC come from for a real project, so the tab
and any report share one honest definition:

* **BAC** — the project's contract value, falling back to its budget. The whole
  job's authorised value.
* **AC**  — cost to date: ``project_cost_rollup``'s ``total_cost`` (material +
  labour + hire attributed to the project).
* **EV**  — value of work done to date: the same rollup's ``revenue``, i.e. the
  Approved/Paid RA and tax bills raised against the job. This is a *billed*
  proxy for earned value — truthful, but it tracks certification, not raw site
  progress, so a job measured-but-not-yet-billed reads low.
* **PV**  — planned value at today: ``BAC × planned%``, where planned% is the
  fraction of the project's own ``start_date``..``end_date`` window elapsed.
  A baseline S-curve would give a truer PV; time-elapsed is the honest stand-in
  when no baseline programme exists (``None`` planned% ⇒ PV 0, SPI blank).

DB-only, no tkinter. ``project_cost_rollup`` is imported lazily inside the call
(exactly as :mod:`dashboard` and :mod:`tab_kpi` do) so a head-less caller — the
web server, a test — doesn't drag the GUI in at import time.
"""

from datetime import date

import earnedvalue


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _parse(value):
    """A YYYY-MM-DD(...) string to a ``date``, or ``None`` if unparseable."""
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (ValueError, TypeError, AttributeError):
        return None


def planned_pct(start_date, end_date, today=None):
    """Percent of the project window elapsed at ``today``, clamped 0..100.

    Returns ``None`` when the dates are missing or degenerate (end on/before
    start) — the caller then leaves PV at 0 and SPI blank rather than inventing
    a schedule. Pure: exercised directly by the tests.
    """
    start, end = _parse(start_date), _parse(end_date)
    now = _parse(today) if today is not None else date.today()
    if not start or not end or not now or end <= start:
        return None
    span = (end - start).days
    done = (now - start).days
    return max(0.0, min(100.0, round(done / span * 100.0, 1)))


def project_evm(conn, project, today=None):
    """Full EVM dict for one ``projects`` row (a Row/dict with id, name, …).

    Wraps :func:`earnedvalue.earned_value` and tacks on ``id``, ``name`` and the
    ``planned_pct`` used, so a caller can render a row without re-querying.
    """
    from tab_projects import project_cost_rollup

    pid = project['id']
    bac = _num(project['contract_value']) or _num(project['budget'])
    roll = project_cost_rollup(conn, pid)
    ac = _num(roll.get('total_cost'))
    ev = _num(roll.get('revenue'))
    pp = planned_pct(project['start_date'], project['end_date'], today)
    pv = earnedvalue.pv_from_planned(bac, pp) if pp is not None else 0.0

    out = earnedvalue.earned_value(bac, pv, ac, ev)
    out['id'] = pid
    out['name'] = project['name']
    out['planned_pct'] = pp
    return out


def portfolio_evm(conn, today=None):
    """``(rows, portfolio)`` across every project that has a value to measure.

    ``rows`` is a list of :func:`project_evm` dicts; ``portfolio`` is
    :func:`earnedvalue.portfolio` rolled up over them. Projects with neither a
    contract value nor a budget are skipped — there is no baseline to earn
    against, so an EVM line for them would be noise.
    """
    rows = []
    for project in conn.execute('SELECT * FROM projects ORDER BY name').fetchall():
        if not (_num(project['contract_value']) or _num(project['budget'])):
            continue
        rows.append(project_evm(conn, project, today))
    port = earnedvalue.portfolio([(r['name'], r) for r in rows])
    return rows, port
