"""Read-only / draft-returning tools for ACO agents.

No tkinter. Every tool takes ``conn`` and returns a dict with ``ok``, ``basis``,
and payload keys. Tools never write money or dates — they only read or describe
drafts. Soft-fail on missing tables so older books stay usable.
"""

from datetime import date, timedelta


def _safe(fn, basis):
    try:
        payload = fn()
        if isinstance(payload, dict) and 'ok' in payload:
            return payload
        out = {'ok': True, 'basis': basis}
        out.update(payload if isinstance(payload, dict) else {'value': payload})
        return out
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'basis': basis, 'error': str(exc)}


def money_snapshot(conn):
    def run():
        import dashboard
        s = dashboard.collect(conn)
        return {
            'cash': s.get('cash'),
            'receivable': s.get('receivable'),
            'payable': s.get('payable'),
            'basis_detail': 'dashboard.collect money core',
        }
    return _safe(run, 'Cash / receivable / payable from the live book')


def ageing_summary(conn):
    def run():
        import ageing
        import allocation
        docs, allocs = [], []
        for c in conn.execute('SELECT id FROM clients'):
            for r in conn.execute(
                    "SELECT b.id, b.bill_date, b.net_payable FROM bills b "
                    "JOIN contracts k ON k.id=b.contract_id "
                    "WHERE k.client_id=? AND b.status IN ('Approved','Paid')",
                    (c['id'],)):
                docs.append({'doc_type': 'Bill', 'doc_id': r['id'],
                             'date': r['bill_date'], 'number': '',
                             'amount': r['net_payable'] or 0})
        for r in conn.execute(
                'SELECT pa.doc_type, pa.doc_id, pa.amount FROM payment_allocations pa '
                "JOIN payments p ON p.id=pa.payment_id WHERE p.party_type='Client'"):
            allocs.append({'doc_type': r['doc_type'], 'doc_id': r['doc_id'],
                           'amount': r['amount']})
        settled = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payments "
            "WHERE direction='Receipt' AND party_type='Client'"
        ).fetchone()[0] or 0
        used = sum(allocation.money(a['amount']) for a in allocs)
        unalloc = max(allocation.money(settled) - allocation.money(used), 0.0)
        buckets = ageing.age_open_items(
            allocation.open_items_for_ageing(docs, allocs, unalloc))
        return {'buckets': buckets, 'total': buckets.get('total')}
    return _safe(run, 'Client receivables aged FIFO')


def cashflow_hint(conn):
    def run():
        import cashflow_assemble
        payload = cashflow_assemble.assemble(conn, periods=4, mode='week')
        return {
            'labels': payload.get('labels'),
            'values': payload.get('values'),
            'series': payload.get('series'),
        }
    return _safe(run, '4-week cash-flow forecast buckets')


def gst_totals(conn):
    def run():
        import gst
        month = date.today().strftime('%Y-%m')
        _, out_tot = gst.outward(conn, month)
        _, in_tot = gst.inward(conn, month)
        _, tds_tot = gst.tds_register(conn, month)
        return {'month': month, 'outward': out_tot, 'inward': in_tot,
                'tds': tds_tot}
    return _safe(run, 'GST/TDS for current month')


def retention_due(conn):
    def run():
        import kpi_store
        lines = kpi_store._retention_lines(conn, 12)
        import retention
        return retention.summarise(lines)
    return _safe(run, 'Retention register due_now / outstanding')


def match_summary(conn):
    def run():
        import procurement
        pos = conn.execute(
            'SELECT id, total_amount FROM purchase_orders').fetchall()
        recv, inv = {}, {}
        for r in conn.execute(
                'SELECT g.purchase_order_id AS pid, SUM(gi.amount) AS a '
                'FROM grn_items gi JOIN goods_receipts g ON g.id=gi.grn_id '
                "WHERE g.status='Posted' GROUP BY g.purchase_order_id"):
            recv[r['pid']] = r['a'] or 0
        for r in conn.execute(
                'SELECT purchase_order_id AS pid, SUM(subtotal) AS a '
                'FROM vendor_invoices WHERE purchase_order_id IS NOT NULL '
                'GROUP BY purchase_order_id'):
            inv[r['pid']] = r['a'] or 0
        matches = [procurement.three_way(
            p['total_amount'], recv.get(p['id'], 0), inv.get(p['id'], 0), 100)
            for p in pos]
        return procurement.summarise(matches)
    return _safe(run, 'PO ↔ GRN ↔ invoice three-way roll-up')


