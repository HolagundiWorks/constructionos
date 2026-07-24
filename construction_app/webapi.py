"""JSON API over the domain core (U0 — WinUI / localhost client contract).

Stdlib only, tkinter-free. Every endpoint delegates to a pure/DB module and
serialises the result — **no business maths lives here**. Routed from
``webapp.handle`` for paths under ``/api/``; socket-free via
``Request → Response`` (same as the HTML layer).

Auth: the same session cookie (``cosid``) as the browser. Writes require a
role that can write (Admin/Operator) **and** a CSRF token — either the form
field ``csrf``, JSON body key ``csrf``, or header ``X-CSRF-Token``, matching
the session's minted token (``GET /api/me`` returns it).
"""

import json
import re

import advisory
import allocation
import auth
import boq_import
import capture
import cashflow_assemble
import dashboard
import drift
import event_hooks
import evm
import followups
import forecast
import finance
import grn_draft
import journal_post
import lessons_store
import menu
import modules
import muster_draft
import narrative
import nl_intent
import opportunity_store
import pattern_learn
import pdf_text
import portfolio_store
import review_assemble
import risk_store
import sidecar_bridge
import signal_feed
import signal_suggest
import submittals as submittals_mod
import text_extract
import takeoff_store
import drawing_geometry
import drawing_store
import revision_delta
import vendor_invoice_draft
import web_docs
import web_masters
import webapp
import workflow
import workflow_state

# Masters exposed as flat CRUD registers over the JSON API.
_API_MASTERS = (
    'sites', 'clients', 'vendors', 'materials', 'labor', 'equipment',
    'projects', 'milestones', 'thekedars', 'rate_book', 'contracts',
    'measurements',
)

# Money documents: create + list/get (no edit — records of fact).
_API_DOCS = tuple(web_docs.DOCS.keys())

# Read-only register tables the WinUI client surfaces as data tables (list only,
# newest first). A curated whitelist of existing DB tables — no writes, no
# arbitrary-table access. These back the Operations / Billing / Purchases /
# Accounts tabs that aren't a master, money doc, or a dedicated computed report.
_API_TABLES = (
    'attendance', 'payroll', 'equipment_hire', 'plant_logs', 'consumption_norms',
    'daily_progress', 'ncrs', 'incidents', 'snags', 'rate_analysis',
    'bid_assessments', 'quotations', 'estimates', 'variations',
    'material_requisitions', 'approvals', 'retention_releases', 'journal_entries',
    'timeline_tasks', 'material_ledger',
)

_RISK_ID = re.compile(r'^risks/(\d+)$')
_OPP_ID = re.compile(r'^opportunities/(\d+)$')
_LESSON_ID = re.compile(r'^lessons/(\d+)$')
_SUBMITTAL_ID = re.compile(r'^submittals/(\d+)$')
_MASTER_ID = re.compile(
    r'^(' + '|'.join(_API_MASTERS) + r')/(\d+)$')
_DOC_ID = re.compile(
    r'^(' + '|'.join(_API_DOCS) + r')/(\d+)$')
_PROJECT_EVM = re.compile(r'^project/(\d+)/evm$')


def handle(request, sess):
    """Dispatch one ``/api/...`` request. Caller has already authenticated."""
    path = request.path[len('/api'):].lstrip('/')  # '' or 'dashboard' etc.
    method = (request.method or 'GET').upper()

    if path in ('', 'health'):
        return _ok({'ok': True, 'service': 'aco', 'api': 'u0.16'})

    if path == 'me' and method == 'GET':
        return _ok({
            'username': sess['username'],
            'role': sess['role'],
            'csrf': sess['csrf'],
            'can_write': webapp.can_write(sess['role']),
        })

    if path == 'login' and method == 'POST':
        # Authenticated callers shouldn't hit this; login is handled before
        # sess exists. Kept as a clear 405 so clients don't guess wrong.
        return _err('Already signed in', 405)

    if path == 'contract' and method == 'GET':
        return _api_contract()

    if path == 'agents' and method == 'GET':
        return _agents_list()
    if path == 'agents/workflows' and method == 'GET':
        return _agents_workflows_list()
    if path == 'agents/provider' and method == 'GET':
        return _agents_provider()
    if path == 'agents/eval' and method == 'GET':
        return _agents_eval_cases()
    if path == 'agents/eval' and method == 'POST':
        return _agents_eval_run(request, sess)
    if path == 'agents/ask' and method == 'POST':
        return _agents_ask(request, sess)
    if path == 'agents/workflow' and method == 'POST':
        return _agents_workflow_run(request, sess)
    m = re.match(r'^agents/([a-z_]+)$', path)
    if m and method == 'GET':
        return _agents_get(m.group(1))

    if path == 'dashboard' and method == 'GET':
        return _dashboard()

    if path == 'kpi' and method == 'GET':
        return _key_numbers()

    if path == 'insight' and method == 'GET':
        return _insight()

    if path == 'home' and method == 'GET':
        return _home(request)

    if path == 'review' and method == 'GET':
        return _review()

    if path == 'portfolio' and method == 'GET':
        return _portfolio(request)

    if path == 'productivity' and method == 'GET':
        return _productivity(request)

    if path == 'filings/feed' and method == 'GET':
        return _filings_feed(request)

    # Tools / settings (Tools rail entry): firm letterhead identity + module
    # on/off toggles. Reads are open to any session; writes are CSRF + write-gated.
    if path == 'firm' and method == 'GET':
        return _firm_get()

    if path == 'firm' and method == 'POST':
        return _firm_save(request, sess)

    if path == 'modules' and method == 'GET':
        return _modules_get()

    if path == 'modules' and method == 'POST':
        return _modules_save(request, sess)

    if path == 'purchase_orders' and method == 'GET':
        return _list_ops_table('purchase_orders')

    if path == 'purchase_orders' and method == 'POST':
        return _create_purchase_order(request, sess)

    if path == 'goods_receipts' and method == 'GET':
        return _list_ops_table('goods_receipts')

    # Read-only register tables (Operations/Billing/Purchases/Accounts).
    if path in _API_TABLES and method == 'GET':
        return _list_ops_table(path)

    if path == 'match' and method == 'GET':
        return _three_way_match(request)

    if path == 'reconcile' and method == 'POST':
        return _reconcile(request)

    if path == 'ageing' and method == 'GET':
        return _ageing_summary(request)

    if path == 'cashflow' and method == 'GET':
        return _cashflow(request)

    if path == 'parties' and method == 'GET':
        return _parties()

    if path == 'gst' and method == 'GET':
        return _gst_report(request)

    if path == 'gst/export' and method == 'GET':
        return _gst_export(request)

    if path == 'pnl' and method == 'GET':
        return _pnl_report(request)

    if path in ('balance_sheet', 'balancesheet') and method == 'GET':
        return _balance_sheet_report(request)

    if path in ('lookahead', 'look-ahead') and method == 'GET':
        return _lookahead_report(request)

    if path == 'commitments' and method == 'GET':
        return _list_commitments(request)
    if path == 'commitments' and method == 'POST':
        return _create_commitment(request, sess)
    m = re.match(r'^commitments/(\d+)$', path)
    if m:
        cid = int(m.group(1))
        if method == 'GET':
            return _get_commitment(cid)
        if method == 'PUT':
            return _update_commitment(request, sess, cid)
        if method == 'DELETE':
            return _delete_commitment(request, sess, cid)
        if method == 'POST':
            # POST /api/commitments/{id} with {done:true|false, reason?}
            return _mark_commitment(request, sess, cid)

    if path == 'timeline' and method == 'GET':
        return _timeline(request)

    if path == 'ra_bills/generate' and method == 'POST':
        return _ra_generate(request, sess)

    if path == 'work_orders' and method == 'GET':
        return _list_work_orders()
    if path == 'work_orders' and method == 'POST':
        return _create_work_order(request, sess)
    m = re.match(r'^work_orders/(\d+)$', path)
    if m:
        wid = int(m.group(1))
        if method == 'GET':
            return _get_work_order(wid)
        if method == 'PUT':
            return _update_work_order(request, sess, wid)
        if method == 'DELETE':
            return _delete_work_order(request, sess, wid)

    if path == 'sub_bills' and method == 'GET':
        return _list_sub_bills(request)
    if path == 'sub_bills' and method == 'POST':
        return _create_sub_bill(request, sess)
    m = re.match(r'^sub_bills/(\d+)$', path)
    if m:
        bid = int(m.group(1))
        if method == 'GET':
            return _get_sub_bill(bid)
        if method == 'PUT':
            return _update_sub_bill(request, sess, bid)
        if method == 'DELETE':
            return _delete_sub_bill(request, sess, bid)

    if path == 'muster' and method == 'GET':
        return _muster_grid(request)
    if path == 'muster' and method == 'POST':
        return _muster_save(request, sess)
    if path == 'muster/payout' and method == 'GET':
        return _muster_payout_compute(request)
    if path == 'muster/payout' and method == 'POST':
        return _muster_payout_record(request, sess)

    if path == 'bills/previous' and method == 'GET':
        return _bills_previous(request)

    if path == 'boq_items' and method == 'GET':
        return _list_boq_items(request)

    if path == 'allocations' and method == 'GET':
        return _list_allocations(request)

    if path == 'allocations' and method == 'POST':
        return _save_allocations(request, sess)

    if path == 'menu' and method == 'GET':
        return _menu(request)

    if path == 'workflow' and method == 'GET':
        return _workflow(request)

    if path == 'search' and method == 'GET':
        return _search(request)

    if path == 'intent' and method == 'POST':
        return _intent(request)

    if path == 'sidecar/status' and method == 'GET':
        return _sidecar_status()

    if path == 'sidecar/extract' and method == 'POST':
        return _sidecar_extract(request)

    if path == 'takeoffs' and method == 'GET':
        return _list_ops_table('takeoffs')
    if path == 'takeoffs' and method == 'POST':
        return _takeoffs_save(request, sess)
    m = re.match(r'^takeoffs/(\d+)$', path)
    if m and method == 'GET':
        return _takeoffs_get(int(m.group(1)))
    if m and method == 'PUT':
        return _takeoffs_save(request, sess, takeoff_id=int(m.group(1)))
    if m and method == 'DELETE':
        return _takeoffs_delete(request, sess, int(m.group(1)))
    m = re.match(r'^takeoffs/(\d+)/to-estimate$', path)
    if m and method == 'POST':
        return _takeoffs_to_estimate(request, sess, int(m.group(1)))

    if path == 'drawings/elements/draft' and method == 'POST':
        return _drawing_elements_draft(request)
    if path == 'drawings/elements/confirm' and method == 'POST':
        return _drawing_elements_confirm(request, sess)
    if path == 'drawings/elements/ingest' and method == 'POST':
        return _drawing_elements_ingest(request)
    if path == 'drawings/revision-delta' and method == 'POST':
        return _drawing_revision_delta(request)
    if path == 'drawings/revision-delta/confirm' and method == 'POST':
        return _drawing_revision_delta_confirm(request, sess)
    m = re.match(r'^drawings/(\d+)/elements$', path)
    if m and method == 'GET':
        return _drawing_elements_list(int(m.group(1)))

    if path == 'narrative' and method == 'GET':
        return _narrative(request)

    if path == 'text/extract' and method == 'POST':
        return _text_extract(request)

    if path == 'muster/draft' and method == 'POST':
        return _muster_draft(request)

    if path == 'muster/confirm' and method == 'POST':
        return _muster_confirm(request, sess)

    if path == 'boq/import/draft' and method == 'POST':
        return _boq_import_draft(request)

    if path == 'boq/import/confirm' and method == 'POST':
        return _boq_import_confirm(request, sess)

    if path == 'patterns/learn' and method == 'POST':
        return _patterns_learn(request, sess)

    if path == 'signals/preview' and method == 'POST':
        return _signals_preview(request)

    if path == 'signals/suggest' and method == 'POST':
        return _signals_suggest(request, sess)

    if path == 'grn/draft' and method == 'POST':
        return _grn_draft(request)

    if path == 'grn/confirm' and method == 'POST':
        return _grn_confirm(request, sess)

    if path == 'vendor_invoice/draft' and method == 'POST':
        return _vendor_invoice_draft(request)

    if path == 'vendor_invoice/confirm' and method == 'POST':
        return _vendor_invoice_confirm(request, sess)

    if path == 'pdf/extract' and method == 'POST':
        return _pdf_extract(request)

    if path == 'capture/draft' and method == 'POST':
        return _capture_draft(request, sess)

    if path == 'capture/confirm' and method == 'POST':
        return _capture_confirm(request, sess)

    if path == 'evm' and method == 'GET':
        return _evm_portfolio()

    m = _PROJECT_EVM.match(path)
    if m and method == 'GET':
        return _evm_project(int(m.group(1)))

    if path == 'forecast' and method == 'POST':
        return _post_forecast(request)

    if path == 'drift' and method == 'POST':
        return _post_drift(request)

    # Assistant — read-only text-to-SQL over the user's own data. Quick answers
    # are exact and need no model; the ask endpoint runs the RAG pipeline (which
    # needs the local AI engine, else returns a friendly {error}). Read-only.
    if path == 'assistant/quick' and method == 'GET':
        return _assistant_quick()

    if path == 'assistant' and method == 'POST':
        return _assistant_answer(request)

    if path == 'events' and method == 'POST':
        return _post_event(request, sess)

    if path == 'signals/feed' and method == 'POST':
        return _post_signal_feed(request, sess)

    if path == 'audit' and method == 'GET':
        return _list_audit(request)

    if path == 'submittals':
        if method == 'GET':
            return _list_submittals(request)
        if method == 'POST':
            return _create_submittal(request, sess)
    m = _SUBMITTAL_ID.match(path)
    if m:
        sid = int(m.group(1))
        if method == 'GET':
            return _get_submittal(sid)
        if method == 'PUT':
            return _update_submittal(request, sess, sid)
        if method == 'DELETE':
            return _delete_submittal(request, sess, sid)

    if path == 'lessons':
        if method == 'GET':
            return _list_lessons(request)
        if method == 'POST':
            return _create_lesson(request, sess)
    m = _LESSON_ID.match(path)
    if m:
        lid = int(m.group(1))
        if method == 'GET':
            return _get_lesson(lid)
        if method == 'PUT':
            return _update_lesson(request, sess, lid)
        if method == 'DELETE':
            return _delete_lesson(request, sess, lid)

    if path == 'risks/detect' and method == 'POST':
        return _risks_detect(request, sess)
    if path == 'risks/accept' and method == 'POST':
        return _risks_accept(request, sess)

    if path == 'risks':
        if method == 'GET':
            return _list_risks(request)
        if method == 'POST':
            return _create_risk(request, sess)
    m = _RISK_ID.match(path)
    if m:
        rid = int(m.group(1))
        if method == 'GET':
            return _get_risk(rid)
        if method == 'PUT':
            return _update_risk(request, sess, rid)
        if method == 'DELETE':
            return _delete_risk(request, sess, rid)

    if path == 'opportunities':
        if method == 'GET':
            return _list_opps(request)
        if method == 'POST':
            return _create_opp(request, sess)
    m = _OPP_ID.match(path)
    if m:
        oid = int(m.group(1))
        if method == 'GET':
            return _get_opp(oid)
        if method == 'PUT':
            return _update_opp(request, sess, oid)
        if method == 'DELETE':
            return _delete_opp(request, sess, oid)

    # Money documents (create + list/get only)
    if path in _API_DOCS:
        if method == 'GET':
            return _list_doc(path)
        if method == 'POST':
            return _create_doc(request, sess, path)
    m = _DOC_ID.match(path)
    if m:
        table, rid = m.group(1), int(m.group(2))
        if method == 'GET':
            return _get_doc(table, rid)
        return _err('Money documents are create+view only', 405)

    if path in _API_MASTERS:
        if method == 'GET':
            return _list_master(path, request)
        if method == 'POST':
            return _create_master(request, sess, path)
    m = _MASTER_ID.match(path)
    if m:
        table, rid = m.group(1), int(m.group(2))
        if method == 'GET':
            return _get_master(table, rid)
        if method == 'PUT':
            return _update_master(request, sess, table, rid)
        if method == 'DELETE':
            return _delete_master(request, sess, table, rid)

    return _err('Not found', 404)


