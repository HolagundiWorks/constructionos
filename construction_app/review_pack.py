"""Automated review pack (E4) + portfolio roll-up (E2).

No tkinter, no database. This is the roadmap's automation payoff without the
toil: it *assembles* the weekly project review — KPIs, advisories, risks,
forecast and a plain-language narrative — from pieces that already exist
(``advisory``, ``risk_detect``, ``narrative``, ``earnedvalue``, ``forecast``),
so the review that used to take a day to compile is one function call over the
snapshot. It generates a **draft to read**, not a decision — nothing here books,
files or pays.

Two entry points:

* ``build(snapshot, ...)`` — one project's review pack (a nested dict a tab or a
  report can render, or the assistant can re-voice).
* ``portfolio(projects)`` — the same idea across many projects: value-weighted
  EVM, pooled risk, and a pointer at the job that needs attention rather than an
  average that hides it.
"""

from datetime import date

import advisory
import earnedvalue
import forecast as forecast_mod
import narrative
import risk_detect


def _n(s, key, default=0):
    v = s.get(key, default)
    return default if v is None else v


def _kpi_block(s):
    """The headline numbers pulled into a compact, stable shape."""
    return {
        'cash': _n(s, 'cash'),
        'receivable': _n(s, 'receivable'),
        'receivable_90plus': _n(s, 'receivable_90plus'),
        'payable': _n(s, 'payable'),
        'billed_this_month': _n(s, 'billed_this_month'),
        'collected_this_month': _n(s, 'collected_this_month'),
        'retention_due_now': _n(s, 'retention_due_now'),
    }


def build(snapshot, evm=None, ppc_series=None, opportunities=None,
          generated=None):
    """Assemble one project's review pack from its metrics ``snapshot``.

    ``evm`` (an ``earnedvalue.earned_value`` dict), ``ppc_series`` (recent
    Plan-Percent-Complete readings for a reliability forecast) and
    ``opportunities`` (a list of ``opportunity.assess`` dicts, or rows from
    ``opportunity_store``) are optional — passed in rather than queried here so
    this stays DB-free and testable. ``generated`` defaults to today
    (overridable for a reproducible test).
    """
    s = snapshot or {}
    cards = advisory.build(s)
    pack = {
        'generated': generated or date.today().isoformat(),
        'kpis': _kpi_block(s),
        'advisories': {
            'counts': advisory.counts(cards),
            'cards': cards,
        },
        'risks': risk_detect.summary(s),
        'narrative': {
            'kpi': narrative.kpi_briefing(s),
            'risk': narrative.risk_briefing(s),
        },
    }
    if evm is not None:
        pack['evm'] = evm
    if ppc_series:
        pack['ppc_forecast'] = forecast_mod.project(ppc_series, 1)
    if opportunities is not None:
        import opportunity as opportunity_mod
        pack['opportunities'] = opportunity_mod.register_summary(opportunities)
    return pack


def portfolio(projects, generated=None):
    """Roll several projects up into a portfolio review.

    ``projects`` is an iterable of dicts, each ``{name, snapshot, evm?}``.
    Returns pooled advisory counts, a pooled risk summary, a value-weighted EVM
    roll-up (over whichever projects carry an ``evm``), and the worst performer
    by CPI — so a portfolio dashboard leads with the one to look at.
    """
    projects = list(projects or [])
    packs = []
    evms = []
    all_risks = []
    adv_counts = {advisory.ACT: 0, advisory.WATCH: 0,
                  advisory.GOOD: 0, advisory.INFO: 0}

    for p in projects:
        s = p.get('snapshot') or {}
        cards = advisory.build(s)
        for k, v in advisory.counts(cards).items():
            adv_counts[k] = adv_counts.get(k, 0) + v
        all_risks.extend(risk_detect.detect(s))
        if p.get('evm') is not None:
            evms.append((p.get('name'), p['evm']))
        packs.append({'name': p.get('name'),
                      'risks': risk_detect.summary(s)})

    import risk as risk_mod
    return {
        'generated': generated or date.today().isoformat(),
        'projects': len(projects),
        'advisory_counts': adv_counts,
        'risk_summary': risk_mod.register_summary(all_risks, top_n=5),
        'evm': earnedvalue.portfolio(evms) if evms else None,
        'per_project': packs,
    }
