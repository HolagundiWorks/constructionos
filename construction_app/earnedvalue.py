"""Earned Value Management (EVM) — the money+schedule forecast, as pure maths.

No tkinter, no database. This is the E0 foundation the enterprise roadmap
(``docs/ENTERPRISE-PM-SOLUTION.md`` / ``docs/ROADMAP.md``) leans on: it turns three numbers the
app already knows into the standard cost/schedule performance indices and a
forecast-at-completion, so a KPI board can say not just *where we are* but *where
this is heading*.

The three inputs, and where they come from in this app:

* **BAC** — Budget At Completion. The tendered contract / BOQ value, or the
  project budget (``analytics.contract_progress`` ``boq_value``; project budget).
* **EV**  — Earned Value (BCWP): the *budgeted* value of the work actually done.
  In civil billing that is the **measured value** — work measured against the BOQ
  (``analytics.contract_progress`` ``measured_value``). It is a value, not a cost.
* **AC**  — Actual Cost (ACWP): what that work actually cost. The project cost
  rollup (``projectcost.rollup`` ``total_cost``).
* **PV**  — Planned Value (BCWS): the value that *should* have been earned by the
  data date, per the baseline programme. This is the one input not always to
  hand; pass it, or derive it from a planned-percent with ``pv_from_planned``.

Everything else is derived. Two honesty rules, the same as the rest of the pure
layer: a ratio whose denominator is zero is **None** (undefined, not a
fabricated 0 or infinity), and money rounds to 2 / indices to 3 / percentages to
1 so the numbers read like the rest of the app.

Exercise with ``python -c`` — e.g.::

    python -c "import earnedvalue as e; print(e.earned_value(100, 40, 50, 45))"
"""


def _num(value, default=0.0):
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _ratio(part, whole, ndigits=3):
    """``part / whole`` rounded, or None when ``whole`` is 0 (undefined)."""
    whole = _num(whole)
    if not whole:
        return None
    return round(_num(part) / whole, ndigits)


def _pct(part, whole, ndigits=1):
    r = _ratio(part, whole, ndigits + 4)
    return None if r is None else round(r * 100.0, ndigits)


# --------------------------------------------------------------- derive inputs

def ev_from_progress(bac, progress_pct):
    """Earned Value from physical progress: ``BAC x progress% / 100``.

    Handy when you have a progress percentage rather than a measured rupee value.
    In this app the measured value *is* the earned value, so prefer passing that
    directly; this is the fallback when only a percent is known."""
    return round(_num(bac) * _num(progress_pct) / 100.0, 2)


def pv_from_planned(bac, planned_pct):
    """Planned Value from the baseline's planned percent-complete at the data
    date: ``BAC x planned% / 100``. The baseline programme owns ``planned%``;
    this only turns it into a value."""
    return round(_num(bac) * _num(planned_pct) / 100.0, 2)


# --------------------------------------------------------------------- indices

def schedule_variance(ev, pv):
    """SV = EV - PV. Positive = ahead of schedule (in value terms)."""
    return round(_num(ev) - _num(pv), 2)


def cost_variance(ev, ac):
    """CV = EV - AC. Positive = under budget."""
    return round(_num(ev) - _num(ac), 2)


def spi(ev, pv):
    """Schedule Performance Index = EV / PV. >1 ahead, <1 behind. None if PV=0."""
    return _ratio(ev, pv)


def cpi(ev, ac):
    """Cost Performance Index = EV / AC. >1 under budget, <1 over. None if AC=0."""
    return _ratio(ev, ac)


# ------------------------------------------------------------------- forecasts
# Estimate At Completion (EAC) has more than one honest formula because it rests
# on an assumption about the *future*, which the maths cannot settle:
#
#   * 'cpi'      EAC = BAC / CPI           — today's cost efficiency continues.
#                The usual default when the overrun is systemic, not a one-off.
#   * 'budget'   EAC = AC + (BAC - EV)     — the variance was a one-off; the
#                remaining work runs at the budgeted rate.
#   * 'cpi_spi'  EAC = AC + (BAC-EV)/(CPI*SPI) — both cost *and* schedule
#                pressure continue; the most pessimistic of the three.
#
# So EAC is returned as a dict of all three (None where undefined), plus a
# ``default`` — the CPI method, falling back to the budget method when CPI is
# undefined — rather than pretending one number is *the* forecast.

