"""The advisory engine — the dashboard's "what should I do about it?" layer.

The KPI board (Key Numbers) answers *what is true*. This answers *what to do
about it*, and in what order. It is deliberately **rule-based and on-device**:
every advisory is derived by an explicit rule from the firm's own figures, so it
is explainable ("why am I seeing this?") and works with no internet and no model
— the right default for a single-PC contractor. There is no black box here.

Each advisory carries a **confidence**, and confidence means something precise:
how much the underlying data supports the call, not how loud the wording is.

* ``HIGH``   — a hard fact drawn from complete records (a filing already past
  its statutory due date; specific invoices aged beyond 90 days; a vendor
  invoice with no goods receipt behind it). Not a prediction.
* ``MEDIUM`` — a real signal off a soft threshold or a moderate sample (cash
  below total payables — but not all of it is due today).
* ``LOW``    — the signal is there but the history is thin (plan reliability
  from only a week or two). Shown, but flagged not to be over-trusted.

The ``basis`` string states, in a few words, *why* that confidence — the count
or sample the call rests on — so the number is never bare.

Pure module: no tkinter, no database. ``build(snapshot)`` takes the dict that
``dashboard.collect`` assembles and returns a ranked list of advisory dicts.
"""

# --- severity: how urgent (drives colour + sort order)
ACT = 'act'        # money or risk that needs an action now
WATCH = 'watch'    # worth keeping an eye on
GOOD = 'good'      # a positive worth confirming
INFO = 'info'      # neutral context

_SEV_RANK = {ACT: 0, WATCH: 1, INFO: 2, GOOD: 3}

# --- confidence: how well the data backs the call
HIGH, MEDIUM, LOW = 'High', 'Medium', 'Low'
_CONF_RANK = {HIGH: 0, MEDIUM: 1, LOW: 2}


def _money(value):
    """Rupee, no paise — matches the rest of the app's headline figures."""
    return '₹ {:,.0f}'.format(round(float(value or 0)))


def _card(severity, title, detail, action, confidence, basis, where):
    return {
        'severity': severity,
        'title': title,
        'detail': detail,
        'action': action,
        'confidence': confidence,
        'basis': basis,
        'where': where,
    }


def _n(snapshot, key, default=0):
    v = snapshot.get(key, default)
    return default if v is None else v


# --------------------------------------------------------------------- rules
# Each rule reads the snapshot and returns one advisory dict, or None when it
# has nothing to say. Kept as small functions so each is unit-testable on its
# own and the list below reads as a table of what the dashboard watches.

def r_cash_position(s):
    cash = _n(s, 'cash')
    payable = _n(s, 'payable')
    if cash < 0:
        return _card(
            ACT, 'Cash has gone negative',
            'Recorded cash in hand is {}. Either a payment was entered that the '
            'box could not cover, or a receipt has not been booked.'.format(
                _money(cash)),
            'Reconcile the cash book today before paying anything further.',
            HIGH, 'from the cash book', 'Money › Cash & Parties')
    if payable > 0 and cash < payable:
        share = cash / payable if payable else 1.0
        sev = ACT if share < 0.5 else WATCH
        return _card(
            sev, 'Cash is thin against what you owe',
            'Cash in hand {} is below the {} owed to vendors. Not all of it is '
            'due at once, but a large bill landing now would not clear.'.format(
                _money(cash), _money(payable)),
            'Line up collections or stagger vendor payments this week.',
            MEDIUM, 'payables are a total, not only what falls due now',
            'Money › Cash Flow')
    return None


