"""Event-driven follow-on suggestions (E4.1 — the decision logic).

No tkinter, no database. When one thing happens on site, a handful of rote
follow-ups should happen next — a goods receipt should prompt the 3-way match, a
completed activity should refresh the look-ahead, an approaching filing should
assemble its checklist. The *wiring* that fires these lives in the GUI (a save
handler), but the **decision** — given this event, what should be drafted next —
is pure, and it lives here so it is testable and consistent.

Every suggested follow-up carries a ``gated`` flag: **True** means it moves
money, files with a department, or changes a contractual date, and so must be a
draft a human approves — never auto-run. **False** means it is safe assembly
(refresh a view, compile a checklist). This is the automation guardrail from the
roadmap, encoded rather than hoped for.
"""

# Event types a caller (a save handler, a scheduler) can raise.
GRN_SAVED = 'grn_saved'
ACTIVITY_COMPLETE = 'activity_complete'
FILING_DUE = 'filing_due'
MEASUREMENT_ENTERED = 'measurement_entered'
VARIATION_APPROVED = 'variation_approved'
PAYMENT_DUE = 'payment_due'
RA_BILL_APPROVED = 'ra_bill_approved'
NCR_RAISED = 'ncr_raised'
ATTENDANCE_SAVED = 'attendance_saved'
SNAG_RAISED = 'snag_raised'
RUNNING_BILL_APPROVED = 'running_bill_approved'

EVENTS = (GRN_SAVED, ACTIVITY_COMPLETE, FILING_DUE, MEASUREMENT_ENTERED,
          VARIATION_APPROVED, PAYMENT_DUE, RA_BILL_APPROVED, NCR_RAISED,
          ATTENDANCE_SAVED, SNAG_RAISED, RUNNING_BILL_APPROVED)


def _f(action, where, gated=False):
    return {'action': action, 'where': where, 'gated': gated}


def for_event(event_type, payload=None):
    """The ordered follow-ups a given event should draft.

    ``payload`` is an optional dict of event context (ids, amounts) a caller can
    thread into the drafted artefacts; it is echoed back untouched so the GUI can
    pre-fill. Returns a list of ``{action, where, gated}`` — empty for an unknown
    event rather than raising, so a new event type degrades to 'no suggestions'.
    """
    payload = payload or {}
    if event_type == GRN_SAVED:
        return [
            _f('Run the 3-way match (PO ↔ GRN ↔ invoice) and flag any mismatch.',
               'Purchases › Goods Receipt'),
            _f('Update the material ledger with the accepted quantity.',
               'Operations › Warehouse'),
        ]
    if event_type == ACTIVITY_COMPLETE:
        return [
            _f('Advance % complete and recompute the critical path and float.',
               'Project Management › Timeline'),
            _f('Refresh next week’s look-ahead against the new dates.',
               'Project Management › Look-ahead'),
        ]
    if event_type == FILING_DUE:
        return [
            _f('Assemble the filing checklist and pre-fill the register summary.',
               'Accounts › Compliance'),
            _f('File the return.', 'Accounts › Compliance', gated=True),
        ]
    if event_type == MEASUREMENT_ENTERED:
        return [
            _f('Draft the RA-bill abstract line for the measured work.',
               'Billing › BOQ / RA Bills'),
            _f('Flag a deviation if the quantity over-runs the BOQ.',
               'Billing › Variations'),
        ]
    if event_type == VARIATION_APPROVED:
        return [
            _f('Pull the approved variation into the next running bill.',
               'Billing › Variations', gated=True),
        ]
    if event_type == PAYMENT_DUE:
        return [
            _f('Draft the payment batch respecting TDS and ageing priority.',
               'Money › Approvals', gated=True),
        ]
    if event_type == RA_BILL_APPROVED:
        return [
            _f('Issue / update the tax invoice for the approved RA amount.',
               'Billing › Tax Invoice', gated=True),
            _f('Refresh retention and cash-flow against the new certified value.',
               'Money › Retention'),
        ]
    if event_type == NCR_RAISED:
        return [
            _f('Assign root cause and corrective action; hold related work if Critical.',
               'Operations › Quality'),
            _f('Log a risk draft if the NCR threatens programme or cost.',
               'Controls › Risk Register', gated=True),
        ]
    if event_type == ATTENDANCE_SAVED:
        return [
            _f('Recompute weekly payout / muster totals for the site.',
               'Operations › Muster & Wages'),
        ]
    if event_type == SNAG_RAISED:
        return [
            _f('Assign trade owner and target date; block handover if Blocker.',
               'Operations › Closeout'),
            _f('Add to weekly look-ahead if the fix is on the critical path.',
               'Project Management › Look-ahead'),
        ]
    if event_type == RUNNING_BILL_APPROVED:
        return [
            _f('Issue / update the tax invoice for the approved running bill.',
               'Billing › Tax Invoice', gated=True),
            _f('Refresh retention and party balances.',
               'Money › Retention'),
        ]
    return []


def gated_actions(event_type, payload=None):
    """Just the consequential follow-ups (money / filing / dates) — the ones a
    human must approve. Handy for a UI that shows 'needs your sign-off'."""
    return [f for f in for_event(event_type, payload) if f['gated']]
