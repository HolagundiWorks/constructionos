"""Plain-language narration of the numbers (E2 KPI briefing, E3 risk briefing).

No tkinter, no database, **no model**. This is the deterministic *floor* for the
roadmap's narration: it turns the metrics snapshot and the detected risks into a
few plain sentences, each one built from — and citing — a figure the engine
already computed. A local LLM (the assistant's sidecar) can later re-voice these
for tone, but the facts, and their basis, come from here, so a narrated line can
never say something the numbers don't.

Every sentence is a template over a number. That is the whole point: narration
that cannot hallucinate, because it has no freedom to. Exercised with
``python -c``.
"""

import risk_detect


def _money(value):
    """₹ with no paise — matches the app's headline figures."""
    try:
        return '₹ {:,.0f}'.format(round(float(value or 0)))
    except (TypeError, ValueError):
        return '₹ 0'


def _n(s, key, default=0):
    v = s.get(key, default)
    return default if v is None else v


def kpi_briefing(snapshot):
    """A short plain-language read of the KPI snapshot — a list of sentences.

    Leads with cash, then receivables, then the month's billing/collection, then
    any margin/programme flags. Only says what the numbers support; a healthy
    firm gets a short, calm briefing rather than manufactured drama.
    """
    s = snapshot or {}
    lines = []

    cash = _n(s, 'cash')
    payable = _n(s, 'payable')
    if cash < 0:
        lines.append('Cash in hand is negative ({}) — the cash book needs '
                     'reconciling before any further payment.'.format(_money(cash)))
    elif payable and cash < payable:
        lines.append('Cash in hand is {}, below the {} owed to vendors — thin '
                     'if a large bill lands at once.'.format(
                         _money(cash), _money(payable)))
    else:
        lines.append('Cash in hand is {}.'.format(_money(cash)))

    old = _n(s, 'receivable_90plus')
    recv = _n(s, 'receivable')
    if old > 0:
        lines.append('{} of receivables is past 90 days — the hardest money to '
                     'collect.'.format(_money(old)))
    elif recv:
        lines.append('Receivables stand at {}, none of it past 90 '
                     'days.'.format(_money(recv)))

    billed = _n(s, 'billed_this_month')
    collected = _n(s, 'collected_this_month')
    if billed or collected:
        lines.append('This month: {} billed, {} collected.'.format(
            _money(billed), _money(collected)))

    if _n(s, 'projects_at_loss') > 0:
        worst = s.get('projects_worst') or 'one job'
        lines.append('{} project(s) are running at a loss — worst is {} at '
                     '{}.'.format(_n(s, 'projects_at_loss'), worst,
                                  _money(_n(s, 'projects_worst_margin'))))

    days = _n(s, 'programme_delay_days')
    if days and days > 0:
        proj = s.get('programme_project') or 'a project'
        lines.append('{} is {} day(s) behind baseline, about {} of LD '
                     'exposure.'.format(proj, days, _money(_n(s, 'programme_ld'))))

    return lines


def risk_briefing(snapshot, top_n=3):
    """A plain-language 'top risks by exposure' paragraph, over detected risks.

    Uses ``risk_detect`` so the briefing and the register agree on what the top
    risks are. Returns a short string; empty when nothing is flagged."""
    s = risk_detect.summary(snapshot, top_n=top_n)
    if not s['count']:
        return 'No risks flagged on the numbers recorded so far.'

    head = ('{} risk(s) flagged ({} needing attention now), total expected '
            'exposure about {}.'.format(
                s['count'], s['needs_action'],
                _money(s['total_expected_exposure'])))
    bullets = []
    for r in s['top']:
        exp = (' (~{} exposure)'.format(_money(r['expected_exposure']))
               if r.get('expected_exposure') else '')
        bullets.append('• [{}] {} — {}{}'.format(
            r['band'], r.get('title', 'risk'), r.get('basis', ''), exp))
    return head + '\n' + '\n'.join(bullets)
