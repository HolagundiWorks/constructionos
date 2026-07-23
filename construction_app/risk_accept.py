"""Risk detect + accept helpers for the JSON API (P3).

No tkinter. Detection uses the same dashboard snapshot + ``risk_detect`` path
as the desktop Risk tab; accept persists drafts (or flips Open AI drafts to
Accepted) with an audit-friendly decided_by stamp.
"""

from datetime import date

import dashboard
import event_hooks
import risk_detect
import risk_store


def detect(conn, apply=False, username='system'):
    """Run detection over a live dashboard snapshot.

    When ``apply`` is true, persist as Open AI drafts (deduped). Returns
    detected risk dicts plus any applied ids.
    """
    snap = dashboard.collect(conn)
    risks = risk_detect.with_mitigations(risk_detect.detect(snap))
    applied = []
    if apply and risks:
        applied = event_hooks.apply_risk_drafts(
            conn, risks, username=username, dedupe=True)
    return {
        'snapshot_keys': sorted(snap.keys()),
        'detected': risks,
        'count': len(risks),
        'applied_ids': applied,
        'applied': bool(apply and applied),
    }


def accept(conn, risk_ids=None, detect_and_apply=False, username='system',
           status='Accepted'):
    """Accept risks: either by id list, or detect→apply→accept in one call.

    ``status`` defaults to Accepted (human-owned). Passing ``Open`` after
    detect_and_apply just leaves drafts open.
    """
    applied = []
    if detect_and_apply:
        result = detect(conn, apply=True, username=username)
        applied = list(result.get('applied_ids') or [])
        if risk_ids is None:
            risk_ids = applied
        detected = result.get('detected') or []
    else:
        detected = []
        risk_ids = list(risk_ids or [])

    accepted = []
    missing = []
    today = date.today().isoformat()
    for rid in risk_ids:
        try:
            rid = int(rid)
        except (TypeError, ValueError):
            missing.append(rid)
            continue
        row = risk_store.get(conn, rid)
        if row is None:
            missing.append(rid)
            continue
        if status and status != row['status']:
            risk_store.set_status(
                conn, rid, status, decided_by=username, decided_date=today)
        accepted.append(rid)
    return {
        'accepted_ids': accepted,
        'applied_ids': applied,
        'missing': missing,
        'detected_count': len(detected),
        'status': status,
    }