# ------------------------------------------------------------------ helpers
def _ok(payload, status=200):
    body = json.dumps(payload, default=_json_default, ensure_ascii=False)
    return webapp.Response(body, status=status,
                           content_type='application/json; charset=utf-8')


def _err(message, status=400, **extra):
    payload = {'error': message}
    payload.update(extra)
    return _ok(payload, status=status)


def _json_default(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return str(obj)


def _row(r):
    if r is None:
        return None
    return {k: r[k] for k in r.keys()}


def _rows(seq):
    return [_row(r) for r in seq]


def _payload(request):
    """JSON body if present, else form fields (strings)."""
    if getattr(request, 'json_body', None) is not None:
        data = request.json_body
        return data if isinstance(data, dict) else {}
    return dict(request.form or {})


def _csrf_ok(request, sess):
    token = sess.get('csrf')
    if not token:
        return False
    if request.form.get('csrf') == token:
        return True
    header = (request.headers or {}).get('X-CSRF-Token') or \
             (request.headers or {}).get('X-Csrf-Token') or ''
    if header == token:
        return True
    body = getattr(request, 'json_body', None) or {}
    if isinstance(body, dict) and body.get('csrf') == token:
        return True
    return False


def _require_write(request, sess):
    if not webapp.can_write(sess['role']):
        return _err('Read-only (Viewer)', 403)
    if not _csrf_ok(request, sess):
        return _err('CSRF token missing or invalid', 403)
    return None


def _conn():
    import db
    return db.get_conn()


# ----------------------------------------------------------------- endpoints
def _dashboard():
    conn = _conn()
    try:
        snap = dashboard.collect(conn)
        # Drop non-JSON-friendly nested bits that are list-of-tuples etc. —
        # advisory rebuilds from the snapshot cleanly.
        advisories = advisory.build(snap)
        return _ok({'snapshot': snap, 'advisories': advisories})
    finally:
        conn.close()


def _review():
    conn = _conn()
    try:
        return _ok(review_assemble.assemble(conn))
    finally:
        conn.close()


def _menu(request):
    persona = (request.query.get('persona') or menu.OWNER).strip() or menu.OWNER
    conn = _conn()
    try:
        enabled = modules.enabled_map(conn)
    finally:
        conn.close()

    def is_on(label):
        return enabled.get(label, True)

    sections = []
    for title, tabs in menu.resolve(persona, is_enabled=is_on):
        groups = [{'label': g, 'tabs': list(t)}
                  for g, t in menu.groups_for(title, tabs)]
        sections.append({'title': title, 'tabs': list(tabs), 'groups': groups})
    return _ok({
        'persona': persona,
        'personas': list(menu.PERSONAS),
        'always_on': list(menu.ALWAYS_ON),
        'sections': sections,
    })


def _workflow(request):
    # Optional per-flow completion state as query: state.<flow>.<key>=1
    # With no explicit state (or ?infer=1), derive completion from the books.
    state_by_flow = {}
    for key, val in (request.query or {}).items():
        if not key.startswith('state.'):
            continue
        parts = key.split('.', 2)
        if len(parts) != 3:
            continue
        _, flow, step = parts
        state_by_flow.setdefault(flow, {})[step] = val in ('1', 'true', 'True')
    infer = (request.query or {}).get('infer', '1') in ('1', 'true', 'True')
    if not state_by_flow and infer:
        conn = _conn()
        try:
            state_by_flow = workflow_state.infer(conn)
        finally:
            conn.close()
    elif not state_by_flow:
        state_by_flow = {name: {} for name in workflow.WORKFLOWS}
    progress = workflow.all_progress(state_by_flow)
    # serialise next_step objects
    out = {}
    for name, info in progress.items():
        nxt = info.get('next')
        out[name] = {
            'done': info.get('done'),
            'total': info.get('total'),
            'pct': info.get('pct'),
            'next': nxt,
            'complete': info.get('complete'),
        }
    return _ok({
        'workflows': {
            name: [{'key': s['key'], 'label': s['label'],
                    'section': s['section'], 'tab': s['tab']}
                   for s in steps]
            for name, steps in workflow.WORKFLOWS.items()
        },
        'progress': out,
        'inferred': bool(infer and not any(
            k.startswith('state.') for k in (request.query or {}))),
    })


def _evm_portfolio():
    conn = _conn()
    try:
        rows, port = evm.portfolio_evm(conn)
        # Chart-ready parallel arrays (WinUI LiveCharts); detail unchanged.
        labels = [r.get('name') or '' for r in rows]
        values = [
            (r.get('spi') if r.get('spi') is not None else 0.0) for r in rows
        ]
        return _ok({
            'rows': rows,
            'portfolio': port,
            'labels': labels,
            'values': values,
        })
    finally:
        conn.close()


def _evm_project(pid):
    conn = _conn()
    try:
        row = conn.execute('SELECT * FROM projects WHERE id = ?',
                           (pid,)).fetchone()
        if row is None:
            return _err('Project not found', 404)
        return _ok(evm.project_evm(conn, row))
    finally:
        conn.close()


def _list_risks(request):
    conn = _conn()
    try:
        project_id = request.query.get('project_id')
        status = request.query.get('status')
        pid = int(project_id) if project_id not in (None, '') else None
        rows = risk_store.list_risks(conn, project_id=pid, status=status or None)
        return _ok({
            'items': _rows(rows),
            'summary': risk_store.summary(conn, project_id=pid),
        })
    finally:
        conn.close()


def _get_risk(rid):
    conn = _conn()
    try:
        row = risk_store.get(conn, rid)
        if row is None:
            return _err('Risk not found', 404)
        return _ok(_row(row))
    finally:
        conn.close()


def _create_risk(request, sess):
    denied = _require_write(request, sess)
    if denied:
        return denied
    fields = _payload(request)
    fields.pop('csrf', None)
    origin = auth.ORIGIN_AI if fields.get('source') == 'ai' else auth.ORIGIN_MANUAL
    conn = _conn()
    try:
        new_id = risk_store.add(conn, **fields)
        auth.audit(conn, sess['username'], 'api_create', 'risks', new_id,
                   origin=origin)
        conn.commit()
        return _ok(_row(risk_store.get(conn, new_id)), status=201)
    finally:
        conn.close()


def _update_risk(request, sess, rid):
    denied = _require_write(request, sess)
    if denied:
        return denied
    fields = _payload(request)
    fields.pop('csrf', None)
    conn = _conn()
    try:
        if risk_store.get(conn, rid) is None:
            return _err('Risk not found', 404)
        risk_store.update(conn, rid, **fields)
        auth.audit(conn, sess['username'], 'api_update', 'risks', rid)
        conn.commit()          # the store committed the change; persist the audit too
        return _ok(_row(risk_store.get(conn, rid)))
    finally:
        conn.close()


def _delete_risk(request, sess, rid):
    denied = _require_write(request, sess)
    if denied:
        return denied
    conn = _conn()
    try:
        if risk_store.get(conn, rid) is None:
            return _err('Risk not found', 404)
        risk_store.delete(conn, rid)
        auth.audit(conn, sess['username'], 'api_delete', 'risks', rid)
        conn.commit()          # persist the audit alongside the store's delete
        return _ok({'deleted': rid})
    finally:
        conn.close()


def _list_opps(request):
    conn = _conn()
    try:
        project_id = request.query.get('project_id')
        status = request.query.get('status')
        pid = int(project_id) if project_id not in (None, '') else None
        rows = opportunity_store.list_opportunities(
            conn, project_id=pid, status=status or None)
        return _ok({'items': _rows(rows),
                    'summary': opportunity_store.summary(conn, project_id=pid)})
    finally:
        conn.close()


def _get_opp(oid):
    conn = _conn()
    try:
        row = opportunity_store.get(conn, oid)
        if row is None:
            return _err('Opportunity not found', 404)
        return _ok(_row(row))
    finally:
        conn.close()


def _create_opp(request, sess):
    denied = _require_write(request, sess)
    if denied:
        return denied
    fields = _payload(request)
    fields.pop('csrf', None)
    conn = _conn()
    try:
        new_id = opportunity_store.add(conn, **fields)
        auth.audit(conn, sess['username'], 'api_create', 'opportunities', new_id)
        conn.commit()          # the store committed the row; persist the audit too
        return _ok(_row(opportunity_store.get(conn, new_id)), status=201)
    finally:
        conn.close()


def _update_opp(request, sess, oid):
    denied = _require_write(request, sess)
    if denied:
        return denied
    fields = _payload(request)
    fields.pop('csrf', None)
    conn = _conn()
    try:
        if opportunity_store.get(conn, oid) is None:
            return _err('Opportunity not found', 404)
        opportunity_store.update(conn, oid, **fields)
        auth.audit(conn, sess['username'], 'api_update', 'opportunities', oid)
        conn.commit()          # persist the audit alongside the store's update
        return _ok(_row(opportunity_store.get(conn, oid)))
    finally:
        conn.close()


def _delete_opp(request, sess, oid):
    denied = _require_write(request, sess)
    if denied:
        return denied
    conn = _conn()
    try:
        if opportunity_store.get(conn, oid) is None:
            return _err('Opportunity not found', 404)
        opportunity_store.delete(conn, oid)
        auth.audit(conn, sess['username'], 'api_delete', 'opportunities', oid)
        conn.commit()          # persist the audit alongside the store's delete
        return _ok({'deleted': oid})
    finally:
        conn.close()


def _list_master(table, request=None):
    conn = _conn()
    try:
        where, params = '', []
        q = (request.query if request else None) or {}
        # Optional FK filters used by WinUI drill-downs (measurements by contract).
        if table == 'measurements' and q.get('contract_id') not in (None, ''):
            try:
                where, params = ' WHERE contract_id = ?', [int(q['contract_id'])]
            except (TypeError, ValueError):
                return _err('contract_id must be an integer', 400)
        rows = conn.execute(
            'SELECT * FROM "{}"{} ORDER BY id DESC LIMIT 500'.format(
                table, where),
            params,
        ).fetchall()
        return _ok({
            'table': table,
            'label': web_masters.label(table),
            'fields': web_masters.enrich_fields(conn, web_masters.fields(table)),
            'items': _rows(rows),
        })
    finally:
        conn.close()


def _get_master(table, rid):
    conn = _conn()
    try:
        row = conn.execute(
            'SELECT * FROM "{}" WHERE id = ?'.format(table), (rid,)
        ).fetchone()
        if row is None:
            return _err('Not found', 404)
        return _ok(_row(row))
    finally:
        conn.close()


def _collect_master_values(table, payload):
    """Validate payload against web_masters field specs → (ok, values, error)."""
    values = {}
    for field in web_masters.fields(table):
        key = field['key']
        if key not in payload:
            if field.get('required') and not field.get('default'):
                return False, None, '{} is required.'.format(field['label'])
            raw = web_masters.resolve_default(field.get('default', ''))
        else:
            raw = payload[key]
            if raw is None:
                raw = ''
            elif not isinstance(raw, str):
                raw = str(raw)
        ok, val, err = web_masters.coerce(field, raw)
        if not ok:
            return False, None, err
        values[key] = val
    return True, values, None


def _create_master(request, sess, table):
    denied = _require_write(request, sess)
    if denied:
        return denied
    ok, values, err = _collect_master_values(table, _payload(request))
    if not ok:
        return _err(err, 400)
    # Derive computed columns (e.g. measurements.quantity) before insert —
    # same path as the browser register (web_masters.derive).
    values = web_masters.derive(table, values)
    conn = _conn()
    try:
        cols = list(values.keys())
        sql = 'INSERT INTO "{}" ({}) VALUES ({})'.format(
            table, ', '.join('"{}"'.format(c) for c in cols),
            ', '.join('?' for _ in cols))
        cur = conn.execute(sql, [values[c] for c in cols])
        new_id = cur.lastrowid
        auth.audit(conn, sess['username'], 'api_create', table, new_id)
        conn.commit()
        row = conn.execute(
            'SELECT * FROM "{}" WHERE id = ?'.format(table), (new_id,)
        ).fetchone()
        return _ok(_row(row), status=201)
    finally:
        conn.close()


def _update_master(request, sess, table, rid):
    denied = _require_write(request, sess)
    if denied:
        return denied
    payload = _payload(request)
    # Partial update: only keys present; still coerce via field specs.
    conn = _conn()
    try:
        existing = conn.execute(
            'SELECT * FROM "{}" WHERE id = ?'.format(table), (rid,)
        ).fetchone()
        if existing is None:
            return _err('Not found', 404)
        merged = {k: existing[k] for k in existing.keys() if k != 'id'}
        for field in web_masters.fields(table):
            key = field['key']
            if key not in payload:
                continue
            raw = payload[key]
            if raw is None:
                raw = ''
            elif not isinstance(raw, str):
                raw = str(raw)
            ok, val, err = web_masters.coerce(field, raw)
            if not ok:
                return _err(err, 400)
            merged[key] = val
        # Re-derive after merge so quantity / obligation keys stay consistent.
        derived = web_masters.derive(table, {
            k: merged[k] for k in merged
            if k in {f['key'] for f in web_masters.fields(table)}
            or k in ('quantity',)
        })
        merged.update(derived)
        field_keys = {f['key'] for f in web_masters.fields(table)}
        # Include derived columns that aren't form fields (quantity).
        cols = [c for c in merged if c in field_keys or c in ('quantity',)]
        sql = 'UPDATE "{}" SET {} WHERE id = ?'.format(
            table, ', '.join('"{}" = ?'.format(c) for c in cols))
        conn.execute(sql, [merged[c] for c in cols] + [rid])
        auth.audit(conn, sess['username'], 'api_update', table, rid)
        conn.commit()
        row = conn.execute(
            'SELECT * FROM "{}" WHERE id = ?'.format(table), (rid,)
        ).fetchone()
        return _ok(_row(row))
    finally:
        conn.close()


def _delete_master(request, sess, table, rid):
    denied = _require_write(request, sess)
    if denied:
        return denied
    conn = _conn()
    try:
        existing = conn.execute(
            'SELECT id FROM "{}" WHERE id = ?'.format(table), (rid,)
        ).fetchone()
        if existing is None:
            return _err('Not found', 404)
        try:
            conn.execute('DELETE FROM "{}" WHERE id = ?'.format(table), (rid,))
        except Exception as exc:  # noqa: BLE001 — FK integrity → plain error
            return _err('Cannot delete: record is still used elsewhere ({})'
                        .format(exc), 409)
        auth.audit(conn, sess['username'], 'api_delete', table, rid)
        conn.commit()
        return _ok({'deleted': rid})
    finally:
        conn.close()


# ------------------------------------------------------- lessons / events / feed
def _list_lessons(request):
    conn = _conn()
    try:
        project_id = request.query.get('project_id')
        status = request.query.get('status')
        category = request.query.get('category')
        pid = int(project_id) if project_id not in (None, '') else None
        rows = lessons_store.list_lessons(
            conn, project_id=pid, category=category or None,
            status=status or None)
        return _ok({
            'items': _rows(rows),
            'summary': lessons_store.summary(conn, project_id=pid),
            'feed_forward': _rows(lessons_store.feed_forward(conn, project_id=pid)),
        })
    finally:
        conn.close()


def _get_lesson(lid):
    conn = _conn()
    try:
        row = lessons_store.get(conn, lid)
        if row is None:
            return _err('Lesson not found', 404)
        return _ok(_row(row))
    finally:
        conn.close()


def _create_lesson(request, sess):
    denied = _require_write(request, sess)
    if denied:
        return denied
    fields = _payload(request)
    fields.pop('csrf', None)
    conn = _conn()
    try:
        new_id = lessons_store.add(conn, **fields)
        auth.audit(conn, sess['username'], 'api_create', 'lessons_learned',
                   new_id, origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(_row(lessons_store.get(conn, new_id)), status=201)
    finally:
        conn.close()


def _update_lesson(request, sess, lid):
    denied = _require_write(request, sess)
    if denied:
        return denied
    fields = _payload(request)
    fields.pop('csrf', None)
    conn = _conn()
    try:
        if lessons_store.get(conn, lid) is None:
            return _err('Lesson not found', 404)
        lessons_store.update(conn, lid, **fields)
        auth.audit(conn, sess['username'], 'api_update', 'lessons_learned',
                   lid, origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(_row(lessons_store.get(conn, lid)))
    finally:
        conn.close()


def _delete_lesson(request, sess, lid):
    denied = _require_write(request, sess)
    if denied:
        return denied
    conn = _conn()
    try:
        if lessons_store.get(conn, lid) is None:
            return _err('Lesson not found', 404)
        lessons_store.delete(conn, lid)
        auth.audit(conn, sess['username'], 'api_delete', 'lessons_learned',
                   lid, origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok({'deleted': lid})
    finally:
        conn.close()


def _post_event(request, sess):
    """POST /api/events — {event, payload?, apply_risks?, snapshot?}

    Returns follow-ups + optional detected risks. When ``apply_risks`` is true
    and the caller can write, detected risks are persisted as AI drafts.
    """
    body = _payload(request)
    event = (body.get('event') or '').strip()
    if not event:
        return _err('event is required', 400)
    payload = body.get('payload') if isinstance(body.get('payload'), dict) else {}
    snapshot = body.get('snapshot')
    if snapshot is None and body.get('include_detect'):
        # Collect a live snapshot when asked — keeps the client thin.
        conn = _conn()
        try:
            snapshot = dashboard.collect(conn)
        finally:
            conn.close()
    result = event_hooks.react(event, payload=payload, snapshot=snapshot)
    applied = []
    if body.get('apply_risks') and result['risks']:
        denied = _require_write(request, sess)
        if denied:
            return denied
        conn = _conn()
        try:
            applied = event_hooks.apply_risk_drafts(
                conn, result['risks'], username=sess['username'])
        finally:
            conn.close()
    result['applied_risk_ids'] = applied
    return _ok(result)


def _post_signal_feed(request, sess):
    """POST /api/signals/feed — prediction signals → draft risks.

    Body keys (all optional): ``drift``, ``schedule_forecast``, ``cost_trend``,
    ``project_id``, ``ld_exposure``, ``apply`` (default true).
    """
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    drafts = signal_feed.collect(
        drift=body.get('drift'),
        schedule_forecast=body.get('schedule_forecast'),
        cost_trend=body.get('cost_trend'),
        project_id=body.get('project_id'),
        ld_exposure=body.get('ld_exposure') or 0,
    )
    apply = body.get('apply', True)
    ids = []
    if apply and drafts:
        conn = _conn()
        try:
            ids = signal_feed.apply_drafts(
                conn, drafts, username=sess['username'])
        finally:
            conn.close()
    return _ok({'drafts': drafts, 'applied_ids': ids,
                'applied': bool(apply and ids)})


def _list_audit(request):
    origin = request.query.get('origin') or None
    try:
        limit = int(request.query.get('limit') or 100)
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 500))
    conn = _conn()
    try:
        rows = auth.recent_audit(conn, limit=limit, origin=origin)
        return _ok({'items': _rows(rows)})
    finally:
        conn.close()


# ------------------------------------- contract / portfolio / forecast / drift
def _api_contract():
    """Machine-readable endpoint map for WinUI / clients (C2 DTO coverage)."""
    return _ok({
        'api': 'u0.16',
        'auth': {
            'login': 'POST /api/login {username,password,company?}',
            'companies': 'GET /api/companies (public)',
            'session_cookie': 'cosid',
            'csrf_header': 'X-CSRF-Token',
            'me': 'GET /api/me',
        },
        'reads': [
            'GET /api/health', 'GET /api/contract', 'GET /api/companies',
            'GET /api/dashboard', 'GET /api/home', 'GET /api/kpi', 'GET /api/insight',
            'GET /api/review',
            'GET /api/portfolio', 'GET /api/menu?persona=',
            'GET /api/productivity', 'GET /api/filings/feed',
            'GET /api/firm', 'GET /api/modules', 'GET /api/assistant/quick',
            'GET /api/parties',
            'GET /api/agents', 'GET /api/agents/{id}', 'GET /api/agents/workflows',
            'GET /api/agents/provider', 'GET /api/agents/eval',
            'GET /api/purchase_orders', 'GET /api/goods_receipts',
            'GET /api/work_orders', 'GET /api/sub_bills',
            'GET /api/match', 'GET /api/ageing', 'GET /api/cashflow',
            'GET /api/gst?month=', 'GET /api/gst/export?month=',
            'GET /api/pnl?period=', 'GET /api/balance_sheet?as_of=',
            'GET /api/lookahead?project_id=&weeks=',
            'GET /api/commitments', 'GET /api/timeline?project_id=',
            'GET /api/muster?site_id=&att_date=',
            'GET /api/muster/payout?site_id=&week_start=',
            'GET /api/bills/previous?contract_id=',
            'GET /api/boq_items?contract_id=',
            'GET /api/allocations?payment_id=',
            'GET /api/workflow', 'GET /api/evm',
            'GET /api/project/{id}/evm',
            'GET /api/risks', 'GET /api/opportunities', 'GET /api/lessons',
            'GET /api/submittals', 'GET /api/audit?origin=',
            'GET /api/search?q=', 'GET /api/narrative?kind=',
            'GET /api/sidecar/status',
            'GET /api/takeoffs', 'GET /api/takeoffs/{id}',
            'GET /api/drawings/{id}/elements',
            'GET /api/{master}', 'GET /api/{doc}',
            'GET /api/{register}  (label+columns+FK names)',
        ],
        'writes': [
            'POST /api/agents/ask', 'POST /api/agents/workflow',
            'POST /api/agents/eval',
            'POST/PUT/DELETE /api/risks[/{id}]',
            'POST /api/risks/detect', 'POST /api/risks/accept',
            'POST/PUT/DELETE /api/opportunities[/{id}]',
            'POST/PUT/DELETE /api/lessons[/{id}]',
            'POST/PUT/DELETE /api/submittals[/{id}]',
            'POST /api/capture/draft', 'POST /api/capture/confirm',
            'POST /api/text/extract',
            'POST /api/muster/draft', 'POST /api/muster/confirm',
            'GET|POST /api/muster', 'GET|POST /api/muster/payout',
            'POST /api/boq/import/draft', 'POST /api/boq/import/confirm',
            'POST /api/ra_bills/generate',
            'POST/PUT/DELETE /api/work_orders[/{id}]',
            'POST/PUT/DELETE /api/sub_bills[/{id}]',
            'POST/PUT/DELETE /api/commitments[/{id}]',
            'POST /api/grn/draft', 'POST /api/grn/confirm',
            'POST /api/vendor_invoice/draft', 'POST /api/vendor_invoice/confirm',
            'POST /api/pdf/extract',
            'POST /api/patterns/learn',
            'POST /api/signals/preview', 'POST /api/signals/suggest',
            'POST /api/reconcile', 'POST /api/intent',
            'POST /api/sidecar/extract',
            'POST/PUT/DELETE /api/takeoffs[/{id}]',
            'POST /api/takeoffs/{id}/to-estimate',
            'POST /api/drawings/elements/draft',
            'POST /api/drawings/elements/confirm',
            'POST /api/drawings/elements/ingest',
            'POST /api/drawings/revision-delta',
            'POST /api/drawings/revision-delta/confirm',
            'POST /api/purchase_orders',
            'POST /api/allocations',
            'POST /api/firm', 'POST /api/modules', 'POST /api/assistant',
            'POST/PUT/DELETE /api/{master}[/{id}]',
            'POST /api/{doc}  (create only: payments, tax_invoices, …)',
            'POST /api/events', 'POST /api/signals/feed',
            'POST /api/forecast', 'POST /api/drift',
        ],
        'masters': list(_API_MASTERS),
        'docs': list(_API_DOCS),
        'personas': list(menu.PERSONAS),
        'chart_bind': {
            'cashflow': 'labels + values (balance) + series.{in,out,balance}',
            'ageing': 'labels + values (bucket amounts)',
            'evm': 'labels (project name) + values (SPI)',
        },
    })


def _portfolio(request):
    """Current-file portfolio roll-up; optional ``?paths=a.db,b.db`` federates."""
    raw = (request.query.get('paths') or '').strip()
    if raw:
        paths = [p.strip() for p in raw.split(',') if p.strip()]
        roll = portfolio_store.roll_up(paths)
        roll['advisories'] = advisory.for_portfolio(roll.get('per_file') or [])
        return _ok(roll)
    conn = _conn()
    try:
        current = portfolio_store.file_rollup(conn, name='current')
        return _ok({
            'current': current,
            'federated': False,
            'advisories': advisory.for_portfolio([current]),
        })
    finally:
        conn.close()


def _productivity(request):
    """GET /api/productivity — crew/plant utilisation from muster + plant logs."""
    import productivity_store
    conn = _conn()
    try:
        return _ok(productivity_store.firm_summary(
            conn,
            from_date=(request.query or {}).get('from'),
            to_date=(request.query or {}).get('to')))
    finally:
        conn.close()


def _filings_feed(request):
    """GET /api/filings/feed — overdue/due-soon → gated FILING_DUE drafts."""
    import compliance
    import compliance_feed
    conn = _conn()
    try:
        raw = conn.execute(
            'SELECT * FROM compliance_filings ORDER BY due_date').fetchall()
        plain = [{k: r[k] for k in r.keys()} for r in raw]
    except Exception:  # noqa: BLE001
        plain = []
    finally:
        conn.close()
    late = compliance.overdue(plain)
    soon = compliance.upcoming(plain, within_days=30)
    events = compliance_feed.filing_events(late + soon)
    return _ok({
        'overdue': len(late),
        'due_soon': len(soon),
        'events': events,
        'gated_count': sum(e.get('gated_count', 0) for e in events),
    })


def _firm_get():
    """GET /api/firm — the firm's letterhead identity fields for an editable
    form: ``{fields: [{key, label, value}]}`` in ``firm.FIELDS`` order."""
    import firm
    conn = _conn()
    try:
        saved = {r['key']: (r['value'] or '') for r in conn.execute(
            "SELECT key, value FROM app_settings WHERE key LIKE 'firm_%' "
            "OR key IN ('company_name', 'seller_gstin', 'seller_address')")}
    finally:
        conn.close()
    return _ok({'fields': [
        {'key': k, 'label': label, 'value': saved.get(k, '')}
        for k, label in firm.FIELDS]})


def _firm_save(request, sess):
    """POST /api/firm — persist the firm letterhead fields (whitelisted to
    ``firm.FIELDS`` keys). Returns the saved fields."""
    denied = _require_write(request, sess)
    if denied:
        return denied
    import firm
    body = _payload(request)
    body.pop('csrf', None)
    allowed = {k for k, _ in firm.FIELDS}
    conn = _conn()
    try:
        for key in allowed:
            if key in body:
                conn.execute(
                    'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                    'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                    (key, str(body.get(key) or '').strip()))
        conn.commit()
    finally:
        conn.close()
    return _firm_get()


def _modules_get():
    """GET /api/modules — per-section module on/off states (absent = enabled),
    for the Tools toggle grid: ``{sections: [{title, tabs:[{label, enabled}]}]}``."""
    conn = _conn()
    try:
        states = modules.enabled_map(conn)
    finally:
        conn.close()
    return _ok({'sections': [
        {'title': title,
         'tabs': [{'label': label, 'enabled': states.get(label, True)}
                  for label in labels]}
        for title, labels in modules.SECTIONS_CATALOG]})


def _modules_save(request, sess):
    """POST /api/modules — persist a ``{states: {label: bool}}`` map (whitelisted
    to real catalog labels). Hidden modules drop out of the menu next login."""
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    body.pop('csrf', None)
    states = body.get('states')
    if not isinstance(states, dict):
        return _err('states must be an object of label -> bool', 400)
    valid = set(modules.ALL_MODULES)
    clean = {k: bool(v) for k, v in states.items() if k in valid}
    if not clean:
        return _err('no known module labels in states', 400)
    conn = _conn()
    try:
        modules.set_states(conn, clean)
    finally:
        conn.close()
    return _modules_get()


def _list_ops_table(table):
    """Read-only list of a whitelisted register table (newest first when the
    table has an ``id``; otherwise natural order). Returns curated ``label`` /
    ``columns`` and FK-resolved ``items`` via ``web_tables`` (CT-6)."""
    import web_tables
    conn = _conn()
    try:
        try:
            rows = conn.execute(
                'SELECT * FROM "{}" ORDER BY id DESC LIMIT 500'.format(table)
            ).fetchall()
        except Exception:  # noqa: BLE001 — table without an ``id`` column
            rows = conn.execute(
                'SELECT * FROM "{}" LIMIT 500'.format(table)
            ).fetchall()
        items = _rows(rows)
        label, columns, enriched = web_tables.enrich(conn, table, items)
        return _ok({
            'table': table,
            'label': label,
            'columns': columns,
            'items': enriched,
        })
    finally:
        conn.close()


def _three_way_match(request):
    """GET /api/match?tolerance= — PO ↔ GRN ↔ invoice with narration."""
    import procurement
    try:
        tol = float((request.query or {}).get('tolerance') or 0)
    except (TypeError, ValueError):
        tol = 0.0
    conn = _conn()
    try:
        pos = conn.execute(
            'SELECT po.id, po.po_no, po.total_amount, v.name AS vendor '
            'FROM purchase_orders po LEFT JOIN vendors v ON v.id = po.vendor_id '
            'ORDER BY po.id DESC').fetchall()
        received, invoiced = {}, {}
        for r in conn.execute(
                'SELECT g.purchase_order_id AS pid, SUM(gi.amount) AS a '
                'FROM grn_items gi JOIN goods_receipts g ON g.id = gi.grn_id '
                "WHERE g.status = 'Posted' GROUP BY g.purchase_order_id"):
            received[r['pid']] = r['a'] or 0
        for r in conn.execute(
                'SELECT purchase_order_id AS pid, SUM(subtotal) AS a '
                'FROM vendor_invoices WHERE purchase_order_id IS NOT NULL '
                'GROUP BY purchase_order_id'):
            invoiced[r['pid']] = r['a'] or 0
        items = []
        matches = []
        for po in pos:
            m = procurement.three_way(po['total_amount'],
                                      received.get(po['id'], 0),
                                      invoiced.get(po['id'], 0), tol)
            matches.append(m)
            label = po['po_no'] or 'PO {}'.format(po['id'])
            items.append({
                'id': po['id'], 'po_no': label, 'vendor': po['vendor'],
                'match': m,
                'narration': procurement.narrate_match(m, label),
            })
        summary = procurement.summarise(matches)
        return _ok({
            'items': items,
            'summary': summary,
            'narration': procurement.narrate_summary(summary),
        })
    finally:
        conn.close()


def _reconcile(request):
    """POST /api/reconcile — {po_subtotal, invoice_subtotal, tolerance?}."""
    import finance
    body = _payload(request)
    result = finance.reconcile(
        body.get('po_subtotal'), body.get('invoice_subtotal'),
        body.get('tolerance') or 0)
    return _ok({
        'result': result,
        'narration': finance.narrate_reconcile(
            result, po_label=body.get('label')),
    })


def _ageing_summary(request):
    """GET /api/ageing — firm receivables ageing from open tax invoices."""
    import ageing
    conn = _conn()
    try:
        snap = dashboard.collect(conn)
        items = []
        for r in conn.execute(
                "SELECT invoice_date, total_amount FROM tax_invoices "
                "WHERE status != 'Cancelled'"):
            if r['invoice_date']:
                items.append((r['invoice_date'], float(r['total_amount'] or 0)))
        aged = ageing.age_open_items(items)
        buckets = [
            {'label': label, 'amount': aged.get(label, 0.0)}
            for label in ageing.BUCKETS
        ]
        labels = [b['label'] for b in buckets]
        values = [b['amount'] for b in buckets]
        return _ok({
            'ageing': aged,
            'buckets': buckets,
            'labels': labels,
            'values': values,
            'total': aged.get('total', 0.0),
            'receivable': snap.get('receivable'),
            'receivable_90plus': snap.get('receivable_90plus'),
        })
    finally:
        conn.close()


def _assistant_quick():
    """GET /api/assistant/quick — the exact, no-model quick answers (cash in
    hand, receivables, payables, billed this month) as labelled money items."""
    import assistant
    conn = _conn()
    try:
        qa = assistant.quick_answers(conn)
    finally:
        conn.close()
    return _ok({'items': [{'label': k, 'value': v} for k, v in qa.items()]})


def _assistant_answer(request):
    """POST /api/assistant {question, history?} — one RAG turn over the user's
    data. Returns {sql, columns, rows, summary} or {error} (e.g. AI engine off).
    Read-only: the pipeline validates the SQL is a single SELECT before running."""
    import assistant
    body = _payload(request)
    question = (body.get('question') or '').strip()
    if not question:
        return _err('question is required', 400)
    history = body.get('history') if isinstance(body.get('history'), list) else None
    return _ok(assistant.answer(question, history=history))


def _parties():
    """GET /api/parties — per-party balances (receivable + payable) with totals,
    from ``parties_store`` (billed vs settled = the "baaki"). The internal
    ``party_id`` is dropped from the display rows."""
    import parties_store
    conn = _conn()
    try:
        s = parties_store.summary(conn)
    finally:
        conn.close()
    for side in ('receivable', 'payable'):
        s[side] = [{k: v for k, v in r.items() if k != 'party_id'}
                   for r in s[side]]
    return _ok(s)


def _cashflow(request):
    """GET /api/cashflow — plottable weekly/monthly forecast buckets."""
    q = request.query or {}
    conn = _conn()
    try:
        result = cashflow_assemble.assemble(
            conn,
            periods=q.get('periods') or 8,
            mode=q.get('mode') or 'week',
            receipt_lag_days=q.get('receipt_lag') or 45,
            payment_lag_days=q.get('payment_lag') or 15,
            weekly_wages=q.get('weekly_wages') or 0,
        )
        buckets = result.get('buckets') or []
        # Parallel arrays for LiveCharts; detail buckets stay intact.
        result['labels'] = [
            (b.get('start').isoformat() if hasattr(b.get('start'), 'isoformat')
             else str(b.get('start') or ''))
            for b in buckets
        ]
        result['values'] = [b.get('balance', 0.0) for b in buckets]
        result['series'] = {
            'in': [b.get('in', 0.0) for b in buckets],
            'out': [b.get('out', 0.0) for b in buckets],
            'balance': list(result['values']),
        }
        return _ok(result)
    finally:
        conn.close()


def _gst_report(request):
    """GET /api/gst?month=YYYY-MM — outward/inward/HSN/TDS over ``gst.py``."""
    import gst
    from datetime import date
    month = ((request.query or {}).get('month') or '').strip()
    if not month:
        month = date.today().strftime('%Y-%m')
    conn = _conn()
    try:
        out_rows, out_tot = gst.outward(conn, month)
        in_rows, in_tot = gst.inward(conn, month)
        hsn_rows, hsn_tot = gst.hsn_summary(conn, month)
        tds_rows, tds_tot = gst.tds_register(conn, month)
        return _ok({
            'month': month,
            'outward': {
                'cols': list(gst.COLS['outward']),
                'rows': [list(r) for r in out_rows],
                'totals': out_tot,
            },
            'hsn': {
                'cols': list(gst.COLS['hsn']),
                'rows': [list(r) for r in hsn_rows],
                'totals': hsn_tot,
            },
            'inward': {
                'cols': list(gst.COLS['inward']),
                'rows': [list(r) for r in in_rows],
                'totals': in_tot,
            },
            'tds': {
                'cols': list(gst.COLS['tds']),
                'rows': [list(r) for r in tds_rows],
                'total': tds_tot,
            },
        })
    finally:
        conn.close()


def _pnl_report(request):
    """GET /api/pnl?period=YYYY-MM|FY|YYYY-YY — P&L over posted ledger."""
    import reports_store
    period = ((request.query or {}).get('period') or '').strip()
    conn = _conn()
    try:
        return _ok(reports_store.pnl_payload(conn, period=period or None))
    finally:
        conn.close()


def _balance_sheet_report(request):
    """GET /api/balance_sheet?as_of=YYYY-MM-DD&period= — Balance Sheet."""
    import reports_store
    q = request.query or {}
    as_of = (q.get('as_of') or '').strip() or None
    period = (q.get('period') or '').strip() or None
    conn = _conn()
    try:
        return _ok(reports_store.balance_sheet_payload(
            conn, as_of=as_of, period=period))
    finally:
        conn.close()


def _lookahead_report(request):
    """GET /api/lookahead?project_id=&weeks= — weekly look-ahead + PPC."""
    import commitments_store
    import lookahead_store
    q = request.query or {}
    project_id = q.get('project_id') or None
    site_id = q.get('site_id') or None
    weeks = q.get('weeks') or None
    try:
        project_id = int(project_id) if project_id not in (None, '') else None
    except (TypeError, ValueError):
        return _err('project_id must be an integer', 400)
    try:
        site_id = int(site_id) if site_id not in (None, '') else None
    except (TypeError, ValueError):
        return _err('site_id must be an integer', 400)
    conn = _conn()
    try:
        payload = lookahead_store.lookahead(
            conn, project_id=project_id, site_id=site_id, weeks=weeks)
        return _ok(commitments_store.enrich_lookahead(payload))
    finally:
        conn.close()


def _bills_previous(request):
    """GET /api/bills/previous?contract_id= — sum of Approved/Paid net_payable.

    Mirrors desktop running-bill previous_billed (Draft/Submitted excluded).
    """
    q = request.query or {}
    try:
        cid = int(q.get('contract_id') or 0)
    except (TypeError, ValueError):
        return _err('contract_id required', 400)
    if cid <= 0:
        return _err('contract_id required', 400)
    exclude = q.get('exclude_id')
    conn = _conn()
    try:
        sql = ("SELECT COALESCE(SUM(net_payable), 0) AS s FROM bills "
               "WHERE contract_id = ? AND status IN ('Approved', 'Paid')")
        params = [cid]
        if exclude:
            try:
                sql += ' AND id != ?'
                params.append(int(exclude))
            except (TypeError, ValueError):
                pass
        s = conn.execute(sql, params).fetchone()['s']
        return _ok({'contract_id': cid, 'previous_billed': float(s or 0)})
    finally:
        conn.close()


def _list_boq_items(request):
    """GET /api/boq_items?contract_id= — BOQ lines for a contract."""
    q = request.query or {}
    try:
        cid = int(q.get('contract_id') or 0)
    except (TypeError, ValueError):
        cid = 0
    conn = _conn()
    try:
        if cid > 0:
            rows = conn.execute(
                'SELECT * FROM boq_items WHERE contract_id = ? '
                'ORDER BY id', (cid,)).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM boq_items ORDER BY id DESC LIMIT 500'
            ).fetchall()
        return _ok({
            'table': 'boq_items',
            'contract_id': cid or None,
            'items': _rows(rows),
        })
    finally:
        conn.close()


def _list_allocations(request):
    """GET /api/allocations?payment_id= — lines for one payment."""
    q = request.query or {}
    try:
        pid = int(q.get('payment_id') or 0)
    except (TypeError, ValueError):
        return _err('payment_id required', 400)
    if pid <= 0:
        return _err('payment_id required', 400)
    conn = _conn()
    try:
        pay = conn.execute(
            'SELECT * FROM payments WHERE id = ?', (pid,)).fetchone()
        if pay is None:
            return _err('Payment not found', 404)
        rows = conn.execute(
            'SELECT * FROM payment_allocations WHERE payment_id = ? '
            'ORDER BY id', (pid,)).fetchall()
        allocs = _rows(rows)
        return _ok({
            'payment_id': pid,
            'payment': _row(pay),
            'items': allocs,
            'allocated': allocation.money(
                sum(allocation.money(a.get('amount')) for a in allocs)),
            'unallocated': allocation.unallocated_amount(
                pay['amount'], allocs),
        })
    finally:
        conn.close()


def _save_allocations(request, sess):
    """POST /api/allocations — {payment_id, lines:[{doc_type,doc_id,amount}]}.

    Replaces existing lines for the payment (same as desktop Allocate tab).
    """
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    body.pop('csrf', None)
    try:
        pid = int(body.get('payment_id') or 0)
    except (TypeError, ValueError):
        return _err('payment_id required', 400)
    if pid <= 0:
        return _err('payment_id required', 400)
    lines = body.get('lines') or body.get('items') or []
    if not isinstance(lines, list):
        return _err('lines must be a list', 400)
    conn = _conn()
    try:
        pay = conn.execute(
            'SELECT * FROM payments WHERE id = ?', (pid,)).fetchone()
        if pay is None:
            return _err('Payment not found', 404)
        proposed = []
        for row in lines:
            if not isinstance(row, dict):
                continue
            try:
                amount = float(row.get('amount') or 0)
            except (TypeError, ValueError):
                amount = 0.0
            if amount <= 0:
                continue
            proposed.append({
                'doc_type': (row.get('doc_type') or '').strip(),
                'doc_id': int(row.get('doc_id') or 0),
                'amount': amount,
                'number': row.get('number'),
                'open': row.get('open'),
            })
        ok, msg = allocation.validate(pay['amount'], proposed)
        if not ok:
            return _err(msg, 400)
        conn.execute(
            'DELETE FROM payment_allocations WHERE payment_id = ?', (pid,))
        for row in proposed:
            if not row['doc_type'] or row['doc_id'] <= 0:
                continue
            conn.execute(
                'INSERT INTO payment_allocations '
                '(payment_id, doc_type, doc_id, amount) VALUES (?,?,?,?)',
                (pid, row['doc_type'], row['doc_id'],
                 allocation.money(row['amount'])))
        auth.audit(conn, sess['username'], 'api_allocate', 'payments', pid,
                   origin=auth.ORIGIN_MANUAL)
        conn.commit()
        rows = conn.execute(
            'SELECT * FROM payment_allocations WHERE payment_id = ? '
            'ORDER BY id', (pid,)).fetchall()
        allocs = _rows(rows)
        return _ok({
            'payment_id': pid,
            'payment': _row(pay),
            'items': allocs,
            'allocated': allocation.money(
                sum(allocation.money(a.get('amount')) for a in allocs)),
            'unallocated': allocation.unallocated_amount(
                pay['amount'], allocs),
        })
    finally:
        conn.close()


def _create_purchase_order(request, sess):
    """POST /api/purchase_orders — header + optional items; total = sum(amount)."""
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    body.pop('csrf', None)
    items = body.get('items') or []
    if items and not isinstance(items, list):
        return _err('items must be a list', 400)
    conn = _conn()
    try:
        total = 0.0
        cleaned = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            try:
                qty = float(it.get('qty') or 0)
                rate = float(it.get('rate') or 0)
            except (TypeError, ValueError):
                qty, rate = 0.0, 0.0
            amount = round(qty * rate, 2)
            total = round(total + amount, 2)
            cleaned.append({
                'description': (it.get('description') or '').strip(),
                'unit': (it.get('unit') or '').strip(),
                'qty': qty, 'rate': rate, 'amount': amount,
                'material_id': it.get('material_id'),
            })
        if body.get('total_amount') is not None and not cleaned:
            try:
                total = float(body.get('total_amount') or 0)
            except (TypeError, ValueError):
                total = 0.0
        cur = conn.execute(
            'INSERT INTO purchase_orders '
            '(po_no, vendor_id, site_id, po_date, expected_date, status, '
            'gst_pct, notes, total_amount) VALUES (?,?,?,?,?,?,?,?,?)',
            (
                body.get('po_no') or '',
                body.get('vendor_id'),
                body.get('site_id'),
                body.get('po_date') or '',
                body.get('expected_date') or '',
                body.get('status') or 'Draft',
                float(body.get('gst_pct') or 18),
                body.get('notes') or '',
                total,
            ))
        po_id = cur.lastrowid
        for it in cleaned:
            mid = it.get('material_id')
            try:
                mid = int(mid) if mid not in (None, '') else None
            except (TypeError, ValueError):
                mid = None
            conn.execute(
                'INSERT INTO purchase_order_items '
                '(purchase_order_id, description, unit, qty, rate, amount, '
                'material_id) VALUES (?,?,?,?,?,?,?)',
                (po_id, it['description'], it['unit'], it['qty'], it['rate'],
                 it['amount'], mid))
        auth.audit(conn, sess['username'], 'api_create', 'purchase_orders',
                   po_id, origin=auth.ORIGIN_MANUAL)
        conn.commit()
        row = conn.execute(
            'SELECT * FROM purchase_orders WHERE id = ?', (po_id,)).fetchone()
        lines = conn.execute(
            'SELECT * FROM purchase_order_items WHERE purchase_order_id = ?',
            (po_id,)).fetchall()
        out = _row(row)
        out['items'] = _rows(lines)
        return _ok(out, status=201)
    finally:
        conn.close()


def _post_forecast(request):
    """POST /api/forecast — {series, periods_ahead?} or {baseline_duration, spi}."""
    body = _payload(request)
    if 'baseline_duration' in body or 'spi' in body:
        result = forecast.schedule_forecast(
            body.get('baseline_duration'), body.get('spi'))
        if result is None:
            return _err('Schedule forecast undefined (need baseline + SPI)', 400)
        return _ok({'kind': 'schedule', 'result': result})
    series = body.get('series') or []
    try:
        ahead = int(body.get('periods_ahead') or 1)
    except (TypeError, ValueError):
        ahead = 1
    result = forecast.project(series, periods_ahead=ahead)
    if result is None:
        return _err('Trend undefined (need ≥2 numeric points)', 400)
    return _ok({'kind': 'trend', 'result': result,
                'direction': forecast.direction(series)})


def _post_drift(request):
    """POST /api/drift — soft-signal dict → drift assessment."""
    body = _payload(request)
    signals = body.get('signals') if isinstance(body.get('signals'), dict) else body
    # Strip non-signal keys if a wrapper was sent
    clean = {k: signals.get(k) for k in (
        'ppc_series', 'slip_series', 'rfi_age_series', 'low_conf_measurements')
        if k in signals}
    return _ok(drift.assess_drift(clean))


# -------------------------------------------------------------- submittals
_SUBMITTAL_FIELDS = (
    'submittal_no', 'site_id', 'contract_id', 'spec_ref', 'title',
    'submittal_type', 'submitted_date', 'submitted_by', 'required_by',
    'status', 'reviewer', 'reviewed_date', 'review_remarks',
    'supersedes_id', 'remarks',
)


def _list_submittals(request):
    conn = _conn()
    try:
        status = request.query.get('status')
        sql = 'SELECT * FROM submittals'
        params = []
        if status:
            sql += ' WHERE status = ?'
            params.append(status)
        sql += ' ORDER BY id DESC LIMIT 500'
        rows = conn.execute(sql, params).fetchall()
        items = []
        for r in rows:
            d = _row(r)
            d['is_open'] = submittals_mod.is_open(r['status'])
            d['is_overdue'] = submittals_mod.is_overdue(
                r['required_by'], r['status'])
            items.append(d)
        return _ok({'items': items, 'statuses': list(submittals_mod.STATUSES)})
    finally:
        conn.close()


def _get_submittal(sid):
    conn = _conn()
    try:
        row = conn.execute('SELECT * FROM submittals WHERE id = ?',
                           (sid,)).fetchone()
        if row is None:
            return _err('Submittal not found', 404)
        d = _row(row)
        d['is_open'] = submittals_mod.is_open(row['status'])
        d['is_overdue'] = submittals_mod.is_overdue(
            row['required_by'], row['status'])
        return _ok(d)
    finally:
        conn.close()


def _create_submittal(request, sess):
    denied = _require_write(request, sess)
    if denied:
        return denied
    fields = _payload(request)
    fields.pop('csrf', None)
    row = {k: fields[k] for k in _SUBMITTAL_FIELDS if k in fields}
    row.setdefault('status', 'Submitted')
    if row.get('status') and row['status'] not in submittals_mod.STATUSES:
        return _err('Invalid status', 400)
    conn = _conn()
    try:
        cols = list(row.keys())
        cur = conn.execute(
            'INSERT INTO submittals ({}) VALUES ({})'.format(
                ', '.join(cols), ', '.join('?' for _ in cols)),
            [row[c] for c in cols])
        new_id = cur.lastrowid
        auth.audit(conn, sess['username'], 'api_create', 'submittals', new_id,
                   origin=auth.ORIGIN_MANUAL)
        conn.commit()
        row = conn.execute('SELECT * FROM submittals WHERE id = ?',
                           (new_id,)).fetchone()
        d = _row(row)
        d['is_open'] = submittals_mod.is_open(row['status'])
        d['is_overdue'] = submittals_mod.is_overdue(
            row['required_by'], row['status'])
        return _ok(d, status=201)
    finally:
        conn.close()


def _update_submittal(request, sess, sid):
    denied = _require_write(request, sess)
    if denied:
        return denied
    fields = _payload(request)
    fields.pop('csrf', None)
    conn = _conn()
    try:
        existing = conn.execute('SELECT * FROM submittals WHERE id = ?',
                                (sid,)).fetchone()
        if existing is None:
            return _err('Submittal not found', 404)
        updates = {k: fields[k] for k in _SUBMITTAL_FIELDS if k in fields}
        if updates.get('status') and updates['status'] not in submittals_mod.STATUSES:
            return _err('Invalid status', 400)
        if not updates:
            return _ok(_row(existing))
        cols = list(updates.keys())
        conn.execute(
            'UPDATE submittals SET {} WHERE id = ?'.format(
                ', '.join('{} = ?'.format(c) for c in cols)),
            [updates[c] for c in cols] + [sid])
        auth.audit(conn, sess['username'], 'api_update', 'submittals', sid,
                   origin=auth.ORIGIN_MANUAL)
        conn.commit()
    finally:
        conn.close()
    return _get_submittal(sid)


def _delete_submittal(request, sess, sid):
    denied = _require_write(request, sess)
    if denied:
        return denied
    conn = _conn()
    try:
        row = conn.execute('SELECT id FROM submittals WHERE id = ?',
                           (sid,)).fetchone()
        if row is None:
            return _err('Submittal not found', 404)
        conn.execute('DELETE FROM submittals WHERE id = ?', (sid,))
        auth.audit(conn, sess['username'], 'api_delete', 'submittals', sid,
                   origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok({'deleted': sid})
    finally:
        conn.close()


# --------------------------------------------------------- money documents
def _list_doc(table):
    conn = _conn()
    try:
        rows = conn.execute(
            'SELECT * FROM "{}" ORDER BY id DESC LIMIT 500'.format(table)
        ).fetchall()
        return _ok({
            'table': table,
            'label': web_docs.label(table),
            'note': web_docs.note(table),
            'fields': web_masters.enrich_fields(conn, web_docs.fields(table)),
            'items': _rows(rows),
            'create_only': True,
        })
    finally:
        conn.close()


def _get_doc(table, rid):
    conn = _conn()
    try:
        row = conn.execute(
            'SELECT * FROM "{}" WHERE id = ?'.format(table), (rid,)
        ).fetchone()
        if row is None:
            return _err('Not found', 404)
        return _ok(_row(row))
    finally:
        conn.close()


def _create_doc(request, sess, table):
    """Create a money document via web_docs.compute + journal_post.post_all."""
    denied = _require_write(request, sess)
    if denied:
        return denied
    payload = _payload(request)
    payload.pop('csrf', None)
    values = {}
    errs = []
    for f in web_docs.fields(table):
        key = f['key']
        if key in payload:
            raw = payload[key]
        else:
            raw = web_docs.resolve_default(f.get('default', ''))
        if raw is None:
            raw = ''
        elif not isinstance(raw, str):
            raw = str(raw)
        ok, val, err = web_masters.coerce(f, raw)
        if ok:
            values[key] = val
        else:
            errs.append(err)
    if errs:
        return _err('; '.join(errs), 400)
    columns = web_docs.compute(table, values)
    conn = _conn()
    try:
        keys = list(columns.keys())
        cur = conn.execute(
            'INSERT INTO "{}" ({}) VALUES ({})'.format(
                table, ', '.join('"{}"'.format(k) for k in keys),
                ', '.join('?' for _ in keys)),
            [columns[k] for k in keys])
        new_id = cur.lastrowid
        auth.audit(conn, sess['username'], 'api_create', table, new_id,
                   origin=auth.ORIGIN_MANUAL)
        conn.commit()
        try:
            journal_post.post_all(conn)
        except Exception:  # noqa: BLE001 — document saved; post later
            pass
        row = conn.execute(
            'SELECT * FROM "{}" WHERE id = ?'.format(table), (new_id,)
        ).fetchone()
        out = _row(row)
        # Draft follow-ups only — never auto-apply gated money/date actions.
        if table == 'payments':
            reacted = event_hooks.react(
                followups.PAYMENT_DUE, payload={'payment_id': new_id})
            out['followups'] = reacted.get('followups') or []
            out['gated_count'] = reacted.get('gated_count', 0)
        elif table == 'bills' and (out.get('status') or '') in ('Approved', 'Paid'):
            reacted = event_hooks.react(
                followups.RUNNING_BILL_APPROVED,
                payload={'bill_id': new_id})
            out['followups'] = reacted.get('followups') or []
            out['gated_count'] = reacted.get('gated_count', 0)
        return _ok(out, status=201)
    finally:
        conn.close()


def _search(request):
    """GET /api/search?q= — tab hits + record hits (N4)."""
    import record_search
    q = (request.query or {}).get('q') or ''
    tabs = menu.search_tabs(q)
    conn = _conn()
    try:
        records = record_search.search_records(conn, q)
    finally:
        conn.close()
    return _ok({
        'query': q,
        'hits': tabs,           # backward-compatible tab list
        'tabs': tabs,
        'records': records,
    })


def _intent(request):
    """POST /api/intent — {text, payload?} → gated follow-up / workflow drafts."""
    body = _payload(request)
    text = body.get('text') or body.get('query') or ''
    payload = body.get('payload') if isinstance(body.get('payload'), dict) else {}
    return _ok(nl_intent.resolve(text, payload=payload))


def _sidecar_status():
    """GET /api/sidecar/status — OCR/STT/VLM stub + live probe."""
    return _ok({'sidecars': sidecar_bridge.status()})


def _sidecar_extract(request):
    """POST /api/sidecar/extract — {kind, payload?} → capture draft (soft-fail)."""
    body = _payload(request)
    kind = (body.get('kind') or '').strip().lower()
    payload = body.get('payload') if isinstance(body.get('payload'), dict) else {}
    if kind not in sidecar_bridge.KINDS:
        return _err('kind must be one of: {}'.format(', '.join(sidecar_bridge.KINDS)))
    result = sidecar_bridge.extract(kind, payload=payload)
    # Soft-fail: still 200 with ok=False so clients degrade cleanly.
    return _ok(result)


# ------------------------------------- takeoffs + drawing Phase D (u0.16)
def _takeoffs_list(request):
    q = request.query or {}
    conn = _conn()
    try:
        rows = takeoff_store.list_takeoffs(
            conn, project_id=q.get('project_id'), site_id=q.get('site_id'))
    finally:
        conn.close()
    return _ok({'items': rows, 'count': len(rows)})


def _takeoffs_get(takeoff_id):
    conn = _conn()
    try:
        data = takeoff_store.get_takeoff(conn, takeoff_id)
    finally:
        conn.close()
    if not data:
        return _err('Takeoff not found', 404)
    return _ok(data)


def _takeoffs_save(request, sess, takeoff_id=None):
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    header = body.get('header') if isinstance(body.get('header'), dict) else body
    items = body.get('items') if isinstance(body.get('items'), list) else []
    conn = _conn()
    try:
        tid = takeoff_store.save(conn, header, items, takeoff_id=takeoff_id)
        data = takeoff_store.get_takeoff(conn, tid)
    finally:
        conn.close()
    return _ok({'ok': True, 'id': tid, 'takeoff': data})


def _takeoffs_delete(request, sess, takeoff_id):
    denied = _require_write(request, sess)
    if denied:
        return denied
    conn = _conn()
    try:
        takeoff_store.delete_takeoff(conn, takeoff_id)
    finally:
        conn.close()
    return _ok({'ok': True, 'deleted': takeoff_id})


def _takeoffs_to_estimate(request, sess, takeoff_id):
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    conn = _conn()
    try:
        out = takeoff_store.to_estimate(
            conn, takeoff_id, title=body.get('title'))
    finally:
        conn.close()
    if not out.get('ok'):
        return _err(out.get('reason') or 'Could not create estimate')
    return _ok(out)


def _drawing_elements_list(drawing_id):
    conn = _conn()
    try:
        rows = drawing_store.list_elements(conn, drawing_id)
    finally:
        conn.close()
    return _ok({'drawing_id': drawing_id, 'items': rows, 'count': len(rows)})


def _drawing_elements_draft(request):
    """POST — normalize proposed elements (no write)."""
    body = _payload(request)
    elements = body.get('elements') if isinstance(body.get('elements'), list) else []
    try:
        scale = float(body.get('scale') or 0)
    except (TypeError, ValueError):
        scale = 0.0
    unit = body.get('unit') or 'm'
    normalized = drawing_geometry.normalize_elements(
        elements, scale=scale, linear_unit=unit,
        default_source=body.get('source') or 'ai')
    draft = capture.build_draft(
        {'element_count': len(normalized),
         'totals': drawing_geometry.totals(normalized)},
        confidence={'element_count': 0.5},
        source=capture.AI)
    return _ok({
        'ok': True,
        'elements': normalized,
        'totals': drawing_geometry.totals(normalized),
        'count': len(normalized),
        'draft': draft,
        'needs_review': True,
        'gated': True,
        'note': 'Draft only — POST /api/drawings/elements/confirm to persist',
    })


def _drawing_elements_confirm(request, sess):
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    drawing_id = body.get('drawing_id')
    if drawing_id in (None, ''):
        return _err('drawing_id required')
    elements = body.get('elements') if isinstance(body.get('elements'), list) else []
    try:
        scale = float(body.get('scale') or 0)
    except (TypeError, ValueError):
        scale = 0.0
    unit = body.get('unit') or 'm'
    sync = bool(body.get('sync_takeoff'))
    conn = _conn()
    try:
        if scale or unit:
            conn.execute(
                'UPDATE drawings SET scale = COALESCE(NULLIF(?, 0), scale), '
                "unit = COALESCE(NULLIF(?, ''), unit) WHERE id = ?",
                (scale, unit, int(drawing_id)))
        out = drawing_store.replace_elements(
            conn, drawing_id, elements, scale=scale, linear_unit=unit,
            reviewed_by=sess.get('username'), mark_reviewed=True)
        if sync:
            sync_out = drawing_store.sync_elements_to_takeoff(
                conn, drawing_id, takeoff_id=body.get('takeoff_id'),
                name=body.get('takeoff_name'))
            out['takeoff'] = sync_out
    finally:
        conn.close()
    return _ok(out)


def _drawing_elements_ingest(request):
    """POST — accept already-parsed vector JSON (no DXF in core)."""
    body = _payload(request)
    payload = body.get('payload') if isinstance(body.get('payload'), dict) else body
    try:
        scale = float(body.get('scale') or 0)
    except (TypeError, ValueError):
        scale = 0.0
    return _ok(drawing_geometry.ingest_vector_payload(
        payload, scale=scale, linear_unit=body.get('unit') or 'm'))


def _drawing_revision_delta(request):
    """POST — compute element diff (read-only)."""
    body = _payload(request)
    fro = body.get('from_drawing_id')
    to = body.get('to_drawing_id')
    if fro in (None, '') or to in (None, ''):
        return _err('from_drawing_id and to_drawing_id required')
    align = body.get('align') if isinstance(body.get('align'), dict) else None
    try:
        measure_scale = float(body.get('scale') or 0)
    except (TypeError, ValueError):
        measure_scale = 0.0
    conn = _conn()
    try:
        diff = drawing_store.compute_revision_delta(
            conn, fro, to, align=align, measure_scale=measure_scale,
            linear_unit=body.get('unit') or 'm')
    finally:
        conn.close()
    draft = revision_delta.variation_draft_lines(diff, rate=body.get('rate') or 0)
    changes = []
    for c in diff.get('changes') or []:
        cc = dict(c)
        for side in ('from', 'to'):
            el = cc.get(side)
            if isinstance(el, dict) and 'points' in el:
                el = dict(el)
                el['points'] = [list(p) for p in (el.get('points') or [])]
                cc[side] = el
        changes.append(cc)
    diff = dict(diff)
    diff['changes'] = changes
    return _ok({
        'ok': True,
        'diff': diff,
        'variation_draft': draft,
        'gated': True,
        'note': 'Confirm via POST /api/drawings/revision-delta/confirm',
    })


def _drawing_revision_delta_confirm(request, sess):
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    fro = body.get('from_drawing_id')
    to = body.get('to_drawing_id')
    if fro in (None, '') or to in (None, ''):
        return _err('from_drawing_id and to_drawing_id required')
    align = body.get('align') if isinstance(body.get('align'), dict) else None
    conn = _conn()
    try:
        diff = drawing_store.compute_revision_delta(
            conn, fro, to, align=align,
            measure_scale=float(body.get('scale') or 0),
            linear_unit=body.get('unit') or 'm')
        saved = drawing_store.save_element_changes(
            conn, fro, to, diff,
            variation_id=body.get('variation_id'),
            accepted_by=sess.get('username'))
        draft = revision_delta.variation_draft_lines(
            diff, rate=body.get('rate') or 0)
    finally:
        conn.close()
    return _ok({
        'ok': True,
        'saved': saved,
        'variation_draft': draft,
        'gated': True,
        'note': (
            'Changes persisted. Variation lines are still a draft — raise in '
            'Billing › Variations for human approval.'
        ),
    })


def _narrative(request):
    """GET /api/narrative?kind=kpi|risk — plain-language briefing over dashboard."""
    kind = ((request.query or {}).get('kind') or 'kpi').strip().lower()
    conn = _conn()
    try:
        snap = dashboard.collect(conn)
    finally:
        conn.close()
    if kind == 'risk':
        text = narrative.risk_briefing(snap)
    else:
        text = narrative.kpi_briefing(snap)
        kind = 'kpi'
    return _ok({'kind': kind, 'text': text})


def _text_extract(request):
    """POST /api/text/extract — {text, target?} → capture draft fields."""
    body = _payload(request)
    text = body.get('text') or ''
    target = body.get('target')
    return _ok(text_extract.extract(text, target=target))


def _muster_draft(request):
    """POST /api/muster/draft — {text|names, att_date, site_id?} → match drafts."""
    body = _payload(request)
    att_date = (body.get('att_date') or '').strip()
    names = body.get('names') if isinstance(body.get('names'), list) else None
    text = body.get('text') or ''
    conn = _conn()
    try:
        sql = 'SELECT id, name, father_name FROM labor WHERE status = ?'
        params = ['Active']
        site_id = body.get('site_id')
        if site_id not in (None, ''):
            try:
                sql += ' AND site_id = ?'
                params.append(int(site_id))
            except (TypeError, ValueError):
                pass
        labor_rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    if names is not None:
        draft = muster_draft.draft_from_names(
            [str(n) for n in names], labor_rows, att_date,
            default_status=body.get('status') or 'Present',
            hours=body.get('hours', 8.0))
    else:
        draft = muster_draft.draft_from_text(
            text, labor_rows, att_date,
            default_status=body.get('status') or 'Present',
            hours=body.get('hours', 8.0))
    return _ok(draft)


def _muster_confirm(request, sess):
    """POST /api/muster/confirm — {att_date, rows:[{labor_id,status,hours}]}."""
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    att_date = (body.get('att_date') or '').strip()
    rows = body.get('rows') if isinstance(body.get('rows'), list) else []
    if not att_date:
        return _err('att_date is required', 400)
    if not rows:
        return _err('rows required', 400)
    written = []
    conn = _conn()
    try:
        for row in rows:
            try:
                lid = int(row.get('labor_id'))
            except (TypeError, ValueError):
                continue
            status = row.get('status') or 'Present'
            try:
                hours = float(row.get('hours') if row.get('hours') is not None else 8)
            except (TypeError, ValueError):
                hours = 8.0
            conn.execute(
                'DELETE FROM attendance WHERE labor_id = ? AND att_date = ?',
                (lid, att_date))
            cur = conn.execute(
                'INSERT INTO attendance (labor_id, att_date, status, hours) '
                'VALUES (?, ?, ?, ?)', (lid, att_date, status, hours))
            written.append(cur.lastrowid)
        auth.audit(conn, sess['username'], 'muster_confirm', 'attendance',
                   None, detail='{} marks on {}'.format(len(written), att_date),
                   origin=auth.ORIGIN_MANUAL)
        conn.commit()
        reacted = event_hooks.react(
            followups.ATTENDANCE_SAVED,
            payload={'att_date': att_date, 'rows': len(written)})
        return _ok({
            'att_date': att_date,
            'written': len(written),
            'ids': written,
            'followups': reacted.get('followups') or [],
            'gated_count': reacted.get('gated_count', 0),
        }, status=201)
    finally:
        conn.close()


def _boq_import_draft(request):
    """POST /api/boq/import/draft — {text} → parsed BOQ line drafts."""
    body = _payload(request)
    parsed = boq_import.parse_text(body.get('text') or '',
                                   default_unit=body.get('unit') or 'Nos')
    parsed['drafts'] = boq_import.to_capture_drafts(parsed.get('lines') or [])
    return _ok(parsed)


def _boq_import_confirm(request, sess):
    """POST /api/boq/import/confirm — {contract_id, lines:[...]} writes boq_items."""
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    try:
        contract_id = int(body.get('contract_id'))
    except (TypeError, ValueError):
        return _err('contract_id is required', 400)
    lines = body.get('lines') if isinstance(body.get('lines'), list) else []
    if not lines:
        return _err('lines required', 400)
    ids = []
    conn = _conn()
    try:
        for line in lines:
            try:
                qty = float(line.get('qty') or 0)
                rate = float(line.get('rate') or 0)
            except (TypeError, ValueError):
                qty, rate = 0.0, 0.0
            amount = round(qty * rate, 2)
            desc = str(line.get('description') or '').strip()
            if not desc:
                continue
            cur = conn.execute(
                'INSERT INTO boq_items '
                '(contract_id, item_no, description, unit, qty, rate, amount) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (contract_id, str(line.get('item_no') or ''),
                 desc, str(line.get('unit') or 'Nos'), qty, rate, amount))
            ids.append(cur.lastrowid)
        auth.audit(conn, sess['username'], 'boq_import', 'boq_items',
                   None, detail='{} lines on contract {}'.format(
                       len(ids), contract_id),
                   origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok({'contract_id': contract_id, 'ids': ids,
                    'written': len(ids)}, status=201)
    finally:
        conn.close()


def _patterns_learn(request, sess):
    """POST /api/patterns/learn — {apply?:bool, min_count?} → AI lesson drafts.

    Default is preview only. ``apply=true`` writes via lessons_store (source=ai).
    """
    body = _payload(request)
    try:
        min_count = int(body.get('min_count') or 2)
    except (TypeError, ValueError):
        min_count = 2
    apply = bool(body.get('apply'))
    conn = _conn()
    try:
        lessons = conn.execute('SELECT * FROM lessons_learned').fetchall()
        risks = conn.execute('SELECT * FROM risks').fetchall()
        drafts = pattern_learn.collect(lessons, risks, min_count=min_count)
        applied_ids = []
        if apply and drafts:
            denied = _require_write(request, sess)
            if denied:
                return denied
            for d in drafts:
                lid = lessons_store.add(
                    conn, category=d.get('category'), title=d.get('title'),
                    description=d.get('description'),
                    outcome=d.get('outcome'),
                    recommendation=d.get('recommendation'),
                    source=d.get('source'), status=d.get('status'),
                    impact_value=d.get('impact_value') or 0)
                applied_ids.append(lid)
                auth.audit(conn, sess['username'], 'pattern_learn',
                           'lessons_learned', lid, detail=d.get('title'),
                           origin=auth.ORIGIN_AI)
            conn.commit()
        return _ok({
            'drafts': drafts,
            'applied_ids': applied_ids,
            'applied': bool(applied_ids),
        })
    finally:
        conn.close()


def _signals_preview(request):
    """POST /api/signals/preview — collect forecast/drift drafts without writing."""
    body = _payload(request)
    drafts = signal_feed.collect(
        drift=body.get('drift'),
        schedule_forecast=body.get('schedule_forecast'),
        cost_trend=body.get('cost_trend') or body.get('trend'),
        project_id=body.get('project_id'),
        ld_exposure=body.get('ld_exposure') or 0,
    )
    return _ok({'drafts': drafts, 'count': len(drafts)})


def _signals_suggest(request, sess):
    """POST /api/signals/suggest — soft signals from the live book → drafts.

    Body: ``{apply?: bool, project_id?}``. Default preview-only.
    """
    body = _payload(request)
    apply = bool(body.get('apply'))
    if apply:
        denied = _require_write(request, sess)
        if denied:
            return denied
    project_id = body.get('project_id')
    try:
        project_id = int(project_id) if project_id not in (None, '') else None
    except (TypeError, ValueError):
        project_id = None
    conn = _conn()
    try:
        result = signal_suggest.suggest(
            conn, project_id=project_id, apply=apply,
            username=sess.get('username') or 'system')
        return _ok(result)
    finally:
        conn.close()


def _grn_draft(request):
    """POST /api/grn/draft — {text} challan paste → matched GRN line drafts."""
    body = _payload(request)
    text = body.get('text') or ''
    conn = _conn()
    try:
        mats = conn.execute(
            'SELECT id, name, unit, category FROM materials').fetchall()
    finally:
        conn.close()
    return _ok(grn_draft.draft_from_text(text, mats))


def _grn_confirm(request, sess):
    """POST /api/grn/confirm — write a Draft GRN + lines (no stock post).

    Body: {header?, lines:[{material_id, description, unit, qty_received,
    qty_rejected?}], purchase_order_id?, vendor_id?, site_id?, source?}
    """
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    header = body.get('header') if isinstance(body.get('header'), dict) else {}
    lines = body.get('lines') if isinstance(body.get('lines'), list) else []
    if not lines:
        return _err('lines required', 400)
    source = body.get('source') or 'manual'
    origin = auth.ORIGIN_AI if source == 'ai' else auth.ORIGIN_MANUAL

    def _id(key):
        raw = body.get(key)
        if raw in (None, ''):
            raw = header.get(key)
        try:
            return int(raw) if raw not in (None, '') else None
        except (TypeError, ValueError):
            return None

    conn = _conn()
    try:
        cur = conn.execute(
            'INSERT INTO goods_receipts '
            '(grn_no, purchase_order_id, vendor_id, site_id, grn_date, '
            'challan_no, vehicle_no, received_by, status, remarks) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (str(header.get('grn_no') or body.get('grn_no') or ''),
             _id('purchase_order_id'), _id('vendor_id'), _id('site_id'),
             str(header.get('grn_date') or ''),
             str(header.get('challan_no') or ''),
             str(header.get('vehicle_no') or ''),
             str(header.get('received_by') or ''),
             'Draft',
             str(header.get('remarks') or '')))
        grn_id = cur.lastrowid
        item_ids = []
        for line in lines:
            try:
                mid = int(line['material_id']) if line.get('material_id') not in (None, '') else None
            except (TypeError, ValueError):
                mid = None
            try:
                recv = float(line.get('qty_received') or 0)
            except (TypeError, ValueError):
                recv = 0.0
            try:
                rej = float(line.get('qty_rejected') or 0)
            except (TypeError, ValueError):
                rej = 0.0
            accepted = max(0.0, recv - rej)
            try:
                rate = float(line.get('rate') or 0)
            except (TypeError, ValueError):
                rate = 0.0
            cur = conn.execute(
                'INSERT INTO grn_items '
                '(grn_id, material_id, description, unit, qty_received, '
                'qty_rejected, qty_accepted, rate, amount, remarks) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (grn_id, mid,
                 str(line.get('description') or line.get('matched_name') or ''),
                 str(line.get('unit') or ''),
                 recv, rej, accepted, rate, round(accepted * rate, 2),
                 str(line.get('remarks') or '')))
            item_ids.append(cur.lastrowid)
        auth.audit(conn, sess['username'], 'grn_confirm', 'goods_receipts',
                   grn_id, detail='{} lines'.format(len(item_ids)),
                   origin=origin)
        conn.commit()
        reacted = event_hooks.react(
            followups.GRN_SAVED, payload={'grn_id': grn_id})
        return _ok({
            'id': grn_id, 'status': 'Draft', 'item_ids': item_ids,
            'followups': reacted.get('followups') or [],
            'gated_count': reacted.get('gated_count', 0),
        }, status=201)
    finally:
        conn.close()


