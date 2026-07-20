"""Per-project cost and revenue rollup.

No tkinter, no database.

Costs in this app are recorded against a **site**. That works until a site
hosts more than one project — a phased job, or two contracts on the same plot —
and then "cost on this site" can no longer answer "cost on this project".
Optional project tagging (a nullable ``project_id`` on the cost and revenue
rows) fixes that, and this module does the rollup.

The attribution policy is the careful part, and it is deliberately conservative:

* A row **explicitly tagged** to the project always counts. No ambiguity.
* An **untagged** row (``project_id`` is null) counts toward the project only
  when the project is the **sole** project on its site — because then "on the
  site" and "on the project" mean the same thing, and this reproduces exactly
  what the old site-only rollup did, so nothing regresses for existing data.
* An untagged row on a site with **more than one** project is **not** guessed.
  Splitting it would be inventing a number; assigning it to one project would
  rob the other. It is reported as *unattributed* instead, with a total, so the
  view can say "tag these to a project" rather than quietly mis-stating both.

That last rule is the whole point. The honest failure — "we cannot tell whose
cost this is until you tag it" — is worth more than a confident wrong split.
"""

import projman

REVENUE = 'revenue'
MATERIAL = 'material'
LABOUR = 'labour'
HIRE = 'hire'
SUBCONTRACT = 'subcontract'
OTHER = 'other'

COST_CATEGORIES = (MATERIAL, LABOUR, HIRE, SUBCONTRACT, OTHER)


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


def attribution(row, project_id, project_site_id, sole_on_site):
    """How one row attaches to the project: 'tagged', 'by-site', 'ambiguous',
    or 'other'.

    ``row`` carries ``project_id`` (may be None) and ``site_id``. A row tagged
    to a *different* project is 'other' and never counts here, even if it sits
    on this project's site — an explicit tag always wins over the site.
    """
    tag = _g(row, 'project_id')
    if tag is not None:
        return 'tagged' if str(tag) == str(project_id) else 'other'
    # untagged from here
    if str(_g(row, 'site_id')) != str(project_site_id):
        return 'other'
    return 'by-site' if sole_on_site else 'ambiguous'


def rollup(rows, project_id, project_site_id, sole_on_site, budget=0):
    """Roll a project's candidate cost/revenue rows up to a cost sheet.

    Each row is a dict/Row with ``category`` (one of REVENUE or a cost
    category), ``amount``, ``project_id`` and ``site_id``. Rows that do not
    belong to the project are ignored; untagged rows on a shared site are
    summed separately as ``unattributed`` rather than counted.
    """
    by_cat = {c: 0.0 for c in COST_CATEGORIES}
    revenue = 0.0
    unattributed = 0.0
    unattributed_n = 0
    for r in rows or []:
        how = attribution(r, project_id, project_site_id, sole_on_site)
        amount = _num(_g(r, 'amount'))
        if how in ('tagged', 'by-site'):
            cat = str(_g(r, 'category', OTHER))
            if cat == REVENUE:
                revenue += amount
            elif cat in by_cat:
                by_cat[cat] += amount
            else:
                by_cat[OTHER] += amount
        elif how == 'ambiguous':
            # Only untagged *costs* are worth flagging; ambiguous revenue is
            # rare and would just be noise here.
            if str(_g(r, 'category')) != REVENUE:
                unattributed += amount
                unattributed_n += 1

    by_cat = {c: round(v, 2) for c, v in by_cat.items()}
    total_cost = round(sum(by_cat.values()), 2)
    revenue = round(revenue, 2)
    budget_view = projman.budget_status(budget, total_cost)
    return {
        'by_category': by_cat,
        'total_cost': total_cost,
        'revenue': revenue,
        'margin': round(revenue - total_cost, 2),
        'margin_pct': round((revenue - total_cost) / revenue * 100.0, 1)
        if revenue else None,
        'budget': _num(budget),
        'budget_used_pct': budget_view['used_pct'],
        'over_budget': budget_view['over_budget'],
        'unattributed_cost': round(unattributed, 2),
        'unattributed_count': unattributed_n,
    }


def portfolio(projects):
    """Totals across several ``rollup`` results — for a portfolio KPI.

    ``projects`` is an iterable of ``(name, rollup_dict)``. Returns the count
    over budget, the count running at a loss, and the worst margin, so a
    dashboard can point at the one that needs attention rather than an average
    that hides it.
    """
    projects = list(projects or [])
    over = [n for n, r in projects if r.get('over_budget')]
    loss = [(n, r) for n, r in projects
            if r.get('revenue') and r.get('margin', 0) < 0]
    worst = min(projects, key=lambda nr: nr[1].get('margin', 0),
                default=None)
    return {
        'projects': len(projects),
        'over_budget': len(over),
        'over_budget_names': over,
        'at_a_loss': len(loss),
        'worst': worst[0] if worst else None,
        'worst_margin': worst[1].get('margin') if worst else None,
        'unattributed_total': round(
            sum(r.get('unattributed_cost', 0) for _n, r in projects), 2),
    }