def open_pos(conn):
    def run():
        rows = [dict(r) for r in conn.execute(
            "SELECT id, po_no, vendor_id, status, total_amount, po_date "
            "FROM purchase_orders WHERE status NOT IN ('Closed','Cancelled') "
            "ORDER BY id DESC LIMIT 20")]
        return {'items': rows, 'count': len(rows)}
    return _safe(run, 'Open / active purchase orders (top 20)')


def vendor_flags(conn):
    def run():
        # Rating columns are additive migrations — select * and project safely.
        rows = []
        for r in conn.execute(
                'SELECT * FROM vendors ORDER BY name LIMIT 50'):
            d = dict(r)
            rows.append({
                'id': d.get('id'),
                'name': d.get('name'),
                'quality': d.get('quality'),
                'delivery': d.get('delivery'),
                'price': d.get('price'),
                'approved': d.get('approved'),
            })
        return {'items': rows}
    return _safe(run, 'Vendor master (rating fields when present)')


def requisition_open(conn):
    def run():
        rows = [dict(r) for r in conn.execute(
            "SELECT id, req_no, site_id, req_date, status FROM "
            "material_requisitions WHERE status='Open' ORDER BY id DESC "
            "LIMIT 30")]
        return {'items': rows, 'count': len(rows)}
    return _safe(run, 'Open material requisitions')


def lookahead_ppc(conn):
    def run():
        import lookahead_store
        return lookahead_store.lookahead(conn, weeks=4)
    return _safe(run, 'Weekly look-ahead + PPC (planning.py)')


def programme_delay(conn):
    def run():
        import timeline_store
        wd = timeline_store.worst_delay(conn)
        return {'worst': wd}
    return _safe(run, 'Worst baselined programme delay / LD exposure')


def evm_portfolio(conn):
    def run():
        import evm
        rows, port = evm.portfolio_evm(conn)
        return {'portfolio': port, 'projects': rows}
    return _safe(run, 'Earned-value portfolio SPI/CPI')


def rate_book_summary(conn):
    def run():
        n = conn.execute('SELECT COUNT(*) AS c FROM rate_book').fetchone()['c']
        sample = [dict(r) for r in conn.execute(
            'SELECT code, category, description, unit, rate FROM rate_book '
            'ORDER BY id DESC LIMIT 8')]
        return {'count': n, 'sample': sample}
    return _safe(run, 'Rate book item count + recent sample')


def estimate_totals(conn):
    def run():
        rows = [dict(r) for r in conn.execute(
            'SELECT id, est_number, title, status, total_estimate '
            'FROM estimates ORDER BY id DESC LIMIT 15')]
        return {'items': rows}
    return _safe(run, 'Recent estimates')


def lessons_rates(conn):
    def run():
        import lessons_store
        items = lessons_store.list_lessons(conn)
        rows = []
        for r in list(items)[:15]:
            rows.append({k: r[k] for k in r.keys()} if hasattr(r, 'keys')
                        else dict(r))
        return {'items': rows, 'count': len(rows)}
    return _safe(run, 'Lessons-learned / achieved rates register')


def project_cost_hint(conn):
    def run():
        import project_rollup
        import projectcost
        rolls = []
        for r in conn.execute(
                "SELECT id, name FROM projects WHERE status != 'Cancelled'"):
            rolls.append((r['name'],
                          project_rollup.project_cost_rollup(conn, r['id'])))
        return projectcost.portfolio(rolls) if rolls else {
            'projects': 0, 'note': 'No projects'}
    return _safe(run, 'Project cost roll-up portfolio')


def boq_overview(conn):
    def run():
        rows = []
        for r in conn.execute(
                'SELECT c.id AS contract_id, c.contract_no, '
                'COUNT(b.id) AS lines, COALESCE(SUM(b.amount),0) AS boq_value '
                'FROM contracts c LEFT JOIN boq_items b ON b.contract_id=c.id '
                'GROUP BY c.id ORDER BY c.id DESC LIMIT 20'):
            rows.append(dict(r))
        return {'contracts': rows}
    return _safe(run, 'BOQ line counts and values per contract')


