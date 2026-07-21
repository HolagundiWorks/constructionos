"""Automatic risk detection (E3) — turn the dashboard snapshot into scored,
register-ready risks.

No tkinter, no database. This is the E3 "risk detection taxonomy over rules"
from the roadmap. It deliberately reuses the **same metrics snapshot** that
``advisory.build`` consumes (the dict ``dashboard.collect`` assembles), so it
needs no new queries — where the advisory board says *what to do*, this says
*what could go wrong, how badly, and how likely*, in the register's own
language.

Each rule maps a signal to a **category**, a **likelihood** and **impact**
(1..5), an **impact value** (rupees or days at stake) and a **basis** — then
``risk.assess`` scores it, so detection and the register share one definition of
a score. The output is a ranked list of assessed risk dicts, ready to seed the
``risks`` table via ``risk_store`` (with ``source='ai'``) or to summarise
directly.

Nothing here *decides* — it detects and ranks with a stated basis, and a human
owns the accept/dismiss. Explainable by construction: no flag without its basis.
"""

import risk

# Risk categories — the taxonomy the register groups by.
SCHEDULE = 'schedule'
COST = 'cost'
COMMERCIAL = 'commercial'
QUALITY = 'quality'
STATUTORY = 'statutory'
EXTERNAL = 'external'


def _n(s, key, default=0):
    v = s.get(key, default)
    return default if v is None else v


def _bucket(value, thresholds):
    """Map a magnitude to a 1..5 impact via four ascending cutoffs.

    ``thresholds`` = (t1, t2, t3, t4): below t1 → 1, up to t2 → 2, … above t4 →
    5. Keeps each rule's severity mapping explicit and unit-testable rather than
    buried in nested ifs."""
    v = abs(float(value or 0))
    for i, t in enumerate(thresholds):
        if v < t:
            return i + 1
    return 5


def _risk(category, title, likelihood, impact, value, basis, where):
    """Score one detected risk and tag it with its register metadata."""
    a = risk.assess(likelihood, impact, value=value)
    a.update({
        'category': category,
        'title': title,
        'basis': basis,
        'where': where,
        'source': 'ai',
    })
    return a


# --------------------------------------------------------------------- rules
# Each reads the snapshot and returns one risk dict, or None. Rupee buckets are
# tuned for a T2/T3 contractor (lakh-scale), not an EPC firm.
_RUPEE_BUCKETS = (50000, 200000, 500000, 1000000)


def r_cost_overrun(s):
    n_loss = _n(s, 'projects_at_loss')
    if n_loss > 0:
        margin = abs(_n(s, 'projects_worst_margin'))
        return _risk(
            COST, 'Project running at a loss',
            likelihood=5, impact=_bucket(margin, _RUPEE_BUCKETS), value=margin,
            basis='{} project(s) with cost above billed'.format(n_loss),
            where='Project Management › Projects')
    over = _n(s, 'projects_over_budget')
    if over > 0:
        return _risk(
            COST, 'Project over budget',
            likelihood=4, impact=3, value=0,
            basis='{} project(s) past budget'.format(over),
            where='Project Management › Projects')
    return None


def r_liquidity(s):
    cash = _n(s, 'cash')
    payable = _n(s, 'payable')
    if cash < 0:
        return _risk(
            COST, 'Cash has gone negative',
            likelihood=5, impact=_bucket(cash, _RUPEE_BUCKETS), value=abs(cash),
            basis='recorded cash in hand is negative',
            where='Money › Cash & Parties')
    if payable > 0 and cash < payable:
        share = cash / payable if payable else 1.0
        return _risk(
            COST, 'Cash thin against payables',
            likelihood=4 if share < 0.5 else 3,
            impact=_bucket(payable - cash, _RUPEE_BUCKETS), value=payable - cash,
            basis='cash below total owed (not all due at once)',
            where='Money › Cash Flow')
    return None


def r_overdue_receivables(s):
    old = _n(s, 'receivable_90plus')
    if old <= 0:
        return None
    count = _n(s, 'receivable_aged_count')
    return _risk(
        COMMERCIAL, 'Receivables ageing past 90 days',
        likelihood=5, impact=_bucket(old, _RUPEE_BUCKETS), value=old,
        basis='{} invoice(s) past 90 days'.format(count) if count
        else 'aged from billing dates',
        where='Money › Cash & Parties')


def r_retention_locked(s):
    due = _n(s, 'retention_due_now')
    if due <= 0:
        return None
    return _risk(
        COMMERCIAL, 'Retention past its release date',
        likelihood=4, impact=_bucket(due, _RUPEE_BUCKETS), value=due,
        basis='against the DLP dates on record',
        where='Money › Retention')


def r_unbilled_variations(s):
    amt = _n(s, 'variations_approved_unbilled')
    if amt <= 0:
        return None
    return _risk(
        COMMERCIAL, 'Approved variations not yet billed',
        likelihood=4, impact=_bucket(amt, _RUPEE_BUCKETS), value=amt,
        basis='approved variations on record',
        where='Billing › Variations')


def r_invoice_without_grn(s):
    amt = _n(s, 'at_risk')
    if amt <= 0:
        return None
    return _risk(
        COST, 'Vendor invoices without a goods receipt',
        likelihood=4, impact=_bucket(amt, _RUPEE_BUCKETS), value=amt,
        basis='from the 3-way match',
        where='Purchases › Goods Receipt')


