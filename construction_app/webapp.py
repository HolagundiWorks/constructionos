"""The browser/LAN application: routing, sessions, the login gate, and the
read views — all standard library, sharing the *same* SQLite file and business
logic as the desktop app.

Design notes:

* **``handle(request) -> Response`` is the whole app**, and it never touches a
  socket. ``webserver`` translates HTTP <-> ``Request``/``Response`` around it,
  so every route here is unit-testable by constructing a ``Request`` and reading
  the ``Response`` back — no port, no browser.
* **Login is always required** (the chosen posture for putting the books on a
  network). It reuses ``auth`` — the same users, PBKDF2 hashing, lockout and
  audit log as the desktop. With no users yet, the first visit creates the
  administrator. Roles carry through (Viewer is read-only); write routes will
  gate on ``can_write`` as they are added.
* **Read views are whitelisted.** Table browsing discovers real tables from
  ``sqlite_master`` minus a denylist (never the ``users`` hashes), and every SQL
  identifier comes from that trusted set or ``PRAGMA table_info`` — user input
  only ever reaches the database as a bound parameter.

This is the foundation; write flows (Masters, then billing, then money) grow on
top route by route.
"""

import secrets
import sqlite3
import threading
import urllib.parse
import json

import db
import auth
import bill_export
import estimate
import evm
import journal_post
import mb_report
import review_assemble
import web_docs
import web_masters
import webrender as R

# Register lists scroll (with a sticky header) rather than page; this caps how
# many rows are loaded into one scroll view — beyond it, the count line says so
# and the user narrows with search.
MAX_ROWS = 500

# Writable registers beyond the flat-CRUD Masters. Estimates have child line
# items and a computed total, but (unlike bills) never post to the ledger, so
# they are safe to edit in the browser without the double-entry engine.
_WRITABLE_EXTRA = {'estimates': 'Estimate'}


def _is_writable(table):
    """Editable/deletable in the browser (Masters + estimates). Posting money
    documents are create-only and handled separately."""
    return web_masters.is_master(table) or table in _WRITABLE_EXTRA


def _writable_label(table):
    if web_masters.is_master(table):
        return web_masters.label(table)
    return _WRITABLE_EXTRA.get(table, _label(table))


def _can_create(table):
    """Anything the browser can add a new row to: Masters, estimates, and the
    postable money documents (payments, invoices, running bills)."""
    return _is_writable(table) or web_docs.is_doc(table)


def _create_label(table):
    if web_docs.is_doc(table):
        return web_docs.label(table)
    return _writable_label(table)

# Tables never exposed over the network: the password hashes, app config, and
# SQLite's own bookkeeping.
_DENY = {'users', 'app_settings', 'sqlite_sequence'}

# Friendly labels + a rail grouping for the registers we know; anything else
# discovered still shows, under "Other", with a Title-Cased name.
_LABELS = {
    'sites': 'Sites', 'clients': 'Clients', 'vendors': 'Vendors',
    'materials': 'Materials', 'labour': 'Labour', 'equipment': 'Equipment',
    'projects': 'Projects', 'timeline_tasks': 'Timeline',
    'estimates': 'Estimates', 'quotations': 'Quotations',
    'contracts': 'Contracts', 'bills': 'Running Bills', 'ra_bills': 'RA Bills',
    'variations': 'Variations', 'tax_invoices': 'Tax Invoices',
    'bid_assessments': 'Bid / No-Bid', 'takeoffs': 'Takeoffs',
    'purchase_orders': 'Purchase Orders', 'grns': 'Goods Receipts',
    'vendor_invoices': 'Vendor Invoices', 'subcontracts': 'Subcontractors',
    'payments': 'Payments', 'audit_log': 'Audit Log', 'rate_book': 'Rate Book',
    'milestones': 'Milestones', 'thekedars': 'Thekedars', 'snags': 'Snags',
    'ncrs': 'NCRs',
}
_GROUPS = [
    ('Project Management', ['projects', 'milestones', 'timeline_tasks']),
    ('Masters', ['sites', 'clients', 'vendors', 'materials', 'labour',
                 'equipment', 'thekedars']),
    ('Billing', ['rate_book', 'estimates', 'quotations', 'contracts', 'bills',
                 'ra_bills', 'variations', 'tax_invoices', 'takeoffs',
                 'bid_assessments']),
    ('Operations', ['snags', 'ncrs']),
    ('Purchases', ['purchase_orders', 'grns', 'vendor_invoices',
                   'subcontracts']),
    ('Money', ['payments']),
]


# --------------------------------------------------------------- HTTP objects
class Request:
    def __init__(self, method, path, query=None, form=None, form_multi=None,
                 cookies=None, headers=None, client='', json_body=None):
        self.method = method
        self.path = path
        self.query = query or {}
        self.form = form or {}
        # Repeated fields kept as lists (line-item rows: li_qty=[..], ...).
        self.form_multi = form_multi or {}
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.client = client
        # Parsed JSON body for /api writes (dict/list/None). Separate from
        # form so HTML form posts are unchanged.
        self.json_body = json_body


class Response:
    def __init__(self, body='', status=200, content_type='text/html; charset=utf-8'):
        self.status = status
        self.headers = {'Content-Type': content_type,
                        'X-Content-Type-Options': 'nosniff',
                        'Referrer-Policy': 'no-referrer',
                        'Content-Security-Policy':
                            "default-src 'self'; style-src 'unsafe-inline'; "
                            "script-src 'unsafe-inline'"}
        self.cookies = []
        self.body = body.encode('utf-8') if isinstance(body, str) else body

    def set_cookie(self, name, value, max_age=None, http_only=True):
        parts = ['{}={}'.format(name, value), 'Path=/', 'SameSite=Lax']
        if http_only:
            parts.append('HttpOnly')
        if max_age is not None:
            parts.append('Max-Age={}'.format(int(max_age)))
        self.cookies.append('; '.join(parts))
        return self


def _redirect(location):
    r = Response('', status=303)
    r.headers['Location'] = location
    return r


# ------------------------------------------------------------- session store
_SESSIONS = {}
_LOCK = threading.Lock()


def _new_session(username, role):
    token = secrets.token_urlsafe(24)
    with _LOCK:
        _SESSIONS[token] = {'username': username, 'role': role,
                            'csrf': secrets.token_urlsafe(18)}
    return token


def _csrf_ok(request, sess):
    """Synchroniser-token check for authenticated POSTs: the form must carry the
    token minted with this session."""
    token = sess.get('csrf')
    return bool(token) and request.form.get('csrf') == token


def _session(token):
    if not token:
        return None
    with _LOCK:
        return _SESSIONS.get(token)


def _drop_session(token):
    with _LOCK:
        _SESSIONS.pop(token, None)


def can_write(role):
    """Viewers are read-only; Operator/Admin may write (for the write routes to
    come)."""
    return role in ('Admin', 'Operator')


def reset_sessions():
    """Drop every session — used by tests, and worth calling if the server is
    restarted against a different company file."""
    with _LOCK:
        _SESSIONS.clear()


# -------------------------------------------------------------- register meta
def _viewable_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r['name'] for r in rows
            if r['name'] not in _DENY and not r['name'].startswith('sqlite_')}


def _label(name):
    return _LABELS.get(name) or name.replace('_', ' ').title()


def _columns(conn, table):
    return [(r['name'], (r['type'] or '').upper(), r['pk'])
            for r in conn.execute('PRAGMA table_info("{}")'.format(table))]


def _pk(cols):
    for name, _type, pk in cols:
        if pk:
            return name
    return None