def _vendor_invoice_draft(request):
    """POST /api/vendor_invoice/draft — pasted invoice → draft + totals."""
    body = _payload(request)
    return _ok(vendor_invoice_draft.draft_from_text(body.get('text') or ''))


def _vendor_invoice_confirm(request, sess):
    """POST /api/vendor_invoice/confirm — write vendor invoice + items."""
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    header = body.get('header') if isinstance(body.get('header'), dict) else {}
    lines = body.get('lines') if isinstance(body.get('lines'), list) else []
    if not lines:
        return _err('lines required', 400)
    source = body.get('source') or 'manual'
    origin = auth.ORIGIN_AI if source == 'ai' else auth.ORIGIN_MANUAL
    subtotal = 0.0
    parsed_lines = []
    for line in lines:
        try:
            qty = float(line.get('qty') or 0)
            rate = float(line.get('rate') or 0)
        except (TypeError, ValueError):
            qty, rate = 0.0, 0.0
        amount = round(qty * rate, 2)
        subtotal += amount
        parsed_lines.append({
            'description': str(line.get('description') or '').strip(),
            'unit': str(line.get('unit') or 'Nos'),
            'qty': qty, 'rate': rate, 'amount': amount,
        })
    subtotal = round(subtotal, 2)
    try:
        gst_pct = float(header.get('gst_pct') if header.get('gst_pct') is not None else 18)
    except (TypeError, ValueError):
        gst_pct = 18.0
    try:
        tds_pct = float(header.get('tds_pct') or 0)
    except (TypeError, ValueError):
        tds_pct = 0.0
    interstate = bool(int(header.get('interstate') or 0))
    totals = finance.invoice_totals(subtotal, gst_pct, tds_pct, interstate)

    def _id(key):
        raw = body.get(key, header.get(key))
        try:
            return int(raw) if raw not in (None, '') else None
        except (TypeError, ValueError):
            return None

    conn = _conn()
    try:
        cur = conn.execute(
            'INSERT INTO vendor_invoices '
            '(invoice_no, vendor_id, purchase_order_id, invoice_date, '
            'received_date, interstate, gst_pct, tds_pct, subtotal, '
            'tax_amount, tds_amount, total_amount, net_payable, status, notes) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (str(header.get('invoice_no') or ''),
             _id('vendor_id'), _id('purchase_order_id'),
             str(header.get('invoice_date') or ''),
             str(header.get('received_date') or ''),
             1 if interstate else 0, gst_pct, tds_pct, subtotal,
             totals['tax_amount'], totals['tds_amount'],
             totals['total_amount'], totals['net_payable'],
             str(header.get('status') or 'Received'),
             str(header.get('notes') or '')))
        vid = cur.lastrowid
        item_ids = []
        for line in parsed_lines:
            if not line['description']:
                continue
            cur = conn.execute(
                'INSERT INTO vendor_invoice_items '
                '(vendor_invoice_id, description, unit, qty, rate, amount) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (vid, line['description'], line['unit'],
                 line['qty'], line['rate'], line['amount']))
            item_ids.append(cur.lastrowid)
        auth.audit(conn, sess['username'], 'vendor_invoice_confirm',
                   'vendor_invoices', vid,
                   detail='{} lines'.format(len(item_ids)), origin=origin)
        conn.commit()
        return _ok({
            'id': vid, 'item_ids': item_ids, 'totals': totals,
            'subtotal': subtotal,
        }, status=201)
    finally:
        conn.close()