def boq_duplicates(conn):
    def run():
        dups = [dict(r) for r in conn.execute(
            'SELECT contract_id, lower(trim(description)) AS d, COUNT(*) AS n '
            'FROM boq_items WHERE description IS NOT NULL AND trim(description)!=\'\' '
            'GROUP BY contract_id, lower(trim(description)) HAVING n > 1 '
            'LIMIT 30')]
        return {'duplicates': dups, 'count': len(dups)}
    return _safe(run, 'Duplicate BOQ descriptions within a contract')


def measurement_progress(conn):
    def run():
        import analytics
        rows = []
        for c in conn.execute(
                'SELECT id, contract_no FROM contracts ORDER BY id DESC LIMIT 10'):
            boq = conn.execute(
                'SELECT COALESCE(SUM(amount),0) FROM boq_items WHERE contract_id=?',
                (c['id'],)).fetchone()[0]
            measured = conn.execute(
                'SELECT COALESCE(SUM(m.quantity*b.rate),0) FROM measurements m '
                'JOIN boq_items b ON b.id=m.boq_item_id WHERE m.contract_id=?',
                (c['id'],)).fetchone()[0]
            rows.append({'contract_no': c['contract_no'],
                         **analytics.contract_progress(boq, measured)})
        return {'items': rows}
    return _safe(run, 'Measured value vs tendered BOQ')


def deviation_hint(conn):
    def run():
        # Light: contracts where measured > BOQ value
        items = []
        prog = measurement_progress(conn)
        for row in (prog.get('items') or []):
            pct = row.get('progress_pct')
            if pct is not None and pct > 100:
                items.append(row)
        return {'over_boq': items, 'count': len(items)}
    return _safe(run, 'Contracts with measured value over BOQ')


def sidecar_status(conn=None):
    def run():
        import sidecar_bridge
        return sidecar_bridge.status()
    return _safe(run, 'OCR/STT/VLM sidecar probe')


def pdf_extract_hint(conn=None):
    return {
        'ok': True,
        'basis': 'Use POST /api/pdf/extract then human review',
        'gated': True,
        'action': 'Extract PDF text into a draft for review',
        'where': 'Assistant › Capture / Drawing',
    }


def takeoff_status(conn):
    def run():
        import takeoff_store
        n = conn.execute('SELECT COUNT(*) AS c FROM takeoffs').fetchone()['c']
        ne = conn.execute(
            'SELECT COUNT(*) AS c FROM drawing_elements').fetchone()['c']
        recent = takeoff_store.list_takeoffs(conn, limit=5)
        return {
            'takeoff_count': n,
            'element_count': ne,
            'recent': recent,
            'note': (
                'Deterministic element→quantity + revision-delta shipped (Phase D). '
                'VLM weights remain local L8 — sidecar soft-fails until installed.'
            ),
        }
    return _safe(run, 'Takeoff + drawing element counts')


def drawings_summary(conn):
    def run():
        rows = [dict(r) for r in conn.execute(
            'SELECT id, drawing_no, title, revision, superseded, scale, unit, '
            'takeoff_id FROM drawings ORDER BY id DESC LIMIT 30')]
        return {'items': rows, 'count': len(rows)}
    return _safe(run, 'Drawing register (latest 30)')


def element_totals(conn):
    def run():
        import drawing_geometry as geom
        import drawing_store
        d = conn.execute(
            'SELECT id, scale, unit FROM drawings ORDER BY id DESC LIMIT 1'
        ).fetchone()
        if not d:
            return {'totals': {}, 'note': 'No drawings yet'}
        els = drawing_store.elements_as_normalized(conn, d['id'])
        normalized = geom.normalize_elements(
            els, scale=float(d['scale'] or 0),
            linear_unit=d['unit'] or 'm')
        return {
            'drawing_id': d['id'],
            'count': len(normalized),
            'totals': geom.totals(normalized),
        }
    return _safe(run, 'Measured totals for latest drawing elements')


