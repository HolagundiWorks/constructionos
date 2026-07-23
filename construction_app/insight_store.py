"""Insight analytics — site profit, outstanding, contract progress, material.

Pure DB assembly over ``money`` / ``analytics`` / ``ageing``. No tkinter.
Companion to ``kpi_store`` so Key Numbers and Insight stay split for WinUI.
"""

import analytics
import money as m


def _sum_map(conn, sql, params=()):
    return {r[0]: (r[1] or 0) for r in conn.execute(sql, params)}


def site_profitability(conn):
    rev_bills = _sum_map(conn,
        "SELECT c.site_id, SUM(b.net_payable) FROM bills b "
        "JOIN contracts c ON c.id = b.contract_id "
        "WHERE b.status IN ('Approved','Paid') GROUP BY c.site_id")
    rev_ra = _sum_map(conn,
        "SELECT c.site_id, SUM(r.net_payable) FROM ra_bills r "
        "JOIN contracts c ON c.id = r.contract_id "
        "WHERE r.status IN ('Approved','Paid') GROUP BY c.site_id")
    material = _sum_map(conn,
        "SELECT site_id, SUM(qty * rate) FROM material_ledger "
        "WHERE txn_type = 'OUT' GROUP BY site_id")
    labour = _sum_map(conn,
        "SELECT site_id, SUM(amount) FROM payments "
        "WHERE direction = 'Payment' AND party_type = 'Labour' GROUP BY site_id")
    hire = _sum_map(conn,
        "SELECT site_id, SUM(total_amount) FROM equipment_hire GROUP BY site_id")
    rows = []
    for s in conn.execute('SELECT id, name FROM sites ORDER BY name'):
        sid = s['id']
        revenue = (rev_bills.get(sid, 0) or 0) + (rev_ra.get(sid, 0) or 0)
        mat = material.get(sid, 0) or 0
        lab = labour.get(sid, 0) or 0
        hr = hire.get(sid, 0) or 0
        cost = mat + lab + hr
        if revenue == 0 and cost == 0:
            continue
        pm = m.profit_margin(revenue, cost)
        rows.append({
            'site_id': sid,
            'site': s['name'],
            'revenue': pm['revenue'],
            'material': round(float(mat), 2),
            'labour': round(float(lab), 2),
            'hire': round(float(hr), 2),
            'cost': pm['cost'],
            'profit': pm['profit'],
            'margin_pct': pm['margin_pct'],
        })
    return {
        'rows': rows,
        'cols': [
            {'key': 'site', 'label': 'Site'},
            {'key': 'revenue', 'label': 'Revenue', 'align': 'right'},
            {'key': 'material', 'label': 'Material', 'align': 'right'},
            {'key': 'labour', 'label': 'Labour', 'align': 'right'},
            {'key': 'hire', 'label': 'Equip hire', 'align': 'right'},
            {'key': 'cost', 'label': 'Cost', 'align': 'right'},
            {'key': 'profit', 'label': 'Profit', 'align': 'right'},
            {'key': 'margin_pct', 'label': 'Margin %', 'align': 'right'},
        ],
    }


def contract_progress(conn):
    rows = []
    for c in conn.execute(
            'SELECT id, contract_no, site_id FROM contracts ORDER BY id DESC'):
        boq = conn.execute(
            'SELECT COALESCE(SUM(amount), 0) AS v FROM boq_items '
            'WHERE contract_id = ?', (c['id'],)).fetchone()['v']
        measured = conn.execute(
            'SELECT COALESCE(SUM(m.quantity * b.rate), 0) AS v '
            'FROM measurements m JOIN boq_items b ON b.id = m.boq_item_id '
            'WHERE m.contract_id = ?', (c['id'],)).fetchone()['v']
        prog = analytics.contract_progress(boq, measured)
        if prog['boq_value'] == 0 and prog['measured_value'] == 0:
            continue
        rows.append({
            'contract_id': c['id'],
            'contract_no': c['contract_no'],
            'site_id': c['site_id'],
            **prog,
        })
    return {
        'rows': rows,
        'cols': [
            {'key': 'contract_no', 'label': 'Contract'},
            {'key': 'boq_value', 'label': 'BOQ value', 'align': 'right'},
            {'key': 'measured_value', 'label': 'Measured', 'align': 'right'},
            {'key': 'progress_pct', 'label': 'Progress %', 'align': 'right'},
            {'key': 'balance_value', 'label': 'Balance', 'align': 'right'},
        ],
    }


def material_budget(conn):
    """Roll theoretical vs actual material value per material (when norms exist)."""
    rows = []
    norms = conn.execute(
        'SELECT material_id, activity, qty_per_unit, unit FROM consumption_norms'
    ).fetchall()
    if not norms:
        return {
            'rows': [],
            'cols': [
                {'key': 'material', 'label': 'Material'},
                {'key': 'budget_value', 'label': 'Budget', 'align': 'right'},
                {'key': 'actual_value', 'label': 'Actual', 'align': 'right'},
                {'key': 'variance_value', 'label': 'Variance', 'align': 'right'},
                {'key': 'overspend_pct', 'label': 'Over %', 'align': 'right'},
            ],
            'note': 'No consumption norms recorded yet.',
        }
    # Work done by activity.
    work = _sum_map(conn,
        'SELECT activity, SUM(qty) FROM work_done_entries GROUP BY activity')
    # Actual OUT qty + average rate per material.
    actual_qty = _sum_map(conn,
        "SELECT material_id, SUM(qty) FROM material_ledger "
        "WHERE txn_type='OUT' GROUP BY material_id")
    rates = {}
    for r in conn.execute(
            "SELECT material_id, AVG(rate) AS rate FROM material_ledger "
            "WHERE rate IS NOT NULL AND rate > 0 GROUP BY material_id"):
        rates[r['material_id']] = r['rate'] or 0
    names = {r['id']: r['name'] for r in conn.execute(
        'SELECT id, name FROM materials')}
    # Theoretical qty per material = Σ (norm.qty_per_unit × work[activity])
    theoretical = {}
    for n in norms:
        mid = n['material_id']
        if not mid:
            continue
        theoretical[mid] = theoretical.get(mid, 0) + (
            (n['qty_per_unit'] or 0) * (work.get(n['activity'], 0) or 0))
    for mid, theo in theoretical.items():
        mb = analytics.material_budget(
            theo, actual_qty.get(mid, 0) or 0, rates.get(mid, 0) or 0)
        rows.append({
            'material_id': mid,
            'material': names.get(mid) or str(mid),
            **mb,
        })
    return {
        'rows': rows,
        'cols': [
            {'key': 'material', 'label': 'Material'},
            {'key': 'budget_value', 'label': 'Budget', 'align': 'right'},
            {'key': 'actual_value', 'label': 'Actual', 'align': 'right'},
            {'key': 'variance_value', 'label': 'Variance', 'align': 'right'},
            {'key': 'overspend_pct', 'label': 'Over %', 'align': 'right'},
        ],
    }


def assemble(conn):
    return {
        'site_profitability': site_profitability(conn),
        'contract_progress': contract_progress(conn),
        'material_budget': material_budget(conn),
    }
