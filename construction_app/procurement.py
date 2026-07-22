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


def narrate_match(match, po_label=None):
    """One plain-language sentence for a three-way match row.

    Explains *why* a flag matters — over-invoiced is money about to leave for
    goods that never arrived; under-received is stock still in transit.
    """
    if not match:
        return ''
    label = po_label or 'This PO'
    status = match.get('status')
    over = match.get('over_invoiced') or 0
    pending_r = match.get('pending_receipt') or 0
    pending_i = match.get('pending_invoice') or 0
    if status == OVER_INVOICED or over > 0:
        return ('{} is over-invoiced by ₹{:,.0f} — billed beyond what was '
                'received; hold payment until the GRN catches up.'.format(
                    label, over))
    if status in (PART_RECEIVED, NOT_RECEIVED, OVER_RECEIVED) or (
            pending_r and pending_r > 0 and match.get('invoiced', 0) > 0):
        return ('{} still has ₹{:,.0f} of ordered value not yet received — '
                'do not treat the invoice as fully matched.'.format(
                    label, pending_r or match.get('ordered', 0)))
    if pending_i and pending_i > 0:
        return ('{} has ₹{:,.0f} received but not yet invoiced — chase the '
                'vendor bill or book a GRN-only accrual.'.format(
                    label, pending_i))
    if match.get('ok'):
        return ('{} matches within tolerance — ordered, received and invoiced '
                'line up.'.format(label))
    return '{} needs a closer look (status: {}).'.format(
        label, status or 'unknown')


def narrate_summary(summary):
    """Firm-level three-way narration from ``summarise`` output."""
    if not summary or not summary.get('total_count'):
        return 'No purchase orders to match yet.'
    lines = []
    at_risk = summary.get('at_risk') or 0
    problems = summary.get('problem_count') or 0
    if at_risk > 0:
        lines.append(
            '₹{:,.0f} is over-invoiced across {} problem PO(s) — value billed '
            'with no receipt behind it.'.format(at_risk, problems))
    elif problems:
        lines.append(
            '{} PO(s) are outside tolerance but nothing is over-invoiced yet.'
            .format(problems))
    else:
        lines.append(
            'All {} PO(s) match within tolerance.'.format(
                summary.get('total_count')))
    awaiting = summary.get('awaiting_delivery') or 0
    if awaiting > 0:
        lines.append('₹{:,.0f} still awaits delivery.'.format(awaiting))
    unbilled = summary.get('received_not_invoiced') or 0
    if unbilled > 0:
        lines.append('₹{:,.0f} received is not yet invoiced.'.format(unbilled))
    return ' '.join(lines)


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
