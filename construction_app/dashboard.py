"""Gather one snapshot of the whole business for the Home dashboard.

This is the collection half; ``advisory.build`` is the judgement half. Keeping
them apart means the judging is a pure function of a plain dict — trivial to
unit-test with hand-made numbers — while all the SQL and the reuse of the app's
proven helpers lives here.

Nothing is computed twice: every figure comes from the same tables and the same
pure ``summarise`` functions the individual tabs already use (``ageing``,
``retention``, ``procurement``, ``variation``, ``quality``, ``planning``,
``projectcost`` …), so Home can never disagree with the tab it summarises.

Every block is wrapped so that a missing table on an older data file, or one
tab-helper raising, degrades to zeros for that block instead of taking the whole
dashboard down. The tab-module helpers are imported inside ``collect`` (not at
module scope) to avoid an import cycle — the same convention the KPI tab uses.
"""

from datetime import date

import ageing
import allocation
import money as m
import planning
import procurement
import projectcost
import quality
import retention
import variation


def _scalar(conn, sql, params=(), default=0.0):
    try:
        row = conn.execute(sql, params).fetchone()
    except Exception:                                   # noqa: BLE001
        return default
    if not row:
        return default
    val = row[0]
    return default if val is None else val


def collect(conn):
    """Return one flat snapshot dict of every figure the dashboard shows.

    Keys fall into three groups: headline KPIs (``cash``, ``receivable`` …),
    raw signals the advisory rules read (``receivable_90plus``, ``at_risk`` …),
    and two ready-to-render lists (``bottlenecks``, ``decisions``).
    """
    today = date.today().isoformat()
    ym = today[:7]
    s = {}

    # ------------------------------------------------------------ money core
    opening = float(_scalar(
        conn, "SELECT value FROM app_settings WHERE key = 'cash_opening'",
        default=0.0) or 0.0)
    try:
        cash_moves = conn.execute(
            "SELECT direction, amount FROM payments WHERE mode = 'Cash'"
        ).fetchall()
        s['cash'] = m.closing_balance(
            [m.signed_cash(r['direction'], r['amount']) for r in cash_moves],
            opening)
    except Exception:                                   # noqa: BLE001
        s['cash'] = opening

    billed = (_scalar(conn, "SELECT COALESCE(SUM(net_payable),0) FROM bills "
                      "WHERE status IN ('Approved','Paid')")
              + _scalar(conn, "SELECT COALESCE(SUM(net_payable),0) FROM ra_bills "
                        "WHERE status IN ('Approved','Paid')"))
    received = _scalar(conn, "SELECT COALESCE(SUM(amount),0) FROM payments "
                       "WHERE direction = 'Receipt' AND party_type = 'Client'")
    s['receivable'] = m.party_outstanding(billed, received)

    invoiced = _scalar(conn, "SELECT COALESCE(SUM(net_payable),0) "
                       "FROM vendor_invoices")
    paid = _scalar(conn, "SELECT COALESCE(SUM(amount),0) FROM payments "
                   "WHERE direction = 'Payment' AND party_type = 'Vendor'")
    s['payable'] = m.party_outstanding(invoiced, paid)
    s['net_position'] = round(s['receivable'] - s['payable'], 2)

    s['sites'] = int(_scalar(conn, "SELECT COUNT(*) FROM sites "
                             "WHERE status = 'Active'"))
    s['billed_month'] = (
        _scalar(conn, "SELECT COALESCE(SUM(net_payable),0) FROM bills "
                "WHERE status IN ('Approved','Paid') "
                "AND substr(bill_date,1,7) = ?", (ym,))
        + _scalar(conn, "SELECT COALESCE(SUM(net_payable),0) FROM ra_bills "
                  "WHERE status IN ('Approved','Paid') "
                  "AND substr(bill_date,1,7) = ?", (ym,)))
    s['collected_month'] = _scalar(
        conn, "SELECT COALESCE(SUM(amount),0) FROM payments "
        "WHERE direction = 'Receipt' AND substr(pay_date,1,7) = ?", (ym,))

    # ------------------------------------------- receivables ageing (reused)
    s['receivable_60_90'] = 0.0
    s['receivable_90plus'] = 0.0
    s['receivable_aged_count'] = 0
    try:
        from tab_allocate import party_documents
        docs = []
        for c in conn.execute('SELECT id FROM clients'):
            docs += party_documents(conn, 'Client', c['id'])
        allocs = [{'doc_type': r['doc_type'], 'doc_id': r['doc_id'],
                   'amount': r['amount']} for r in conn.execute(
            'SELECT pa.doc_type, pa.doc_id, pa.amount FROM payment_allocations pa '
            'JOIN payments p ON p.id = pa.payment_id '
            "WHERE p.party_type = 'Client'")]
        settled = _scalar(conn, "SELECT COALESCE(SUM(amount),0) FROM payments "
                          "WHERE direction='Receipt' AND party_type='Client'")
        used = sum(allocation.money(a['amount']) for a in allocs)
        unalloc = max(allocation.money(settled) - allocation.money(used), 0.0)
        items = allocation.open_items_for_ageing(docs, allocs, unalloc)
        aged = ageing.age_open_items(items)
        s['receivable_60_90'] = aged['60-90']
        s['receivable_90plus'] = aged['90+']
        s['receivable_aged_count'] = sum(
            1 for d, amt in items
            if amt > 0 and ageing.days_between(d, today) >= 60)
    except Exception:                                   # noqa: BLE001
        pass

    # ------------------------------------------------------------- retention
    s['retention_due_now'] = 0.0
    s['retention_outstanding'] = 0.0
    s['retention_max_overdue_days'] = 0
    try:
        from tab_retention import retention_lines
        rsum = retention.summarise(retention_lines(conn, 12))
        s['retention_due_now'] = rsum['due_now']
        s['retention_outstanding'] = rsum['outstanding']
        s['retention_max_overdue_days'] = rsum['max_overdue_days']
    except Exception:                                   # noqa: BLE001
        pass

    # ------------------------------------------------------------ variations
    s['variations_approved_unbilled'] = 0.0
    s['variations_pending_count'] = 0
    s['variations_pending_value'] = 0.0
    try:
        vsum = variation.summarise(
            conn.execute('SELECT * FROM variations').fetchall())
        s['variations_approved_unbilled'] = vsum['approved_unbilled']
        s['variations_pending_value'] = vsum['pending_approval']
        s['variations_pending_count'] = vsum['counts'].get('Raised', 0)
    except Exception:                                   # noqa: BLE001
        pass

    # -------------------------------------------- 3-way match (invoiced/GRN)
    s['at_risk'] = 0.0
    try:
        pos = conn.execute(
            'SELECT id, total_amount FROM purchase_orders').fetchall()
        recv, inv = {}, {}
        for r in conn.execute(
                'SELECT g.purchase_order_id AS pid, SUM(gi.amount) AS a '
                'FROM grn_items gi JOIN goods_receipts g ON g.id = gi.grn_id '
                "WHERE g.status = 'Posted' GROUP BY g.purchase_order_id"):
            recv[r['pid']] = r['a'] or 0
        for r in conn.execute(
                'SELECT purchase_order_id AS pid, SUM(subtotal) AS a '
                'FROM vendor_invoices WHERE purchase_order_id IS NOT NULL '
                'GROUP BY purchase_order_id'):
            inv[r['pid']] = r['a'] or 0
        matches = [procurement.three_way(p['total_amount'], recv.get(p['id'], 0),
                                         inv.get(p['id'], 0), 100) for p in pos]
        s['at_risk'] = procurement.summarise(matches)['at_risk']
    except Exception:                                   # noqa: BLE001
        pass

    # ----------------------------------------------------------- compliance
    s['compliance_overdue'] = 0
    s['compliance_due_soon'] = 0
    s['compliance_max_days_late'] = 0
    try:
        from tab_compliance import open_obligations
        csum = open_obligations(conn)
        s['compliance_overdue'] = csum['overdue']
        s['compliance_due_soon'] = csum['due_soon']
        s['compliance_max_days_late'] = csum['max_days_late']
    except Exception:                                   # noqa: BLE001
        pass

    # ----------------------------------------------------- programme / delay
    s['programme_delay_days'] = None
    s['programme_ld'] = 0.0
    s['programme_project'] = None
    s['programme_claimable'] = 0
    try:
        from tab_timeline import worst_delay
        wd = worst_delay(conn)
        if wd:
            s['programme_delay_days'] = wd['net_delay_days']
            s['programme_ld'] = wd['ld']['exposure']
            s['programme_project'] = wd['project']
            s['programme_claimable'] = wd['claimable_days']
    except Exception:                                   # noqa: BLE001
        pass

    # ------------------------------------------------------- project margins
    s['projects_at_loss'] = 0
    s['projects_over_budget'] = 0
    s['projects_worst'] = None
    s['projects_worst_margin'] = 0.0
    s['unattributed_cost'] = 0.0
    try:
        from tab_projects import project_cost_rollup
        rolls = [(r['name'], project_cost_rollup(conn, r['id']))
                 for r in conn.execute("SELECT id, name FROM projects "
                                       "WHERE status != 'Cancelled'")]
        if rolls:
            port = projectcost.portfolio(rolls)
            s['projects_at_loss'] = port['at_a_loss']
            s['projects_over_budget'] = port['over_budget']
            s['projects_worst'] = port['worst']
            s['projects_worst_margin'] = port['worst_margin'] or 0.0
            s['unattributed_cost'] = port['unattributed_total']
    except Exception:                                   # noqa: BLE001
        pass

    # ------------------------------------------------------------- plant/fuel
    s['plant_overdue'] = 0
    s['plant_due'] = 0
    s['plant_fuel_flags'] = 0
    s['plant_excess_litres'] = 0.0
    try:
        from tab_plant import open_plant_alerts
        p = open_plant_alerts(conn)
        if p.get('machines'):
            s['plant_overdue'] = p.get('overdue', 0)
            s['plant_due'] = p.get('due', 0)
            s['plant_fuel_flags'] = p.get('fuel_flags', 0)
            s['plant_excess_litres'] = p.get('excess_litres', 0.0)
    except Exception:                                   # noqa: BLE001
        pass

    # --------------------------------------------------------- plan (PPC)
    s['ppc_last'] = None
    s['ppc_weeks'] = 0
    s['ppc_top_reason'] = None
    try:
        rows = conn.execute(
            'SELECT week_start, status, reason FROM commitments').fetchall()
        weeks = {}
        for r in rows:
            weeks.setdefault(r['week_start'] or '', []).append(r)
        s['ppc_weeks'] = len(weeks)
        if weeks:
            s['ppc_last'] = planning.ppc(weeks[max(weeks)])
        reasons = planning.reasons_for_misses(rows)
        s['ppc_top_reason'] = reasons[0][0] if reasons else None
    except Exception:                                   # noqa: BLE001
        pass

    # ----------------------------------------------------------- quality/NCR
    s['ncr_open'] = 0
    s['ncr_oldest_days'] = 0
    s['ncr_critical'] = 0
    try:
        qn = quality.ncr_summary(
            conn.execute('SELECT * FROM ncrs').fetchall(), today)
        s['ncr_open'] = qn['open']
        s['ncr_oldest_days'] = qn['oldest_open_days'] or 0
        s['ncr_critical'] = int(_scalar(
            conn, "SELECT COUNT(*) FROM ncrs "
            "WHERE status = 'Open' AND severity = 'Critical'"))
    except Exception:                                   # noqa: BLE001
        pass

    # ------------------------------------------------------------------ snags
    s['snags_open'] = int(_scalar(
        conn, "SELECT COUNT(*) FROM snags WHERE status = 'Open'"))
    s['snags_blockers'] = int(_scalar(
        conn, "SELECT COUNT(*) FROM snags "
        "WHERE status = 'Open' AND severity = 'Blocker'"))

    # ------------------------------------------------------------------- RFIs
    s['rfis_open'] = 0
    s['rfis_oldest_days'] = 0
    try:
        rfi_rows = conn.execute(
            "SELECT raised_date FROM rfis WHERE status = 'Open'").fetchall()
        s['rfis_open'] = len(rfi_rows)
        s['rfis_oldest_days'] = max(
            (ageing.days_between(r['raised_date'], today) for r in rfi_rows),
            default=0)
    except Exception:                                   # noqa: BLE001
        pass

    s['requisitions_open'] = int(_scalar(
        conn, "SELECT COUNT(*) FROM material_requisitions "
        "WHERE status IN ('Open','Ordered')"))

    # ------------------------------------------- decisions waiting on sign-off
    s['approvals_count'] = 0
    s['approvals_amount'] = 0.0
    s['bids_undecided'] = 0
    s['bids_undecided_value'] = 0.0
    decisions = []
    try:
        from tab_approvals import pending_documents
        pend = pending_documents(conn)
        s['approvals_count'] = len(pend)
        s['approvals_amount'] = sum(float(d['amount'] or 0) for d in pend)
        grouped = {}
        for d in pend:
            g = grouped.setdefault(d['label'], {
                'label': d['label'], 'count': 0, 'value': 0.0,
                'where': 'Money › Approvals'})
            g['count'] += 1
            g['value'] += float(d['amount'] or 0)
        decisions = sorted(grouped.values(), key=lambda g: -g['value'])
    except Exception:                                   # noqa: BLE001
        pass
    try:
        row = conn.execute(
            "SELECT COUNT(*) c, COALESCE(SUM(tender_value),0) v "
            "FROM bid_assessments WHERE decision = 'Not decided'").fetchone()
        s['bids_undecided'] = row['c']
        s['bids_undecided_value'] = row['v'] or 0.0
        if s['bids_undecided']:
            decisions.append({'label': 'Tender — bid / no-bid decision',
                              'count': s['bids_undecided'],
                              'value': s['bids_undecided_value'],
                              'where': 'Billing › Bid / No Bid'})
    except Exception:                                   # noqa: BLE001
        pass
    s['decisions'] = decisions

    s['bottlenecks'] = _bottlenecks(s)
    return s


