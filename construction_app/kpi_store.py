"""Key Numbers KPI rows — pure store (no tkinter / no tab_* imports).

Mirrors the desktop Key Numbers judgements using the same pure maths modules
the GUI tab uses, so headless / WinUI clients get an honest split from Insight.
"""

from datetime import date

import ageing
import allocation
import planning
import procurement
import projectcost
import project_rollup
import quality
import retention
import variation

ACT = 'act'
WATCH = 'watch'
GOOD = 'good'
NONE = 'none'


def _retention_lines(conn, dlp_months=12):
    """Documents that withheld retention — same SQL as the retention tab."""
    released = {}
    try:
        for r in conn.execute(
                'SELECT doc_type, doc_id, SUM(amount) AS a '
                'FROM retention_releases GROUP BY doc_type, doc_id'):
            released[(r['doc_type'], r['doc_id'])] = r['a'] or 0
    except Exception:  # noqa: BLE001
        released = {}

    lines = []

    def add(doc_type, doc_id, number, party, side, withheld, completion):
        w = retention.money(withheld)
        if w <= 0:
            return
        rel = retention.money(released.get((doc_type, doc_id), 0))
        due = retention.release_due_date(completion, dlp_months)
        lines.append({
            'doc_type': doc_type, 'doc_id': doc_id, 'number': number or '-',
            'party': party or '-', 'side': side, 'withheld': w,
            'released': rel,
            'outstanding': retention.outstanding(w, rel),
            'due_date': due.isoformat() if due else None,
            'completion': completion or '',
        })

    for r in conn.execute(
            'SELECT b.id, b.bill_no, b.retention_amt, cl.name AS party, '
            'c.end_date FROM bills b '
            'JOIN contracts c ON c.id = b.contract_id '
            'LEFT JOIN clients cl ON cl.id = c.client_id '
            "WHERE b.status IN ('Approved','Paid')"):
        add('Bill', r['id'], r['bill_no'], r['party'], retention.CLIENT,
            r['retention_amt'], r['end_date'])
    for r in conn.execute(
            'SELECT rb.id, rb.bill_no, rb.retention_amt, cl.name AS party, '
            'c.end_date FROM ra_bills rb '
            'JOIN contracts c ON c.id = rb.contract_id '
            'LEFT JOIN clients cl ON cl.id = c.client_id '
            "WHERE rb.status IN ('Approved','Paid')"):
        add('RABill', r['id'], r['bill_no'], r['party'], retention.CLIENT,
            r['retention_amt'], r['end_date'])
    try:
        for r in conn.execute(
                'SELECT sb.id, sb.bill_no, sb.retention_amt, sb.bill_date, '
                'v.name AS party FROM sub_bills sb '
                'LEFT JOIN work_orders wo ON wo.id = sb.work_order_id '
                'LEFT JOIN vendors v ON v.id = wo.vendor_id '
                "WHERE sb.status IN ('Approved','Paid')"):
            add('SubBill', r['id'], r['bill_no'], r['party'], retention.SUB,
                r['retention_amt'], r['bill_date'])
    except Exception:  # noqa: BLE001
        pass
    return lines


def _party_documents(conn, party_type, party_id):
    """Minimal open-item docs for client ageing (bills + RA + tax invoices)."""
    docs = []
    if party_type != 'Client':
        return docs
    for r in conn.execute(
            "SELECT id, bill_no AS number, bill_date AS date, net_payable "
            "FROM bills WHERE contract_id IN "
            "(SELECT id FROM contracts WHERE client_id = ?) "
            "AND status IN ('Approved','Paid','Submitted')", (party_id,)):
        docs.append({'doc_type': 'Bill', 'doc_id': r['id'],
                     'number': r['number'], 'date': r['date'],
                     'amount': r['net_payable'] or 0})
    for r in conn.execute(
            "SELECT id, bill_no AS number, bill_date AS date, net_payable "
            "FROM ra_bills WHERE contract_id IN "
            "(SELECT id FROM contracts WHERE client_id = ?) "
            "AND status IN ('Approved','Paid','Submitted')", (party_id,)):
        docs.append({'doc_type': 'RABill', 'doc_id': r['id'],
                     'number': r['number'], 'date': r['date'],
                     'amount': r['net_payable'] or 0})
    for r in conn.execute(
            "SELECT id, invoice_no AS number, invoice_date AS date, "
            "total_amount FROM tax_invoices WHERE client_id = ? "
            "AND status != 'Cancelled'", (party_id,)):
        docs.append({'doc_type': 'TaxInvoice', 'doc_id': r['id'],
                     'number': r['number'], 'date': r['date'],
                     'amount': r['total_amount'] or 0})
    return docs