def _pdf_extract(request):
    """POST /api/pdf/extract — {path} → text via local pdftotext (soft-fail)."""
    body = _payload(request)
    path = body.get('path') or ''
    result = pdf_text.extract_text(path, max_pages=body.get('max_pages'))
    result['available'] = pdf_text.available()
    return _ok(result)


def _capture_draft(request, sess):
    """POST /api/capture/draft — stage extracted fields for human review."""
    body = _payload(request)
    extracted = body.get('fields') if isinstance(body.get('fields'), dict) else {}
    confidence = body.get('confidence') if isinstance(body.get('confidence'), dict) else {}
    source = body.get('source') or capture.AI
    if source not in (capture.AI, capture.MANUAL):
        source = capture.AI
    draft = capture.build_draft(extracted, confidence=confidence, source=source)
    return _ok({
        'draft': draft,
        'needs_review': capture.needs_review(draft),
        'low_confidence': capture.low_confidence_fields(draft),
        'summary': capture.confidence_summary(draft),
        'origin': capture.origin_of(draft),
    })


def _capture_confirm(request, sess):
    """POST /api/capture/confirm — apply overrides and write a target record.

    Body: {fields?, overrides?, confidence?, source?, target?}
    ``target`` ∈ work_done | daily_progress | ncr | snag (default work_done).
    Nothing is written without this explicit confirm.
    """
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    extracted = body.get('fields') if isinstance(body.get('fields'), dict) else {}
    confidence = body.get('confidence') if isinstance(body.get('confidence'), dict) else {}
    source = body.get('source') or capture.MANUAL
    draft = capture.build_draft(extracted, confidence=confidence, source=source)
    overrides = body.get('overrides') if isinstance(body.get('overrides'), dict) else {}
    draft = capture.apply_overrides(draft, overrides)
    record = capture.to_record(draft)
    target = (body.get('target') or 'work_done').strip()
    origin = (auth.ORIGIN_AI if capture.origin_of(draft) == capture.AI
              else auth.ORIGIN_MANUAL)

    if target == 'work_done':
        return _confirm_work_done(sess, record, draft, origin)
    if target == 'daily_progress':
        return _confirm_daily_progress(sess, record, draft, origin)
    if target == 'ncr':
        return _confirm_ncr(sess, record, draft, origin)
    if target == 'snag':
        return _confirm_snag(sess, record, draft, origin)
    return _err('Unsupported target {!r}'.format(target), 400)


