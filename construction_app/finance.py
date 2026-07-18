"""Pure finance/accounting helpers for the Indian construction context.

Everything here is a plain function with no tkinter and no database — GST
splitting, TDS, invoice roll-ups, PO/invoice reconciliation, and the
double-entry balance check. Kept separate so the tax and accounting maths can
be unit-tested and exercised with ``python -c``.

Money is REAL (float) throughout the app; these helpers round to 2 decimals at
their boundaries to keep displayed totals tidy, but callers should still avoid
equality comparisons on floats (use the ``eps`` in ``is_balanced``).
"""


def money(value):
    """Coerce to float and round to 2 decimals; None/blank -> 0.0."""
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def split_gst(taxable, gst_pct, interstate=False):
    """Split GST on a taxable amount into CGST/SGST (intra-state) or IGST.

    Intra-state supply splits the rate half-and-half into CGST + SGST;
    inter-state supply is a single IGST at the full rate.
    Returns a dict with cgst, sgst, igst, total_tax (all rounded).
    """
    taxable = money(taxable)
    rate = float(gst_pct or 0)
    total_tax = money(taxable * rate / 100.0)
    if interstate:
        return {'cgst': 0.0, 'sgst': 0.0, 'igst': total_tax,
                'total_tax': total_tax}
    half = money(total_tax / 2.0)
    # Put any rounding remainder on SGST so cgst+sgst == total_tax exactly.
    return {'cgst': half, 'sgst': money(total_tax - half), 'igst': 0.0,
            'total_tax': total_tax}


def compute_tds(taxable, tds_pct):
    """TDS is deducted on the taxable (pre-GST) base and withheld from payment."""
    return money(money(taxable) * float(tds_pct or 0) / 100.0)


def invoice_totals(subtotal, gst_pct, tds_pct=0, interstate=False):
    """Roll a vendor invoice's line-item subtotal up to full tax figures.

        tax_amount   = GST on subtotal (CGST+SGST or IGST)
        total_amount = subtotal + tax_amount          (invoice gross value)
        tds_amount   = TDS on subtotal (pre-GST base)
        net_payable  = total_amount - tds_amount      (paid to the vendor)
    """
    subtotal = money(subtotal)
    gst = split_gst(subtotal, gst_pct, interstate)
    tds = compute_tds(subtotal, tds_pct)
    total = money(subtotal + gst['total_tax'])
    return {
        'subtotal': subtotal,
        'cgst': gst['cgst'], 'sgst': gst['sgst'], 'igst': gst['igst'],
        'tax_amount': gst['total_tax'],
        'tds_amount': tds,
        'total_amount': total,
        'net_payable': money(total - tds),
    }


def reconcile(po_subtotal, invoice_subtotal, tolerance=0.0):
    """Compare a vendor invoice's subtotal against its linked PO subtotal.

    ``tolerance`` is an absolute amount within which a variance is treated as a
    match. Returns variance, variance_pct, within_tolerance, and a status of
    'Matched' / 'Over-billed' / 'Under-billed' / 'No PO'.
    """
    if po_subtotal is None:
        return {'variance': money(invoice_subtotal), 'variance_pct': None,
                'within_tolerance': False, 'status': 'No PO'}
    po = money(po_subtotal)
    inv = money(invoice_subtotal)
    variance = money(inv - po)
    variance_pct = round((variance / po) * 100.0, 2) if po else None
    if abs(variance) <= abs(tolerance):
        status = 'Matched'
    elif variance > 0:
        status = 'Over-billed'
    else:
        status = 'Under-billed'
    return {'variance': variance, 'variance_pct': variance_pct,
            'within_tolerance': abs(variance) <= abs(tolerance),
            'status': status}


# ------------------------------------------------------------- double-entry
NORMAL_DEBIT = ('Asset', 'Expense')
NORMAL_CREDIT = ('Liability', 'Income', 'Equity')


def is_balanced(total_debit, total_credit, eps=0.01):
    """A journal entry is valid only when debits equal credits."""
    return abs(money(total_debit) - money(total_credit)) <= eps


def account_net(debit_total, credit_total, acc_type):
    """Signed balance in the account's *normal* direction.

    For asset/expense accounts a positive result is a debit balance; for
    liability/income/equity a positive result is a credit balance.
    """
    debit_total = money(debit_total)
    credit_total = money(credit_total)
    if acc_type in NORMAL_CREDIT:
        return money(credit_total - debit_total)
    return money(debit_total - credit_total)


def gst_summary(output_tax, input_tax):
    """Net GST position for a period (a simplified GSTR-3B view).

    output_tax = GST collected on sales (tax invoices); input_tax = GST paid on
    purchases (vendor invoices, available as input credit). If output exceeds
    input the difference is payable; otherwise the surplus credit carries
    forward.
    """
    output_tax = money(output_tax)
    input_tax = money(input_tax)
    net = money(output_tax - input_tax)
    return {
        'output_tax': output_tax,
        'input_tax': input_tax,
        'net_payable': net if net > 0 else 0.0,
        'credit_carried': money(-net) if net < 0 else 0.0,
    }