def _nav(conn):
    """Rail groups, in a stable order, listing only tables that exist here."""
    have = _viewable_tables(conn)
    nav = [('', [('/', 'Dashboard', 'dashboard'),
                 ('/evm', 'Earned Value', 'evm'),
                 ('/review', 'Weekly Review', 'review'),
                 ('/m/capture', 'Field capture', 'capture')])]
    placed = set()
    for group, keys in _GROUPS:
        items = []
        for k in keys:
            if k in have:
                items.append(('/t/' + k, _label(k), k))
                placed.add(k)
        if items:
            nav.append((group, items))
    other = sorted(have - placed)
    if other:
        nav.append(('Other', [('/t/' + k, _label(k), k) for k in other]))
    return nav


# -------------------------------------------------------------- controllers
def handle(request):
    """Route a request to a response. The one entry point the server calls."""
    path = request.path
    if path in ('/favicon.ico',):
        return Response('', status=204)

    # JSON API login is public (creates the session); other /api/* need auth.
    if path == '/api/login':
        return _api_login(request)

    if path == '/login':
        return _login(request)
    if path == '/logout':
        return _logout(request)

    sess = _session(request.cookies.get('cosid'))
    if not sess:
        if path.startswith('/api/'):
            return _api_unauthorized()
        return _redirect('/login')

    if path.startswith('/api/'):
        import webapi
        return webapi.handle(request, sess)

    if path == '/':
        return _dashboard(request, sess)
    if path == '/evm':
        return _evm(request, sess)
    if path == '/review':
        return _review(request, sess)
    if path in ('/m', '/m/', '/m/capture'):
        return _mobile_capture(request, sess)
    if path == '/t' or path == '/t/':
        return _redirect('/')
    if path.startswith('/t/'):
        return _table_route(request, sess, path[3:])
    return _page('Not found', '<p class="muted">No such page.</p>', sess, conn=None)


def _api_unauthorized():
    body = json.dumps({'error': 'Authentication required'})
    return Response(body, status=401,
                    content_type='application/json; charset=utf-8')


def _api_login(request):
    """POST /api/login — JSON {username, password} → session cookie + me."""
    if request.method != 'POST':
        body = json.dumps({'error': 'POST required'})
        return Response(body, status=405,
                        content_type='application/json; charset=utf-8')
    data = request.json_body if isinstance(request.json_body, dict) else {}
    if not data:
        # Allow form-encoded too for curl convenience.
        data = {
            'username': request.form.get('username', ''),
            'password': request.form.get('password', ''),
        }
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    conn = db.get_conn()
    try:
        first_run = auth.user_count(conn) == 0
        if first_run:
            ok, msg = auth.create_user(conn, username, password,
                                       role='Admin', actor='api-setup')
            if not ok:
                body = json.dumps({'error': msg})
                return Response(body, status=400,
                                content_type='application/json; charset=utf-8')
            role = 'Admin'
        else:
            ok, msg, user = auth.authenticate(conn, username, password)
            if not ok:
                body = json.dumps({'error': msg})
                return Response(body, status=401,
                                content_type='application/json; charset=utf-8')
            role = user['role']
        token = _new_session(username, role)
        sess = _session(token)
        body = json.dumps({
            'username': username,
            'role': role,
            'csrf': sess['csrf'],
            'can_write': can_write(role),
        })
        resp = Response(body, status=200,
                        content_type='application/json; charset=utf-8')
        resp.set_cookie('cosid', token)
        return resp
    finally:
        conn.close()



def _login(request):
    conn = db.get_conn()
    try:
        first_run = auth.user_count(conn) == 0
        if request.method == 'POST':
            cookie_csrf = request.cookies.get('coscsrf', '')
            form_csrf = request.form.get('csrf', '')
            if not cookie_csrf or cookie_csrf != form_csrf:
                return _login_form('Your session expired — try again.', first_run)
            username = (request.form.get('username') or '').strip()
            password = request.form.get('password') or ''
            if first_run:
                ok, msg = auth.create_user(conn, username, password,
                                           role='Admin', actor='web-setup')
                if not ok:
                    return _login_form(msg, first_run=True)
                role = 'Admin'
            else:
                ok, msg, user = auth.authenticate(conn, username, password)
                if not ok:
                    return _login_form(msg, first_run=False)
                role = user['role']
            token = _new_session(username, role)
            resp = _redirect('/')
            resp.set_cookie('cosid', token)
            return resp
        # GET
        return _login_form('', first_run)
    finally:
        conn.close()


def _login_form(error, first_run):
    csrf = secrets.token_urlsafe(18)
    note = ('This login travels over your local network in the clear — use it '
            'on a trusted LAN, or put it behind HTTPS for anything wider.')
    resp = Response(R.login_page(error=error, first_run=first_run, csrf=csrf,
                                 host_note=note))
    resp.set_cookie('coscsrf', csrf, http_only=False)
    return resp


def _logout(request):
    _drop_session(request.cookies.get('cosid'))
    resp = _redirect('/login')
    resp.set_cookie('cosid', '', max_age=0)
    return resp


def _shell(title, body, sess, conn, active='', status=200):
    """Wrap page content in the signed-in chrome (rail, user, read-only banner)."""
    warn = '' if can_write(sess['role']) else \
        'You are signed in as a Viewer — read-only access.'
    resp = Response(R.page(title, body, user='{} ({})'.format(
        sess['username'], sess['role']), nav=_nav(conn) if conn else [],
        active=active, warning=warn))
    resp.status = status
    return resp


def _page(title, body, sess, conn, active='', status=200):
    return _shell(title, body, sess, conn, active=active, status=status)


def _forbidden(sess, conn, msg='You do not have permission to do that.'):
    return _shell('Not allowed', '<p class="muted">{}</p>'.format(R.esc(msg)),
                  sess, conn, status=403)


def _dashboard(request, sess):
    import dashboard
    import advisory
    conn = db.get_conn()
    try:
        s = dashboard.collect(conn)
        nav = _nav(conn)
        cards = advisory.build(s)
        body = _dashboard_body(s, cards, advisory)
        return _shell('Dashboard', body, sess, conn, active='dashboard')
    finally:
        conn.close()


def _dashboard_body(s, cards, advisory):
    kpis = [
        ('Cash in hand', R.money(s.get('cash'))),
        ('Receivable', R.money(s.get('receivable'))),
        ('Payable', R.money(s.get('payable'))),
        ('Net position', R.money(s.get('net_position'))),
        ('Billed this month', R.money(s.get('billed_month'))),
        ('Collected this month', R.money(s.get('collected_month'))),
        ('Active sites', s.get('sites', 0)),
        ('Approvals pending', s.get('approvals_count', 0)),
    ]
    kpi_html = ''.join(
        '<div class="card"><div class="k">{}</div><div class="v">{}</div></div>'
        .format(R.esc(k), R.esc(v)) for k, v in kpis)
    parts = ['<h1>Dashboard</h1>',
             '<div class="cards">{}</div>'.format(kpi_html)]

    if cards:
        parts.append('<h2>Advisories</h2>')
        for c in cards:
            parts.append(
                '<div class="adv {sev}"><div class="t">{title}'
                '<span class="pill">{conf}</span></div>'
                '<div class="m">{detail}</div>'
                '<div class="m"><strong>Do:</strong> {action} '
                '<span class="muted">· {where}</span></div></div>'.format(
                    sev=R.esc(c['severity']), title=R.esc(c['title']),
                    conf=R.esc(c['confidence']), detail=R.esc(c['detail']),
                    action=R.esc(c['action']), where=R.esc(c.get('where', ''))))

    bottlenecks = s.get('bottlenecks') or []
    if bottlenecks:
        parts.append('<h2>Bottlenecks</h2>')
        rows = [[b['label'], b['metric'], b.get('detail', ''), b.get('where', '')]
                for b in bottlenecks]
        parts.append(R.table(['Where work is stuck', 'Amount', 'Note', 'Screen'],
                             rows))

    decisions = s.get('decisions') or []
    if decisions:
        parts.append('<h2>Decisions pending</h2>')
        rows = [[d['label'], d.get('count', ''), R.money(d.get('value')),
                 d.get('where', '')] for d in decisions]
        parts.append(R.table(['Decision', 'Count', 'Value', 'Screen'], rows))

    return ''.join(parts)