def _site_id(record):
    try:
        return int(record.get('site_id') or 0) or None
    except (TypeError, ValueError):
        return None


def _confirm_work_done(sess, record, draft, origin):
    try:
        qty = float(record.get('qty') or 0)
    except (TypeError, ValueError):
        qty = 0.0
    activity = str(record.get('activity') or '').strip()
    if not activity:
        return _err('activity is required', 400)
    site_id = _site_id(record)
    unit = str(record.get('unit') or '').strip()
    entry_date = str(record.get('entry_date') or '').strip()
    remarks = str(record.get('remarks') or '').strip()
    conn = _conn()
    try:
        cur = conn.execute(
            'INSERT INTO work_done_entries '
            '(site_id, activity, unit, qty, entry_date, remarks) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (site_id, activity, unit, qty, entry_date, remarks))
        new_id = cur.lastrowid
        auth.audit(conn, sess['username'], 'capture_confirm',
                   'work_done_entries', new_id, origin=origin)
        conn.commit()
        row = conn.execute(
            'SELECT * FROM work_done_entries WHERE id = ?', (new_id,)
        ).fetchone()
        reacted = event_hooks.react(
            followups.ACTIVITY_COMPLETE,
            payload={'work_done_id': new_id, 'activity': activity,
                     'site_id': site_id, 'qty': qty})
        return _ok({
            'id': new_id, 'target': 'work_done',
            'record': _row(row),
            'origin': capture.origin_of(draft),
            'followups': reacted.get('followups') or [],
            'gated_count': reacted.get('gated_count', 0),
        }, status=201)
    finally:
        conn.close()


def _confirm_daily_progress(sess, record, draft, origin):
    site_id = _site_id(record)
    try:
        labour = float(record.get('labour_count') or 0)
    except (TypeError, ValueError):
        labour = 0.0
    try:
        plant = float(record.get('plant_count') or 0)
    except (TypeError, ValueError):
        plant = 0.0
    conn = _conn()
    try:
        cur = conn.execute(
            'INSERT INTO daily_progress '
            '(site_id, report_date, weather, labour_count, plant_count, '
            'work_summary, remarks) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (site_id, str(record.get('report_date') or ''),
             str(record.get('weather') or ''), labour, plant,
             str(record.get('work_summary') or ''),
             str(record.get('remarks') or '')))
        new_id = cur.lastrowid
        auth.audit(conn, sess['username'], 'capture_confirm',
                   'daily_progress', new_id, origin=origin)
        conn.commit()
        row = conn.execute(
            'SELECT * FROM daily_progress WHERE id = ?', (new_id,)
        ).fetchone()
        reacted = event_hooks.react(
            followups.ACTIVITY_COMPLETE,
            payload={'daily_progress_id': new_id, 'site_id': site_id})
        return _ok({
            'id': new_id, 'target': 'daily_progress',
            'record': _row(row),
            'origin': capture.origin_of(draft),
            'followups': reacted.get('followups') or [],
            'gated_count': reacted.get('gated_count', 0),
        }, status=201)
    finally:
        conn.close()