def revision_delta_hint(conn):
    def run():
        pair = conn.execute(
            'SELECT a.id AS from_id, b.id AS to_id, a.drawing_no, '
            'a.revision AS from_rev, b.revision AS to_rev '
            'FROM drawings a JOIN drawings b '
            'ON a.drawing_no = b.drawing_no AND a.id < b.id '
            'ORDER BY b.id DESC LIMIT 1'
        ).fetchone()
        if not pair:
            return {
                'ok': True,
                'gated': True,
                'note': 'Need two revisions of the same drawing_no to diff',
                'action': 'POST /api/drawings/revision-delta',
            }
        import drawing_store
        diff = drawing_store.compute_revision_delta(
            conn, pair['from_id'], pair['to_id'])
        return {
            'from_drawing_id': pair['from_id'],
            'to_drawing_id': pair['to_id'],
            'drawing_no': pair['drawing_no'],
            'from_rev': pair['from_rev'],
            'to_rev': pair['to_rev'],
            'summary': diff.get('summary'),
            'quantity_deltas': diff.get('quantity_deltas'),
            'gated': True,
            'action': 'Confirm delta then draft variation (human approve)',
            'where': 'Billing › Variations',
        }
    return _safe(run, 'Latest same-sheet revision delta (draft)')


def open_rfis(conn):
    def run():
        rows = [dict(r) for r in conn.execute(
            "SELECT id, rfi_no, subject, status, raised_date, required_by "
            "FROM rfis WHERE status='Open' ORDER BY id DESC LIMIT 30")]
        return {'items': rows, 'count': len(rows)}
    return _safe(run, 'Open RFIs')


def open_submittals(conn):
    def run():
        import submittals as sub
        if hasattr(sub, 'list_open'):
            return {'items': list(sub.list_open(conn))}
        rows = [dict(r) for r in conn.execute(
            "SELECT id, title, status, due_date FROM submittals "
            "WHERE status NOT IN ('Closed','Approved') "
            "ORDER BY id DESC LIMIT 30")]
        return {'items': rows, 'count': len(rows)}
    return _safe(run, 'Open submittals')


def contract_list(conn):
    def run():
        rows = [dict(r) for r in conn.execute(
            'SELECT id, contract_no, client_id, site_id, contract_value, status '
            'FROM contracts ORDER BY id DESC LIMIT 25')]
        return {'items': rows}
    return _safe(run, 'Recent contracts')


def open_ncrs(conn):
    def run():
        rows = [dict(r) for r in conn.execute(
            "SELECT id, ncr_no, status, raised_date, description FROM ncrs "
            "WHERE status NOT IN ('Closed','Cleared') ORDER BY id DESC LIMIT 30")]
        return {'items': rows, 'count': len(rows)}
    return _safe(run, 'Open NCRs')


def open_snags(conn):
    def run():
        rows = [dict(r) for r in conn.execute(
            "SELECT id, snag_no, status, raised_date, location, description "
            "FROM snags WHERE status != 'Closed' ORDER BY id DESC LIMIT 30")]
        return {'items': rows, 'count': len(rows)}
    return _safe(run, 'Open snags')


def inspection_pass_rate(conn):
    def run():
        import quality
        insp = conn.execute('SELECT * FROM inspections').fetchall()
        return {'first_time_pass_pct': quality.first_time_pass_rate(insp),
                'inspections': len(insp)}
    return _safe(run, 'Inspection first-time pass rate')


def muster_hint(conn):
    def run():
        today = date.today().isoformat()
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        n = conn.execute(
            'SELECT COUNT(*) AS c FROM attendance WHERE att_date BETWEEN ? AND ?',
            (week_ago, today)).fetchone()['c']
        return {'attendance_rows_7d': n, 'from': week_ago, 'to': today}
    return _safe(run, 'Attendance marks in the last 7 days')


def incident_summary(conn):
    def run():
        # Schema has no status column — severity / lost_days / description.
        rows = [dict(r) for r in conn.execute(
            'SELECT id, incident_date, severity, description, lost_days '
            'FROM incidents ORDER BY id DESC LIMIT 20')]
        return {'items': rows, 'count': len(rows)}
    return _safe(run, 'Recent HSE incidents')


def ltifr_summary(conn):
    def run():
        import hse
        incidents = conn.execute('SELECT * FROM incidents').fetchall()
        # Hours worked: optional setting or attendance hours as proxy.
        hours = 0.0
        try:
            hours = float(conn.execute(
                "SELECT COALESCE(SUM(hours),0) FROM attendance"
            ).fetchone()[0] or 0)
        except Exception:  # noqa: BLE001
            hours = 0.0
        return hse.summarise(incidents, hours_worked=hours)
    return _safe(run, 'HSE summarise incl. LTIFR when hours known')


def open_permits(conn):
    def run():
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT id, permit_no, status, valid_to FROM work_permits "
                "WHERE status='Open' ORDER BY id DESC LIMIT 20")]
        except Exception:  # noqa: BLE001
            rows = []
        return {'items': rows, 'count': len(rows)}
    return _safe(run, 'Open work permits')