def _evm(request, sess):
    """Earned Value, in the browser — the same figures as the desktop tab, read
    only. Reuses ``evm.portfolio_evm`` so the two surfaces can never disagree."""
    conn = db.get_conn()
    try:
        rows, port = evm.portfolio_evm(conn)
        return _shell('Earned Value', _evm_body(rows, port), sess, conn,
                      active='evm')
    finally:
        conn.close()


def _evm_index(value):
    return '—' if value is None else '{:.2f}'.format(value)


def _evm_pct(value):
    return '—' if value is None else '{:.0f}%'.format(value)


def _evm_health(row):
    on_budget, on_schedule = row.get('on_budget'), row.get('on_schedule')
    if on_budget is None and on_schedule is None:
        return '—'
    bad = []
    if on_budget is False:
        bad.append('over cost')
    if on_schedule is False:
        bad.append('behind')
    return 'On track' if not bad else ' & '.join(bad).capitalize()


def _evm_body(rows, port):
    if not port['projects']:
        return ('<h1>Earned Value</h1><p class="muted">No projects with a '
                'contract value or budget yet — add one to measure earned '
                'value against it.</p>')

    kpis = [
        ('Projects measured', port['projects']),
        ('Portfolio CPI', _evm_index(port['cpi'])),
        ('Portfolio SPI', _evm_index(port['spi'])),
        ('Over cost', port['over_cost']),
        ('Behind schedule', port['behind_schedule']),
        ('EV of BAC', '{} / {}'.format(R.money(port['ev']),
                                       R.money(port['bac']))),
    ]
    kpi_html = ''.join(
        '<div class="card"><div class="k">{}</div><div class="v">{}</div></div>'
        .format(R.esc(k), R.esc(v)) for k, v in kpis)

    # Worst cost performance first — the jobs needing attention on top.
    ordered = sorted(rows, key=lambda r: (r['cpi'] is None, r.get('cpi') or 0))
    trows = [[
        r['name'], R.money(r['bac']), R.money(r['pv']), R.money(r['ev']),
        R.money(r['ac']), _evm_index(r['spi']), _evm_index(r['cpi']),
        _evm_pct(r['percent_complete']), R.money(r['eac']['default']),
        R.money(r['vac']), _evm_health(r)] for r in ordered]
    headers = ['Project', 'BAC', 'PV (planned)', 'EV (earned)', 'AC (actual)',
               'SPI', 'CPI', '% complete', 'EAC (forecast)', 'VAC', 'Health']

    worst = ''
    if port['worst_cpi']:
        worst = '<p class="muted">Worst CPI: {} ({}).</p>'.format(
            R.esc(port['worst_cpi']), _evm_index(port['worst_cpi_value']))
    note = ('EV is billed/certified value — work measured but not yet billed '
            'reads low. PV is the elapsed fraction of each project’s start→end '
            'window; a baseline programme would give a truer schedule.')
    return ''.join([
        '<h1>Earned Value</h1>',
        '<div class="cards">{}</div>'.format(kpi_html),
        worst,
        R.table(headers, trows, scroll=True),
        '<p class="muted">{}</p>'.format(R.esc(note)),
    ])


def _review(request, sess):
    """Weekly Review, in the browser — the same assembled pack as the desktop
    tab, read only. Reuses ``review_assemble.assemble`` so the two agree."""
    conn = db.get_conn()
    try:
        pack = review_assemble.assemble(conn)
        return _shell('Weekly Review', _review_body(pack), sess, conn,
                      active='review')
    finally:
        conn.close()