def collect(conn):
    """Return structured Key Numbers rows.

    Each row: ``{kpi, value, verdict, meaning}`` — verdict in
    act/watch/good/none.
    """
    out = []
    today = date.today().isoformat()  # noqa: F841 — kept for parity / future

    vars_all = conn.execute('SELECT * FROM variations').fetchall()
    vsum = variation.summarise(vars_all)
    unbilled = vsum['approved_unbilled']
    out.append({
        'kpi': 'Variations approved, not billed',
        'value': round(float(unbilled), 2),
        'value_text': '{:,.2f}'.format(unbilled),
        'verdict': ACT if unbilled > 0 else GOOD,
        'meaning': (
            'Work the client agreed to pay for that has not been billed.'
            if unbilled else 'Nothing agreed is waiting to be billed.'),
    })

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
    matches = [procurement.three_way(
        p['total_amount'], recv.get(p['id'], 0), inv.get(p['id'], 0), 100)
        for p in pos]
    psum = procurement.summarise(matches)
    out.append({
        'kpi': 'Invoiced without a goods receipt',
        'value': round(float(psum['at_risk']), 2),
        'value_text': '{:,.2f}'.format(psum['at_risk']),
        'verdict': ACT if psum['at_risk'] > 0 else GOOD,
        'meaning': (
            'Vendor value billed with no receipt behind it — check before paying.'
            if psum['at_risk'] else
            'Every vendor invoice is backed by a receipt.'),
    })

    all_purchases = conn.execute(
        'SELECT COALESCE(SUM(subtotal), 0) FROM vendor_invoices'
    ).fetchone()[0] or 0
    under_po = conn.execute(
        'SELECT COALESCE(SUM(subtotal), 0) FROM vendor_invoices '
        'WHERE purchase_order_id IS NOT NULL').fetchone()[0] or 0
    if all_purchases:
        pct = round(under_po / all_purchases * 100.0, 1)
        out.append({
            'kpi': 'Purchases made under a PO',
            'value': pct,
            'value_text': '{:.1f}%'.format(pct),
            'verdict': GOOD if pct >= 80 else WATCH if pct >= 50 else ACT,
            'meaning': 'Buying without a PO is the classic leak; aim high.',
        })
    else:
        out.append({
            'kpi': 'Purchases made under a PO',
            'value': None,
            'value_text': '—',
            'verdict': NONE,
            'meaning': 'No vendor invoices recorded yet.',
        })

    docs, allocs = [], []
    for c in conn.execute('SELECT id FROM clients'):
        docs += _party_documents(conn, 'Client', c['id'])
    for r in conn.execute(
            'SELECT pa.doc_type, pa.doc_id, pa.amount FROM payment_allocations pa '
            "JOIN payments p ON p.id = pa.payment_id WHERE p.party_type = 'Client'"):
        allocs.append({'doc_type': r['doc_type'], 'doc_id': r['doc_id'],
                       'amount': r['amount']})
    settled = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM payments WHERE direction='Receipt' "
        "AND party_type='Client'").fetchone()[0] or 0
    used = sum(allocation.money(a['amount']) for a in allocs)
    unalloc = max(allocation.money(settled) - allocation.money(used), 0.0)
    try:
        aged = ageing.age_open_items(
            allocation.open_items_for_ageing(docs, allocs, unalloc))
    except Exception:  # noqa: BLE001
        aged = {'total': 0.0, '90+': 0.0}
    out.append({
        'kpi': 'Receivables outstanding',
        'value': round(float(aged.get('total') or 0), 2),
        'value_text': '{:,.2f}'.format(aged.get('total') or 0),
        'verdict': WATCH if (aged.get('total') or 0) > 0 else GOOD,
        'meaning': 'Money owed to you across all clients.',
    })
    old = aged.get('90+') or 0
    out.append({
        'kpi': 'of which over 90 days',
        'value': round(float(old), 2),
        'value_text': '{:,.2f}'.format(old),
        'verdict': ACT if old > 0 else GOOD,
        'meaning': (
            'The hardest money to collect. Chase before it ages further.'
            if old else 'Nothing has aged past 90 days.'),
    })

    rlines = _retention_lines(conn, 12)
    rsum = retention.summarise(rlines)
    out.append({
        'kpi': 'Retention due for release',
        'value': round(float(rsum['due_now']), 2),
        'value_text': '{:,.2f}'.format(rsum['due_now']),
        'verdict': ACT if rsum['due_now'] > 0 else GOOD,
        'meaning': (
            'Past its defect-liability date and still held.'
            if rsum['due_now'] else 'Nothing is overdue for release.'),
    })
    out.append({
        'kpi': 'Retention still held (total)',
        'value': round(float(rsum['outstanding']), 2),
        'value_text': '{:,.2f}'.format(rsum['outstanding']),
        'verdict': NONE,
        'meaning': 'Earned money held by others until the DLP expires.',
    })

    rolls = []
    for r in conn.execute(
            "SELECT id, name FROM projects WHERE status != 'Cancelled'"):
        rolls.append((r['name'], project_rollup.project_cost_rollup(conn, r['id'])))
    if rolls:
        port = projectcost.portfolio(rolls)
        if port['at_a_loss']:
            out.append({
                'kpi': 'Projects running at a loss',
                'value': port['at_a_loss'],
                'value_text': str(port['at_a_loss']),
                'verdict': ACT,
                'meaning': 'Worst is {} at {:,.2f}.'.format(
                    port['worst'], port['worst_margin']),
            })
        elif port.get('over_budget'):
            out.append({
                'kpi': 'Projects over budget',
                'value': port['over_budget'],
                'value_text': str(port['over_budget']),
                'verdict': WATCH,
                'meaning': 'Cost has passed the budget on {}.'.format(
                    ', '.join((port.get('over_budget_names') or [])[:3])),
            })

    import timeline_store
    looped = sum(
        1 for r in conn.execute(
            "SELECT id FROM projects WHERE status != 'Closed'")
        if timeline_store.project_schedule(conn, r['id']).get('cycle'))
    if looped:
        out.append({
            'kpi': 'Programmes with a dependency loop',
            'value': looped,
            'value_text': str(looped),
            'verdict': ACT,
            'meaning': 'Tasks that wait on each other — fix before trusting CPM.',
        })
    wd = timeline_store.worst_delay(conn)
    if wd is None:
        out.append({
            'kpi': 'Programme delay',
            'value': None,
            'value_text': '—',
            'verdict': NONE,
            'meaning': 'No project has a frozen baseline yet.',
        })
    else:
        days = wd.get('net_delay_days') or 0
        out.append({
            'kpi': 'Worst programme delay',
            'value': days,
            'value_text': '{} day(s)'.format(days) if days else 'On time',
            'verdict': ACT if days > 0 else GOOD,
            'meaning': (
                '{} — LD exposure {:,.2f}.'.format(
                    wd.get('project'), (wd.get('ld') or {}).get('exposure') or 0)
                if days else 'Nothing running late against baseline.'),
        })

    commits = conn.execute('SELECT * FROM commitments').fetchall()
    weeks = {}
    for r in commits:
        weeks.setdefault(r['week_start'] or '?', []).append(r)
    trend = planning.ppc_trend(weeks)
    if trend['average'] is None:
        out.append({
            'kpi': 'Plan reliability (PPC)',
            'value': None,
            'value_text': '—',
            'verdict': NONE,
            'meaning': 'No weekly commitments recorded yet.',
        })
    else:
        avg = trend['average']
        out.append({
            'kpi': 'Plan reliability (PPC)',
            'value': avg,
            'value_text': '{:.0f}%'.format(avg),
            'verdict': GOOD if avg >= 80 else WATCH if avg >= 60 else ACT,
            'meaning': 'Share of weekly promises actually finished.',
        })
        worst = planning.reasons_for_misses(commits)
        if worst:
            out.append({
                'kpi': 'biggest cause of misses',
                'value': worst[0][0],
                'value_text': str(worst[0][0]),
                'verdict': WATCH,
                'meaning': 'Fix this and reliability moves more than chasing.',
            })

    insp = conn.execute('SELECT * FROM inspections').fetchall()
    ftp = quality.first_time_pass_rate(insp)
    if ftp is None:
        out.append({
            'kpi': 'Inspections passed first time',
            'value': None,
            'value_text': '—',
            'verdict': NONE,
            'meaning': 'No inspections recorded yet.',
        })
    else:
        out.append({
            'kpi': 'Inspections passed first time',
            'value': ftp,
            'value_text': '{:.0f}%'.format(ftp),
            'verdict': GOOD if ftp >= 90 else WATCH if ftp >= 75 else ACT,
            'meaning': 'Rework is the most expensive way to build.',
        })
    ncrs = conn.execute('SELECT * FROM ncrs').fetchall()
    nsum = quality.ncr_summary(ncrs)
    out.append({
        'kpi': 'Open non-conformances',
        'value': nsum['open'],
        'value_text': str(nsum['open']),
        'verdict': (
            ACT if nsum.get('oldest_open_days', 0) > 30
            else WATCH if nsum['open'] else GOOD),
        'meaning': 'Open NCRs that still need a close-out.',
    })

    action = sum(1 for r in out if r['verdict'] == ACT)
    return {
        'rows': out,
        'action_count': action,
        'headline': (
            '{} number(s) need action today.'.format(action)
            if action else 'Nothing urgent on the Key Numbers board.'),
        'cols': [
            {'key': 'kpi', 'label': 'Indicator'},
            {'key': 'value_text', 'label': 'Now'},
            {'key': 'verdict', 'label': ''},
            {'key': 'meaning', 'label': 'What it means'},
        ],
    }