def quote_compare(conn):
    def run():
        import sourcing
        req = conn.execute(
            'SELECT requisition_id AS id, COUNT(*) AS n FROM quotes '
            'GROUP BY requisition_id ORDER BY n DESC, requisition_id DESC '
            'LIMIT 1').fetchone()
        if not req:
            return {'items': [], 'note': 'No quotes recorded yet'}
        quotes = [dict(r) for r in conn.execute(
            'SELECT q.*, v.name AS vendor FROM quotes q '
            'LEFT JOIN vendors v ON v.id = q.vendor_id '
            'WHERE q.requisition_id = ?', (req['id'],))]
        compared = sourcing.compare_quotes(quotes)
        best, note = sourcing.recommendation(quotes)
        # Ranked may be dict-like quote rows — coerce for JSON.
        ranked = []
        for q in (compared.get('ranked') or []):
            ranked.append(dict(q) if hasattr(q, 'keys') else q)
        best_out = None
        if best is not None:
            best_out = dict(best) if hasattr(best, 'keys') else best
        return {
            'requisition_id': req['id'],
            'priced': compared.get('priced'),
            'spread': compared.get('spread'),
            'ranked': ranked,
            'recommendation': best_out,
            'note': note,
        }
    return _safe(run, 'Quote comparison for busiest requisition')


def pnl_hint(conn):
    def run():
        import reports_store
        return reports_store.pnl_payload(conn, period=None)
    return _safe(run, 'P&L snapshot (current / default period)')


def top_risks(conn):
    def run():
        import risk_store
        rows = risk_store.list_risks(conn, status='Open')
        out = []
        for r in list(rows)[:5]:
            out.append({
                'id': r['id'], 'title': r['title'], 'score': r['score'],
                'expected_exposure': r['expected_exposure'], 'band': r['band'],
            })
        return {'items': out, 'count': len(out)}
    return _safe(run, 'Top open risks by score')


def advisories(conn):
    def run():
        import advisory
        import dashboard
        snap = dashboard.collect(conn)
        return {'items': advisory.build(snap), 'snapshot_keys': sorted(snap)}
    return _safe(run, 'Home advisory rules over live snapshot')


# Registry: tool id → callable(conn) -> dict
TOOLS = {
    'money_snapshot': money_snapshot,
    'ageing_summary': ageing_summary,
    'cashflow_hint': cashflow_hint,
    'gst_totals': gst_totals,
    'retention_due': retention_due,
    'match_summary': match_summary,
    'open_pos': open_pos,
    'vendor_flags': vendor_flags,
    'requisition_open': requisition_open,
    'lookahead_ppc': lookahead_ppc,
    'programme_delay': programme_delay,
    'evm_portfolio': evm_portfolio,
    'rate_book_summary': rate_book_summary,
    'estimate_totals': estimate_totals,
    'lessons_rates': lessons_rates,
    'project_cost_hint': project_cost_hint,
    'boq_overview': boq_overview,
    'boq_duplicates': boq_duplicates,
    'measurement_progress': measurement_progress,
    'deviation_hint': deviation_hint,
    'sidecar_status': sidecar_status,
    'pdf_extract_hint': pdf_extract_hint,
    'takeoff_status': takeoff_status,
    'drawings_summary': drawings_summary,
    'element_totals': element_totals,
    'revision_delta_hint': revision_delta_hint,
    'open_rfis': open_rfis,
    'open_submittals': open_submittals,
    'contract_list': contract_list,
    'open_ncrs': open_ncrs,
    'open_snags': open_snags,
    'inspection_pass_rate': inspection_pass_rate,
    'muster_hint': muster_hint,
    'incident_summary': incident_summary,
    'ltifr_summary': ltifr_summary,
    'open_permits': open_permits,
    'quote_compare': quote_compare,
    'pnl_hint': pnl_hint,
    'top_risks': top_risks,
    'advisories': advisories,
}


def run_tool(name, conn):
    """Execute one tool by id. Unknown → ok=False."""
    fn = TOOLS.get(name)
    if fn is None:
        return {'ok': False, 'basis': name, 'error': 'Unknown tool'}
    # Tools that ignore conn still accept it
    try:
        return fn(conn)
    except TypeError:
        return fn()
