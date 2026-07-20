"""Rate analysis on the CPWD Analysis of Rates skeleton.

No tkinter, no database. Builds a per-unit rate from its inputs the way the
CPWD DAR does, so a contractor can price an item they have never done before
from first principles instead of guessing, and can show the department how the
figure was reached when it is questioned.

The build-up:

    material + labour + machinery + sundries      (the inputs)
      + 1%  water charges                          (wet items only)
      = subtotal
      + 15% CPOH  (7.5% contractor's profit + 7.5% overhead)
      = total for the analysis quantity
      / analysis quantity                          = rate per unit

Two deliberate choices:

**Water and scaffolding are per-item toggles, not constants.** The DAR applies
water charges to items that consume water — concrete, mortar, masonry — and
scaffolding to items needing access. Charging 1% water on a steel-supply item
would be wrong, and hard-coding it would make every rate slightly wrong in a
way nobody would notice.

**The analysis quantity is explicit.** The DAR analyses a convenient block —
10 cum of concrete, 100 sqm of plaster — because labour constants are quoted
that way, then divides. Analysing per 1 unit and rounding at each step
accumulates error, so the division happens once, at the end.

The DAR's own rates are dated (materials Delhi Mar-Apr 2014, labour at the
statutory minimum wage of 01.04.2014). This module deliberately holds **no
rate data** — it is the arithmetic only. Rates come from the user's own
material and labour masters, so the analysis reflects what they actually pay
rather than a decade-old schedule.
"""

WATER_PCT = 1.0            # DAR: 1% of the input cost, on wet items
CPOH_PCT = 15.0            # contractor's profit and overhead
PROFIT_SHARE = 7.5         # the two halves of CPOH, quoted separately
OVERHEAD_SHARE = 7.5


def _money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _g(row, key, default=0):
    if row is None:
        return default
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


MATERIAL = 'Material'
LABOUR = 'Labour'
MACHINERY = 'Machinery'
SUNDRIES = 'Sundries'
KINDS = (MATERIAL, LABOUR, MACHINERY, SUNDRIES)


def line_amount(qty, rate):
    """One input line: quantity x rate."""
    return _money(float(_num(qty)) * float(_num(rate)))


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def subtotal_by_kind(lines):
    """Input cost grouped by Material / Labour / Machinery / Sundries.

    An unrecognised kind is counted under Sundries rather than dropped —
    silently losing a cost line would understate the rate.
    """
    totals = {k: 0.0 for k in KINDS}
    for ln in lines or []:
        kind = str(_g(ln, 'kind', SUNDRIES) or SUNDRIES)
        if kind not in totals:
            kind = SUNDRIES
        amount = _g(ln, 'amount', None)
        if amount is None:
            amount = line_amount(_g(ln, 'qty'), _g(ln, 'rate'))
        totals[kind] = _money(totals[kind] + _num(amount))
    return totals


def analyse(lines, analysis_qty=1, apply_water=False, water_pct=WATER_PCT,
            cpoh_pct=CPOH_PCT, scaffolding=0):
    """Build the per-unit rate from the input lines.

    ``analysis_qty`` is the block the analysis is written for (10 cum, 100 sqm);
    the division to a per-unit rate happens once at the end so rounding does
    not compound. A zero or missing quantity yields a rate of None rather than
    raising — an incomplete analysis is a normal in-progress state, not an
    error, and returning 0 would look like a real (free) rate.

    ``apply_water`` defaults to **False**: water charges belong on items that
    consume water, and defaulting them on would silently inflate every dry
    item by 1%.
    """
    kinds = subtotal_by_kind(lines)
    scaffolding = _money(scaffolding)
    if scaffolding:
        kinds[SUNDRIES] = _money(kinds[SUNDRIES] + scaffolding)

    inputs = _money(sum(kinds.values()))
    water = _money(inputs * _num(water_pct) / 100.0) if apply_water else 0.0
    subtotal = _money(inputs + water)
    cpoh = _money(subtotal * _num(cpoh_pct) / 100.0)
    total = _money(subtotal + cpoh)

    qty = _num(analysis_qty)
    rate = _money(total / qty) if qty > 0 else None

    # Split CPOH in the 7.5 : 7.5 ratio the DAR quotes, i.e. by the shares'
    # own sum — not by cpoh_pct, which would break the moment someone used a
    # rate other than 15% and leave profit + overhead disagreeing with CPOH.
    share_total = PROFIT_SHARE + OVERHEAD_SHARE
    return {
        'by_kind': kinds,
        'scaffolding': scaffolding,
        'inputs': inputs,
        'water': water,
        'water_applied': bool(apply_water),
        'subtotal': subtotal,
        'cpoh': cpoh,
        # The DAR quotes CPOH as 7.5 profit + 7.5 overhead; split it in the
        # same proportion so a non-default rate still divides sensibly.
        'profit': _money(cpoh * PROFIT_SHARE / share_total),
        'overhead': _money(cpoh - _money(cpoh * PROFIT_SHARE / share_total)),
        'total': total,
        'analysis_qty': qty,
        'rate_per_unit': rate,
    }


def is_complete(result):
    """True when the analysis yields a usable rate."""
    return bool(result) and result.get('rate_per_unit') is not None \
        and result.get('inputs', 0) > 0


def labour_share_pct(result):
    """Labour as a percentage of input cost — a sanity check on the analysis.

    An item analysed with no labour at all, or with labour at 90% of a
    material-heavy item, usually means a line was missed or mis-keyed.
    """
    inputs = _money(_g(result, 'inputs', 0)) if result else 0
    if not inputs:
        return None
    return round(_g(result.get('by_kind', {}), LABOUR, 0) / inputs * 100.0, 2)


def warnings(result):
    """Plain-language checks on a finished analysis."""
    out = []
    if not result:
        return out
    if result.get('inputs', 0) <= 0:
        out.append('No input costs entered — the rate would be zero.')
        return out
    if not result.get('analysis_qty'):
        out.append('Set the analysis quantity (the block this is written for, '
                   'e.g. 10 cum) before using the rate.')
    kinds = result.get('by_kind', {})
    if not kinds.get(LABOUR):
        out.append('No labour in this analysis. Most civil items need some — '
                   'check nothing was missed.')
    if not kinds.get(MATERIAL) and not kinds.get(MACHINERY):
        out.append('No material or machinery in this analysis.')
    return out
