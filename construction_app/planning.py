"""Pure production-planning maths: look-ahead, PPC, and CVR (Wave 3).

No tkinter, no database.

Two ideas from the research, both about seeing trouble early.

**Percent Plan Complete** (Last Planner). Traditional planning completes only
about half of what it promises each week, and the gap is invisible because
nobody counts. PPC counts it: commitments made at the start of the week
against commitments finished by the end. The number alone is not the point —
the **reasons for misses** are, because they name the constraint (material
late, no drawing, no labour) that will bite again next week if nobody fixes it.

PPC is deliberately *binary*: a task is done or it is not. "80% complete" is
how a programme drifts for a month while every line reports progress.

**Cost-Value Reconciliation.** Profit at the end of a job is a post-mortem.
CVR compares cost *incurred* against value *earned* per cost head while there
is still time to act, which is how a loss-making job is caught in month two
rather than month ten.
"""

import finance

DONE = 'Done'
NOT_DONE = 'Not done'
PARTIAL = 'Partial'

# The usual constraints, offered as a list so misses get categorised rather
# than free-typed into uselessness.
REASONS = [
    'Material not available',
    'Labour short',
    'Drawing / instruction awaited',
    'Preceding work not finished',
    'Equipment breakdown',
    'Weather',
    'Client / approval delay',
    'Rework',
    'Other',
]


def money(value):
    return finance.money(value)


def _status(row):
    try:
        return (row['status'] or '').strip() or NOT_DONE
    except (KeyError, IndexError, TypeError):
        return NOT_DONE


def ppc(commitments):
    """Percent Plan Complete: finished ÷ promised, as a percentage.

    Binary by design — only ``Done`` counts. A part-finished task is a miss,
    because counting it as progress is precisely how a programme slips while
    every line looks busy. Returns None when nothing was promised, rather than
    a meaningless 0% or 100%.
    """
    rows = list(commitments or [])
    if not rows:
        return None
    done = sum(1 for r in rows if _status(r) == DONE)
    return money(done / len(rows) * 100.0)


def reasons_for_misses(commitments):
    """Count misses by reason, worst first — the constraints to fix.

    This is the half of Last Planner that actually changes anything: the score
    tells you the plan was unreliable, the reasons tell you why.
    """
    counts = {}
    for r in commitments or []:
        if _status(r) == DONE:
            continue
        try:
            reason = (r['reason'] or '').strip() or 'Not stated'
        except (KeyError, IndexError, TypeError):
            reason = 'Not stated'
        counts[reason] = counts.get(reason, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def ppc_trend(weeks):
    """PPC per week plus the average.

    ``weeks`` maps a week label to its commitments. Reliability is a trend:
    one bad week is noise, four in a row is a broken process.
    """
    out = []
    for label in sorted(weeks or {}):
        out.append((label, ppc(weeks[label])))
    scored = [p for _l, p in out if p is not None]
    average = money(sum(scored) / len(scored)) if scored else None
    return {'weeks': out, 'average': average}


def cvr(cost_heads):
    """Cost-Value Reconciliation.

    ``cost_heads`` maps a head (Material, Labour, Plant, Subcontract…) to a
    ``(cost, value)`` pair. Returns per-head and total cost, value, margin and
    margin %, with the heads sorted by the largest loss first — a loss-making
    head should not have to be hunted for.
    """
    rows = []
    total_cost = total_value = 0.0
    for head in sorted(cost_heads or {}):
        cost, value = cost_heads[head]
        cost, value = money(cost), money(value)
        margin = money(value - cost)
        rows.append({
            'head': head,
            'cost': cost,
            'value': value,
            'margin': margin,
            'margin_pct': money(margin / value * 100.0) if value else None,
        })
        total_cost = money(total_cost + cost)
        total_value = money(total_value + value)
    rows.sort(key=lambda r: r['margin'])
    total_margin = money(total_value - total_cost)
    return {
        'rows': rows,
        'cost': total_cost,
        'value': total_value,
        'margin': total_margin,
        'margin_pct': money(total_margin / total_value * 100.0) if total_value else None,
        'losing': [r['head'] for r in rows if r['margin'] < 0],
    }