def eac_methods(bac, ev, ac, cpi_value, spi_value):
    bac, ev, ac = _num(bac), _num(ev), _num(ac)
    remaining = bac - ev

    by_cpi = round(bac / cpi_value, 2) if cpi_value else None
    by_budget = round(ac + remaining, 2)
    denom = (cpi_value or 0) * (spi_value or 0)
    by_cpi_spi = round(ac + remaining / denom, 2) if denom else None

    default = by_cpi if by_cpi is not None else by_budget
    return {
        'cpi': by_cpi,
        'budget': by_budget,
        'cpi_spi': by_cpi_spi,
        'default': default,
    }


def tcpi(bac, ev, ac):
    """To-Complete Performance Index = (BAC - EV) / (BAC - AC).

    The cost efficiency the *remaining* work must achieve to still land on BAC.
    >1 means you must do better than budget from here — a red flag. None when
    the work left to fund (BAC - AC) is zero."""
    bac, ev, ac = _num(bac), _num(ev), _num(ac)
    return _ratio(bac - ev, bac - ac)


# ----------------------------------------------------------------- the rollup

def earned_value(bac, pv, ac, ev):
    """The full EVM picture from the four base numbers.

    Returns the inputs, the variances (SV/CV), the indices (SPI/CPI), percent
    complete vs percent spent, and the forecast block (EAC methods, ETC, VAC,
    TCPI). Ratios are None where undefined rather than faked.
    """
    bac, pv, ac, ev = _num(bac), _num(pv), _num(ac), _num(ev)
    cpi_value = cpi(ev, ac)
    spi_value = spi(ev, pv)
    eac = eac_methods(bac, ev, ac, cpi_value, spi_value)
    eac_default = eac['default']

    return {
        'bac': round(bac, 2),
        'pv': round(pv, 2),
        'ev': round(ev, 2),
        'ac': round(ac, 2),
        'sv': schedule_variance(ev, pv),
        'cv': cost_variance(ev, ac),
        'spi': spi_value,
        'cpi': cpi_value,
        'percent_complete': _pct(ev, bac),   # value earned / budget
        'percent_spent': _pct(ac, bac),      # cost incurred / budget
        'eac': eac,
        'etc': round(eac_default - ac, 2) if eac_default is not None else None,
        'vac': round(bac - eac_default, 2) if eac_default is not None else None,
        'tcpi': tcpi(bac, ev, ac),
        # A plain-language health flag for a KPI badge — not a decision.
        'on_budget': None if cpi_value is None else cpi_value >= 1.0,
        'on_schedule': None if spi_value is None else spi_value >= 1.0,
    }


def portfolio(projects):
    """Roll EVM up across projects for a portfolio KPI.

    ``projects`` is an iterable of ``(name, evm_dict)`` from ``earned_value``.
    Sums the money bases (so a portfolio CPI/SPI is value-weighted, the correct
    way to average indices — a big overrunning job must outweigh a tiny tidy
    one), and points at the worst performer rather than hiding it in a mean.
    """
    projects = list(projects or [])
    bac = sum(_num(r.get('bac')) for _n, r in projects)
    ev = sum(_num(r.get('ev')) for _n, r in projects)
    ac = sum(_num(r.get('ac')) for _n, r in projects)
    pv = sum(_num(r.get('pv')) for _n, r in projects)

    over_cost = [n for n, r in projects if r.get('on_budget') is False]
    behind = [n for n, r in projects if r.get('on_schedule') is False]
    worst_cpi = min(
        (nr for nr in projects if nr[1].get('cpi') is not None),
        key=lambda nr: nr[1]['cpi'], default=None)

    return {
        'projects': len(projects),
        'bac': round(bac, 2),
        'ev': round(ev, 2),
        'ac': round(ac, 2),
        'pv': round(pv, 2),
        'cpi': cpi(ev, ac),                 # value-weighted by construction
        'spi': spi(ev, pv),
        'over_cost': len(over_cost),
        'over_cost_names': over_cost,
        'behind_schedule': len(behind),
        'behind_schedule_names': behind,
        'worst_cpi': worst_cpi[0] if worst_cpi else None,
        'worst_cpi_value': worst_cpi[1]['cpi'] if worst_cpi else None,
    }