def _confirm_ncr(sess, record, draft, origin):
    desc = str(record.get('description') or '').strip()
    if not desc:
        return _err('description is required', 400)
    site_id = _site_id(record)
    conn = _conn()
    try:
        cur = conn.execute(
            'INSERT INTO ncrs (ncr_no, site_id, raised_date, raised_by, '
            'description, severity, status, remarks) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (str(record.get('ncr_no') or ''),
             site_id,
             str(record.get('raised_date') or ''),
             str(record.get('raised_by') or ''),
             desc,
             str(record.get('severity') or 'Major'),
             str(record.get('status') or 'Open'),
             str(record.get('remarks') or '')))
        new_id = cur.lastrowid
        auth.audit(conn, sess['username'], 'capture_confirm',
                   'ncrs', new_id, origin=origin)
        conn.commit()
        row = conn.execute(
            'SELECT * FROM ncrs WHERE id = ?', (new_id,)
        ).fetchone()
        reacted = event_hooks.react(
            followups.NCR_RAISED, payload={'ncr_id': new_id})
        return _ok({
            'id': new_id, 'target': 'ncr',
            'record': _row(row),
            'origin': capture.origin_of(draft),
            'followups': reacted.get('followups') or [],
            'gated_count': reacted.get('gated_count', 0),
        }, status=201)
    finally:
        conn.close()


