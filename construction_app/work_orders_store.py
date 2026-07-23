"""Work orders + subcontractor bills — DB store over ``subcontract``.

No tkinter. Header+items for work orders; sub_bills use
``subcontract.sub_bill_totals`` so net payable stays derived.
"""

import subcontract


WO_STATUSES = ('Draft', 'Awarded', 'Running', 'Closed', 'Cancelled')
SUB_STATUSES = ('Draft', 'Approved', 'Paid')

_WO_FIELDS = (
    'wo_no', 'vendor_id', 'site_id', 'contract_id', 'wo_date',
    'description', 'retention_pct', 'tds_pct', 'status', 'notes',
)


def _f(v, default=0.0):
    try:
        return float(v if v is not None else default)
    except (TypeError, ValueError):
        return default


def _i(v):
    if v is None or v == '':
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def list_work_orders(conn):
    rows = []
    for r in conn.execute(
            'SELECT wo.*, v.name AS vendor, s.name AS site '
            'FROM work_orders wo '
            'LEFT JOIN vendors v ON v.id = wo.vendor_id '
            'LEFT JOIN sites s ON s.id = wo.site_id '
            'ORDER BY wo.id DESC'):
        rows.append(dict(r))
    return rows


def get_work_order(conn, wo_id):
    row = conn.execute(
        'SELECT wo.*, v.name AS vendor, s.name AS site '
        'FROM work_orders wo '
        'LEFT JOIN vendors v ON v.id = wo.vendor_id '
        'LEFT JOIN sites s ON s.id = wo.site_id '
        'WHERE wo.id = ?', (int(wo_id),)).fetchone()
    if row is None:
        return None
    items = [dict(r) for r in conn.execute(
        'SELECT * FROM work_order_items WHERE work_order_id = ? ORDER BY id',
        (int(wo_id),))]
    out = dict(row)
    out['items'] = items
    return out


def create_work_order(conn, header, items=None):
    """Insert a work order + line items. ``total_amount`` = sum of amounts."""
    header = dict(header or {})
    items = list(items or [])
    status = (header.get('status') or 'Draft').strip() or 'Draft'
    if status not in WO_STATUSES:
        status = 'Draft'
    lines = []
    total = 0.0
    for it in items:
        qty = _f(it.get('qty'))
        rate = _f(it.get('rate'))
        amount = round(qty * rate, 2)
        if it.get('amount') is not None and it.get('amount') != '':
            try:
                amount = round(float(it['amount']), 2)
            except (TypeError, ValueError):
                pass
        total += amount
        lines.append((
            str(it.get('item_no') or ''),
            str(it.get('description') or ''),
            str(it.get('unit') or ''),
            qty, rate, amount,
        ))
    cur = conn.execute(
        'INSERT INTO work_orders (wo_no, vendor_id, site_id, contract_id, '
        'wo_date, description, retention_pct, tds_pct, status, total_amount, '
        'notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        (
            str(header.get('wo_no') or ''),
            _i(header.get('vendor_id')),
            _i(header.get('site_id')),
            _i(header.get('contract_id')),
            str(header.get('wo_date') or ''),
            str(header.get('description') or ''),
            _f(header.get('retention_pct')),
            _f(header.get('tds_pct')),
            status,
            round(total, 2),
            str(header.get('notes') or ''),
        ))
    wo_id = cur.lastrowid
    if lines:
        conn.executemany(
            'INSERT INTO work_order_items (work_order_id, item_no, description, '
            'unit, qty, rate, amount) VALUES (?,?,?,?,?,?,?)',
            [(wo_id,) + ln for ln in lines])
    conn.commit()
    return get_work_order(conn, wo_id)


