"""Auto-posting engine (Phase 7): turn business documents into journal entries.

``post_all(conn)`` scans every posting source — tax invoices, vendor invoices,
payments, subcontractor bills, payroll runs, and **running / RA bills** — and
for each one not already posted writes a balanced ``journal_entries`` +
``journal_lines`` set using the rules in ``posting.py``. It is **idempotent**:
a document is considered posted if a ``journal_entries`` row exists with its
``(source, source_id)``, so re-running only posts new documents.

DB-only (no tkinter), so it is testable with a real connection.

Running/RA bills post the client-withheld retention to **Retention Receivable**
(code 1400), an asset recovered on release rather than a loss. That account is
newer than the original seeded chart, so ``_ensure_accounts`` creates any
missing posting account before use — without it ``_write_entry`` would silently
drop the line and write an unbalanced entry on databases created earlier.
"""

import posting


def _account_ids(conn):
    return {r['code']: r['id'] for r in conn.execute('SELECT id, code FROM accounts')}


# Accounts the posting rules rely on. Databases created before an account was
# introduced won't have it, and a missing code is silently skipped by
# _write_entry, so make sure they all exist before posting.
_REQUIRED_ACCOUNTS = [
    (posting.RETENTION_RECEIVABLE, 'Retention Receivable', 'Asset'),
]


def _ensure_accounts(conn):
    """Create any posting account missing from this database's chart."""
    have = {r['code'] for r in conn.execute('SELECT code FROM accounts')}
    added = [(c, n, t) for c, n, t in _REQUIRED_ACCOUNTS if c not in have]
    if added:
        conn.executemany(
            'INSERT INTO accounts (code, name, type) VALUES (?, ?, ?)', added)
        conn.commit()
    return len(added)


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
    _ensure_accounts(conn)
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

    # Subcontractor running bills (Approved/Paid). Dr Subcontractor Charges;
    # Cr Retention Payable + TDS Payable + Payable.
    for r in conn.execute(
            "SELECT * FROM sub_bills WHERE status IN ('Approved','Paid')"):
        if not (r['this_bill_value'] or 0) or _already_posted(conn, 'SubBill', r['id']):
            continue
        lines = posting.sub_bill_lines(
            r['this_bill_value'], r['retention_amt'], r['tds_amount'],
            r['other_deductions'], r['net_payable'])
        _write_entry(conn, accounts, 'SubBill', r['id'], r['bill_date'],
                     ('Sub bill ' + (r['bill_no'] or '')).strip(), r['bill_no'],
                     lines)
        posted += 1

    # Measurement-driven RA bills (Approved/Paid), our outward side: the work
    # value is revenue, split into what the client pays now, what they retain,
    # and what they otherwise deducted.
    for r in conn.execute(
            "SELECT * FROM ra_bills WHERE status IN ('Approved','Paid')"):
        if not (r['this_bill_value'] or 0) or _already_posted(conn, 'RABill', r['id']):
            continue
        lines = posting.ra_bill_lines(
            r['this_bill_value'], r['retention_amt'], r['other_deductions'],
            r['net_payable'])
        _write_entry(conn, accounts, 'RABill', r['id'], r['bill_date'],
                     ('RA bill ' + (r['bill_no'] or '')).strip(), r['bill_no'],
                     lines)
        posted += 1

    # Generic running bills (Approved/Paid). Their work_done_value is
    # cumulative, so the value *this* bill adds is net of what was already
    # billed — otherwise every bill would re-post the whole contract to date.
    for r in conn.execute(
            "SELECT * FROM bills WHERE status IN ('Approved','Paid')"):
        this_value = round((r['work_done_value'] or 0)
                           - (r['previous_billed'] or 0), 2)
        if this_value <= 0 or _already_posted(conn, 'Bill', r['id']):
            continue
        lines = posting.ra_bill_lines(
            this_value, r['retention_amt'], r['other_deductions'],
            r['net_payable'])
        _write_entry(conn, accounts, 'Bill', r['id'], r['bill_date'],
                     ('Running bill ' + (r['bill_no'] or '')).strip(),
                     r['bill_no'], lines)
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