def _confirm_snag(sess, record, draft, origin):
    desc = str(record.get('description') or '').strip()
    if not desc:
        return _err('description is required', 400)
    site_id = _site_id(record)
    conn = _conn()
    try:
        cur = conn.execute(
            'INSERT INTO snags (site_id, snag_no, raised_date, location, '
            'description, severity, status, remarks) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (site_id,
             str(record.get('snag_no') or ''),
             str(record.get('raised_date') or ''),
             str(record.get('location') or ''),
             desc,
             str(record.get('severity') or 'Minor'),
             str(record.get('status') or 'Open'),
             str(record.get('remarks') or '')))
        new_id = cur.lastrowid
        auth.audit(conn, sess['username'], 'capture_confirm',
                   'snags', new_id, origin=origin)
        conn.commit()
        row = conn.execute(
            'SELECT * FROM snags WHERE id = ?', (new_id,)
        ).fetchone()
        reacted = event_hooks.react(
            followups.SNAG_RAISED, payload={'snag_id': new_id})
        return _ok({
            'id': new_id, 'target': 'snag',
            'record': _row(row),
            'origin': capture.origin_of(draft),
            'followups': reacted.get('followups') or [],
            'gated_count': reacted.get('gated_count', 0),
        }, status=201)
    finally:
        conn.close()


# ------------------------------------- u0.13 cloud roadmap handlers
def _home(request):
    """GET /api/home — dashboard + companion blocks in one round-trip."""
    import home_store
    q = request.query or {}
    raw = (q.get('include') or '').strip()
    include = [p.strip() for p in raw.split(',') if p.strip()] or None
    conn = _conn()
    try:
        return _ok(home_store.assemble(conn, include=include))
    finally:
        conn.close()


def _key_numbers():
    """GET /api/kpi — Key Numbers rows (split from Insight / dashboard)."""
    import kpi_store
    conn = _conn()
    try:
        return _ok(kpi_store.collect(conn))
    finally:
        conn.close()


def _insight():
    """GET /api/insight — site profit / progress / material budget."""
    import insight_store
    conn = _conn()
    try:
        return _ok(insight_store.assemble(conn))
    finally:
        conn.close()


def _gst_export(request):
    """GET /api/gst/export?month=YYYY-MM — CA CSV/HTML pack."""
    import gst_export
    month = ((request.query or {}).get('month') or '').strip()
    conn = _conn()
    try:
        return _ok(gst_export.pack(conn, month))
    finally:
        conn.close()


def _risks_detect(request, sess):
    """POST /api/risks/detect — {apply?} run risk_detect over live snapshot."""
    import risk_accept
    body = _payload(request)
    apply = bool(body.get('apply'))
    if apply:
        denied = _require_write(request, sess)
        if denied:
            return denied
    conn = _conn()
    try:
        result = risk_accept.detect(
            conn, apply=apply, username=sess['username'])
        if apply and result.get('applied_ids'):
            auth.audit(conn, sess['username'], 'risk_detect_apply', 'risks',
                       None, detail='applied={}'.format(
                           len(result['applied_ids'])),
                       origin=auth.ORIGIN_AI)
            conn.commit()
        return _ok(result)
    finally:
        conn.close()


