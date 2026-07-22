"""Weak-signal drift detection (E5.2 — catch a project drifting early).

No tkinter, no database, no model. Threshold rules (``risk_detect``) fire when a
single number crosses a line. But a project often *drifts* before any one line is
crossed — a run of small schedule slips, a look-ahead reliability quietly
falling, RFI ages creeping up, a rash of low-confidence measurements. None of
these alone trips a threshold; together they say "this job is going wrong slowly".

This module correlates those soft signals into one honest flag. It is
deliberately additive and explainable: each contributing signal is named with
its basis, and the flag is raised only when enough weak signals agree — so it is
an early warning, not a jittery alarm. Confidence is low by construction (that is
the nature of a weak signal) and labelled as such.

Exercised with ``python -c``.
"""

import forecast

# Points a signal contributes, and the total at which drift is called. Tuned so
# no single soft signal trips it — drift needs at least two weak signals to agree.
_DRIFT_THRESHOLD = 3

LOW = 'Low'          # a drift flag is a hint; its confidence is never more than this


def _series(values):
    out = []
    for v in values or []:
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def assess_drift(signals):
    """Correlate soft indicators into a drift flag.

    ``signals`` is a dict, all keys optional:
      * ``ppc_series``           — recent Plan-Percent-Complete readings
      * ``slip_series``          — recent per-period schedule slip (days)
      * ``rfi_age_series``       — recent oldest-open-RFI age (days)
      * ``low_conf_measurements``— count of recent low-confidence measurements

    Returns ``{drifting, score, confidence, signals}`` where ``signals`` names
    each contributing weak signal with its basis — so 'why am I seeing this?'
    always has an answer, even for a soft call.
    """
    signals = signals or {}
    contributing = []
    score = 0

    ppc = _series(signals.get('ppc_series'))
    if len(ppc) >= 3 and forecast.direction(ppc) == 'falling':
        score += 2
        contributing.append({'signal': 'plan reliability falling',
                             'basis': '{} periods of PPC, trending down'.format(len(ppc))})

    slips = _series(signals.get('slip_series'))
    small_slips = sum(1 for d in slips if 0 < d <= 3)
    if small_slips >= 3:
        score += 2
        contributing.append({'signal': 'repeated small schedule slips',
                             'basis': '{} periods slipping by 1-3 days'.format(small_slips)})

    rfi = _series(signals.get('rfi_age_series'))
    if len(rfi) >= 3 and forecast.direction(rfi) == 'rising':
        score += 1
        contributing.append({'signal': 'RFI ages creeping up',
                             'basis': '{} periods of rising oldest-RFI age'.format(len(rfi))})

    low_conf = int(signals.get('low_conf_measurements') or 0)
    if low_conf >= 3:
        score += 1
        contributing.append({'signal': 'low-confidence measurements',
                             'basis': '{} recent measurements flagged for review'.format(low_conf)})

    return {
        'drifting': score >= _DRIFT_THRESHOLD,
        'score': score,
        'confidence': LOW,          # a weak-signal call is never high-confidence
        'signals': contributing,
    }
