"""Risk scoring — the deterministic heart of the risk register (E0 foundation).

No tkinter, no database. The enterprise roadmap
(``docs/ENTERPRISE-PM-SOLUTION.md`` / ``docs/ROADMAP.md``) makes risk a first-class capability;
the register's *storage* and *screen* come later, but the **maths must be pure,
explainable and testable** first, because a risk score that quietly
mis-classifies an exposure is as dangerous as a wrong money figure.

The model is the standard, defensible one a QS or PM already knows: a **5x5
likelihood x impact matrix**. Likelihood and impact are each an ordinal 1..5;
the raw score is their product (1..25); a band (Low / Medium / High / Critical)
turns the number into an action colour. Where a rupee (or days) figure for the
impact is known, an **expected exposure** = probability(likelihood) x value puts
a comparable size on each risk so a portfolio can be ranked by what is actually
at stake, not just by a matrix cell.

Two honesty rules, as everywhere in the pure layer: inputs are clamped to the
valid 1..5 range rather than trusted blindly (a mistyped 9 must not invent a
score of 45), and nothing here *decides* — it scores and ranks so a human can.

Exercise with ``python -c`` — e.g.::

    python -c "import risk; print(risk.assess(4, 5, value=200000))"
"""

# --- the ordinal scales (1..5), lowest first
LIKELIHOOD_LABELS = {
    1: 'Rare', 2: 'Unlikely', 3: 'Possible', 4: 'Likely', 5: 'Almost certain',
}
IMPACT_LABELS = {
    1: 'Insignificant', 2: 'Minor', 3: 'Moderate', 4: 'Major', 5: 'Severe',
}

# A representative probability for each likelihood step, for expected-value
# sizing. Deliberately mid-band and evenly spaced — this is a sizing aid, not a
# statistical claim, so it stays simple and explainable.
_PROBABILITY = {1: 0.1, 2: 0.3, 3: 0.5, 4: 0.7, 5: 0.9}

# --- bands over the 1..25 raw score. Boundaries chosen so a top-row (severe,
# impact 5) risk is never merely 'Low', and a 5x5 is unambiguously Critical.
LOW, MEDIUM, HIGH, CRITICAL = 'Low', 'Medium', 'High', 'Critical'
_BAND_RANK = {LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3}

# --- risk response strategies (PMI-standard). The band says how big; the
# response says what to do about it. Kept as data so a store can validate.
AVOID, REDUCE, TRANSFER, ACCEPT = 'Avoid', 'Reduce', 'Transfer', 'Accept'
RESPONSES = (AVOID, REDUCE, TRANSFER, ACCEPT)


def valid_response(response):
    """Return the response if it is a recognised strategy, else None — a bad
    value is dropped rather than stored, never raised (a register import with a
    typo must not crash the roll-up)."""
    r = (response or '').strip().title()
    return r if r in RESPONSES else None


