"""Pure payment-to-bill allocation (Phase 8, Wave 1).

No tkinter, no database.

Until now a party's position was *billed minus received* — a lump comparison
that cannot answer the question a contractor actually asks: **which** bills are
still open. Ageing therefore had to guess, applying receipts oldest-first
(``ageing.apply_receipts_fifo``). That guess is usually right and occasionally
badly wrong: a client who pays the newest bill while disputing an old one looks,
under FIFO, like a client with no old debt at all.

This module lets a receipt be split across the specific bills it settles, and
computes the open position from those allocations.

The model is deliberately **hybrid**, because a contractor will allocate some
receipts and not others, and a half-migrated ledger must still add up:

1. every document is reduced by the amounts explicitly allocated to it; then
2. whatever receipts remain *unallocated* are applied FIFO to what is left.

So explicit allocation always wins where it exists, and the old behaviour is
the fallback rather than a contradiction. Allocate nothing and the numbers match
the previous release exactly; allocate everything and the ageing is fully
reconciled.
"""

import ageing


def money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def doc_key(doc_type, doc_id):
    """Stable identity for a billed document across tables."""
    return '{}:{}'.format(doc_type or '', doc_id)


def allocated_by_doc(allocations):
    """Sum allocations per document -> {doc_key: amount}."""
    out = {}
    for a in allocations or []:
        key = doc_key(a['doc_type'], a['doc_id'])
        out[key] = money(out.get(key, 0.0) + money(a['amount']))
    return out


def open_documents(documents, allocations):
    """Reduce each document by what has been explicitly allocated to it.

    ``documents`` are mappings with doc_type, doc_id, date, number, amount.
    Returns the same rows plus ``allocated`` and ``open``, dropping nothing —
    a fully settled document is returned with ``open`` of 0 so the caller can
    still show it if it wants.
    """
    by_doc = allocated_by_doc(allocations)
    out = []
    for d in documents or []:
        key = doc_key(d['doc_type'], d['doc_id'])
        amount = money(d['amount'])
        alloc = money(by_doc.get(key, 0.0))
        out.append({
            'doc_type': d['doc_type'],
            'doc_id': d['doc_id'],
            'date': d.get('date') or '',
            'number': d.get('number') or '',
            'amount': amount,
            'allocated': alloc,
            'open': money(max(amount - alloc, 0.0)),
        })
    return out


def unallocated_amount(payment_amount, allocations):
    """How much of a payment is not yet tied to a document (never negative)."""
    used = money(sum(money(a['amount']) for a in allocations or []))
    return money(max(money(payment_amount) - used, 0.0))


def validate(payment_amount, proposed):
    """Check a proposed allocation set. Returns (ok, message).

    Guards the two mistakes that corrupt a ledger: allocating more than the
    payment, and allocating more to a document than it is worth.
    """
    total = 0.0
    for row in proposed or []:
        amount = money(row.get('amount'))
        if amount < 0:
            return False, 'An allocation cannot be negative.'
        limit = row.get('open')
        if limit is not None and amount > money(limit) + 0.005:
            return False, ('Cannot allocate {:,.2f} to {} — only {:,.2f} is '
                           'open on it.'.format(amount, row.get('number') or
                                                'that document', money(limit)))
        total = money(total + amount)
    if total > money(payment_amount) + 0.005:
        return False, ('Allocated {:,.2f} but the payment is only {:,.2f}.'
                       .format(total, money(payment_amount)))
    return True, ''


def suggest_fifo(open_docs, amount):
    """Propose an allocation of ``amount`` across open docs, oldest first.

    Powers the "Auto (oldest first)" button — the sensible default, made
    explicit and editable rather than assumed silently as ageing used to.
    """
    remaining = money(amount)
    proposal = {}
    for d in sorted(open_docs or [],
                    key=lambda x: (str(x.get('date') or '9999-12-31'), x['doc_id'])):
        if remaining <= 0:
            break
        take = money(min(money(d['open']), remaining))
        if take <= 0:
            continue
        proposal[doc_key(d['doc_type'], d['doc_id'])] = take
        remaining = money(remaining - take)
    return proposal


def open_items_for_ageing(documents, allocations, unallocated_receipts=0):
    """``(date, open_amount)`` pairs for ageing, honouring real allocations.

    Explicit allocations are applied first; any receipts not tied to a document
    are then spread FIFO over what remains, so a partly-allocated ledger still
    reconciles to the same total.
    """
    docs = open_documents(documents, allocations)
    remaining_open = [(d['date'], d['open']) for d in docs if d['open'] > 0]
    if money(unallocated_receipts) <= 0:
        return remaining_open
    return ageing.apply_receipts_fifo(remaining_open, unallocated_receipts)


def party_position(documents, allocations, unallocated_receipts=0, as_on=None):
    """Full picture for one party: totals plus aged buckets."""
    docs = open_documents(documents, allocations)
    billed = money(sum(d['amount'] for d in docs))
    allocated = money(sum(d['allocated'] for d in docs))
    items = open_items_for_ageing(documents, allocations, unallocated_receipts)
    buckets = ageing.age_open_items(items, as_on)
    return {
        'billed': billed,
        'allocated': allocated,
        'unallocated_receipts': money(unallocated_receipts),
        'outstanding': buckets['total'],
        'buckets': buckets,
        'documents': docs,
    }