def update_work_order(conn, wo_id, header, items=None):
    """Update header fields; when ``items`` is a list, replace all lines."""
    wo_id = int(wo_id)
    existing = get_work_order(conn, wo_id)
    if existing is None:
        return None
    header = dict(header or {})
    status = header.get('status', existing.get('status')) or 'Draft'
    if status not in WO_STATUSES:
        status = existing.get('status') or 'Draft'
    fields = {
        'wo_no': str(header.get('wo_no', existing.get('wo_no') or '')),
        'vendor_id': _i(header['vendor_id']) if 'vendor_id' in header
        else existing.get('vendor_id'),
        'site_id': _i(header['site_id']) if 'site_id' in header
        else existing.get('site_id'),
        'contract_id': _i(header['contract_id']) if 'contract_id' in header
        else existing.get('contract_id'),
        'wo_date': str(header.get('wo_date', existing.get('wo_date') or '')),
        'description': str(header.get(
            'description', existing.get('description') or '')),
        'retention_pct': _f(header.get(
            'retention_pct', existing.get('retention_pct'))),
        'tds_pct': _f(header.get('tds_pct', existing.get('tds_pct'))),
        'status': status,
        'notes': str(header.get('notes', existing.get('notes') or '')),
    }
    total = existing.get('total_amount') or 0
    if items is not None:
        conn.execute('DELETE FROM work_order_items WHERE work_order_id = ?',
                     (wo_id,))
        total = 0.0
        for it in items:
            qty = _f(it.get('qty'))
            rate = _f(it.get('rate'))
            amount = round(qty * rate, 2)
            total += amount
            conn.execute(
                'INSERT INTO work_order_items (work_order_id, item_no, '
                'description, unit, qty, rate, amount) '
                'VALUES (?,?,?,?,?,?,?)',
                (wo_id, str(it.get('item_no') or ''),
                 str(it.get('description') or ''),
                 str(it.get('unit') or ''), qty, rate, amount))
    fields['total_amount'] = round(float(total), 2)
    conn.execute(
        'UPDATE work_orders SET wo_no=?, vendor_id=?, site_id=?, contract_id=?, '
        'wo_date=?, description=?, retention_pct=?, tds_pct=?, status=?, '
        'total_amount=?, notes=? WHERE id=?',
        (fields['wo_no'], fields['vendor_id'], fields['site_id'],
         fields['contract_id'], fields['wo_date'], fields['description'],
         fields['retention_pct'], fields['tds_pct'], fields['status'],
         fields['total_amount'], fields['notes'], wo_id))
    conn.commit()
    return get_work_order(conn, wo_id)


def delete_work_order(conn, wo_id):
    conn.execute('DELETE FROM work_orders WHERE id = ?', (int(wo_id),))
    conn.commit()
    return True


def previous_sub_value(conn, work_order_id, exclude_id=None):
    sql = ("SELECT COALESCE(SUM(this_bill_value), 0) AS v FROM sub_bills "
           "WHERE work_order_id = ? AND status IN ('Approved', 'Paid')")
    params = [int(work_order_id)]
    if exclude_id:
        sql += ' AND id != ?'
        params.append(int(exclude_id))
    return conn.execute(sql, params).fetchone()['v']


def list_sub_bills(conn, work_order_id=None):
    where, params = [], []
    if work_order_id:
        where.append('sb.work_order_id = ?')
        params.append(int(work_order_id))
    sql = ('SELECT sb.*, wo.wo_no, v.name AS vendor '
           'FROM sub_bills sb '
           'LEFT JOIN work_orders wo ON wo.id = sb.work_order_id '
           'LEFT JOIN vendors v ON v.id = wo.vendor_id')
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY sb.id DESC'
    return [dict(r) for r in conn.execute(sql, params)]


def get_sub_bill(conn, bill_id):
    row = conn.execute(
        'SELECT sb.*, wo.wo_no, v.name AS vendor '
        'FROM sub_bills sb '
        'LEFT JOIN work_orders wo ON wo.id = sb.work_order_id '
        'LEFT JOIN vendors v ON v.id = wo.vendor_id '
        'WHERE sb.id = ?', (int(bill_id),)).fetchone()
    return dict(row) if row else None


