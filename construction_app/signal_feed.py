"""Prediction → register feed (E5 / cloud C4).

No tkinter. Turns forecast / drift *signals* into **draft** risk rows a human
accepts or dismisses — never an auto-accepted decision. Pure helpers build the
draft dicts; ``apply_drafts`` is the thin DB write (``source='ai'``) so the
prediction loop closes without a GUI.

Every draft carries a stated ``basis`` (and the forecast band / drift signals
behind it), matching the explainability guardrail.
"""

import risk
import risk_detect
import risk_store

SCHEDULE = risk_detect.SCHEDULE
COST = risk_detect.COST


def _draft(category, title, likelihood, impact, value, basis, project_id=None,
           description='', where='Project Management › Risks'):
    """One register-ready AI draft (scored via ``risk.assess``)."""
    a = risk.assess(likelihood, impact, value=value)
    a.update({
        'category': category,
        'title': title,
        'description': description,
        'basis': basis,
        'where': where,
        'source': 'ai',
        'status': 'Open',
        'project_id': project_id,
        'impact_value': value,
        'likelihood': likelihood,
        'impact': impact,
    })
    return a


def from_drift(drift_result, project_id=None):
    """Draft a risk when weak-signal drift is raised; None if not drifting."""
    drift_result = drift_result or {}
    if not drift_result.get('drifting'):
        return None
    signals = drift_result.get('signals') or []
    names = ', '.join(s.get('signal', '?') for s in signals) or 'weak signals'
    bases = '; '.join(s.get('basis', '') for s in signals if s.get('basis'))
    score = int(drift_result.get('score') or 0)
    # Soft call → moderate likelihood; more agreeing signals → higher.
    likelihood = 2 if score < 4 else (3 if score < 5 else 4)
    return _draft(
        SCHEDULE,
        'Project drifting (weak signals)',
        likelihood, 3,
        value=0,
        basis=bases or names,
        project_id=project_id,
        description='Early drift flag from: {}.'.format(names),
    )


def from_schedule_forecast(forecast_result, project_id=None, ld_exposure=0):
    """Draft a risk when schedule forecast shows positive slip; else None."""
    forecast_result = forecast_result or {}
    slip = float(forecast_result.get('slip') or 0)
    if slip <= 0:
        return None
    impact = 2 if slip < 7 else (3 if slip < 21 else (4 if slip < 45 else 5))
    value = float(ld_exposure or 0) or slip  # days if no ₹ LD given
    return _draft(
        SCHEDULE,
        'Schedule forecast slip ({:.0f} days)'.format(slip),
        3, impact,
        value=value,
        basis='baseline {:.0f}d → forecast {:.0f}d (SPI-based)'.format(
            float(forecast_result.get('baseline_duration') or 0),
            float(forecast_result.get('forecast_duration') or 0)),
        project_id=project_id,
        description='If today\'s schedule performance continues, the job '
                    'finishes ~{:.0f} days late.'.format(slip),
    )


def from_trend(projection, metric='cost', project_id=None, value_at_stake=0):
    """Draft a risk when a trend projection is rising toward trouble.

    ``projection`` is a ``forecast.project`` result. Only rising series with a
    stated confidence produce a draft; flat/falling/undefined → None.
    """
    if not projection:
        return None
    slope = float(projection.get('slope') or 0)
    if slope <= 0:
        return None
    conf = projection.get('confidence') or 'Low'
    likelihood = 2 if conf == 'Low' else (3 if conf == 'Medium' else 4)
    high = float(projection.get('high') or projection.get('value') or 0)
    category = COST if metric == 'cost' else SCHEDULE
    title = 'Rising {} trend (forecast)'.format(metric)
    return _draft(
        category, title, likelihood, 3,
        value=float(value_at_stake or high),
        basis='{}; slope {:+.2f}/period; band {:.0f}–{:.0f}'.format(
            projection.get('basis', 'trend'),
            slope,
            float(projection.get('low') or 0),
            float(projection.get('high') or 0)),
        project_id=project_id,
        description='Forward projection for {} is rising '
                    '(confidence {}).'.format(metric, conf),
    )


def collect(drift=None, schedule_forecast=None, cost_trend=None,
            project_id=None, ld_exposure=0):
    """All material prediction drafts from the given signals (may be empty)."""
    out = []
    d = from_drift(drift, project_id=project_id)
    if d:
        out.append(d)
    s = from_schedule_forecast(schedule_forecast, project_id=project_id,
                               ld_exposure=ld_exposure)
    if s:
        out.append(s)
    t = from_trend(cost_trend, metric='cost', project_id=project_id)
    if t:
        out.append(t)
    return out


def _open_titles(conn, project_id=None):
    rows = risk_store.list_risks(conn, project_id=project_id, status='Open')
    return {r['title'] for r in rows}


def apply_drafts(conn, drafts, username='system', dedupe=True):
    """Write draft risks with ``source='ai'``. Returns list of new row ids.

    When ``dedupe`` is True, skips a draft whose title already exists as an
    Open risk (same project scope) so re-running a feed does not spam the
    register. Each write is audited with ``origin='ai'``.
    """
    import auth
    drafts = drafts or []
    if not drafts:
        return []
    existing = _open_titles(conn) if dedupe else set()
    # Also scope by project when present
    ids = []
    for d in drafts:
        title = d.get('title')
        if dedupe and title in existing:
            continue
        fields = {
            'project_id': d.get('project_id'),
            'category': d.get('category'),
            'title': title,
            'description': d.get('description') or d.get('basis'),
            'likelihood': d.get('likelihood', 1),
            'impact': d.get('impact', 1),
            'impact_value': d.get('impact_value') or d.get('expected_exposure') or 0,
            'source': 'ai',
            'status': 'Open',
            'remarks': d.get('basis'),
        }
        new_id = risk_store.add(conn, **fields)
        auth.audit(conn, username, 'ai_draft', 'risks', new_id,
                   detail=title, origin=auth.ORIGIN_AI)
        # risk_store.add already committed; persist the audit row too.
        try:
            conn.commit()
        except Exception:
            pass
        ids.append(new_id)
        if dedupe and title:
            existing.add(title)
    return ids
