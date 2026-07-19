"""Pure progress / budget analytics (Phase 6 — honest numbers, not dashboards).

No tkinter, no database. Two ideas a site engineer actually tracks:

* **Physical progress** — how much of the tendered BOQ has been *measured* as
  executed, in value terms: measured value / BOQ value.
* **Material budget** — the *money* view of consumption: theoretical material
  requirement (norm x work done) valued at rate, against what was actually
  issued, valued the same way. The qty-level wastage lives in
  ``civil.reconcile_consumption``; this adds the rupee dimension and rolls up.

Plain functions, exercised with ``python -c``.
"""


def money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def pct(part, whole, ndigits=1):
    """``part`` as a percentage of ``whole``; None when ``whole`` is 0."""
    whole = money(whole)
    if not whole:
        return None
    return round(money(part) / whole * 100.0, ndigits)


def contract_progress(boq_value, measured_value):
    """Physical progress of a contract from BOQ vs measured value.

        progress_pct  = measured_value / boq_value * 100   (None if no BOQ)
        balance_value = boq_value - measured_value         (work left to bill)

    ``progress_pct`` can exceed 100 when measurements over-run the BOQ (a
    deviation / excess quantity) — that is real information, so it is not
    clamped.
    """
    boq_value = money(boq_value)
    measured_value = money(measured_value)
    return {
        'boq_value': boq_value,
        'measured_value': measured_value,
        'progress_pct': pct(measured_value, boq_value),
        'balance_value': money(boq_value - measured_value),
    }


def material_budget(theoretical_qty, actual_qty, rate):
    """Money view of one material's consumption against its budget.

        budget_value   = theoretical_qty x rate
        actual_value   = actual_qty x rate
        variance_value = actual_value - budget_value   (+ = overspend)
        overspend_pct  = variance_value / budget_value * 100  (None if no budget)
    """
    rate = money(rate)
    budget_value = money(money(theoretical_qty) * rate)
    actual_value = money(money(actual_qty) * rate)
    variance = money(actual_value - budget_value)
    return {
        'budget_value': budget_value,
        'actual_value': actual_value,
        'variance_value': variance,
        'overspend_pct': pct(variance, budget_value),
    }