def r_overdue_receivables(s):
    old = _n(s, 'receivable_90plus')
    mid = _n(s, 'receivable_60_90')
    count = _n(s, 'receivable_aged_count')
    if old > 0:
        basis = ('{} invoice(s) past 90 days'.format(count) if count
                 else 'aged from your billing dates')
        return _card(
            ACT, 'Money is ageing past 90 days',
            '{} is older than 90 days — the hardest money to collect, and the '
            'first that turns into a write-off.'.format(_money(old)),
            'Call these clients this week and put the reminders in writing.',
            HIGH, basis, 'Money › Cash & Parties')
    if mid > 0:
        return _card(
            WATCH, 'Receivables slipping into the 60–90 band',
            '{} is now 60–90 days old. It is still collectable, but it is '
            'heading the wrong way.'.format(_money(mid)),
            'Send a statement before it crosses 90 days.',
            HIGH, 'aged from your billing dates', 'Money › Cash & Parties')
    return None


def r_retention_due(s):
    due = _n(s, 'retention_due_now')
    if due <= 0:
        return None
    days = _n(s, 'retention_max_overdue_days')
    tail = ' — oldest by {} days'.format(days) if days else ''
    return _card(
        ACT, 'Retention is past its release date',
        '{} of retention is past its defect-liability date and still being '
        'held by clients{}. This is earned money sitting with someone '
        'else.'.format(_money(due), tail),
        'Raise the release request with the supporting completion evidence.',
        HIGH, 'against the DLP dates on record', 'Money › Retention')


def r_variations_unbilled(s):
    amt = _n(s, 'variations_approved_unbilled')
    if amt <= 0:
        return None
    return _card(
        ACT, 'Agreed variations not yet billed',
        '{} of variation work the client has already approved has not been '
        'billed. Un-billed agreed work is the quietest way a job loses '
        'money.'.format(_money(amt)),
        'Pull the approved variations into the next running bill.',
        HIGH, 'approved variations on record', 'Billing › Variations')


def r_invoiced_without_grn(s):
    amt = _n(s, 'at_risk')
    if amt <= 0:
        return None
    return _card(
        ACT, 'Vendor invoices with no goods receipt',
        '{} of vendor invoice value has no goods-receipt behind it. Paying '
        'these means paying for goods nobody has confirmed arrived.'.format(
            _money(amt)),
        'Match each to its GRN before releasing payment.',
        HIGH, 'from the 3-way match', 'Purchases › Goods Receipt')


def r_compliance(s):
    overdue = _n(s, 'compliance_overdue')
    due_soon = _n(s, 'compliance_due_soon')
    if overdue > 0:
        days = _n(s, 'compliance_max_days_late')
        tail = ' (up to {} days late)'.format(days) if days else ''
        return _card(
            ACT, 'Statutory filings overdue',
            '{} filing(s) are overdue{}. Late fees and interest run per day, '
            'and a late GSTR-1 holds up your customer’s credit.'.format(
                overdue, tail),
            'File the oldest first to stop the daily clock.',
            HIGH, 'against statutory due dates', 'Accounts › Compliance')
    if due_soon > 0:
        return _card(
            WATCH, 'Statutory filings due soon',
            '{} filing(s) fall due shortly. Better to clear them than to join '
            'the month-end rush.'.format(due_soon),
            'Prepare the returns now while there is slack.',
            HIGH, 'against statutory due dates', 'Accounts › Compliance')
    return None


def r_programme_delay(s):
    days = _n(s, 'programme_delay_days')
    if days is None or days <= 0:
        return None
    ld = _n(s, 'programme_ld')
    project = s.get('programme_project') or 'a project'
    claim = _n(s, 'programme_claimable')
    claim_txt = (' {} day(s) of it may support an extension claim.'.format(claim)
                 if claim else '')
    return _card(
        ACT, 'Programme is running late',
        '{} is {} day(s) behind its baseline, an exposure of about {} in '
        'liquidated damages on the recorded terms.{}'.format(
            project, days, _money(ld), claim_txt),
        'Log the delay causes now — the claimable days are only defensible '
        'if they are recorded as they happen.',
        HIGH, 'against a frozen baseline', 'Operations › Timeline')


