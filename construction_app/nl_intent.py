"""NL → gated workflow / follow-up drafts (deterministic floor for NL automation).

No tkinter, no model. Maps free-text intents onto the existing ``followups``
events and ``workflow`` steps. Every money / filing / date-moving suggestion
stays ``gated=True`` — AI proposes; a human approves. This is the offline floor
for "NL-triggered workflows" until a model can classify richer intents.

Returns empty lists for unrecognized text rather than guessing.
"""

import followups
import workflow

# Phrase fragments (lowercase) → followups event type. First match wins.
_EVENT_HINTS = (
    (('grn', 'goods receipt', 'three-way', '3-way', '3 way', 'challan'),
     followups.GRN_SAVED),
    (('measurement', 'mb entry', 'measure qty', 'measure quantity'),
     followups.MEASUREMENT_ENTERED),
    (('variation', 'vo approved', 'change order'),
     followups.VARIATION_APPROVED),
    (('payment due', 'pay vendor', 'vendor payment', 'draft payment'),
     followups.PAYMENT_DUE),
    (('ra bill', 'running account approved', 'approve ra'),
     followups.RA_BILL_APPROVED),
    (('ncr', 'non conformance', 'non-conformance'),
     followups.NCR_RAISED),
    (('muster', 'attendance', 'mark present'),
     followups.ATTENDANCE_SAVED),
    (('snag', 'punch list', 'defect liability'),
     followups.SNAG_RAISED),
    (('running bill', 'approve bill', 'bill approved'),
     followups.RUNNING_BILL_APPROVED),
    (('filing', 'gst return', 'gstr', 'tds return', 'compliance due'),
     followups.FILING_DUE),
    (('activity complete', 'work done', 'dpr done', 'progress logged'),
     followups.ACTIVITY_COMPLETE),
)

# Phrase fragments → workflow id (from workflow.WORKFLOWS).
_FLOW_HINTS = (
    (('bid', 'tender', 'quotation', 'estimate', 'no-bid', 'no bid'),
     'bid_to_contract'),
    (('ra bill', 'running bill', 'invoice', 'retention', 'collect cash',
      'tax invoice'),
     'contract_to_cash'),
    (('procure', 'purchase order', 'vendor invoice', 'requisition', 'po '),
     'procure_to_pay'),
    (('lookahead', 'look-ahead', 'closeout', 'programme', 'site report',
      'consumption'),
     'plan_to_execute'),
)

# Extra free-text → concrete gated step (action, where, gated).
_EXTRA = (
    (('close snag', 'close snags', 'handover', 'punch list'),
     'Draft snag close-out and handover checklist.',
     'Operations › Closeout', True),
    (('match invoice', 'three way match', '3-way match'),
     'Run the 3-way match (PO ↔ GRN ↔ invoice) and flag any mismatch.',
     'Purchases › Goods Receipt', False),
    (('weekly review', 'review pack'),
     'Assemble this week’s review pack (KPIs + risks + narrative).',
     'Money › Review', False),
)


def _norm(text):
    return ' '.join((text or '').lower().split())


def match_event(text):
    """Best followups event for ``text``, or None."""
    q = _norm(text)
    if not q:
        return None
    for phrases, event in _EVENT_HINTS:
        if any(p in q for p in phrases):
            return event
    return None


def match_workflow(text):
    """Best workflow id for ``text``, or None."""
    q = _norm(text)
    if not q:
        return None
    for phrases, wid in _FLOW_HINTS:
        if any(p in q for p in phrases):
            return wid
    return None


def resolve(text, payload=None):
    """Turn free text into draft follow-ups + optional workflow pointer.

    Returns::

        {
          'query': str,
          'event': str|None,
          'workflow': str|None,
          'followups': [{action, where, gated, ...}, ...],
          'next_step': {key, label, section, tab}|None,  # when workflow known
          'gated_count': int,
        }
    """
    payload = dict(payload or {})
    q = (text or '').strip()
    event = match_event(q)
    wid = match_workflow(q)
    steps = []
    if event:
        for f in followups.for_event(event, payload):
            step = dict(f)
            step['payload'] = payload
            steps.append(step)
    qn = _norm(q)
    for phrases, action, where, gated in _EXTRA:
        if any(p in qn for p in phrases):
            steps.append({
                'action': action, 'where': where, 'gated': gated,
                'payload': payload,
            })
    # Dedupe by (action, where)
    seen = set()
    uniq = []
    for s in steps:
        key = (s.get('action'), s.get('where'))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)
    next_hit = None
    if wid:
        # Synthetic empty state → first step is "what's next" for guidance.
        steps_list = workflow.get(wid) or []
        next_hit = workflow.next_step(steps_list, {})
    return {
        'query': q,
        'event': event,
        'workflow': wid,
        'followups': uniq,
        'next_step': next_hit,
        'gated_count': sum(1 for s in uniq if s.get('gated')),
    }
