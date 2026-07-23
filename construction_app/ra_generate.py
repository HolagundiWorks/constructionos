"""Measurement-driven RA bill generation — pure store over ``civil``.

Extracted from the desktop ``tab_boq_ra.generate`` so the JSON API and GUI
share one write path. No tkinter.
"""

import civil


def generate(conn, contract_id, bill_date='', retention_pct=0, tds_pct=0,
             cess_pct=0, other_deductions=0):
    """Snapshot MB quantities into a Draft RA bill. Returns the new bill dict.

    Raises ``ValueError`` with a plain-language message when the contract has
    no BOQ. ``bill_date`` filters measurements (``mb_date <= bill_date``);
    blank means include all measurements.
    """
    cid = int(contract_id)
    try:
        retention_pct = float(retention_pct or 0)
        tds_pct = float(tds_pct or 0)
        cess_pct = float(cess_pct or 0)
        other_deductions = float(other_deductions or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            'retention, TDS, cess and deductions must be numbers') from exc

    bill_date = (bill_date or '').strip()
    boq = conn.execute(
        'SELECT id, rate FROM boq_items WHERE contract_id = ?', (cid,)
    ).fetchall()
    if not boq:
        raise ValueError('This contract has no BOQ items')

    lines = []
    for b in boq:
        upto = conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS q FROM measurements "
            "WHERE boq_item_id = ? AND (mb_date <= ? OR mb_date IS NULL "
            "OR mb_date = '')",
            (b['id'], bill_date or '9999-12-31')).fetchone()['q']
        previous = conn.execute(
            "SELECT COALESCE(SUM(ri.current_qty), 0) AS q "
            "FROM ra_bill_items ri JOIN ra_bills rb ON rb.id = ri.ra_bill_id "
            "WHERE ri.boq_item_id = ? AND rb.status IN ('Approved', 'Paid')",
            (b['id'],)).fetchone()['q']
        current, amount = civil.ra_current(upto, previous, b['rate'])
        lines.append((b['id'], upto, previous, current, b['rate'], amount))

    this_bill_value = round(sum(ln[5] for ln in lines), 2)
    previous_value = conn.execute(
        "SELECT COALESCE(SUM(this_bill_value), 0) AS v FROM ra_bills "
        "WHERE contract_id = ? AND status IN ('Approved', 'Paid')",
        (cid,)).fetchone()['v']
    totals = civil.ra_bill_totals(
        this_bill_value, previous_value, retention_pct, other_deductions,
        tds_pct=tds_pct, cess_pct=cess_pct)
    count = conn.execute(
        'SELECT COUNT(*) AS c FROM ra_bills WHERE contract_id = ?',
        (cid,)).fetchone()['c']
    bill_no = 'RA-{}'.format(count + 1)

    cur = conn.execute(
        'INSERT INTO ra_bills (contract_id, bill_no, bill_date, status, '
        'this_bill_value, previous_value, cumulative_value, retention_pct, '
        'retention_amt, tds_pct, tds_amt, cess_pct, cess_amt, '
        'other_deductions, net_payable) '
        "VALUES (?, ?, ?, 'Draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (cid, bill_no, bill_date, totals['this_bill_value'],
         totals['previous_value'], totals['cumulative_value'],
         retention_pct, totals['retention_amt'],
         tds_pct, totals['tds_amt'], cess_pct, totals['cess_amt'],
         other_deductions, totals['net_payable']))
    ra_id = cur.lastrowid
    conn.executemany(
        'INSERT INTO ra_bill_items (ra_bill_id, boq_item_id, upto_qty, '
        'previous_qty, current_qty, rate, current_amount) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        [(ra_id,) + ln for ln in lines])
    conn.commit()

    row = conn.execute('SELECT * FROM ra_bills WHERE id = ?',
                       (ra_id,)).fetchone()
    items = [dict(r) for r in conn.execute(
        'SELECT * FROM ra_bill_items WHERE ra_bill_id = ? ORDER BY id',
        (ra_id,)).fetchall()]
    return {
        'id': ra_id,
        'bill_no': bill_no,
        'bill': dict(row) if row else None,
        'items': items,
        'totals': totals,
        'line_count': len(lines),
    }