def r_programme_delay(s):
    days = _n(s, 'programme_delay_days')
    if not days or days <= 0:
        return None
    ld = _n(s, 'programme_ld')
    # Impact from LD exposure if known, else from the size of the slip.
    impact = (_bucket(ld, _RUPEE_BUCKETS) if ld
              else _bucket(days, (7, 21, 45, 90)))
    return _risk(
        SCHEDULE, 'Programme behind baseline (LD exposure)',
        likelihood=5, impact=impact, value=ld or 0,
        basis='{} day(s) behind a frozen baseline'.format(days),
        where='Project Management › Timeline')


def r_compliance(s):
    overdue = _n(s, 'compliance_overdue')
    if overdue > 0:
        return _risk(
            STATUTORY, 'Statutory filings overdue',
            likelihood=5, impact=3, value=0,
            basis='{} filing(s) past due'.format(overdue),
            where='Accounts › Compliance')
    soon = _n(s, 'compliance_due_soon')
    if soon > 0:
        return _risk(
            STATUTORY, 'Statutory filings due soon',
            likelihood=3, impact=2, value=0,
            basis='{} filing(s) due shortly'.format(soon),
            where='Accounts › Compliance')
    return None


def r_quality(s):
    crit = _n(s, 'ncr_critical')
    if crit > 0:
        return _risk(
            QUALITY, 'Critical non-conformance open',
            likelihood=4, impact=4, value=0,
            basis='{} critical NCR(s) open'.format(crit),
            where='Operations › Quality')
    openn = _n(s, 'ncr_open')
    old = _n(s, 'ncr_oldest_days')
    if openn > 0 and old >= 30:
        return _risk(
            QUALITY, 'Non-conformances ageing',
            likelihood=3, impact=3, value=0,
            basis='{} NCR(s) open, oldest {} days'.format(openn, old),
            where='Operations › Quality')
    return None


def r_plan_reliability(s):
    ppc = s.get('ppc_last')
    weeks = _n(s, 'ppc_weeks')
    if ppc is None or weeks < 1 or ppc >= 80:
        return None
    return _risk(
        SCHEDULE, 'Weekly plan not holding (low PPC)',
        likelihood=4 if weeks >= 4 else 3, impact=3, value=0,
        basis='{:.0f}% PPC over {} week(s)'.format(ppc, weeks),
        where='Project Management › Look-ahead')


def r_open_rfis(s):
    n = _n(s, 'rfis_open')
    oldest = _n(s, 'rfis_oldest_days')
    if n <= 0 or oldest < 7:
        return None
    return _risk(
        EXTERNAL, 'RFIs awaiting an answer',
        likelihood=3, impact=_bucket(oldest, (7, 14, 30, 60)), value=0,
        basis='{} open, oldest {} days'.format(n, oldest),
        where='Purchases › Sourcing')


RULES = (
    r_cost_overrun,
    r_liquidity,
    r_overdue_receivables,
    r_retention_locked,
    r_unbilled_variations,
    r_invoice_without_grn,
    r_programme_delay,
    r_compliance,
    r_quality,
    r_plan_reliability,
    r_open_rfis,
)


# --------------------------------------------------------- mitigation drafts
# A suggested response + first action per category (E3.3). Deliberately a
# *draft* a human edits and owns — never applied automatically. The response is
# a risk.RESPONSES value; the action is a plain first step, not a plan.
# (Uses the module-level ``risk`` import; note ``_risk`` is already a helper.)
_MITIGATION = {
    COST: (risk.REDUCE,
           'Review the cost heads on the worst job; check for unbilled work or '
           'a rate that no longer covers cost.'),
    SCHEDULE: (risk.REDUCE,
               'Log the delay causes now and re-sequence to protect the '
               'critical path; record claimable days as they happen.'),
    COMMERCIAL: (risk.REDUCE,
                 'Pull the agreed value into the next bill and put the reminder '
                 'in writing before it ages further.'),
    QUALITY: (risk.REDUCE,
              'Assign an owner and a close-out date; re-inspect before the work '
              'is covered.'),
    STATUTORY: (risk.AVOID,
                'File the oldest return first to stop the daily late-fee clock.'),
    EXTERNAL: (risk.TRANSFER,
               'Chase the answer in writing and note the wait against the '
               'programme so the delay carries the right name.'),
}


def suggest_mitigation(detected_risk):
    """A draft response + first action for a detected risk, from its category.

    Returns ``{'suggested_response', 'suggested_action'}`` — a starting point for
    the owner to edit, never an applied decision. Unknown categories get a safe
    generic prompt rather than nothing."""
    cat = detected_risk.get('category')
    response, action = _MITIGATION.get(
        cat, (risk.REDUCE, 'Assign an owner and agree a mitigation and a '
                           'target date.'))
    return {'suggested_response': response, 'suggested_action': action}


def with_mitigations(risks):
    """Each detected risk annotated with a mitigation draft — the register's
    'and here's a starting point' column."""
    out = []
    for r in risks or []:
        merged = dict(r)
        merged.update(suggest_mitigation(r))
        out.append(merged)
    return out


def detect(snapshot):
    """Ranked, register-ready risks for a metrics ``snapshot`` (worst first).

    A rule that raises is skipped rather than allowed to blank the list — one
    bad figure must not hide every other risk (the same resilience as
    ``advisory.build``)."""
    found = []
    for rule in RULES:
        try:
            r = rule(snapshot or {})
        except Exception:                       # noqa: BLE001 — never blank out
            r = None
        if r:
            found.append(r)
    return risk.rank(found)


def summary(snapshot, top_n=5):
    """Portfolio-style summary of the detected risks (counts by band, total
    expected exposure, the worst ``top_n``) — via ``risk.register_summary`` so
    detection and the stored register summarise identically."""
    return risk.register_summary(detect(snapshot), top_n=top_n)