def r_projects_loss(s):
    n = _n(s, 'projects_at_loss')
    if n > 0:
        worst = s.get('projects_worst') or 'the worst'
        margin = _n(s, 'projects_worst_margin')
        return _card(
            ACT, 'A project is running at a loss',
            '{} project(s) have costs above what has been billed — worst is {} '
            'at {}. This is worth knowing before the final account, not '
            'after.'.format(n, worst, _money(margin)),
            'Review the cost heads on the worst job and check for unbilled '
            'work or a rate that no longer covers cost.',
            MEDIUM, 'cost is site-scoped; shared-site cost may distort it',
            'Projects')
    over = _n(s, 'projects_over_budget')
    if over > 0:
        return _card(
            WATCH, 'A project has passed its budget',
            '{} project(s) have spent past the budget set for them.'.format(over),
            'Confirm the budget still reflects the agreed scope.',
            MEDIUM, 'against the budget on record', 'Projects')
    return None


def r_plant(s):
    overdue = _n(s, 'plant_overdue')
    due = _n(s, 'plant_due')
    if overdue > 0:
        return _card(
            ACT, 'Plant overdue for service',
            '{} machine(s) are past their service interval. A seizure '
            'mid-pour costs the machine, the pour and the day.'.format(overdue),
            'Schedule the service before the next shift.',
            HIGH, 'against service intervals + running hours',
            'Operations › Plant')
    if due > 0:
        return _card(
            WATCH, 'Plant service coming due',
            '{} machine(s) are near their service interval.'.format(due),
            'Order the parts now so the service is not what stops the machine.',
            MEDIUM, 'against service intervals + running hours',
            'Operations › Plant')
    return None


def r_fuel(s):
    flags = _n(s, 'plant_fuel_flags')
    if flags <= 0:
        return None
    excess = _n(s, 'plant_excess_litres')
    return _card(
        WATCH, 'Fuel running above the usual rate',
        'On {} day(s), machines burned about {:,.0f} litres more than they '
        'normally do for the work done. Questions to ask, not findings — '
        'pilferage, idling, or a machine going off-tune all look like '
        'this.'.format(flags, excess),
        'Spot-check those logs and the meter readings.',
        LOW, 'a pattern in the fuel logs, not a proof',
        'Operations › Plant')


def r_plan_reliability(s):
    ppc = s.get('ppc_last')
    weeks = _n(s, 'ppc_weeks')
    if ppc is None or weeks < 1:
        return None
    if ppc >= 80:
        return None
    conf = LOW if weeks < 4 else MEDIUM
    reason = s.get('ppc_top_reason')
    reason_txt = (' The commonest reason for a miss: {}.'.format(reason)
                  if reason else '')
    return _card(
        WATCH, 'The weekly plan is not holding',
        'Only {:.0f}% of last week’s promised tasks were finished. A plan '
        'that misses is a programme slipping while everyone looks busy.{}'.format(
            ppc, reason_txt),
        'Fix the recurring constraint before making next week’s promises.',
        conf, '{} week(s) of look-ahead history'.format(weeks),
        'Operations › Look-ahead')


def r_quality_ncr(s):
    crit = _n(s, 'ncr_critical')
    if crit > 0:
        return _card(
            ACT, 'Critical non-conformance open',
            '{} NCR(s) at critical severity are still open. A critical NCR is '
            'work that may have to be broken out and redone.'.format(crit),
            'Close out the corrective action and re-inspect.',
            HIGH, 'from the NCR log', 'Operations › Quality')
    old = _n(s, 'ncr_oldest_days')
    openn = _n(s, 'ncr_open')
    if openn > 0 and old >= 30:
        return _card(
            WATCH, 'Non-conformances are ageing',
            '{} NCR(s) are open, the oldest {} days. An NCR that stays open is '
            'rework nobody has owned.'.format(openn, old),
            'Assign an owner and a close-out date to each.',
            HIGH, 'from the NCR log', 'Operations › Quality')
    return None