def _level(value):
    """Clamp an ordinal to the valid 1..5, as an int. A blank/garbage level
    falls to 1 (the least alarming) rather than raising — a register row with a
    missing score should not crash the roll-up."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return 1
    return max(1, min(5, n))


def score(likelihood, impact):
    """Raw risk score = likelihood x impact, each clamped to 1..5 → 1..25."""
    return _level(likelihood) * _level(impact)


def band(raw_score):
    """The action band for a 1..25 score.

        1-4  Low · 5-9 Medium · 10-15 High · 16-25 Critical
    """
    s = _level_score(raw_score)
    if s <= 4:
        return LOW
    if s <= 9:
        return MEDIUM
    if s <= 15:
        return HIGH
    return CRITICAL


def _level_score(raw_score):
    try:
        return max(1, min(25, int(round(float(raw_score)))))
    except (TypeError, ValueError):
        return 1


def probability(likelihood):
    """The representative probability (0..1) for a likelihood step."""
    return _PROBABILITY[_level(likelihood)]


def expected_exposure(likelihood, value):
    """Probability-weighted size of a risk: ``probability(likelihood) x value``.

    ``value`` is the impact if it happens — rupees or days, the caller's choice.
    This is what lets two risks be compared: a rare but ruinous one against a
    likely but small one."""
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        v = 0.0
    return round(probability(likelihood) * v, 2)


def assess(likelihood, impact, value=0,
           residual_likelihood=None, residual_impact=None,
           urgency=None, response=None):
    """Score one risk, inherent and (optionally) residual-after-mitigation.

    Returns the raw score, band, labels, and — when a ``value`` is given — the
    expected exposure. If ``residual_*`` are supplied, the post-mitigation
    picture is included too, plus how many score points the mitigation buys, so
    a register can show that a control actually moved the needle.

    ``urgency`` (1..5, optional) is the *when* to the score's *how big* — two
    equally-scored risks are not equally pressing. It never changes the band
    (that stays likelihood×impact, the classification the industry uses); it
    drives ``priority`` = score×urgency, which sequences same-band items.
    ``response`` records the chosen strategy (Avoid/Reduce/Transfer/Accept),
    validated and dropped if unrecognised.
    """
    lk, im = _level(likelihood), _level(impact)
    raw = score(lk, im)
    urg = _level(urgency) if urgency is not None else None
    out = {
        'likelihood': lk,
        'impact': im,
        'likelihood_label': LIKELIHOOD_LABELS[lk],
        'impact_label': IMPACT_LABELS[im],
        'score': raw,
        'band': band(raw),
        'urgency': urg,
        'priority': raw if urg is None else raw * urg,
        'response': valid_response(response),
        'value': round(float(value or 0), 2) if value else 0.0,
        'expected_exposure': expected_exposure(lk, value),
    }
    if residual_likelihood is not None or residual_impact is not None:
        rlk = _level(residual_likelihood
                     if residual_likelihood is not None else likelihood)
        rim = _level(residual_impact
                     if residual_impact is not None else impact)
        r_raw = score(rlk, rim)
        out['residual'] = {
            'likelihood': rlk,
            'impact': rim,
            'score': r_raw,
            'band': band(r_raw),
            'expected_exposure': expected_exposure(rlk, value),
        }
        # Never report a mitigation as making a risk worse; a control that
        # raises the score is a data error, floored to 0 improvement here.
        out['mitigation_benefit'] = max(0, raw - r_raw)
    return out


def rank(risks):
    """Order assessed risks worst-first: by band, then score, then exposure.

    ``risks`` is an iterable of dicts from ``assess`` (each may also carry its
    own id/title — untouched). A stable, explainable ordering so the register's
    top of list is genuinely the thing to act on first."""
    def key(r):
        priority = r.get('priority')
        if priority is None:
            priority = r.get('score', 1)
        return (
            -_BAND_RANK.get(r.get('band', LOW), 0),
            -float(priority or 0),
            -float(r.get('expected_exposure') or 0),
        )
    return sorted(list(risks or []), key=key)


def register_summary(risks, top_n=5):
    """Portfolio view over a list of assessed risks.

    Counts by band, the total expected exposure (comparable size of the whole
    register), the count of Critical/High that need attention now, and the
    worst ``top_n`` — so a dashboard can lead with the exposure and the short
    list rather than a raw count that hides the one that matters.
    """
    risks = list(risks or [])
    by_band = {LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0}
    exposure = 0.0
    for r in risks:
        b = r.get('band', LOW)
        by_band[b] = by_band.get(b, 0) + 1
        exposure += float(r.get('expected_exposure') or 0)
    ranked = rank(risks)
    return {
        'count': len(risks),
        'by_band': by_band,
        'needs_action': by_band.get(CRITICAL, 0) + by_band.get(HIGH, 0),
        'total_expected_exposure': round(exposure, 2),
        'top': ranked[:max(0, top_n)],
    }
