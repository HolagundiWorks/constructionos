"""Bid / no-bid assessment.

No tkinter, no database.

A scorecard that only weighs the estimator's own guesses is astrology with
arithmetic. This one is built so the parts that can be *checked* are checked,
and the parts that cannot be are at least asked honestly:

**Evidence** comes from the firm's own ledger — whether this client has
actually paid on past work, how much of the firm's money is already sitting
with them, and how much work is already on the books. None of that is a
matter of opinion, and the payment record in particular is the single largest
risk in this trade: a profitable job for a client who pays at 180 days can
still close the business.

**Judgement** factors are scored 1-5 against *anchored* descriptions of what 1
and 5 actually mean. A bare 1-5 scale invites everyone to pick 3 for
everything and produces a confident-looking 60 that means nothing.

**Vetoes** are the part that earns the module its place. A weighted average
lets five comfortable scores drown out one fatal factor — no cash to carry it,
a client already 120 days overdue, work the firm cannot actually do. Those are
not worth 10% each; they end the conversation. So they sit outside the score
and override it, which is the same "gate, don't hope" rule the rest of the app
follows.

The verdict is advisory and says so. The veto list is the useful output: it is
specific, it cites the evidence, and it is arguable — which a single number
never is.
"""

BID = 'BID'
CONDITIONAL = 'BID ONLY IF THE CONDITIONS BELOW ARE FIXED'
NO_BID = 'DO NOT BID'

# Judgement factors. Weights sum to 100. Anchors describe 1 and 5 in concrete
# terms so two people scoring the same tender land in roughly the same place.
FACTORS = [
    {'key': 'capability', 'name': 'Can we actually build it', 'weight': 25,
     'low': 'Work we have never done, needing skills or plant we do not have',
     'high': 'Work we do routinely, with the crew and plant already proven'},
    {'key': 'margin', 'name': 'Margin at the likely winning price', 'weight': 25,
     'low': 'We would have to bid at or below cost to win',
     'high': 'Comfortable margin even if we are undercut'},
    {'key': 'terms', 'name': 'Contract terms', 'weight': 15,
     'low': 'Heavy LDs, large retention, slow payment, one-sided risk',
     'high': 'Standard terms we have worked to before without trouble'},
    {'key': 'cashflow', 'name': 'Can we carry it', 'weight': 15,
     'low': 'We would be funding months of work before the first bill is paid',
     'high': 'Mobilisation advance or early billing keeps us in funds'},
    {'key': 'competition', 'name': 'Who else is bidding', 'weight': 10,
     'low': 'Many bidders, and some will buy the job',
     'high': 'Few credible bidders, or we hold a real advantage'},
    {'key': 'logistics', 'name': 'Distance and site access', 'weight': 10,
     'low': 'Far from our base, poor access, no local labour or materials',
     'high': 'Close to existing work, good access, known suppliers'},
]

BY_KEY = {f['key']: f for f in FACTORS}

# Evidence thresholds. Defaults, not laws — a firm with deep pockets may carry
# a slow payer that would sink a smaller one, so the caller can override.
# The ageing buckets (from ``ageing.BUCKETS``) that count as genuinely late.
AGED_BUCKETS = ('60-90', '90+')

DEFAULT_OVERDUE_VETO = 90          # days: money older than this is a red flag
DEFAULT_EXPOSURE_VETO_PCT = 25.0   # of the new tender value already at risk
DEFAULT_WORKLOAD_VETO_PCT = 150.0  # committed work vs stated capacity
MIN_SCORE_TO_BID = 60.0
CONDITIONAL_FLOOR = 45.0


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


def score(judgements):
    """Weighted score out of 100 from ``{factor_key: 1..5}``.

    Only factors actually scored are counted, and the weights are renormalised
    over those. A half-filled scorecard should read as "what we know so far",
    not be silently punished as though the unscored factors were zeros — that
    would make an incomplete assessment look like a bad tender.
    """
    judgements = judgements or {}
    total_weight = 0.0
    earned = 0.0
    for f in FACTORS:
        raw = judgements.get(f['key'])
        if raw in (None, ''):
            continue
        value = max(1.0, min(5.0, _num(raw, 1)))
        total_weight += f['weight']
        earned += f['weight'] * (value - 1) / 4.0      # 1 -> 0%, 5 -> 100%
    if total_weight <= 0:
        return None
    return round(earned / total_weight * 100.0, 1)


def completeness(judgements):
    """Share of the scorecard actually filled in."""
    judgements = judgements or {}
    done = len([f for f in FACTORS
                if judgements.get(f['key']) not in (None, '')])
    return round(done / len(FACTORS) * 100.0, 0), done, len(FACTORS)


def client_evidence(position=None, retention_held=0, tender_value=0,
                    overdue_days=DEFAULT_OVERDUE_VETO):
    """What the ledger says about this client.

    ``position`` is ``allocation.party_position`` output — outstanding total
    and aged buckets. ``retention_held`` is money of ours they are sitting on
    against past jobs, which belongs in exposure even though it is not overdue.
    """
    position = position or {}
    buckets = position.get('buckets') or {}
    outstanding = _num(position.get('outstanding'))
    # The two oldest ageing buckets: money that should already have arrived.
    # Matched by exact label, not substring — '30-60' contains '60'.
    old = sum(_num(buckets.get(label)) for label in AGED_BUCKETS)
    exposure = round(outstanding + _num(retention_held), 2)
    tv = _num(tender_value)
    return {
        'has_history': bool(position),
        'outstanding': round(outstanding, 2),
        'retention_held': round(_num(retention_held), 2),
        'exposure': exposure,
        'aged_overdue': round(old, 2),
        'exposure_pct_of_tender': round(exposure / tv * 100.0, 1) if tv else None,
        'overdue_days_threshold': overdue_days,
    }