def create_sub_bill(conn, body):
    """Create a subcontractor bill; derived totals from ``sub_bill_totals``."""
    body = dict(body or {})
    wo_id = _i(body.get('work_order_id'))
    if not wo_id:
        raise ValueError('work_order_id is required')
    wo = get_work_order(conn, wo_id)
    if wo is None:
        raise ValueError('Work order not found')
    this_bill_value = _f(body.get('this_bill_value'))
    retention_pct = _f(body.get('retention_pct', wo.get('retention_pct')))
    tds_pct = _f(body.get('tds_pct', wo.get('tds_pct')))
    other = _f(body.get('other_deductions'))
    previous = previous_sub_value(conn, wo_id)
    totals = subcontract.sub_bill_totals(
        this_bill_value, previous, retention_pct, tds_pct, other)
    status = (body.get('status') or 'Draft').strip() or 'Draft'
    if status not in SUB_STATUSES:
        status = 'Draft'
    cur = conn.execute(
        'INSERT INTO sub_bills (work_order_id, bill_no, bill_date, status, '
        'this_bill_value, previous_value, cumulative_value, retention_pct, '
        'retention_amt, tds_pct, tds_amount, other_deductions, net_payable, '
        'remarks) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (wo_id, str(body.get('bill_no') or ''),
         str(body.get('bill_date') or ''), status,
         totals['this_bill_value'], totals['previous_value'],
         totals['cumulative_value'], retention_pct, totals['retention_amt'],
         tds_pct, totals['tds_amount'], other, totals['net_payable'],
         str(body.get('remarks') or '')))
    conn.commit()
    return get_sub_bill(conn, cur.lastrowid)


def update_sub_bill(conn, bill_id, body):
    existing = get_sub_bill(conn, bill_id)
    if existing is None:
        return None
    body = dict(body or {})
    wo_id = _i(body.get('work_order_id', existing.get('work_order_id')))
    this_bill_value = _f(body.get(
        'this_bill_value', existing.get('this_bill_value')))
    retention_pct = _f(body.get(
        'retention_pct', existing.get('retention_pct')))
    tds_pct = _f(body.get('tds_pct', existing.get('tds_pct')))
    other = _f(body.get(
        'other_deductions', existing.get('other_deductions')))
    previous = previous_sub_value(conn, wo_id, exclude_id=bill_id)
    # If status is already Approved/Paid, keep previous as stored unless
    # recalculating from other Approved/Paid siblings (exclude self).
    totals = subcontract.sub_bill_totals(
        this_bill_value, previous, retention_pct, tds_pct, other)
    status = body.get('status', existing.get('status')) or 'Draft'
    if status not in SUB_STATUSES:
        status = existing.get('status') or 'Draft'
    conn.execute(
        'UPDATE sub_bills SET work_order_id=?, bill_no=?, bill_date=?, status=?, '
        'this_bill_value=?, previous_value=?, cumulative_value=?, '
        'retention_pct=?, retention_amt=?, tds_pct=?, tds_amount=?, '
        'other_deductions=?, net_payable=?, remarks=? WHERE id=?',
        (wo_id, str(body.get('bill_no', existing.get('bill_no') or '')),
         str(body.get('bill_date', existing.get('bill_date') or '')), status,
         totals['this_bill_value'], totals['previous_value'],
         totals['cumulative_value'], retention_pct, totals['retention_amt'],
         tds_pct, totals['tds_amount'], other, totals['net_payable'],
         str(body.get('remarks', existing.get('remarks') or '')),
         int(bill_id)))
    conn.commit()
    return get_sub_bill(conn, bill_id)


def delete_sub_bill(conn, bill_id):
    conn.execute('DELETE FROM sub_bills WHERE id = ?', (int(bill_id),))
    conn.commit()
    return True
