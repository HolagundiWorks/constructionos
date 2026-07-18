"""Pure double-entry posting rules (Phase 7).

Given a document's numbers, return the balanced journal lines it should post to
the default chart of accounts (see ``db.DEFAULT_ACCOUNTS``). No tkinter, no
database — the DB-touching engine lives in ``journal_post.py``.

Each line is ``{'code': <account code>, 'debit': x, 'credit': y}`` with exactly
one of debit/credit non-zero. Every function returns a set of lines whose
debits equal its credits.
"""

# Account codes from the seeded chart of accounts.
CASH = '1000'
BANK = '1010'
RECEIVABLE = '1100'
INPUT_GST = '1300'
PAYABLE = '2000'
GST_PAYABLE = '2100'
TDS_PAYABLE = '2200'
EQUITY = '3000'
REVENUE = '4000'
MATERIALS = '5000'
LABOUR = '5100'
OTHER_EXPENSE = '5900'


def _r(x):
    return round(float(x or 0), 2)


def _line(code, debit=0.0, credit=0.0):
    return {'code': code, 'debit': _r(debit), 'credit': _r(credit)}


def _nonzero(lines):
    return [l for l in lines if l['debit'] or l['credit']]


def mode_account(mode):
    """Cash goes to Cash; Bank/UPI/Cheque go to Bank."""
    return CASH if mode == 'Cash' else BANK


def tax_invoice_lines(subtotal, tax_amount, total_amount):
    """Outward sale: Dr Receivable; Cr Revenue + GST Payable."""
    return _nonzero([
        _line(RECEIVABLE, debit=total_amount),
        _line(REVENUE, credit=subtotal),
        _line(GST_PAYABLE, credit=tax_amount),
    ])


def vendor_invoice_lines(subtotal, tax_amount, tds_amount, net_payable):
    """Inward purchase: Dr Materials + Input GST; Cr TDS Payable + Payable."""
    return _nonzero([
        _line(MATERIALS, debit=subtotal),
        _line(INPUT_GST, debit=tax_amount),
        _line(TDS_PAYABLE, credit=tds_amount),
        _line(PAYABLE, credit=net_payable),
    ])


def payment_lines(direction, party_type, mode, amount):
    """Cash movement.

    Receipt: Dr Cash/Bank; Cr Receivable (from a client) or Equity (other).
    Payment: Cr Cash/Bank; Dr Payable (vendor) / Labour / Other Expense.
    """
    acct = mode_account(mode)
    if direction == 'Receipt':
        contra = RECEIVABLE if party_type == 'Client' else EQUITY
        return _nonzero([_line(acct, debit=amount), _line(contra, credit=amount)])
    if party_type == 'Vendor':
        dr = PAYABLE
    elif party_type == 'Labour':
        dr = LABOUR
    else:
        dr = OTHER_EXPENSE
    return _nonzero([_line(dr, debit=amount), _line(acct, credit=amount)])


def lines_balanced(lines, eps=0.01):
    return abs(sum(l['debit'] for l in lines) - sum(l['credit'] for l in lines)) <= eps