def workload_evidence(committed_value, capacity_value, tender_value=0):
    """How full the order book already is."""
    committed = _num(committed_value)
    capacity = _num(capacity_value)
    with_this = committed + _num(tender_value)
    return {
        'committed': round(committed, 2),
        'capacity': round(capacity, 2),
        'with_this_job': round(with_this, 2),
        'utilisation_pct': round(committed / capacity * 100.0, 1) if capacity else None,
        'utilisation_with_this_pct': round(with_this / capacity * 100.0, 1)
        if capacity else None,
    }


def vetoes(judgements=None, client=None, workload=None,
           exposure_veto_pct=DEFAULT_EXPOSURE_VETO_PCT,
           workload_veto_pct=DEFAULT_WORKLOAD_VETO_PCT):
    """Conditions that should end the conversation regardless of the score.

    Each is returned as a sentence naming the evidence, because "score 42" is
    not something anyone can argue with, while "this client still owes you
    4,20,000 more than 60 days old" is.
    """
    out = []
    judgements = judgements or {}
    client = client or {}
    workload = workload or {}

    if _num(judgements.get('capability'), 5) <= 1:
        out.append('We cannot build it. Scored lowest on capability — no crew, '
                   'plant or experience for this work.')
    if _num(judgements.get('cashflow'), 5) <= 1:
        out.append('We cannot carry it. Scored lowest on cash flow — the job '
                   'would be funded out of pocket for months.')
    if _num(judgements.get('margin'), 5) <= 1:
        out.append('There is no margin in it. Winning would mean bidding at or '
                   'below cost.')

    aged = _num(client.get('aged_overdue'))
    if aged > 0:
        out.append('This client already owes {:,.2f} that is more than 60 days '
                   'old. Past behaviour is the best guide to whether they will '
                   'pay for this one.'.format(aged))

    pct = client.get('exposure_pct_of_tender')
    if pct is not None and pct >= _num(exposure_veto_pct):
        out.append('{:,.2f} of our money is already tied up with this client — '
                   '{:g}% of what this tender is worth. Winning would '
                   'concentrate the risk further.'.format(
                       _num(client.get('exposure')), pct))

    util = workload.get('utilisation_with_this_pct')
    if util is not None and util >= _num(workload_veto_pct):
        out.append('The order book would be at {:g}% of stated capacity with '
                   'this job on it. Late delivery on existing work costs more '
                   'than this tender is worth.'.format(util))
    return out


def warnings(judgements=None, client=None, workload=None):
    """Things worth fixing or pricing, short of a veto."""
    out = []
    judgements = judgements or {}
    client = client or {}
    workload = workload or {}

    for f in FACTORS:
        raw = judgements.get(f['key'])
        if raw not in (None, '') and _num(raw, 5) == 2:
            out.append('{}: weak — {}'.format(f['name'], f['low']))

    if client.get('has_history') and not _num(client.get('outstanding')):
        out.append('This client has paid everything billed so far — the best '
                   'evidence available that they will pay again.')
    if not client.get('has_history'):
        out.append('No trading history with this client. Nothing is known '
                   'about how they pay, so price the risk or ask for a '
                   'mobilisation advance.')

    util = workload.get('utilisation_with_this_pct')
    if util is not None and 100 <= util < DEFAULT_WORKLOAD_VETO_PCT:
        out.append('The order book would be at {:g}% of capacity. Winning '
                   'means subletting or hiring.'.format(util))
    return out


def verdict(total, blocked):
    """Advisory verdict. A veto outranks any score."""
    if blocked:
        return NO_BID
    if total is None:
        return CONDITIONAL
    if total >= MIN_SCORE_TO_BID:
        return BID
    if total >= CONDITIONAL_FLOOR:
        return CONDITIONAL
    return NO_BID


def assess(judgements=None, client=None, workload=None, **kw):
    """The whole assessment: score, evidence, vetoes, warnings, verdict."""
    total = score(judgements)
    blocked = vetoes(judgements, client, workload, **kw)
    pct, done, of = completeness(judgements)
    return {
        'score': total,
        'completeness_pct': pct,
        'scored': done,
        'factors': of,
        'client': client or {},
        'workload': workload or {},
        'vetoes': blocked,
        'warnings': warnings(judgements, client, workload),
        'verdict': verdict(total, blocked),
    }


def outcome_review(assessments):
    """Compare what was scored against what actually happened.

    The point of recording the decision *and* the outcome is that the weights
    above are guesses until the firm's own history says otherwise. Bidding at
    high scores and losing means the pricing is off, not the scorecard; winning
    at low scores and losing money means the scorecard is being overruled.
    """
    rows = [a for a in assessments or [] if _g(a, 'score') is not None]
    won = [a for a in rows if str(_g(a, 'outcome', '')) == 'Won']
    lost = [a for a in rows if str(_g(a, 'outcome', '')) == 'Lost']
    bid_against_advice = [
        a for a in rows
        if str(_g(a, 'decision', '')) == 'Bid'
        and str(_g(a, 'verdict', '')) == NO_BID]
    return {
        'assessed': len(rows),
        'won': len(won),
        'lost': len(lost),
        'win_rate': round(len(won) / (len(won) + len(lost)) * 100.0, 1)
        if (won or lost) else None,
        'avg_score_won': round(
            sum(_num(_g(a, 'score')) for a in won) / len(won), 1) if won else None,
        'avg_score_lost': round(
            sum(_num(_g(a, 'score')) for a in lost) / len(lost), 1) if lost else None,
        'bid_against_advice': len(bid_against_advice),
    }