# 'act' = money/risk stuck now, 'watch' = a queue worth watching.
def _bottlenecks(s):
    """The operational scoreboard: where work (and money) is sitting still."""
    out = []

    def add(cond, label, metric, severity, where, detail=''):
        if cond:
            out.append({'label': label, 'metric': metric, 'severity': severity,
                        'where': where, 'detail': detail})

    def money_str(v):
        return '₹ {:,.0f}'.format(round(float(v or 0)))

    add(s.get('at_risk', 0) > 0, 'Invoices awaiting goods receipt',
        money_str(s['at_risk']), 'act', 'Purchases › Goods Receipt',
        'unmatched vendor value')
    add(s.get('variations_approved_unbilled', 0) > 0, 'Approved variations unbilled',
        money_str(s['variations_approved_unbilled']), 'act', 'Billing › Variations',
        'agreed work not yet billed')
    add(s.get('receivable_90plus', 0) > 0, 'Receivables past 90 days',
        money_str(s['receivable_90plus']), 'act', 'Money › Cash & Parties',
        'hardest money to collect')
    add(s.get('retention_due_now', 0) > 0, 'Retention due for release',
        money_str(s['retention_due_now']), 'act', 'Money › Retention',
        'past its DLP date')
    add(s.get('plant_overdue', 0) > 0, 'Plant overdue for service',
        str(s['plant_overdue']), 'act', 'Operations › Plant', 'machine(s)')
    add(s.get('compliance_overdue', 0) > 0, 'Statutory filings overdue',
        str(s['compliance_overdue']), 'act', 'Accounts › Compliance', 'filing(s)')
    add(s.get('snags_blockers', 0) > 0, 'Blocking snags at handover',
        str(s['snags_blockers']), 'act', 'Operations › Closeout', 'blocker(s)')
    add(s.get('ncr_critical', 0) > 0, 'Critical NCRs open',
        str(s['ncr_critical']), 'act', 'Operations › Quality', 'non-conformance(s)')

    add(s.get('rfis_open', 0) > 0, 'RFIs awaiting an answer',
        str(s['rfis_open']), 'watch', 'Purchases › Sourcing',
        'oldest {} day(s)'.format(s.get('rfis_oldest_days', 0)))
    add(s.get('requisitions_open', 0) > 0, 'Material requisitions open',
        str(s['requisitions_open']), 'watch', 'Purchases › Sourcing',
        'not yet ordered/closed')
    add(s.get('ncr_open', 0) > 0 and s.get('ncr_critical', 0) == 0,
        'Non-conformances open', str(s['ncr_open']), 'watch',
        'Operations › Quality', 'oldest {} day(s)'.format(s.get('ncr_oldest_days', 0)))
    add(s.get('snags_open', 0) > 0 and s.get('snags_blockers', 0) == 0,
        'Snags open', str(s['snags_open']), 'watch', 'Operations › Closeout',
        'punch-list items')
    add(s.get('plant_due', 0) > 0 and s.get('plant_overdue', 0) == 0,
        'Plant service coming due', str(s['plant_due']), 'watch',
        'Operations › Plant', 'machine(s)')
    ppc = s.get('ppc_last')
    add(ppc is not None and ppc < 80, 'Weekly plan reliability (PPC)',
        '{:.0f}%'.format(ppc) if ppc is not None else '—', 'watch',
        'Project Management › Look-ahead', 'promised tasks finished')
    add(s.get('approvals_count', 0) > 0, 'Documents awaiting sign-off',
        str(s['approvals_count']), 'watch', 'Money › Approvals',
        'in the approvals queue')

    order = {'act': 0, 'watch': 1}
    out.sort(key=lambda b: order.get(b['severity'], 9))
    return out
