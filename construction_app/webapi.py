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
import auth
import capture
import dashboard
import drift
import event_hooks
import evm
import followups
import forecast
import journal_post
import lessons_store
import menu
import modules
import opportunity_store
import portfolio_store
import review_assemble
import risk_store
import signal_feed
import submittals as submittals_mod
import web_docs
import web_masters
import webapp
import workflow
import workflow_state

# Masters exposed as flat CRUD registers over the JSON API.
_API_MASTERS = (
    'sites', 'clients', 'vendors', 'materials', 'labor', 'equipment',
    'projects', 'milestones', 'thekedars', 'rate_book',
)

# Money documents: create + list/get (no edit — records of fact).
_API_DOCS = tuple(web_docs.DOCS.keys())

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
        return _ok({'ok': True, 'service': 'construction-os', 'api': 'u0.1'})

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

    if path == 'dashboard' and method == 'GET':
        return _dashboard()

    if path == 'kpi' and method == 'GET':
        return _dashboard()  # same snapshot; client picks the KPI band

    if path == 'review' and method == 'GET':
        return _review()

    if path == 'portfolio' and method == 'GET':
        return _portfolio(request)

    if path == 'productivity' and method == 'GET':
        return _productivity(request)

    if path == 'menu' and method == 'GET':
        return _menu(request)

    if path == 'workflow' and method == 'GET':
        return _workflow(request)

    if path == 'search' and method == 'GET':
        return _search(request)

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
            return _list_master(path)
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
        return _ok({'rows': rows, 'portfolio': port})
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
        return _ok({'deleted': oid})
    finally:
        conn.close()


def _list_master(table):
    conn = _conn()
    try:
        rows = conn.execute(
            'SELECT * FROM "{}" ORDER BY id DESC LIMIT 500'.format(table)
        ).fetchall()
        return _ok({
            'table': table,
            'label': web_masters.label(table),
            'fields': web_masters.fields(table),
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
            raw = field.get('default', '')
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
    conn = _conn()
    try:
        cols = list(values.keys())
        sql = 'INSERT INTO "{}" ({}) VALUES ({})'.format(
            table, ', '.join('"{}"'.format(c) for c in cols),
            ', '.join('?' for _ in cols))
        cur = conn.execute(sql, [values[c] for c in cols])
        conn.commit()
        new_id = cur.lastrowid
        auth.audit(conn, sess['username'], 'api_create', table, new_id)
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
        cols = [c for c in merged if c in {f['key'] for f in web_masters.fields(table)}]
        sql = 'UPDATE "{}" SET {} WHERE id = ?'.format(
            table, ', '.join('"{}" = ?'.format(c) for c in cols))
        conn.execute(sql, [merged[c] for c in cols] + [rid])
        conn.commit()
        auth.audit(conn, sess['username'], 'api_update', table, rid)
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
            conn.commit()
        except Exception as exc:  # noqa: BLE001 — FK integrity → plain error
            return _err('Cannot delete: record is still used elsewhere ({})'
                        .format(exc), 409)
        auth.audit(conn, sess['username'], 'api_delete', table, rid)
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
        'api': 'u0.1',
        'auth': {
            'login': 'POST /api/login',
            'session_cookie': 'cosid',
            'csrf_header': 'X-CSRF-Token',
            'me': 'GET /api/me',
        },
        'reads': [
            'GET /api/health', 'GET /api/contract',
            'GET /api/dashboard', 'GET /api/kpi', 'GET /api/review',
            'GET /api/portfolio', 'GET /api/menu?persona=',
            'GET /api/productivity', 'GET /api/workflow', 'GET /api/evm',
            'GET /api/project/{id}/evm',
            'GET /api/risks', 'GET /api/opportunities', 'GET /api/lessons',
            'GET /api/submittals', 'GET /api/audit?origin=',
            'GET /api/search?q=', 'GET /api/{master}', 'GET /api/{doc}',
        ],
        'writes': [
            'POST/PUT/DELETE /api/risks[/{id}]',
            'POST/PUT/DELETE /api/opportunities[/{id}]',
            'POST/PUT/DELETE /api/lessons[/{id}]',
            'POST/PUT/DELETE /api/submittals[/{id}]',
            'POST /api/capture/draft', 'POST /api/capture/confirm',
            'POST/PUT/DELETE /api/{master}[/{id}]',
            'POST /api/{doc}  (create only: payments, tax_invoices, …)',
            'POST /api/events', 'POST /api/signals/feed',
            'POST /api/forecast', 'POST /api/drift',
        ],
        'masters': list(_API_MASTERS),
        'docs': list(_API_DOCS),
        'personas': list(menu.PERSONAS),
    })


def _portfolio(request):
    """Current-file portfolio roll-up; optional ``?paths=a.db,b.db`` federates."""
    raw = (request.query.get('paths') or '').strip()
    if raw:
        paths = [p.strip() for p in raw.split(',') if p.strip()]
        return _ok(portfolio_store.roll_up(paths))
    conn = _conn()
    try:
        return _ok({'current': portfolio_store.file_rollup(conn, name='current'),
                    'federated': False})
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
            'fields': web_docs.fields(table),
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
        return _ok(out, status=201)
    finally:
        conn.close()


def _search(request):
    q = (request.query or {}).get('q') or ''
    return _ok({'query': q, 'hits': menu.search_tabs(q)})


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
    """POST /api/capture/confirm — apply overrides and write work_done_entries.

    Body: {fields?, overrides?, confidence?, source?, target?}
    ``target`` defaults to ``work_done``. Nothing is written without this
    explicit confirm — AI proposes, human disposes.
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
    if target != 'work_done':
        return _err('Unsupported target {!r}'.format(target), 400)
    try:
        site_id = int(record.get('site_id') or 0) or None
    except (TypeError, ValueError):
        site_id = None
    try:
        qty = float(record.get('qty') or 0)
    except (TypeError, ValueError):
        qty = 0.0
    activity = str(record.get('activity') or '').strip()
    if not activity:
        return _err('activity is required', 400)
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
        origin = (auth.ORIGIN_AI if capture.origin_of(draft) == capture.AI
                  else auth.ORIGIN_MANUAL)
        auth.audit(conn, sess['username'], 'capture_confirm',
                   'work_done_entries', new_id, origin=origin)
        conn.commit()
        row = conn.execute(
            'SELECT * FROM work_done_entries WHERE id = ?', (new_id,)
        ).fetchone()
        return _ok({'id': new_id, 'record': _row(row),
                    'origin': capture.origin_of(draft)}, status=201)
    finally:
        conn.close()
