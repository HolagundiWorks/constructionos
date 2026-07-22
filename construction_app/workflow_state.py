"""Infer workflow completion state from the books (E7.4 Process view).

DB bridge over ``workflow.py`` — tkinter-free. Each step key becomes True when
the related register has at least one row (or a stronger signal where obvious).
Honest and coarse: presence, not quality. Returns ``{flow_name: {step: bool}}``.
"""

import workflow


def _has(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return bool(row and row[0])


def infer(conn):
    """Derive a completion map for every named workflow from ``conn``."""
    bid = {
        'sourcing': (_has(conn, 'SELECT COUNT(*) FROM quotes')
                     or _has(conn, 'SELECT COUNT(*) FROM rfis')),
        'rate_analysis': _has(conn, 'SELECT COUNT(*) FROM rate_book'),
        'estimate': _has(conn, 'SELECT COUNT(*) FROM estimates'),
        'bid_decision': _has(conn, 'SELECT COUNT(*) FROM bid_assessments'),
        'quotation': _has(conn, 'SELECT COUNT(*) FROM quotations'),
        'contract': _has(conn, 'SELECT COUNT(*) FROM contracts'),
    }
    cash = {
        'contract': bid['contract'],
        'boq': _has(conn, 'SELECT COUNT(*) FROM boq_items'),
        'measurement': _has(conn, 'SELECT COUNT(*) FROM measurements'),
        'ra_bill': (_has(conn, 'SELECT COUNT(*) FROM ra_bills')
                    or _has(conn, 'SELECT COUNT(*) FROM bills')),
        'variations': _has(conn, 'SELECT COUNT(*) FROM variations'),
        'invoice': _has(conn, 'SELECT COUNT(*) FROM tax_invoices'),
        'receipt': _has(
            conn,
            "SELECT COUNT(*) FROM payments WHERE direction = 'Receipt'"),
        'retention': _has(conn, 'SELECT COUNT(*) FROM retention_releases'),
    }
    procure = {
        'requisition': _has(conn, 'SELECT COUNT(*) FROM material_requisitions'),
        'po': _has(conn, 'SELECT COUNT(*) FROM purchase_orders'),
        'grn': _has(conn, 'SELECT COUNT(*) FROM goods_receipts'),
        'vendor_invoice': _has(conn, 'SELECT COUNT(*) FROM vendor_invoices'),
        'payment': _has(
            conn,
            "SELECT COUNT(*) FROM payments WHERE direction = 'Payment'"),
    }
    plan = {
        'project': _has(conn, 'SELECT COUNT(*) FROM projects'),
        'programme': _has(conn, 'SELECT COUNT(*) FROM timeline_tasks'),
        'lookahead': _has(conn, 'SELECT COUNT(*) FROM commitments'),
        'dpr': (_has(conn, 'SELECT COUNT(*) FROM daily_progress')
                or _has(conn, 'SELECT COUNT(*) FROM work_done_entries')),
        'consumption': _has(conn, 'SELECT COUNT(*) FROM work_done_entries'),
        'quality': (_has(conn, 'SELECT COUNT(*) FROM inspections')
                    or _has(conn, 'SELECT COUNT(*) FROM ncrs')),
        'closeout': _has(conn, 'SELECT COUNT(*) FROM snags'),
    }
    return {
        'bid_to_contract': bid,
        'contract_to_cash': cash,
        'procure_to_pay': procure,
        'plan_to_execute': plan,
    }


def progress_report(conn):
    """``workflow.all_progress`` over the inferred book state."""
    return workflow.all_progress(infer(conn))
