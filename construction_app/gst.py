"""GST & TDS summaries — pure, tkinter-free.

Computed reports over data the app already captures: outward GST from
``tax_invoices`` (+ works-contract RA / running bills), input GST and TDS from
``vendor_invoices``. Each view filters by month (``YYYY-MM``; blank = all).
GST breakups are recomputed from the stored subtotal + rate + inter-state flag
via ``finance.split_gst`` so they always reconcile.

Used by the desktop ``tab_gst``, the browser ``/gst`` view, and ``GET /api/gst``.
"""

import finance


def _fmt(v):
    return '{:,.2f}'.format(float(v or 0))


def _month_clause(col, month):
    return (' WHERE substr({}, 1, 7) = ?'.format(col), [month]) if month else ('', [])


def _works_gst_pct(conn):
    """Configured works-contract GST rate for RA / running bills (default 18)."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'works_gst_pct'").fetchone()
    try:
        return float(row['value']) if row and row['value'] else 18.0
    except (TypeError, ValueError):
        return 18.0


def outward(conn, month):
    """Sales / output GST -> (rows, totals).

    Outward supply is any of: GST tax invoices (their own rate/split), plus
    RA bills and running bills treated as works-contract supply and taxed at
    the configured ``works_gst_pct`` (intra-state CGST+SGST). A Source column
    distinguishes them so a contractor who bills only via RA bills sees them,
    and one who raises a separate tax invoice can avoid double counting.
    """
    tot = {'taxable': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0, 'total': 0.0}
    rows = []

    def add(source, no, dt, party, taxable, gst_pct, interstate, total=None):
        g = finance.split_gst(taxable, gst_pct, interstate)
        total = (taxable or 0) + g['total_tax'] if total is None else total
        rows.append((source, no or '-', dt or '', party or '-', _fmt(taxable),
                     _fmt(g['cgst']), _fmt(g['sgst']), _fmt(g['igst']), _fmt(total)))
        tot['taxable'] += taxable or 0
        tot['cgst'] += g['cgst']
        tot['sgst'] += g['sgst']
        tot['igst'] += g['igst']
        tot['total'] += total or 0

    where, params = _month_clause('ti.invoice_date', month)
    for r in conn.execute(
            "SELECT ti.invoice_no, ti.invoice_date, c.name AS party, ti.subtotal, "
            "ti.gst_pct, ti.interstate, ti.total_amount FROM tax_invoices ti "
            "LEFT JOIN clients c ON c.id = ti.client_id" + where
            + " ORDER BY ti.invoice_date, ti.id", params):
        add('Tax Invoice', r['invoice_no'], r['invoice_date'], r['party'],
            r['subtotal'], r['gst_pct'], bool(r['interstate']), r['total_amount'])

    works_pct = _works_gst_pct(conn)
    where, params = _month_clause('r.bill_date', month)
    for r in conn.execute(
            "SELECT r.bill_no, r.bill_date, cl.name AS party, r.this_bill_value "
            "FROM ra_bills r LEFT JOIN contracts c ON c.id = r.contract_id "
            "LEFT JOIN clients cl ON cl.id = c.client_id "
            "WHERE r.status IN ('Approved','Paid')"
            + (where.replace(' WHERE', ' AND') if where else '')
            + " ORDER BY r.bill_date, r.id", params):
        add('RA Bill', r['bill_no'], r['bill_date'], r['party'],
            r['this_bill_value'], works_pct, False)

    where, params = _month_clause('b.bill_date', month)
    for r in conn.execute(
            "SELECT b.bill_no, b.bill_date, cl.name AS party, b.work_done_value "
            "FROM bills b LEFT JOIN contracts c ON c.id = b.contract_id "
            "LEFT JOIN clients cl ON cl.id = c.client_id "
            "WHERE b.status IN ('Approved','Paid')"
            + (where.replace(' WHERE', ' AND') if where else '')
            + " ORDER BY b.bill_date, b.id", params):
        add('Running Bill', r['bill_no'], r['bill_date'], r['party'],
            r['work_done_value'], works_pct, False)

    return rows, tot


def hsn_summary(conn, month):
    """HSN/SAC-wise summary of outward tax-invoice supplies -> (rows, totals)."""
    where, params = _month_clause('ti.invoice_date', month)
    acc = {}   # hsn -> {taxable, cgst, sgst, igst}
    for r in conn.execute(
            "SELECT COALESCE(NULLIF(it.hsn_code,''),'(none)') AS hsn, it.amount, "
            "ti.gst_pct, ti.interstate FROM tax_invoice_items it "
            "JOIN tax_invoices ti ON ti.id = it.tax_invoice_id" + where, params):
        g = finance.split_gst(r['amount'], r['gst_pct'], bool(r['interstate']))
        a = acc.setdefault(r['hsn'], {'taxable': 0.0, 'cgst': 0.0, 'sgst': 0.0,
                                      'igst': 0.0})
        a['taxable'] += r['amount'] or 0
        a['cgst'] += g['cgst']
        a['sgst'] += g['sgst']
        a['igst'] += g['igst']
    tot = {'taxable': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0}
    rows = []
    for hsn in sorted(acc):
        a = acc[hsn]
        tax = a['cgst'] + a['sgst'] + a['igst']
        rows.append((hsn, _fmt(a['taxable']), _fmt(a['cgst']), _fmt(a['sgst']),
                     _fmt(a['igst']), _fmt(tax)))
        for k in tot:
            tot[k] += a[k]
    return rows, tot


def inward(conn, month):
    """Purchases / input GST from vendor invoices -> (rows, totals)."""
    where, params = _month_clause('vi.invoice_date', month)
    rows, tot = [], {'taxable': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0, 'total': 0.0}
    sql = ("SELECT vi.invoice_no, vi.invoice_date, v.name AS party, "
           "vi.subtotal, vi.gst_pct, vi.interstate, vi.total_amount "
           "FROM vendor_invoices vi LEFT JOIN vendors v ON v.id = vi.vendor_id"
           + where + " ORDER BY vi.invoice_date, vi.id")
    for r in conn.execute(sql, params):
        g = finance.split_gst(r['subtotal'], r['gst_pct'], bool(r['interstate']))
        rows.append((r['invoice_no'] or '-', r['invoice_date'] or '',
                     r['party'] or '-', _fmt(r['subtotal']), _fmt(g['cgst']),
                     _fmt(g['sgst']), _fmt(g['igst']), _fmt(r['total_amount'])))
        tot['taxable'] += r['subtotal'] or 0
        tot['cgst'] += g['cgst']
        tot['sgst'] += g['sgst']
        tot['igst'] += g['igst']
        tot['total'] += r['total_amount'] or 0
    return rows, tot


def tds_register(conn, month):
    """TDS deducted on vendor invoices -> (rows, total_tds)."""
    where, params = _month_clause('vi.invoice_date', month)
    rows, total = [], 0.0
    sql = ("SELECT vi.invoice_no, vi.invoice_date, v.name AS party, "
           "vi.subtotal, vi.tds_pct, vi.tds_amount "
           "FROM vendor_invoices vi LEFT JOIN vendors v ON v.id = vi.vendor_id"
           + where + " ORDER BY vi.invoice_date, vi.id")
    for r in conn.execute(sql, params):
        if not (r['tds_amount'] or 0):
            continue
        rows.append((r['invoice_no'] or '-', r['invoice_date'] or '',
                     r['party'] or '-', _fmt(r['subtotal']),
                     '{:.2f}%'.format(r['tds_pct'] or 0), _fmt(r['tds_amount'])))
        total += r['tds_amount'] or 0
    return rows, total
