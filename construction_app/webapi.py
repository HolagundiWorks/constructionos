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
import dashboard
import event_hooks
import evm
import lessons_store
import menu
import modules
import opportunity_store
import review_assemble
import risk_store
import signal_feed
import web_masters
import webapp
import workflow

# Masters exposed as flat CRUD registers over the JSON API.
_API_MASTERS = (
    'sites', 'clients', 'vendors', 'materials', 'labor', 'equipment',
    'projects', 'milestones', 'thekedars', 'rate_book',
)

_RISK_ID = re.compile(r'^risks/(\d+)$')
_OPP_ID = re.compile(r'^opportunities/(\d+)$')
_LESSON_ID = re.compile(r'^lessons/(\d+)$')
_MASTER_ID = re.compile(
    r'^(' + '|'.join(_API_MASTERS) + r')/(\d+)$')
_PROJECT_EVM = re.compile(r'^project/(\d+)/evm$')


def handle(request, sess):
    """Dispatch one ``/api/...`` request. Caller has already authenticated."""
    path = request.path[len('/api'):].lstrip('/')  # '' or 'dashboard' etc.
    method = (request.method or 'GET').upper()

    if path in ('', 'health'):
        return _ok({'ok': True, 'service': 'construction-os', 'api': 'u0'})

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

    if path == 'dashboard' and method == 'GET':
        return _dashboard()

    if path == 'kpi' and method == 'GET':
        return _dashboard()  # same snapshot; client picks the KPI band

    if path == 'review' and method == 'GET':
        return _review()

    if path == 'menu' and method == 'GET':
        return _menu(request)

    if path == 'workflow' and method == 'GET':
        return _workflow(request)

    if path == 'evm' and method == 'GET':
        return _evm_portfolio()

    m = _PROJECT_EVM.match(path)
    if m and method == 'GET':
        return _evm_project(int(m.group(1)))

    if path == 'events' and method == 'POST':
        return _post_event(request, sess)

    if path == 'signals/feed' and method == 'POST':
        return _post_signal_feed(request, sess)

    if path == 'audit' and method == 'GET':
        return _list_audit(request)

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
    state_by_flow = {}
    for key, val in (request.query or {}).items():
        if not key.startswith('state.'):
            continue
        parts = key.split('.', 2)
        if len(parts) != 3:
            continue
        _, flow, step = parts
        state_by_flow.setdefault(flow, {})[step] = val in ('1', 'true', 'True')
    if not state_by_flow:
        # Empty state → every flow starts at its first step.
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