def _mobile_capture(request, sess):
    """E6-lite field capture — work-done form, free-text note, or muster names.

    Confirm always required for writes. OCR/STT sidecars (L8) can pre-fill later.
    """
    import capture
    import muster_draft
    import text_extract
    from datetime import date

    flash = ''
    preview = ''
    conn = db.get_conn()
    try:
        sites = [(r['id'], r['name'] or 'Site {}'.format(r['id']))
                 for r in conn.execute(
                     'SELECT id, name FROM sites ORDER BY name')]
        qmode = ''
        if request.query:
            qmode = (request.query.get('mode') or '').strip()
        mode = qmode or 'work_done'
        if request.method == 'POST':
            if not can_write(sess['role']):
                return _forbidden(sess, conn)
            if not _csrf_ok(request, sess):
                return _forbidden(sess, conn, 'Invalid form token — try again.')
            mode = (request.form.get('mode') or mode or 'work_done').strip()

            if mode == 'free_text':
                text = request.form.get('note', '')
                target = request.form.get('target') or None
                if target == '':
                    target = None
                extracted = text_extract.extract(text, target=target)
                if request.form.get('confirm') == '1':
                    fields = extracted.get('fields') or {}
                    tgt = extracted.get('target') or 'daily_progress'
                    draft = capture.build_draft(fields, source=capture.AI)
                    record = capture.to_record(draft)
                    if tgt == 'ncr':
                        desc = str(record.get('description') or '').strip()
                        if not desc:
                            flash = 'Could not extract an NCR description.'
                        else:
                            cur = conn.execute(
                                'INSERT INTO ncrs (description, severity, '
                                'raised_date, status) VALUES (?, ?, ?, ?)',
                                (desc, str(record.get('severity') or 'Major'),
                                 str(record.get('raised_date') or ''),
                                 'Open'))
                            auth.audit(conn, sess['username'], 'mobile_capture',
                                       'ncrs', cur.lastrowid,
                                       origin=auth.ORIGIN_AI)
                            conn.commit()
                            flash = 'Saved NCR #{}'.format(cur.lastrowid)
                    elif tgt == 'work_done':
                        activity = str(record.get('activity') or '').strip()
                        if not activity:
                            flash = 'Could not extract activity.'
                        else:
                            try:
                                qty = float(record.get('qty') or 0)
                            except (TypeError, ValueError):
                                qty = 0.0
                            cur = conn.execute(
                                'INSERT INTO work_done_entries '
                                '(activity, unit, qty, entry_date, remarks) '
                                'VALUES (?, ?, ?, ?, ?)',
                                (activity, str(record.get('unit') or ''),
                                 qty, str(record.get('entry_date') or ''),
                                 str(record.get('remarks') or '')[:200]))
                            auth.audit(conn, sess['username'], 'mobile_capture',
                                       'work_done_entries', cur.lastrowid,
                                       origin=auth.ORIGIN_AI)
                            conn.commit()
                            flash = 'Saved work-done #{}'.format(cur.lastrowid)
                    else:
                        try:
                            labour = float(record.get('labour_count') or 0)
                        except (TypeError, ValueError):
                            labour = 0.0
                        try:
                            plant = float(record.get('plant_count') or 0)
                        except (TypeError, ValueError):
                            plant = 0.0
                        cur = conn.execute(
                            'INSERT INTO daily_progress '
                            '(report_date, weather, labour_count, plant_count, '
                            'work_summary) VALUES (?, ?, ?, ?, ?)',
                            (str(record.get('report_date') or ''),
                             str(record.get('weather') or ''), labour, plant,
                             str(record.get('work_summary') or '')[:500]))
                        auth.audit(conn, sess['username'], 'mobile_capture',
                                   'daily_progress', cur.lastrowid,
                                   origin=auth.ORIGIN_AI)
                        conn.commit()
                        flash = 'Saved daily progress #{}'.format(cur.lastrowid)
                else:
                    preview = ('Detected <strong>{}</strong>. Fields: {} '
                               '— set Confirm to save.').format(
                        R.esc(extracted.get('target') or ''),
                        R.esc(str(extracted.get('fields') or {})))

            elif mode == 'muster':
                text = request.form.get('names', '')
                att_date = (request.form.get('att_date')
                            or date.today().isoformat())
                labor_rows = conn.execute(
                    "SELECT id, name, father_name FROM labor "
                    "WHERE status = 'Active'").fetchall()
                draft = muster_draft.draft_from_text(text, labor_rows, att_date)
                if request.form.get('confirm') == '1':
                    written = 0
                    for row in draft.get('rows') or []:
                        if not row.get('labor_id'):
                            continue
                        lid = int(row['labor_id'])
                        conn.execute(
                            'DELETE FROM attendance WHERE labor_id = ? '
                            'AND att_date = ?', (lid, att_date))
                        conn.execute(
                            'INSERT INTO attendance '
                            '(labor_id, att_date, status, hours) '
                            'VALUES (?, ?, ?, ?)',
                            (lid, att_date, row.get('status') or 'Present',
                             float(row.get('hours') or 8)))
                        written += 1
                    auth.audit(conn, sess['username'], 'mobile_muster',
                               'attendance', None,
                               detail='{} marks'.format(written),
                               origin=auth.ORIGIN_MANUAL)
                    conn.commit()
                    flash = 'Saved {} attendance mark(s) for {}.'.format(
                        written, att_date)
                else:
                    preview = (
                        'Matched {} / unmatched {} for {} — set Confirm to '
                        'write.').format(
                        draft.get('matched'), draft.get('unmatched'),
                        R.esc(att_date))

            else:
                fields = {
                    'site_id': request.form.get('site_id', ''),
                    'activity': request.form.get('activity', ''),
                    'unit': request.form.get('unit', ''),
                    'qty': request.form.get('qty', ''),
                    'entry_date': request.form.get('entry_date', '')
                                  or date.today().isoformat(),
                    'remarks': request.form.get('remarks', ''),
                }
                draft = capture.build_draft(fields, source=capture.MANUAL)
                record = capture.to_record(draft)
                activity = str(record.get('activity') or '').strip()
                if not activity:
                    flash = 'Activity is required.'
                else:
                    try:
                        site_id = int(record.get('site_id') or 0) or None
                    except (TypeError, ValueError):
                        site_id = None
                    try:
                        qty = float(record.get('qty') or 0)
                    except (TypeError, ValueError):
                        qty = 0.0
                    cur = conn.execute(
                        'INSERT INTO work_done_entries '
                        '(site_id, activity, unit, qty, entry_date, remarks) '
                        'VALUES (?, ?, ?, ?, ?, ?)',
                        (site_id, activity,
                         str(record.get('unit') or '').strip(), qty,
                         str(record.get('entry_date') or '').strip(),
                         str(record.get('remarks') or '').strip()))
                    new_id = cur.lastrowid
                    auth.audit(conn, sess['username'], 'mobile_capture',
                               'work_done_entries', new_id,
                               origin=auth.ORIGIN_MANUAL)
                    conn.commit()
                    flash = 'Saved work-done #{} — {}'.format(new_id, activity)

        site_opts = [(str(i), n) for i, n in sites]
        switch = (
            '<p>'
            '<a class="btn ghost" href="/m/capture?mode=work_done">Work done</a> '
            '<a class="btn ghost" href="/m/capture?mode=free_text">Paste note</a> '
            '<a class="btn ghost" href="/m/capture?mode=muster">Muster</a>'
            '</p>')
        if mode == 'free_text':
            note_val = request.form.get('note', '') if request.method == 'POST' else ''
            rows = [
                R.field_row('Mode', '<input type="hidden" name="mode" '
                             'value="free_text">Paste note'),
                R.field_row('Note', R.control('textarea', 'note', note_val)),
                R.field_row('Force target', R.control(
                    'combo', 'target', '',
                    [('', 'auto'), ('work_done', 'work_done'),
                     ('daily_progress', 'daily_progress'), ('ncr', 'ncr')])),
                R.field_row('Confirm write', R.control(
                    'combo', 'confirm', '0',
                    [('0', 'Preview only'), ('1', 'Confirm & save')])),
            ]
            submit = 'Preview / Save'
        elif mode == 'muster':
            rows = [
                R.field_row('Mode', '<input type="hidden" name="mode" '
                             'value="muster">Muster names'),
                R.field_row('Date', R.control(
                    'text', 'att_date', date.today().isoformat())),
                R.field_row('Names (one per line)', R.control(
                    'textarea', 'names', '')),
                R.field_row('Confirm write', R.control(
                    'combo', 'confirm', '0',
                    [('0', 'Preview only'), ('1', 'Confirm & save')])),
            ]
            submit = 'Preview / Save'
        else:
            rows = [
                R.field_row('Mode', '<input type="hidden" name="mode" '
                             'value="work_done">Work done'),
                R.field_row('Site', R.control('fk', 'site_id', '', site_opts)),
                R.field_row('Activity', R.control('text', 'activity', '')),
                R.field_row('Unit', R.control('text', 'unit', 'cum')),
                R.field_row('Qty', R.control('number', 'qty', '')),
                R.field_row('Date', R.control(
                    'text', 'entry_date', date.today().isoformat())),
                R.field_row('Remarks', R.control('textarea', 'remarks', '')),
            ]
            submit = 'Confirm & save'
        form_html = R.form('/m/capture', ''.join(rows), sess['csrf'],
                           submit=submit)
        note = ('<p class="muted">Phone-friendly field capture into the same '
                'SQLite file. Paste-note and muster support Preview then Confirm. '
                'AI photo/voice fill is a local sidecar (L8).</p>')
        body = '<h1>Field capture</h1>' + note + switch
        if flash:
            body += '<p><strong>{}</strong></p>'.format(R.esc(flash))
        if preview:
            body += '<p class="muted">{}</p>'.format(preview)
        body += form_html
        return _shell('Field capture', body, sess, conn, active='capture')
    finally:
        conn.close()


