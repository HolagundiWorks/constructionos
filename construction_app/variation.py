"""Pure variation / change-order maths (Phase 8, Wave 1).

No tkinter, no database.

A **variation** is work outside the original BOQ — a client instruction, a
changed site condition, an extra item. The SOP gap analysis puts this first
because unbilled or unapproved extras are the single largest source of
*unrecovered revenue* in contracting: work gets executed on a verbal "just do
it", is never priced, certified or billed, and quietly becomes a gift.

So the number this module exists to produce is **approved but not yet billed**
— money the client has already agreed to pay that has not been asked for. That
figure belongs on screen, not buried in a register.

Statuses, and what each means for the money:

* ``Raised``   — claimed, not yet agreed. *At risk*: no promise to pay yet.
* ``Approved`` — agreed by the client. *Billable now* — chase this.
* ``Billed``   — included in an RA or tax bill. Earned.
* ``Rejected`` — refused. Excluded from every total; kept for the record.
"""

import finance

RAISED = 'Raised'
APPROVED = 'Approved'
BILLED = 'Billed'
REJECTED = 'Rejected'

STATUSES = [RAISED, APPROVED, BILLED, REJECTED]

# Statuses that represent real or promised revenue. 'Rejected' is deliberately
# excluded everywhere: a refused claim must never inflate a contract value.
COUNTED = (RAISED, APPROVED, BILLED)


def variation_amount(qty, rate):
    """Value of one variation line: qty x rate, rounded at the boundary."""
    return finance.money(float(qty or 0) * float(rate or 0))


def _amount(row):
    """Amount from a row mapping, falling back to qty x rate."""
    try:
        stored = row['amount']
    except (KeyError, IndexError, TypeError):
        stored = None
    if stored not in (None, ''):
        return finance.money(stored)
    try:
        return variation_amount(row['qty'], row['rate'])
    except (KeyError, IndexError, TypeError):
        return 0.0


def _status(row):
    try:
        return (row['status'] or '').strip() or RAISED
    except (KeyError, IndexError, TypeError):
        return RAISED


def summarise(variations):
    """Totals by status, plus the two numbers that matter.

    ``approved_unbilled`` is the headline: agreed work not yet asked for.
    ``pending_approval`` is what is still at risk of being refused.
    ``counted_total`` excludes rejected claims.
    """
    totals = {s: 0.0 for s in STATUSES}
    counts = {s: 0 for s in STATUSES}
    for row in variations or []:
        status = _status(row)
        if status not in totals:            # unknown label — treat as raised
            status = RAISED
        totals[status] = finance.money(totals[status] + _amount(row))
        counts[status] += 1
    counted = finance.money(sum(totals[s] for s in COUNTED))
    return {
        'totals': totals,
        'counts': counts,
        'pending_approval': totals[RAISED],
        'approved_unbilled': totals[APPROVED],
        'billed': totals[BILLED],
        'rejected': totals[REJECTED],
        'counted_total': counted,
    }


def contract_impact(contract_value, variations):
    """How far variations have moved the contract, ignoring rejected claims.

    ``revised_value`` counts approved and billed work only — a merely *raised*
    claim is not yet a contract change, so including it would overstate the
    order book. ``variation_pct`` is against the original value (None when
    that is zero, e.g. a contract entered without a figure).
    """
    original = finance.money(contract_value)
    summary = summarise(variations)
    agreed = finance.money(summary['approved_unbilled'] + summary['billed'])
    revised = finance.money(original + agreed)
    pct = finance.money(agreed / original * 100.0) if original else None
    return {
        'original_value': original,
        'agreed_variations': agreed,
        'pending_variations': summary['pending_approval'],
        'revised_value': revised,
        'variation_pct': pct,
    }


def next_var_no(existing, prefix='VO'):
    """Next number in a per-contract variation series ('VO-3').

    Derived from the highest existing serial rather than a count, so deleting
    a variation cannot produce a duplicate number.
    """
    top = 0
    for value in existing or []:
        text = str(value or '').strip()
        if not text.upper().startswith(prefix.upper() + '-'):
            continue
        tail = text.split('-', 1)[1].strip()
        if tail.isdigit():
            top = max(top, int(tail))
    return '{}-{}'.format(prefix, top + 1)
