"""Pure project-management calculations (no tkinter, no DB).

Progress and budget maths for the Projects module. Milestones can be passed as
sqlite3.Row or dict; ``_g`` reads either.
"""

_DONE = ('done', 'completed', 'achieved', 'closed')


def _g(row, key, default=None):
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


def _is_done(m):
    return str(_g(m, 'status', '')).strip().lower() in _DONE


def milestone_progress(milestones):
    """Percent of milestones marked done.

    If any milestone carries an ``amount``, progress is weighted by amount
    (payment-milestone style); otherwise it's a simple count ratio.
    """
    milestones = list(milestones or [])
    if not milestones:
        return 0.0
    total_amt = sum(float(_g(m, 'amount', 0) or 0) for m in milestones)
    if total_amt > 0:
        done_amt = sum(float(_g(m, 'amount', 0) or 0) for m in milestones if _is_done(m))
        return round(done_amt / total_amt * 100.0, 1)
    done = sum(1 for m in milestones if _is_done(m))
    return round(done / len(milestones) * 100.0, 1)


def budget_status(budget, cost):
    """Budget vs cost-to-date."""
    budget = round(float(budget or 0), 2)
    cost = round(float(cost or 0), 2)
    return {
        'budget': budget,
        'cost': cost,
        'remaining': round(budget - cost, 2),
        'used_pct': round(cost / budget * 100.0, 1) if budget else None,
        'over_budget': cost > budget and budget > 0,
    }