def _review_body(pack):
    def li(items):
        return '<ul>{}</ul>'.format(''.join(
            '<li>{}</li>'.format(R.esc(x)) for x in items))

    parts = ['<h1>Weekly Review</h1>',
             '<p class="muted">Generated {} · a draft to read, not a decision '
             '— nothing here books, files or pays.</p>'.format(
                 R.esc(pack['generated']))]

    # In plain words
    parts.append('<h2>In plain words</h2>')
    parts.append(li(pack['narrative']['kpi'] or ['Nothing notable to report.']))
    if pack['narrative']['risk']:
        parts.append('<p class="muted">{}</p>'.format(
            R.esc(pack['narrative']['risk']).replace('\n', '<br>')))

    # Money at a glance
    k = pack['kpis']
    money_cards = [
        ('Cash in hand', R.money(k['cash'])),
        ('Receivable', R.money(k['receivable'])),
        ('Past 90 days', R.money(k['receivable_90plus'])),
        ('Payable', R.money(k['payable'])),
        ('Billed this month', R.money(k['billed_this_month'])),
        ('Collected this month', R.money(k['collected_this_month'])),
    ]
    parts.append('<h2>Money at a glance</h2>')
    parts.append('<div class="cards">{}</div>'.format(''.join(
        '<div class="card"><div class="k">{}</div><div class="v">{}</div></div>'
        .format(R.esc(a), R.esc(b)) for a, b in money_cards)))

    # Earned value (portfolio)
    e = pack.get('evm')
    if e:
        parts.append('<h2>Earned value (portfolio)</h2>')
        parts.append(
            '<p>{n} project(s) measured · CPI {cpi} · SPI {spi} · {oc} over '
            'cost · {bh} behind.{worst}</p>'.format(
                n=e['projects'], cpi=_evm_index(e['cpi']),
                spi=_evm_index(e['spi']), oc=e['over_cost'],
                bh=e['behind_schedule'],
                worst=(' Worst: {} (CPI {}).'.format(
                    R.esc(e['worst_cpi']), _evm_index(e['worst_cpi_value']))
                    if e['worst_cpi'] else '')))

    # Advisories
    adv = pack['advisories']
    c = adv['counts']
    parts.append('<h2>Advisories</h2>')
    parts.append('<p class="muted">{} to act on · {} to watch · {} good · {} '
                 'info</p>'.format(c.get('act', 0), c.get('watch', 0),
                                   c.get('good', 0), c.get('info', 0)))
    for card in adv['cards']:
        parts.append(
            '<div class="adv {sev}"><div class="t">{title}</div>'
            '<div class="m">{detail}</div>'
            '<div class="m"><strong>Do:</strong> {action} '
            '<span class="muted">· {where}</span></div></div>'.format(
                sev=R.esc(card['severity']), title=R.esc(card['title']),
                detail=R.esc(card['detail']), action=R.esc(card['action']),
                where=R.esc(card.get('where', ''))))

    # Risks
    r = pack['risks']
    parts.append('<h2>Risks</h2>')
    if not r['count']:
        parts.append('<p class="muted">No risks flagged on the numbers '
                     'recorded so far.</p>')
    else:
        parts.append('<p class="muted">{} flagged · {} need action now · total '
                     'expected exposure {}</p>'.format(
                         r['count'], r['needs_action'],
                         R.money(r['total_expected_exposure'])))
        parts.append(li('[{}] {} — {}'.format(
            t['band'], t.get('title', 'risk'), t.get('basis', ''))
            for t in r['top']))

    # Opportunities
    o = pack.get('opportunities')
    if o and o['count']:
        parts.append('<h2>Opportunities</h2>')
        parts.append('<p class="muted">{} logged · {} worth pursuing now · '
                     'total expected upside {}</p>'.format(
                         o['count'], o['pursue_now'],
                         R.money(o['total_expected_value'])))
        parts.append(li('[{}] {} — expected upside {}'.format(
            t.get('band', 'Low'), t.get('title', 'opportunity'),
            R.money(t.get('expected_value'))) for t in o['top']))

    return ''.join(parts)


def _table_route(request, sess, rest):
    """Route everything under /t/ — list, record view, and (for the writable
    Masters) new / edit / delete."""
    segs = [s for s in rest.split('/') if s]
    if not segs:
        return _redirect('/')
    table = segs[0]
    conn = db.get_conn()
    try:
        if table not in _viewable_tables(conn):
            return _page('Not found',
                         '<p class="muted">No such register.</p>', sess, conn,
                         status=404)
        cols = _columns(conn, table)
        if len(segs) == 2 and segs[1] == 'new':
            if web_docs.is_doc(table):
                return _doc_create(request, sess, conn, table)
            if table == 'estimates':
                return _estimate_editor(request, sess, conn, None)
            return _master_create(request, sess, conn, table, cols)
        if len(segs) == 3 and segs[2] == 'print' and table == 'estimates':
            return _print_estimate(conn, segs[1])
        if len(segs) == 3 and table == 'ra_bills' and segs[2] in ('mb', 'ra'):
            return _print_ra_document(conn, segs[1], segs[2])
        if len(segs) == 3 and segs[2] == 'edit':
            if table == 'estimates':
                return _estimate_editor(request, sess, conn, segs[1])
            return _master_edit(request, sess, conn, table, cols, segs[1])
        if len(segs) == 3 and segs[2] == 'delete':
            return _row_delete(request, sess, conn, table, cols, segs[1])
        if len(segs) == 2:
            return _record(conn, sess, table, cols, segs[1])
        return _register_list(request, conn, sess, table, cols)
    finally:
        conn.close()


def _register_list(request, conn, sess, table, cols):
    colnames = [c[0] for c in cols]
    text_cols = [c[0] for c in cols if 'CHAR' in c[1] or 'TEXT' in c[1]
                 or 'CLOB' in c[1] or c[1] == '']
    q = (request.query.get('q') or '').strip()
    show = colnames[:9]     # a manageable width; the record view has every field
    pk = _pk(cols)

    where, params = '', []
    if q and text_cols:
        clauses = ' OR '.join('"{}" LIKE ?'.format(c) for c in text_cols)
        where = ' WHERE ' + clauses
        params = ['%{}%'.format(q)] * len(text_cols)

    total = conn.execute(
        'SELECT COUNT(*) AS c FROM "{}"{}'.format(table, where),
        params).fetchone()['c']

    # Sort: the column must be one on screen (identifiers come only from that
    # trusted set, never the raw query value). Default is newest-first by pk.
    sort = request.query.get('sort') or ''
    if sort not in show:
        sort = ''
    direction = 'asc' if request.query.get('dir') == 'asc' else 'desc'
    if sort:
        order = ' ORDER BY "{}" {}'.format(sort, 'ASC' if direction == 'asc'
                                           else 'DESC')
    elif pk:
        order = ' ORDER BY "{}" DESC'.format(pk)
    else:
        order = ''

    # Scroll, not pages: fetch a generous window and let the table scroll; if
    # there is more, say so (honest, not silently truncated).
    rows = conn.execute(
        'SELECT {} FROM "{}"{}{} LIMIT ?'.format(
            ', '.join('"{}"'.format(c) for c in show), table, where, order),
        params + [MAX_ROWS]).fetchall()

    data = [[r[c] for c in show] for r in rows]
    link = None
    if pk:
        ids = [r[pk] for r in rows]
        link = lambda i: '/t/{}/{}'.format(table, ids[i])

    def sort_href(col):
        # first click on a column sorts ascending; clicking it again flips
        nd = 'desc' if (sort == col and direction == 'asc') else 'asc'
        parts = (['q=' + urllib.parse.quote(q)] if q else []) + [
            'sort=' + urllib.parse.quote(col), 'dir=' + nd]
        return '/t/{}?{}'.format(table, '&'.join(parts))

    header_links = [(sort_href(c),
                     ('' if sort != c else (' ▲' if direction == 'asc' else ' ▼')))
                    for c in show]

    add_btn = ''
    if _can_create(table) and can_write(sess['role']):
        add_btn = '<a class="btn" href="/t/{tbl}/new">+ New {lbl}</a>'.format(
            tbl=R.esc(table), lbl=R.esc(_create_label(table)))
    count_txt = ('{} record(s)'.format(total) if total <= MAX_ROWS else
                 'showing first {} of {} — search to narrow'.format(len(data),
                                                                    total))
    search = (
        '<div class="toolbar"><form method="get" action="/t/{tbl}">'
        '<input type="search" name="q" placeholder="Search {lbl}…" value="{q}">'
        '<button class="btn ghost" type="submit">Search</button></form>'
        '<span class="muted">{count}</span>{add}</div>'
    ).format(tbl=R.esc(table), lbl=R.esc(_label(table)), q=R.esc(q),
             count=R.esc(count_txt), add=add_btn)

    body = ['<h1>{}</h1>'.format(R.esc(_label(table))), search,
            R.table([_label(c) for c in show], data, link=link,
                    header_links=header_links, scroll=True)]
    return _shell(_label(table), ''.join(body), sess, conn, active=table)


