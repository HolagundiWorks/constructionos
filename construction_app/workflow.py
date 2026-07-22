"""Operational workflow graph (E7.2) — the process flows across the menu.

No tkinter, no database. The menu is organised by *function* (Masters, Billing,
…); the *work*, though, runs as end-to-end flows that cross several sections —
bid→contract→bill→collect, procure→pay, plan→execute (see
``docs/APP-ARCHITECTURE.md`` §5.2). This module models each flow as an **ordered
list of steps**, and each step names its **menu home** (section + tab) and a
**completion key**.

Given a ``state`` dict — which the GUI derives from the book, and tests supply
synthetically — it computes the **next incomplete step** ("what's next") and
overall **progress**. That is the data behind a guided Process view: it
*sequences* the functional menu without re-organising it (closing gaps N2/N6),
building on the same intent as ``advisory`` (what to do) and ``followups`` (the
rote next actions after an event).

Every step points at a real (section, tab) in ``SECTIONS_CATALOG``; a test
asserts there are no dangling locations, so the graph can never send a user to a
menu place that doesn't exist. Exercised with ``python -c``.
"""

import modules


def step(key, label, section, tab):
    """One workflow step: a completion ``key``, a human ``label``, and its menu
    home (``section`` → ``tab``) so a Process view can deep-link to it."""
    return {'key': key, 'label': label, 'section': section, 'tab': tab}


# --------------------------------------------------------------- the flows
# Pre-construction: from spotting a tender to a signed contract.
BID_TO_CONTRACT = [
    step('sourcing', 'Find the tender', 'Purchases', 'Sourcing'),
    step('rate_analysis', 'Build the rates', 'Billing', 'Rate Analysis'),
    step('estimate', 'Prepare the estimate', 'Billing', 'Estimates'),
    step('bid_decision', 'Make the bid / no-bid call', 'Billing', 'Bid / No Bid'),
    step('quotation', 'Issue the quotation', 'Billing', 'Quotations'),
    step('contract', 'Sign the contract', 'Billing', 'Contracts'),
]

# Commercial: from contract to cash in hand.
CONTRACT_TO_CASH = [
    step('contract', 'Contract in place', 'Billing', 'Contracts'),
    step('boq', 'Load the BOQ', 'Billing', 'BOQ / RA Bills'),
    step('measurement', 'Record measurements', 'Billing', 'BOQ / RA Bills'),
    step('ra_bill', 'Raise the RA bill', 'Billing', 'BOQ / RA Bills'),
    step('variations', 'Bill approved variations', 'Billing', 'Variations'),
    step('invoice', 'Issue the tax invoice', 'Billing', 'Tax Invoice'),
    step('receipt', 'Record the receipt', 'Money', 'Cash & Parties'),
    step('retention', 'Release retention', 'Money', 'Retention'),
]

# Supply: from a need to a paid vendor, gated by the goods receipt.
PROCURE_TO_PAY = [
    step('requisition', 'Raise a requisition', 'Purchases', 'Sourcing'),
    step('po', 'Issue the purchase order', 'Purchases', 'Purchase Orders'),
    step('grn', 'Receive goods (GRN, 3-way match)', 'Purchases', 'Goods Receipt'),
    step('vendor_invoice', 'Book the vendor invoice', 'Purchases', 'Vendor Invoices'),
    step('payment', 'Pay the vendor', 'Money', 'Cash & Parties'),
]

# Delivery: from project set-up to closeout.
PLAN_TO_EXECUTE = [
    step('project', 'Set up the project', 'Project Management', 'Projects'),
    step('programme', 'Baseline the programme', 'Project Management', 'Timeline'),
    step('lookahead', 'Plan the week (PPC)', 'Project Management', 'Look-ahead'),
    step('dpr', 'Log daily progress', 'Operations', 'Site Reports'),
    step('consumption', 'Reconcile consumption', 'Operations', 'Consumption'),
    step('quality', 'Pass the QC hold-points', 'Operations', 'Quality'),
    step('closeout', 'Close out & handover', 'Operations', 'Closeout'),
]

WORKFLOWS = {
    'bid_to_contract': BID_TO_CONTRACT,
    'contract_to_cash': CONTRACT_TO_CASH,
    'procure_to_pay': PROCURE_TO_PAY,
    'plan_to_execute': PLAN_TO_EXECUTE,
}


def get(name):
    """A workflow by name, or None."""
    return WORKFLOWS.get(name)


def _done(state, key):
    return bool((state or {}).get(key))


def next_step(workflow, state):
    """The first step not yet complete — the 'what's next'. None when the whole
    flow is done. Order matters: a later step is not 'next' while an earlier one
    is open, so the flow drives the user through in sequence."""
    for s in workflow or []:
        if not _done(state, s['key']):
            return s
    return None


def progress(workflow, state):
    """How far a flow has run: done/total, percent, whether complete, and the
    next step. ``pct`` is None for an empty flow (no basis), never a fake 0."""
    workflow = workflow or []
    total = len(workflow)
    done = sum(1 for s in workflow if _done(state, s['key']))
    return {
        'total': total,
        'done': done,
        'pct': round(done / total * 100.0, 1) if total else None,
        'complete': total > 0 and done == total,
        'next': next_step(workflow, state),
    }


def all_progress(state_by_flow=None):
    """Progress across every named workflow, given ``{flow_name: state}``.
    A flow with no state is simply 0% done — the honest starting point."""
    state_by_flow = state_by_flow or {}
    return {name: progress(wf, state_by_flow.get(name, {}))
            for name, wf in WORKFLOWS.items()}


def _catalog_locations(catalog=None):
    """The set of valid ``(section, tab)`` locations in the catalog."""
    catalog = catalog if catalog is not None else modules.SECTIONS_CATALOG
    return {(title, tab) for title, tabs in catalog for tab in tabs}


def unknown_locations(catalog=None):
    """Every workflow step whose (section, tab) is NOT a real menu location.

    Should always be empty — a test asserts it, so a renamed tab or a typo in a
    flow is caught at test time rather than sending a user nowhere."""
    valid = _catalog_locations(catalog)
    bad = []
    for name, wf in WORKFLOWS.items():
        for s in wf:
            if (s['section'], s['tab']) not in valid:
                bad.append((name, s['key'], s['section'], s['tab']))
    return bad
