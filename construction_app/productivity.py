"""Productivity KPIs for execution (Part 2): labour, plant, and material waste.

No tkinter, no database. Three questions a site actually asks during execution,
each a plain ratio with an honest ``None`` when the denominator is missing (a
rate with no hours or no output is not a small number, it is *no answer*):

* **Labour productivity** — output per worker-hour (or its inverse, hours per
  unit). Trending this catches a crew quietly slowing before the schedule does.
* **Equipment utilisation** — operating hours as a share of available hours. A
  hired machine standing idle is money burning at the hire rate.
* **Material waste** — actual consumption over the theoretical requirement, as a
  wastage percentage. The rupee view already lives in ``analytics.material_budget``;
  this is the quantity/percentage view a site engineer reads day to day.

A **performance factor** (earned hours ÷ actual hours) is included because it is
the labour twin of EVM's CPI: >1 means the crew is beating the estimated rate.

Exercised with ``python -c``.
"""


def _num(value, default=0.0):
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def labour_productivity(output_qty, labour_hours):
    """Output produced per labour-hour, and its inverse (hours per unit).

    Returns ``{units_per_hour, hours_per_unit}`` with each side None when its
    denominator is zero — you cannot state a rate you have not got the data for.
    """
    out = _num(output_qty)
    hrs = _num(labour_hours)
    return {
        'units_per_hour': round(out / hrs, 4) if hrs else None,
        'hours_per_unit': round(hrs / out, 4) if out else None,
    }


def performance_factor(earned_hours, actual_hours):
    """Labour performance = earned hours ÷ actual hours (the CPI of manpower).

    ``earned_hours`` is the estimated hours for the work actually done; >1 means
    the crew is beating the estimate, <1 means it is behind it. None if no hours
    were actually worked."""
    actual = _num(actual_hours)
    if not actual:
        return None
    return round(_num(earned_hours) / actual, 3)


def equipment_utilisation(operating_hours, available_hours):
    """Operating hours as a percentage of available hours (0..100, capped).

    Capped at 100 because a machine cannot run more than it is available; a
    reading above 100 is a data error (idle/available mis-entered), not a
    super-utilised machine, so it is clamped rather than shown as a fiction.
    None when no availability is recorded.
    """
    avail = _num(available_hours)
    if not avail:
        return None
    pct = _num(operating_hours) / avail * 100.0
    return round(min(pct, 100.0), 1)


def material_waste(theoretical_qty, actual_qty):
    """Material wastage from theoretical vs actual consumption.

    Returns the absolute ``waste`` (actual − theoretical; negative = a saving)
    and ``waste_pct`` over the theoretical requirement. ``waste_pct`` is None
    when there is no theoretical basis to measure against — the honest answer
    when the norm has not been set, rather than a divide-by-zero or a bare 0.
    """
    theo = _num(theoretical_qty)
    actual = _num(actual_qty)
    waste = actual - theo
    return {
        'waste': round(waste, 4),
        'waste_pct': round(waste / theo * 100.0, 1) if theo else None,
    }