def _record(conn, sess, table, cols, rid):
    pk = _pk(cols)
    if not pk:
        return _page('Not found', '<p class="muted">No record view.</p>',
                     sess, conn, status=404)
    row = conn.execute('SELECT * FROM "{}" WHERE "{}" = ?'.format(table, pk),
                       (rid,)).fetchone()
    if not row:
        return _page('Not found', '<p class="muted">Record not found.</p>',
                     sess, conn, status=404)
    items = ''.join('<dt>{}</dt><dd>{}</dd>'.format(R.esc(_label(c[0])),
                                                    R.esc(row[c[0]]))
                    for c in cols)
    actions = ''
    if _is_writable(table) and can_write(sess['role']):
        actions = ('<div class="rowbtns">'
                   '<a class="btn" href="/t/{tbl}/{rid}/edit">Edit</a>{delete}'
                   '</div>').format(
            tbl=R.esc(table), rid=R.esc(rid),
            delete=R.post_button(
                '/t/{}/{}/delete'.format(table, rid), sess['csrf'], 'Delete',
                confirm='Delete this {}?'.format(_writable_label(table))))
    extra = ''
    if table == 'estimates':
        extra = ('<p><a class="btn ghost" href="/t/estimates/{rid}/print" '
                 'target="_blank" rel="noopener">Print / Save as PDF</a></p>'
                 '{lines}').format(rid=R.esc(rid),
                                   lines=_estimate_lines_html(conn, rid))
    elif table == 'ra_bills':
        extra = ('<p><a class="btn ghost" href="/t/ra_bills/{rid}/mb" '
                 'target="_blank" rel="noopener">Measurement Book (Form 23)</a> '
                 '<a class="btn ghost" href="/t/ra_bills/{rid}/ra" '
                 'target="_blank" rel="noopener">RA abstract (PWD Form 26)</a>'
                 '</p>{items}').format(rid=R.esc(rid),
                                       items=_ra_items_html(conn, rid))
    body = ('<h1>{lbl} #{rid}</h1><p><a class="btn ghost" href="/t/{tbl}">'
            '‹ Back to {lbl}</a></p>{actions}<dl class="dl">{items}</dl>'
            '{extra}').format(
        lbl=R.esc(_label(table)), rid=R.esc(rid), tbl=R.esc(table),
        actions=actions, items=items, extra=extra)
    return _shell(_label(table), body, sess, conn, active=table)


# ------------------------------------------------------------ master writes
def _coerce_all(specs, form):
    """Validate + convert a submitted form against a master's field specs."""
    values, errs = {}, []
    for f in specs:
        ok, val, err = web_masters.coerce(f, form.get(f['key'], ''))
        if ok:
            values[f['key']] = val
        else:
            errs.append(err)
    return values, errs


def _master_form(conn, sess, table, row, errs=None, submitted=None):
    specs = web_masters.fields(table)
    lbl = web_masters.label(table)
    editing = row is not None
    pk = _pk(_columns(conn, table)) or 'id'
    rid = row[pk] if editing else None
    rows_html = [R.errors(errs)] if errs else []
    for f in specs:
        if submitted is not None:
            val = submitted.get(f['key'], '')
        elif editing:
            val = row[f['key']]
        else:
            val = web_masters.resolve_default(f['default'])
        options = None
        if f['kind'] == 'fk':
            options = web_masters.fk_options(conn, f['fk_sql'])
        elif f['kind'] == 'combo':
            options = [(o, o) for o in f['options']]
        rows_html.append(R.field_row(
            f['label'], R.control(f['kind'], f['key'], val, options)))
    action = ('/t/{}/{}/edit'.format(table, rid) if editing
              else '/t/{}/new'.format(table))
    title = '{} {}'.format('Edit' if editing else 'New', lbl)
    body = '<h1>{}</h1>{}'.format(R.esc(title), R.form(
        action, ''.join(rows_html), sess['csrf'], submit='Save',
        cancel_href='/t/' + table))
    return _shell(title, body, sess, conn, active=table)


def _guard_write(request, sess, conn):
    """Role + CSRF gate for any authenticated write. Returns a Response to bail
    with, or None to proceed."""
    if not can_write(sess['role']):
        return _forbidden(sess, conn, 'Your account is read-only (Viewer).')
    if request.method == 'POST' and not _csrf_ok(request, sess):
        return _forbidden(sess, conn,
                          'Your session expired — reload the page and retry.')
    return None


def _master_guard(request, sess, conn, table):
    """Precondition for the flat-master write routes."""
    if not web_masters.is_master(table):
        return _page('Not found', '<p class="muted">This register is '
                     'view-only for now.</p>', sess, conn, status=404)
    return _guard_write(request, sess, conn)


def _master_create(request, sess, conn, table, cols):
    bail = _master_guard(request, sess, conn, table)
    if bail:
        return bail
    specs = web_masters.fields(table)
    if request.method != 'POST':
        return _master_form(conn, sess, table, None)
    values, errs = _coerce_all(specs, request.form)
    if errs:
        return _master_form(conn, sess, table, None, errs, request.form)
    keys = list(values.keys())
    cur = conn.execute(
        'INSERT INTO "{}" ({}) VALUES ({})'.format(
            table, ', '.join('"{}"'.format(k) for k in keys),
            ', '.join('?' * len(keys))), [values[k] for k in keys])
    auth.audit(conn, sess['username'], 'web_create', table, cur.lastrowid)
    conn.commit()
    return _redirect('/t/{}/{}'.format(table, cur.lastrowid))


def _master_edit(request, sess, conn, table, cols, rid):
    bail = _master_guard(request, sess, conn, table)
    if bail:
        return bail
    specs = web_masters.fields(table)
    pk = _pk(cols) or 'id'
    row = conn.execute('SELECT * FROM "{}" WHERE "{}" = ?'.format(table, pk),
                       (rid,)).fetchone()
    if not row:
        return _page('Not found', '<p class="muted">Record not found.</p>',
                     sess, conn, status=404)
    if request.method != 'POST':
        return _master_form(conn, sess, table, row)
    values, errs = _coerce_all(specs, request.form)
    if errs:
        return _master_form(conn, sess, table, row, errs, request.form)
    keys = list(values.keys())
    conn.execute(
        'UPDATE "{}" SET {} WHERE "{}" = ?'.format(
            table, ', '.join('"{}" = ?'.format(k) for k in keys), pk),
        [values[k] for k in keys] + [rid])
    auth.audit(conn, sess['username'], 'web_update', table, rid)
    conn.commit()
    return _redirect('/t/{}/{}'.format(table, rid))


def _row_delete(request, sess, conn, table, cols, rid):
    if not _is_writable(table):
        return _page('Not found', '<p class="muted">This register is '
                     'view-only for now.</p>', sess, conn, status=404)
    bail = _guard_write(request, sess, conn)
    if bail:
        return bail
    if request.method != 'POST':
        return _redirect('/t/{}/{}'.format(table, rid))
    pk = _pk(cols) or 'id'
    try:
        conn.execute('DELETE FROM "{}" WHERE "{}" = ?'.format(table, pk), (rid,))
        auth.audit(conn, sess['username'], 'web_delete', table, rid)
        conn.commit()
    except sqlite3.IntegrityError:
        return _page(
            'Cannot delete',
            '<p>This record is still used elsewhere (it has linked entries), so '
            'it cannot be deleted. Remove or reassign those first, or mark it '
            'inactive instead.</p><p><a class="btn ghost" href="/t/{tbl}/{rid}">'
            '‹ Back</a></p>'.format(tbl=R.esc(table), rid=R.esc(rid)),
            sess, conn, active=table, status=409)
    return _redirect('/t/{}'.format(table))


