"""Auto-posting engine (Phase 7): turn business documents into journal entries.

``post_all(conn)`` scans tax invoices, vendor invoices, and payments, and for
each one not already posted writes a balanced ``journal_entries`` +
``journal_lines`` set using the rules in ``posting.py``. It is **idempotent**:
a document is considered posted if a ``journal_entries`` row exists with its
``(source, source_id)``, so re-running only posts new documents.

DB-only (no tkinter), so it is testable with a real connection.

Not posted yet (see docs/ROADMAP.md Phase 7): running bills and RA bills — their
retention-withheld-by-client is an asset the seeded chart of accounts doesn't
model, so posting them naively would misstate retention.
"""

import posting


def _account_ids(conn):
    return {r['code']: r['id'] for r in conn.execute('SELECT id, code FROM accounts')}


def _already_posted(conn, source, source_id):
    return conn.execute(
        'SELECT 1 FROM journal_entries WHERE source = ? AND source_id = ?',
        (source, source_id)).fetchone() is not None


def _write_entry(conn, accounts, source, source_id, entry_date, narration,
                 reference, lines):
    total_debit = round(sum(l['debit'] for l in lines), 2)
    total_credit = round(sum(l['credit'] for l in lines), 2)
    cur = conn.execute(
        'INSERT INTO journal_entries (entry_date, narration, reference, source, '
        'source_id, total_debit, total_credit) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (entry_date, narration, reference, source, source_id, total_debit,
         total_credit))
    jid = cur.lastrowid
    for l in lines:
        aid = accounts.get(l['code'])
        if aid is None:
            continue  # account code missing from CoA — skip that line
        conn.execute(
            'INSERT INTO journal_lines (journal_entry_id, account_id, debit, '
            'credit, notes) VALUES (?, ?, ?, ?, ?)',
            (jid, aid, l['debit'], l['credit'], l['code']))
    return jid


def post_all(conn):
    """Post every not-yet-posted document. Returns the count of new entries."""
    accounts = _account_ids(conn)
    posted = 0

    for r in conn.execute(
            "SELECT * FROM tax_invoices WHERE status != 'Cancelled'"):
        if not (r['subtotal'] or 0) or _already_posted(conn, 'TaxInvoice', r['id']):
            continue
        lines = posting.tax_invoice_lines(r['subtotal'], r['tax_amount'],
                                          r['total_amount'])
        _write_entry(conn, accounts, 'TaxInvoice', r['id'], r['invoice_date'],
                     ('Sale ' + (r['invoice_no'] or '')).strip(),
                     r['invoice_no'], lines)
        posted += 1

    for r in conn.execute('SELECT * FROM vendor_invoices'):
        if not (r['subtotal'] or 0) or _already_posted(conn, 'VendorInvoice', r['id']):
            continue
        lines = posting.vendor_invoice_lines(r['subtotal'], r['tax_amount'],
                                             r['tds_amount'], r['net_payable'])
        _write_entry(conn, accounts, 'VendorInvoice', r['id'], r['invoice_date'],
                     ('Purchase ' + (r['invoice_no'] or '')).strip(),
                     r['invoice_no'], lines)
        posted += 1

    for r in conn.execute('SELECT * FROM payments'):
        if not (r['amount'] or 0) or _already_posted(conn, 'Payment', r['id']):
            continue
        lines = posting.payment_lines(r['direction'], r['party_type'],
                                      r['mode'], r['amount'])
        narration = '{} {}'.format(r['direction'], r['party_name'] or '').strip()
        _write_entry(conn, accounts, 'Payment', r['id'], r['pay_date'],
                     narration, r['ref_no'], lines)
        posted += 1

    # Paid payroll runs (the monthly-payroll path, distinct from muster ->
    # payments). Only 'Paid' rows post, so an unpaid draft doesn't hit the books.
    for r in conn.execute("SELECT * FROM payroll WHERE status = 'Paid'"):
        if not (r['net_amount'] or 0) or _already_posted(conn, 'Payroll', r['id']):
            continue
        lines = posting.payroll_lines(r['net_amount'])
        _write_entry(conn, accounts, 'Payroll', r['id'], r['generated_date'],
                     'Wages {}/{}'.format(r['month'] or '', r['year'] or ''),
                     None, lines)
        posted += 1

    conn.commit()
    return posted
