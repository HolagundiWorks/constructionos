"""Event → follow-on + risk-detection hooks (E4 / cloud C5) — decision logic.

No tkinter. A save handler (GUI or API) raises an event; this module decides
what *draft* follow-ups and optional risk detections should appear. Every
consequential follow-up stays ``gated=True`` (human must approve). Nothing here
auto-posts money or dates.

Composes:
  * ``followups.for_event`` — rote next steps for the event
  * ``risk_detect.detect`` — optional snapshot → register-ready AI risks
"""

import followups
import risk_detect


def react(event_type, payload=None, snapshot=None):
    """Given an event (+ optional dashboard snapshot), return drafts to surface.

    Returns::

        {
          'event': str,
          'payload': dict,
          'followups': [{action, where, gated, payload}, ...],
          'risks': [register-ready risk dicts with mitigations, ...],
          'gated_count': int,   # follow-ups that must stay human-approved
        }
    """
    payload = dict(payload or {})
    steps = []
    for f in followups.for_event(event_type, payload):
        step = dict(f)
        step['payload'] = payload
        steps.append(step)
    risks = []
    if snapshot is not None:
        risks = risk_detect.with_mitigations(risk_detect.detect(snapshot))
    return {
        'event': event_type,
        'payload': payload,
        'followups': steps,
        'risks': risks,
        'gated_count': sum(1 for s in steps if s.get('gated')),
    }


def apply_risk_drafts(conn, risks, username='system', dedupe=True):
    """Persist detected risks as Open AI drafts. Returns new ids.

    Thin wrapper over ``signal_feed.apply_drafts`` so event wiring and
    prediction feed share one write path + audit origin tag.
    """
    import signal_feed
    return signal_feed.apply_drafts(conn, risks, username=username,
                                    dedupe=dedupe)