# --------------------------------------------------------- estimates (3a)
# Estimates = header + line items + a computed total (estimate.estimate_totals),
# with NO ledger posting — so they are safe to edit in the browser without the
# double-entry engine (that is reserved for bills / RA bills / payments).
def _int_or_none(value):
    value = (value or '').strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _estimate_lines_html(conn, rid):
    items = conn.execute(
        'SELECT item_code, description, unit, qty, rate, amount FROM '
        'estimate_items WHERE estimate_id = ? ORDER BY id', (rid,)).fetchall()
    if not items:
        return '<h2>Line items</h2><p class="muted">No line items.</p>'
    rows = [[i['item_code'], i['description'], i['unit'], i['qty'], i['rate'],
             R.money(i['amount'])] for i in items]
    tbl = R.table(['Code', 'Description', 'Unit', 'Qty', 'Rate', 'Amount'], rows)
    est = conn.execute('SELECT contingency_pct, gst_pct FROM estimates '
                       'WHERE id = ?', (rid,)).fetchone()
    t = estimate.estimate_totals(items, est['contingency_pct'] if est else 0,
                                 est['gst_pct'] if est else 0)
    summary = (
        '<dl class="dl" style="margin-top:14px;max-width:420px">'
        '<dt>Subtotal</dt><dd>{sub}</dd>'
        '<dt>Contingency</dt><dd>{con}</dd>'
        '<dt>Taxable</dt><dd>{tax}</dd>'
        '<dt>GST</dt><dd>{gst}</dd>'
        '<dt>Grand total</dt><dd><strong>{grand}</strong></dd></dl>').format(
        sub=R.money(t['subtotal']), con=R.money(t['contingency']),
        tax=R.money(t['taxable']), gst=R.money(t['gst']),
        grand=R.money(t['grand_total']))
    return '<h2>Line items</h2>' + tbl + summary


def _parse_estimate(request):
    """Read the estimate form into (header dict, line list, errors)."""
    f = request.form
    errs = []

    def num(key, label):
        raw = (f.get(key) or '').strip()
        if raw == '':
            return 0.0
        try:
            return float(raw)
        except ValueError:
            errs.append('{} must be a number.'.format(label))
            return 0.0

    hdr = {
        'est_number': (f.get('est_number') or '').strip(),
        'title': (f.get('title') or '').strip(),
        'site_id': _int_or_none(f.get('site_id')),
        'estimate_date': (f.get('estimate_date') or '').strip(),
        'status': (f.get('status') or 'Draft').strip(),
        'contingency_pct': num('contingency_pct', 'Contingency %'),
        'gst_pct': num('gst_pct', 'GST %'),
        'notes': (f.get('notes') or '').strip(),
    }
    if not hdr['title']:
        errs.append('Title is required.')

    m = request.form_multi
    codes = m.get('li_code', [])
    descs = m.get('li_desc', [])
    units = m.get('li_unit', [])
    qtys = m.get('li_qty', [])
    rates = m.get('li_rate', [])
    n = max(len(codes), len(descs), len(units), len(qtys), len(rates))

    def at(seq, i):
        return (seq[i] if i < len(seq) else '').strip()

    lines = []
    for i in range(n):
        code, desc = at(codes, i), at(descs, i)
        unit, qraw, rraw = at(units, i), at(qtys, i), at(rates, i)
        if not any([code, desc, qraw, rraw]):
            continue                       # a wholly blank row — ignore
        try:
            qty = float(qraw or 0)
        except ValueError:
            errs.append('Qty "{}" is not a number.'.format(qraw)); qty = 0.0
        try:
            rate = float(rraw or 0)
        except ValueError:
            errs.append('Rate "{}" is not a number.'.format(rraw)); rate = 0.0
        lines.append({'item_code': code, 'description': desc, 'unit': unit,
                      'qty': qty, 'rate': rate,
                      'amount': estimate.item_amount(rate, qty)})
    if not lines:
        errs.append('Add at least one line item.')
    return hdr, lines, errs


def _estimate_editor(request, sess, conn, rid):
    bail = _guard_write(request, sess, conn)
    if bail:
        return bail
    editing = rid is not None
    row = None
    if editing:
        row = conn.execute('SELECT * FROM estimates WHERE id = ?',
                           (rid,)).fetchone()
        if not row:
            return _page('Not found', '<p class="muted">Estimate not found.</p>',
                         sess, conn, status=404)

    if request.method != 'POST':
        lines = []
        if editing:
            lines = [dict(item_code=r['item_code'], description=r['description'],
                          unit=r['unit'], qty=r['qty'], rate=r['rate'])
                     for r in conn.execute(
                         'SELECT item_code, description, unit, qty, rate FROM '
                         'estimate_items WHERE estimate_id = ? ORDER BY id',
                         (rid,))]
        return _estimate_form(conn, sess, rid, row, lines, None, None)

    hdr, lines, errs = _parse_estimate(request)
    if errs:
        return _estimate_form(conn, sess, rid, row, lines, errs, hdr)
    total = estimate.estimate_totals(
        lines, hdr['contingency_pct'], hdr['gst_pct'])['grand_total']
    if editing:
        conn.execute(
            'UPDATE estimates SET est_number=?, title=?, site_id=?, '
            'estimate_date=?, status=?, contingency_pct=?, gst_pct=?, notes=?, '
            'total_estimate=? WHERE id=?',
            (hdr['est_number'], hdr['title'], hdr['site_id'],
             hdr['estimate_date'], hdr['status'], hdr['contingency_pct'],
             hdr['gst_pct'], hdr['notes'], total, rid))
        conn.execute('DELETE FROM estimate_items WHERE estimate_id = ?', (rid,))
        eid = rid
    else:
        cur = conn.execute(
            'INSERT INTO estimates (est_number, title, site_id, estimate_date, '
            'status, contingency_pct, gst_pct, notes, total_estimate) VALUES '
            '(?,?,?,?,?,?,?,?,?)',
            (hdr['est_number'], hdr['title'], hdr['site_id'],
             hdr['estimate_date'], hdr['status'], hdr['contingency_pct'],
             hdr['gst_pct'], hdr['notes'], total))
        eid = cur.lastrowid
    for ln in lines:
        conn.execute(
            'INSERT INTO estimate_items (estimate_id, item_code, description, '
            'unit, qty, rate, amount) VALUES (?,?,?,?,?,?,?)',
            (eid, ln['item_code'], ln['description'], ln['unit'], ln['qty'],
             ln['rate'], ln['amount']))
    auth.audit(conn, sess['username'],
               'web_update' if editing else 'web_create', 'estimates', eid)
    conn.commit()
    return _redirect('/t/estimates/{}'.format(eid))


def _est_line_row(line):
    def cell(name, val, width=''):
        style = ' style="width:{}px"'.format(width) if width else ''
        return ('<td><input type="text" name="{n}" value="{v}"{s}></td>'.format(
            n=name, v=R.esc('' if val is None else val), s=style))
    return ('<tr>' + cell('li_code', line.get('item_code', ''), 90)
            + cell('li_desc', line.get('description', ''))
            + cell('li_unit', line.get('unit', ''), 70)
            + cell('li_qty', line.get('qty', ''), 80)
            + cell('li_rate', line.get('rate', ''), 100)
            + '<td><button type="button" class="btn ghost" '
              'onclick="delLine(this)">✕</button></td></tr>')