def r_snag_blockers(s):
    blockers = _n(s, 'snags_blockers')
    if blockers <= 0:
        return None
    return _card(
        ACT, 'Blocking snags open at handover',
        '{} snag(s) marked as blockers are still open. Handover cannot proceed '
        'while any blocker stands.'.format(blockers),
        'Clear the blockers first — they gate the certificate.',
        HIGH, 'from the snag list', 'Operations › Closeout')


def r_open_rfis(s):
    n = _n(s, 'rfis_open')
    if n <= 0:
        return None
    oldest = _n(s, 'rfis_oldest_days')
    if oldest < 7:
        return None
    return _card(
        WATCH, 'RFIs waiting on an answer',
        '{} request(s) for information are open, the oldest {} days. An '
        'unanswered RFI is a delay with someone else’s name on it — but '
        'only if the date is on record.'.format(n, oldest),
        'Chase the answers and note the wait against the programme.',
        HIGH, 'from the RFI register', 'Purchases › Sourcing')


def r_pending_approvals(s):
    count = _n(s, 'approvals_count')
    if count <= 0:
        return None
    amount = _n(s, 'approvals_amount')
    return _card(
        WATCH, 'Documents waiting on your sign-off',
        '{} document(s) worth {} are sitting in draft or submitted, waiting on '
        'a decision. Bills unapproved are bills unpaid.'.format(
            count, _money(amount)),
        'Clear the approvals queue in one sitting.',
        HIGH, 'the pending-approvals queue', 'Money › Approvals')


def r_undecided_bids(s):
    n = _n(s, 'bids_undecided')
    if n <= 0:
        return None
    return _card(
        WATCH, 'Tenders scored but not decided',
        '{} tender(s) have been assessed but no bid / no-bid call has been '
        'made. Submission dates do not wait.'.format(n),
        'Make the call while there is still time to prepare a bid.',
        MEDIUM, 'the bid assessments on record',
        'Billing › Bid / No Bid')


# The watch-list, in a stable order. Sorting by severity/confidence happens in
# build(); this order only breaks ties within the same severity+confidence.
RULES = (
    r_cash_position,
    r_overdue_receivables,
    r_retention_due,
    r_variations_unbilled,
    r_invoiced_without_grn,
    r_compliance,
    r_programme_delay,
    r_projects_loss,
    r_plant,
    r_fuel,
    r_plan_reliability,
    r_quality_ncr,
    r_snag_blockers,
    r_open_rfis,
    r_pending_approvals,
    r_undecided_bids,
)


def build(snapshot):
    """Ranked advisories for a metrics ``snapshot`` (most urgent first).

    A rule that raises is skipped rather than allowed to blank the whole board
    — one bad figure should not take the dashboard down. When nothing is
    actionable, a single reassuring card is returned instead of an empty box,
    because "nothing to do" is itself worth stating plainly.
    """
    cards = []
    for rule in RULES:
        try:
            card = rule(snapshot or {})
        except Exception:                       # noqa: BLE001 — never blank out
            card = None
        if card:
            cards.append(card)

    if not any(c['severity'] in (ACT, WATCH) for c in cards):
        cards.append(_card(
            GOOD, 'Nothing needs an action today',
            'No overdue money, no stuck approvals, no risk flags on the numbers '
            'recorded so far. Keep the entries current and this stays true.',
            'Carry on — check back after the next round of entries.',
            MEDIUM, 'only as complete as the data entered', ''))

    cards.sort(key=lambda c: (_SEV_RANK.get(c['severity'], 9),
                              _CONF_RANK.get(c['confidence'], 9)))
    return cards


def counts(cards):
    """Tally by severity, for a one-line headline above the cards."""
    out = {ACT: 0, WATCH: 0, GOOD: 0, INFO: 0}
    for c in cards or []:
        out[c['severity']] = out.get(c['severity'], 0) + 1
    return out