def _risks_accept(request, sess):
    """POST /api/risks/accept — {ids?} and/or {detect_and_apply:true}."""
    import risk_accept
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    ids = body.get('ids') or body.get('risk_ids') or []
    detect_and_apply = bool(body.get('detect_and_apply'))
    status = (body.get('status') or 'Accepted').strip() or 'Accepted'
    conn = _conn()
    try:
        result = risk_accept.accept(
            conn, risk_ids=ids, detect_and_apply=detect_and_apply,
            username=sess['username'], status=status)
        auth.audit(conn, sess['username'], 'risk_accept', 'risks', None,
                   detail='accepted={}'.format(len(result['accepted_ids'])),
                   origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(result)
    finally:
        conn.close()


def _list_commitments(request):
    import lookahead_store
    q = request.query or {}
    project_id = q.get('project_id') or None
    site_id = q.get('site_id') or None
    weeks = q.get('weeks') or None
    try:
        project_id = int(project_id) if project_id not in (None, '') else None
    except (TypeError, ValueError):
        return _err('project_id must be an integer', 400)
    try:
        site_id = int(site_id) if site_id not in (None, '') else None
    except (TypeError, ValueError):
        return _err('site_id must be an integer', 400)
    conn = _conn()
    try:
        items = lookahead_store.load_commitments(
            conn, project_id=project_id, site_id=site_id, weeks=weeks)
        import commitments_store
        return _ok({
            'items': items,
            'reasons': commitments_store.reasons(),
            'statuses': ['Done', 'Not done'],
        })
    finally:
        conn.close()


def _get_commitment(cid):
    import commitments_store
    conn = _conn()
    try:
        row = commitments_store.get(conn, cid)
        if row is None:
            return _err('Commitment not found', 404)
        return _ok(row)
    finally:
        conn.close()


def _create_commitment(request, sess):
    import commitments_store
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    conn = _conn()
    try:
        row = commitments_store.create(conn, body)
        auth.audit(conn, sess['username'], 'api_create', 'commitments',
                   row['id'], origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(row, status=201)
    finally:
        conn.close()


def _update_commitment(request, sess, cid):
    import commitments_store
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    conn = _conn()
    try:
        row = commitments_store.update(conn, cid, body)
        if row is None:
            return _err('Commitment not found', 404)
        auth.audit(conn, sess['username'], 'api_update', 'commitments',
                   cid, origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(row)
    finally:
        conn.close()


def _delete_commitment(request, sess, cid):
    import commitments_store
    denied = _require_write(request, sess)
    if denied:
        return denied
    conn = _conn()
    try:
        if commitments_store.get(conn, cid) is None:
            return _err('Commitment not found', 404)
        commitments_store.delete(conn, cid)
        auth.audit(conn, sess['username'], 'api_delete', 'commitments',
                   cid, origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok({'deleted': cid})
    finally:
        conn.close()


def _mark_commitment(request, sess, cid):
    import commitments_store
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    done = body.get('done')
    if done is None:
        done = (body.get('status') or '') == 'Done'
    conn = _conn()
    try:
        row = commitments_store.mark_done(
            conn, cid, done=bool(done), reason=body.get('reason') or '')
        if row is None:
            return _err('Commitment not found', 404)
        auth.audit(conn, sess['username'], 'api_update', 'commitments',
                   cid, detail='mark_done={}'.format(bool(done)),
                   origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(row)
    finally:
        conn.close()


def _timeline(request):
    """GET /api/timeline?project_id= — CPM + baseline position."""
    import timeline_store
    q = request.query or {}
    try:
        pid = int(q.get('project_id') or 0)
    except (TypeError, ValueError):
        return _err('project_id required', 400)
    if pid <= 0:
        return _err('project_id required', 400)
    conn = _conn()
    try:
        payload = timeline_store.assemble(conn, pid)
        if payload is None:
            return _err('Project not found', 404)
        return _ok(payload)
    finally:
        conn.close()


def _ra_generate(request, sess):
    """POST /api/ra_bills/generate — MB snapshot → Draft RA bill."""
    import ra_generate
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    try:
        cid = int(body.get('contract_id') or 0)
    except (TypeError, ValueError):
        return _err('contract_id required', 400)
    if cid <= 0:
        return _err('contract_id required', 400)
    conn = _conn()
    try:
        try:
            result = ra_generate.generate(
                conn, cid,
                bill_date=body.get('bill_date') or '',
                retention_pct=body.get('retention_pct') or 0,
                tds_pct=body.get('tds_pct') or 0,
                cess_pct=body.get('cess_pct') or 0,
                other_deductions=body.get('other_deductions') or 0)
        except ValueError as exc:
            return _err(str(exc), 400)
        auth.audit(conn, sess['username'], 'ra_generate', 'ra_bills',
                   result['id'], origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(result, status=201)
    finally:
        conn.close()


def _list_work_orders():
    import work_orders_store
    conn = _conn()
    try:
        return _ok({'items': work_orders_store.list_work_orders(conn)})
    finally:
        conn.close()


def _get_work_order(wid):
    import work_orders_store
    conn = _conn()
    try:
        row = work_orders_store.get_work_order(conn, wid)
        if row is None:
            return _err('Work order not found', 404)
        return _ok(row)
    finally:
        conn.close()


def _create_work_order(request, sess):
    import work_orders_store
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    items = body.get('items') if isinstance(body.get('items'), list) else []
    conn = _conn()
    try:
        row = work_orders_store.create_work_order(conn, body, items)
        auth.audit(conn, sess['username'], 'api_create', 'work_orders',
                   row['id'], origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(row, status=201)
    finally:
        conn.close()


def _update_work_order(request, sess, wid):
    import work_orders_store
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    items = body.get('items') if 'items' in body else None
    if items is not None and not isinstance(items, list):
        return _err('items must be a list', 400)
    conn = _conn()
    try:
        row = work_orders_store.update_work_order(conn, wid, body, items)
        if row is None:
            return _err('Work order not found', 404)
        auth.audit(conn, sess['username'], 'api_update', 'work_orders',
                   wid, origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(row)
    finally:
        conn.close()


def _delete_work_order(request, sess, wid):
    import work_orders_store
    denied = _require_write(request, sess)
    if denied:
        return denied
    conn = _conn()
    try:
        if work_orders_store.get_work_order(conn, wid) is None:
            return _err('Work order not found', 404)
        work_orders_store.delete_work_order(conn, wid)
        auth.audit(conn, sess['username'], 'api_delete', 'work_orders',
                   wid, origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok({'deleted': wid})
    finally:
        conn.close()


def _list_sub_bills(request):
    import work_orders_store
    q = request.query or {}
    wo = q.get('work_order_id') or None
    try:
        wo = int(wo) if wo not in (None, '') else None
    except (TypeError, ValueError):
        return _err('work_order_id must be an integer', 400)
    conn = _conn()
    try:
        return _ok({'items': work_orders_store.list_sub_bills(conn, wo)})
    finally:
        conn.close()


def _get_sub_bill(bid):
    import work_orders_store
    conn = _conn()
    try:
        row = work_orders_store.get_sub_bill(conn, bid)
        if row is None:
            return _err('Sub bill not found', 404)
        return _ok(row)
    finally:
        conn.close()


def _create_sub_bill(request, sess):
    import work_orders_store
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    conn = _conn()
    try:
        try:
            row = work_orders_store.create_sub_bill(conn, body)
        except ValueError as exc:
            return _err(str(exc), 400)
        auth.audit(conn, sess['username'], 'api_create', 'sub_bills',
                   row['id'], origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(row, status=201)
    finally:
        conn.close()


def _update_sub_bill(request, sess, bid):
    import work_orders_store
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    conn = _conn()
    try:
        row = work_orders_store.update_sub_bill(conn, bid, body)
        if row is None:
            return _err('Sub bill not found', 404)
        auth.audit(conn, sess['username'], 'api_update', 'sub_bills',
                   bid, origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(row)
    finally:
        conn.close()


def _delete_sub_bill(request, sess, bid):
    import work_orders_store
    denied = _require_write(request, sess)
    if denied:
        return denied
    conn = _conn()
    try:
        if work_orders_store.get_sub_bill(conn, bid) is None:
            return _err('Sub bill not found', 404)
        work_orders_store.delete_sub_bill(conn, bid)
        auth.audit(conn, sess['username'], 'api_delete', 'sub_bills',
                   bid, origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok({'deleted': bid})
    finally:
        conn.close()


def _muster_grid(request):
    """GET /api/muster?site_id=&att_date= — Active labour grid for a day."""
    import muster_ops
    q = request.query or {}
    try:
        site_id = int(q.get('site_id') or 0)
    except (TypeError, ValueError):
        return _err('site_id required', 400)
    att_date = (q.get('att_date') or '').strip()
    if site_id <= 0 or not att_date:
        return _err('site_id and att_date required', 400)
    conn = _conn()
    try:
        try:
            return _ok(muster_ops.load_grid(conn, site_id, att_date))
        except ValueError as exc:
            return _err(str(exc), 400)
    finally:
        conn.close()


def _muster_save(request, sess):
    """POST /api/muster — {site_id, att_date, rows:[{labor_id,status,hours}]}."""
    import muster_ops
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    try:
        site_id = int(body.get('site_id') or 0)
    except (TypeError, ValueError):
        return _err('site_id required', 400)
    att_date = (body.get('att_date') or '').strip()
    rows = body.get('rows') if isinstance(body.get('rows'), list) else None
    if site_id <= 0 or not att_date or rows is None:
        return _err('site_id, att_date and rows required', 400)
    conn = _conn()
    try:
        try:
            result = muster_ops.save_grid(conn, site_id, att_date, rows)
        except ValueError as exc:
            return _err(str(exc), 400)
        auth.audit(conn, sess['username'], 'muster_save', 'attendance',
                   None, detail='saved={}'.format(result['saved']),
                   origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(result)
    finally:
        conn.close()


def _muster_payout_compute(request):
    """GET /api/muster/payout?site_id=&week_start= — 7-day wage compute."""
    import muster_ops
    q = request.query or {}
    try:
        site_id = int(q.get('site_id') or 0)
    except (TypeError, ValueError):
        return _err('site_id required', 400)
    week_start = (q.get('week_start') or '').strip()
    if site_id <= 0 or not week_start:
        return _err('site_id and week_start required', 400)
    conn = _conn()
    try:
        try:
            return _ok(muster_ops.compute_payout(conn, site_id, week_start))
        except ValueError as exc:
            return _err(str(exc), 400)
    finally:
        conn.close()


def _muster_payout_record(request, sess):
    """POST /api/muster/payout — record cash wage payments (idempotent)."""
    import muster_ops
    denied = _require_write(request, sess)
    if denied:
        return denied
    body = _payload(request)
    try:
        site_id = int(body.get('site_id') or 0)
    except (TypeError, ValueError):
        return _err('site_id required', 400)
    week_start = (body.get('week_start') or '').strip()
    if site_id <= 0 or not week_start:
        return _err('site_id and week_start required', 400)
    rows = body.get('rows') if isinstance(body.get('rows'), list) else None
    conn = _conn()
    try:
        try:
            result = muster_ops.record_payout(
                conn, site_id, week_start, rows=rows)
        except ValueError as exc:
            return _err(str(exc), 400)
        auth.audit(conn, sess['username'], 'muster_payout', 'payments',
                   None, detail='recorded={}'.format(result['recorded']),
                   origin=auth.ORIGIN_MANUAL)
        conn.commit()
        return _ok(result, status=201)
    finally:
        conn.close()

# ------------------------------------- Foundry multi-agent (u0.14 / u0.15)
def _agents_list():
    import agent_workflows
    import agents_catalog
    return _ok({
        'items': agents_catalog.list_agents(),
        'workflows': agent_workflows.list_workflows(),
        'note': (
            'Agents propose only. Foundry Local narrates when running; '
            'Azure AI Foundry cloud Agents are Phase C (opt-in).'
        ),
        'doc': 'docs/AI-FOUNDRY-AGENTS.md',
    })


def _agents_get(agent_id):
    import agents_catalog
    row = agents_catalog.get(agent_id)
    if row is None:
        return _err('Agent not found', 404)
    return _ok(row)


def _agents_workflows_list():
    import agent_workflows
    return _ok({'items': agent_workflows.list_workflows()})


def _agents_provider():
    """GET /api/agents/provider — Foundry Local / Azure Foundry status."""
    import agent_provider
    conn = _conn()
    try:
        return _ok(agent_provider.status(conn))
    finally:
        conn.close()


def _agents_eval_cases():
    """GET /api/agents/eval — list golden questions (no run)."""
    import agent_eval
    return _ok({'cases': agent_eval.list_cases()})


def _agents_eval_run(request, sess):
    """POST /api/agents/eval — run golden suite ``{use_model?}``."""
    import agent_eval
    body = _payload(request)
    use_model = body.get('use_model', False)
    if isinstance(use_model, str):
        use_model = use_model.lower() in ('1', 'true', 'yes')
    conn = _conn()
    try:
        result = agent_eval.run_suite(conn, use_model=bool(use_model))
        auth.audit(conn, sess['username'], 'agent_eval', 'agents', None,
                   detail='passed={}/{}'.format(
                       result.get('passed'), result.get('total')),
                   origin=auth.ORIGIN_AI)
        conn.commit()
        return _ok(result)
    finally:
        conn.close()


def _agents_ask(request, sess):
    """POST /api/agents/ask — {question, agent_id?, use_model?, multi?}."""
    import agent_runtime
    body = _payload(request)
    question = (body.get('question') or body.get('q') or '').strip()
    if not question:
        return _err('question is required', 400)
    use_model = body.get('use_model', True)
    if isinstance(use_model, str):
        use_model = use_model.lower() in ('1', 'true', 'yes')
    conn = _conn()
    try:
        if body.get('multi'):
            ids = body.get('agent_ids') or body.get('agents')
            result = agent_runtime.ask_multi(
                conn, question, agent_ids=ids, use_model=bool(use_model))
        else:
            result = agent_runtime.ask(
                conn, question,
                agent_id=body.get('agent_id') or body.get('agent'),
                use_model=bool(use_model))
        auth.audit(conn, sess['username'], 'agent_ask', 'agents',
                   result.get('agent_id'),
                   detail=(question[:120]),
                   origin=auth.ORIGIN_AI)
        conn.commit()
        return _ok(result)
    finally:
        conn.close()


def _agents_workflow_run(request, sess):
    """POST /api/agents/workflow — {workflow_id, context?} multi-agent pack."""
    import agent_workflows
    body = _payload(request)
    wid = (body.get('workflow_id') or body.get('workflow') or '').strip()
    if not wid:
        return _err('workflow_id is required', 400)
    context = body.get('context') if isinstance(body.get('context'), dict) else {}
    if body.get('notes') and 'notes' not in context:
        context = dict(context)
        context['notes'] = body.get('notes')
    conn = _conn()
    try:
        result = agent_workflows.run(conn, wid, context=context)
        if not result.get('ok'):
            return _err(result.get('error') or 'Workflow failed', 400)
        auth.audit(conn, sess['username'], 'agent_workflow', 'agents',
                   wid, detail=wid, origin=auth.ORIGIN_AI)
        conn.commit()
        return _ok(result)
    finally:
        conn.close()

