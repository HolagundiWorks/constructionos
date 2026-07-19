"""Pure approval-gate maths (Phase 8, Wave 3).

No tkinter, no database.

The app already has status words — Draft, Submitted, Approved — but anyone can
change one and nothing records **who** did it or **when**. For a document that
authorises spending or claims money, that is a status, not an approval.

So this is about accountability, not workflow. Deliberately a **single step**
with an approver and a timestamp: the SOP report lists corporate multi-level
approval chains as an explicit non-goal, because a solo contractor who is also
the approver gains nothing from routing a purchase order to themselves twice.

What each approvable document means:

* **Estimate** — reviewed before it goes to the client.
* **Purchase order** — authorised before anything is ordered.
* **Bill / RA bill** — certified before it counts as money owed to us.
* **Subcontractor bill** — certified before it counts as money we owe.
* **Variation** — agreed before the extra work is treated as revenue.
"""

import finance

APPROVED = 'Approved'
REJECTED = 'Rejected'
PENDING = 'Pending'

# doc_type -> (table, id column, status column, statuses that mean "waiting",
#              status to set on approval, human label)
APPROVABLE = {
    'Estimate': ('estimates', 'est_number', 'status', ('Draft',), 'Approved',
                 'Estimate'),
    'PurchaseOrder': ('purchase_orders', 'po_no', 'status', ('Draft',), 'Sent',
                      'Purchase order'),
    'Bill': ('bills', 'bill_no', 'status', ('Draft', 'Submitted'), 'Approved',
             'Running bill'),
    'RABill': ('ra_bills', 'bill_no', 'status', ('Draft', 'Submitted'),
               'Approved', 'RA bill'),
    'SubBill': ('sub_bills', 'bill_no', 'status', ('Draft',), 'Approved',
                'Subcontractor bill'),
    'Variation': ('variations', 'var_no', 'status', ('Raised',), 'Approved',
                  'Variation'),
}


def money(value):
    return finance.money(value)


def latest_by_doc(approvals):
    """Most recent approval per document -> {(doc_type, doc_id): row}.

    Rows are assumed to carry ``approved_at``; the newest wins, so a document
    rejected and later approved reads as approved.
    """
    out = {}
    for a in approvals or []:
        key = (a['doc_type'], a['doc_id'])
        prev = out.get(key)
        if prev is None or str(a['approved_at'] or '') >= str(prev['approved_at'] or ''):
            out[key] = a
    return out


def status_for(doc_type, doc_id, approvals_index):
    """Approval state of one document: Approved, Rejected, or Pending."""
    row = approvals_index.get((doc_type, doc_id))
    if row is None:
        return PENDING
    return (row['action'] or '').strip() or PENDING


def is_approved(doc_type, doc_id, approvals_index):
    return status_for(doc_type, doc_id, approvals_index) == APPROVED


def summarise(pending_rows):
    """Roll up what is waiting: count and value, and the largest single item.

    Value matters more than count — twenty small purchase orders waiting is a
    nuisance, one unapproved bill for a month's work is a problem.
    """
    total = money(sum(money(r.get('amount')) for r in pending_rows or []))
    by_type = {}
    for r in pending_rows or []:
        label = r.get('label') or r.get('doc_type') or '?'
        entry = by_type.setdefault(label, {'count': 0, 'amount': 0.0})
        entry['count'] += 1
        entry['amount'] = money(entry['amount'] + money(r.get('amount')))
    largest = max((money(r.get('amount')) for r in pending_rows or []),
                  default=0.0)
    return {
        'count': len(pending_rows or []),
        'amount': total,
        'largest': largest,
        'by_type': by_type,
    }
