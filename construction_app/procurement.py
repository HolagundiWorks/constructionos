"""Pure procurement-control maths: receipt and three-way match (Phase 8, Wave 2).

No tkinter, no database.

Today material arrives, someone types it into the stock ledger, and later an
invoice is paid. Nothing connects the three, so the classic leak is invisible:
**being invoiced for more than was actually delivered**. The SOP answer is a
goods-receipt note — the gate at the gate — and a three-way match:

    ordered (PO)  ->  received (GRN)  ->  invoiced (vendor invoice)

The number that protects money is ``over_invoiced``: value billed beyond what
was receipted. A short delivery is a nuisance; an over-invoice is a payment
about to leave for goods that never arrived.

Quantities and values are compared with an explicit **tolerance**, because
deliveries of sand, aggregate and steel never tally to the gram, and a match
report that cries wolf on every line gets ignored.
"""

import finance

MATCHED = 'Matched'
OVER_INVOICED = 'Over-invoiced'
OVER_RECEIVED = 'Over-received'
PART_RECEIVED = 'Partly received'
NOT_RECEIVED = 'Not received'
NOT_INVOICED = 'Not invoiced'


def money(value):
    return finance.money(value)


def accepted_qty(qty_received, qty_rejected=0):
    """What actually enters stock. Rejected material never becomes stock."""
    received = float(qty_received or 0)
    rejected = float(qty_rejected or 0)
    return round(max(received - rejected, 0.0), 3)


def line_amount(qty, rate):
    return money(float(qty or 0) * float(rate or 0))


def receipt_status(ordered_value, received_value, tolerance=0.0):
    """How far a PO has been delivered."""
    ordered = money(ordered_value)
    received = money(received_value)
    tol = money(tolerance)
    if received <= tol:
        return NOT_RECEIVED
    if received > ordered + tol:
        return OVER_RECEIVED
    if received < ordered - tol:
        return PART_RECEIVED
    return MATCHED


def three_way(ordered_value, received_value, invoiced_value, tolerance=0.0):
    """Compare PO, GRN and invoice values for one purchase order.

    ``status`` names the worst problem found, worst first: being invoiced for
    undelivered goods outranks an over-delivery, which outranks a part
    delivery. ``over_invoiced`` is the amount at risk — what would be paid for
    goods with no receipt behind them.
    """
    ordered = money(ordered_value)
    received = money(received_value)
    invoiced = money(invoiced_value)
    tol = money(tolerance)

    over_invoiced = money(max(invoiced - received, 0.0))
    over_received = money(max(received - ordered, 0.0))
    pending_receipt = money(max(ordered - received, 0.0))
    pending_invoice = money(max(received - invoiced, 0.0))

    if over_invoiced > tol:
        status = OVER_INVOICED
    elif over_received > tol:
        status = OVER_RECEIVED
    elif received <= tol:
        status = NOT_RECEIVED
    elif pending_receipt > tol:
        status = PART_RECEIVED
    elif invoiced <= tol:
        status = NOT_INVOICED
    else:
        status = MATCHED

    return {
        'ordered': ordered,
        'received': received,
        'invoiced': invoiced,
        'over_invoiced': over_invoiced,
        'over_received': over_received,
        'pending_receipt': pending_receipt,
        'pending_invoice': pending_invoice,
        'status': status,
        'ok': status in (MATCHED, NOT_INVOICED),
    }


def summarise(matches):
    """Roll up three-way results — the headline is total value at risk."""
    at_risk = money(sum(m['over_invoiced'] for m in matches or []))
    awaiting = money(sum(m['pending_receipt'] for m in matches or []))
    unbilled = money(sum(m['pending_invoice'] for m in matches or []))
    problems = [m for m in matches or [] if not m['ok']]
    return {
        'at_risk': at_risk,
        'awaiting_delivery': awaiting,
        'received_not_invoiced': unbilled,
        'problem_count': len(problems),
        'total_count': len(matches or []),
    }


def next_doc_no(existing, prefix):
    """Next serial in a document series ('GRN-4'), from the highest existing.

    Max-based rather than count-based so deleting a note cannot reissue its
    number — the same rule used for invoices and variations.
    """
    top = 0
    for value in existing or []:
        text = str(value or '').strip()
        if not text.upper().startswith(prefix.upper() + '-'):
            continue
        tail = text.split('-', 1)[1].strip()
        if tail.isdigit():
            top = max(top, int(tail))
    return '{}-{}'.format(prefix, top + 1)