def _estimate_form(conn, sess, rid, row, lines, errs, submitted):
    def hv(key, default=''):
        if submitted is not None:
            return submitted.get(key, default)
        if row is not None:
            return row[key]
        return default

    site_opts = web_masters.fk_options(conn, 'SELECT id, name FROM sites '
                                             'ORDER BY name')
    header = ''.join([
        R.field_row('Estimate number', R.control('text', 'est_number',
                                                 hv('est_number'))),
        R.field_row('Title', R.control('text', 'title', hv('title'))),
        R.field_row('Site', R.control('fk', 'site_id', hv('site_id'), site_opts)),
        R.field_row('Date', R.control('text', 'estimate_date',
                                      hv('estimate_date'))),
        R.field_row('Status', R.control('combo', 'status', hv('status', 'Draft'),
                                        [('Draft', 'Draft'), ('Final', 'Final')])),
        R.field_row('Contingency %', R.control('number', 'contingency_pct',
                                               hv('contingency_pct', '0'))),
        R.field_row('GST %', R.control('number', 'gst_pct', hv('gst_pct', '18'))),
        R.field_row('Notes', R.control('textarea', 'notes', hv('notes'))),
    ])
    shown = lines if lines else [{}]
    rows_html = ''.join(_est_line_row(dict(item_code=l.get('item_code', ''),
                                           description=l.get('description', ''),
                                           unit=l.get('unit', ''),
                                           qty=l.get('qty', ''),
                                           rate=l.get('rate', '')))
                        for l in shown)
    blank = _est_line_row({})
    editing = rid is not None
    action = ('/t/estimates/{}/edit'.format(rid) if editing
              else '/t/estimates/new')
    title = '{} Estimate'.format('Edit' if editing else 'New')
    body = (
        '<h1>{title}</h1>{errs}'
        '<form method="post" action="{action}">'
        '<input type="hidden" name="csrf" value="{csrf}">'
        '{header}'
        '<h2>Line items</h2>'
        '<div class="tablewrap"><table><thead><tr><th>Code</th>'
        '<th>Description</th><th>Unit</th><th>Qty</th><th>Rate</th><th></th>'
        '</tr></thead><tbody id="li-body">{rows}</tbody></table></div>'
        '<p><button type="button" class="btn ghost" onclick="addLine()">'
        '+ Add line</button></p>'
        '<div class="formbtns"><button class="btn" type="submit">Save</button>'
        '<a class="btn ghost" href="/t/estimates">Cancel</a></div></form>'
        '<template id="li-tpl">{blank}</template>'
        '<script>function addLine(){{document.getElementById("li-body")'
        '.appendChild(document.getElementById("li-tpl").content.cloneNode(true));}}'
        'function delLine(b){{var t=document.getElementById("li-body");'
        'if(t.rows.length>1){{b.closest("tr").remove();}}}}</script>'
    ).format(title=R.esc(title), errs=R.errors(errs), action=R.esc(action),
             csrf=R.esc(sess['csrf']), header=header, rows=rows_html, blank=blank)
    return _shell(title, body, sess, conn, active='estimates')


def _seller(conn):
    """Firm identity for a printed document, from app_settings — the same three
    fields the desktop's estimate/invoice export uses."""
    rows = {r['key']: r['value'] for r in conn.execute(
        "SELECT key, value FROM app_settings WHERE key IN "
        "('company_name', 'seller_gstin', 'seller_address')")}
    return {'name': rows.get('company_name') or 'Construction OS',
            'gstin': rows.get('seller_gstin', ''),
            'address': rows.get('seller_address', '')}


def _print_estimate(conn, rid):
    """Serve the printable estimate document (browser Print / Save-as-PDF),
    generated by the same pure ``bill_export.build_estimate_html`` the desktop
    uses. A standalone page — not wrapped in the app chrome."""
    est = conn.execute('SELECT * FROM estimates WHERE id = ?', (rid,)).fetchone()
    if not est:
        return Response('Estimate not found', status=404)
    items = conn.execute(
        'SELECT item_code, description, unit, qty, rate, amount FROM '
        'estimate_items WHERE estimate_id = ? ORDER BY id', (rid,)).fetchall()
    seller = _seller(conn)
    html = bill_export.build_estimate_html(
        est, items, seller, company_name=seller.get('name') or 'Construction OS')
    return Response(html)


def _print_ra_document(conn, rid, kind):
    """Serve a statutory RA document as a standalone printable page (not the app
    chrome): ``mb`` = the contract's Measurement Book (Form 23 / CMB), ``ra`` =
    the RA bill's PWD-style abstract (Form 26). Both come from the pure
    ``bill_export`` builders via ``mb_report``, identical to the desktop."""
    if kind == 'mb':
        bill = conn.execute('SELECT contract_id FROM ra_bills WHERE id = ?',
                            (rid,)).fetchone()
        if not bill or bill['contract_id'] is None:
            return Response('This bill has no contract to measure against.',
                            status=404)
        return Response(mb_report.measurement_book_html(conn,
                                                        bill['contract_id']))
    html = mb_report.ra_abstract_html(conn, rid)
    if html is None:
        return Response('RA bill not found', status=404)
    return Response(html)


def _ra_items_html(conn, rid):
    """The measured items on an RA bill, for the browser record view."""
    rows = conn.execute(
        "SELECT b.item_no, b.description, b.unit, ri.upto_qty, ri.previous_qty, "
        "ri.current_qty, ri.rate, ri.current_amount FROM ra_bill_items ri "
        "LEFT JOIN boq_items b ON b.id = ri.boq_item_id "
        "WHERE ri.ra_bill_id = ? ORDER BY ri.id", (rid,)).fetchall()
    if not rows:
        return ('<p class="muted">No measured items recorded on this bill yet — '
                'enter measurements in the desktop BOQ / RA tab.</p>')

    def q(value):
        return '' if value is None else '%g' % value
    headers = ['Item', 'Description', 'Unit', 'Upto qty', 'Prev qty',
               'This qty', 'Rate', 'This amount']
    trows = [[r['item_no'] or '', r['description'] or '', r['unit'] or '',
              q(r['upto_qty']), q(r['previous_qty']), q(r['current_qty']),
              R.money(r['rate']), R.money(r['current_amount'])] for r in rows]
    return '<h2>Measured items</h2>' + R.table(headers, trows, scroll=True)


# ------------------------------------------------ postable money documents
# Payments, tax/vendor invoices and running bills: save the row with the same
# derived amounts the desktop computes, then post via the shared, idempotent
# journal_post.post_all — so the double entry is produced by posting.py, not
# re-implemented here. Create + view only (records of fact).
def _doc_create(request, sess, conn, table):
    bail = _guard_write(request, sess, conn)
    if bail:
        return bail
    specs = web_docs.fields(table)
    if request.method != 'POST':
        return _doc_form(conn, sess, table, None, None)

    values, errs = {}, []
    for f in specs:
        ok, val, err = web_masters.coerce(f, request.form.get(f['key'], ''))
        if ok:
            values[f['key']] = val
        else:
            errs.append(err)
    if errs:
        return _doc_form(conn, sess, table, errs, request.form)

    columns = web_docs.compute(table, values)
    keys = list(columns.keys())
    cur = conn.execute(
        'INSERT INTO "{}" ({}) VALUES ({})'.format(
            table, ', '.join('"{}"'.format(k) for k in keys),
            ', '.join('?' * len(keys))), [columns[k] for k in keys])
    new_id = cur.lastrowid
    auth.audit(conn, sess['username'], 'web_create', table, new_id)
    conn.commit()
    # Post to the ledger with the shared engine. Idempotent + state-gated, so a
    # Draft posts nothing. A posting hiccup must not lose the saved document —
    # post_all will pick it up next time — so failure here is swallowed.
    try:
        journal_post.post_all(conn)
    except Exception:                                        # noqa: BLE001
        pass
    return _redirect('/t/{}/{}'.format(table, new_id))


def _doc_form(conn, sess, table, errs, submitted):
    specs = web_docs.fields(table)
    lbl = web_docs.label(table)
    note = web_docs.note(table)
    rows_html = [R.errors(errs)] if errs else []
    if note:
        rows_html.append('<p class="muted">{}</p>'.format(R.esc(note)))
    for f in specs:
        if submitted is not None:
            val = submitted.get(f['key'], '')
        else:
            val = web_docs.resolve_default(f['default'])
        options = None
        if f['kind'] == 'fk':
            options = web_masters.fk_options(conn, f['fk_sql'])
        elif f['kind'] == 'combo':
            options = [(o, o) for o in f['options']]
        rows_html.append(R.field_row(
            f['label'], R.control(f['kind'], f['key'], val, options)))
    title = 'New {}'.format(lbl)
    body = '<h1>{}</h1>{}'.format(R.esc(title), R.form(
        '/t/{}/new'.format(table), ''.join(rows_html), sess['csrf'],
        submit='Save', cancel_href='/t/' + table))
    return _shell(title, body, sess, conn, active=table)
