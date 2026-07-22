"""Opportunity scoring (Part 2 — the upside twin of ``risk.py``).

No tkinter, no database. A construction execution register tracks not only what
could go wrong but what could go *right* — a lean-construction saving, a
local-sourcing win, a work-sequence that buys back float. Part 2 scores these
the same way as risks (probability × impact) but the meaning flips: the value at
stake is an **upside to capture**, and the responses are Exploit / Enhance /
Share / Accept rather than Avoid / Reduce / Transfer / Accept.

Rather than re-derive the matrix, this reuses ``risk``'s scoring primitives
(same 5×5 likelihood×impact, same bands, same probability weighting) so a risk
and an opportunity of equal likelihood and impact rank alike — only the sign of
what is at stake, and the response vocabulary, differ. ``expected_value`` is the
probability-weighted upside, the mirror of a risk's expected exposure.

Exercised with ``python -c``, e.g.::

    python -c "import opportunity as o; print(o.assess(4, 4, value=300000))"
"""

import risk

# --- opportunity response strategies (PMI-standard, the positive mirror).
EXPLOIT, ENHANCE, SHARE, ACCEPT = 'Exploit', 'Enhance', 'Share', 'Accept'
RESPONSES = (EXPLOIT, ENHANCE, SHARE, ACCEPT)

# Reuse the risk scales/bands so risks and opportunities speak one language.
LIKELIHOOD_LABELS = risk.LIKELIHOOD_LABELS
IMPACT_LABELS = risk.IMPACT_LABELS
LOW, MEDIUM, HIGH, CRITICAL = risk.LOW, risk.MEDIUM, risk.HIGH, risk.CRITICAL


def valid_response(response):
    """The response if recognised, else None (a typo is dropped, not raised)."""
    r = (response or '').strip().title()
    return r if r in RESPONSES else None


def score(likelihood, impact):
    """Likelihood × impact, 1..25 — the same matrix as risk."""
    return risk.score(likelihood, impact)


def band(raw_score):
    """Priority band (Low/Medium/High/Critical) — a 'Critical' opportunity is
    one worth pursuing hardest, not one to fear."""
    return risk.band(raw_score)


def expected_value(likelihood, value):
    """Probability-weighted **upside**: ``probability(likelihood) × value``.

    The mirror of a risk's expected exposure — what the opportunity is worth on
    a weighted basis, so a likely-small win can be compared to a long-shot big
    one."""
    return risk.expected_exposure(likelihood, value)


def assess(likelihood, impact, value=0, urgency=None, response=None):
    """Score one opportunity: band, expected upside, urgency-driven priority and
    a validated response strategy. Mirrors ``risk.assess`` field-for-field so a
    combined register can rank threats and opportunities together."""
    lk, im = risk._level(likelihood), risk._level(impact)
    raw = score(lk, im)
    urg = risk._level(urgency) if urgency is not None else None
    return {
        'kind': 'opportunity',
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
        'expected_value': expected_value(lk, value),
    }


def rank(opportunities):
    """Best-first: by band, then urgency-weighted priority, then expected value —
    so the top of the list is the opportunity to pursue first."""
    def key(o):
        priority = o.get('priority')
        if priority is None:
            priority = o.get('score', 1)
        return (
            -risk._BAND_RANK.get(o.get('band', LOW), 0),
            -float(priority or 0),
            -float(o.get('expected_value') or 0),
        )
    return sorted(list(opportunities or []), key=key)


def register_summary(opportunities, top_n=5):
    """Portfolio view: counts by band, total expected upside, the count worth
    pursuing now (Critical/High), and the best ``top_n``."""
    opportunities = list(opportunities or [])
    by_band = {LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0}
    upside = 0.0
    for o in opportunities:
        b = o.get('band', LOW)
        by_band[b] = by_band.get(b, 0) + 1
        upside += float(o.get('expected_value') or 0)
    ranked = rank(opportunities)
    return {
        'count': len(opportunities),
        'by_band': by_band,
        'pursue_now': by_band.get(CRITICAL, 0) + by_band.get(HIGH, 0),
        'total_expected_value': round(upside, 2),
        'top': ranked[:max(0, top_n)],
    }
