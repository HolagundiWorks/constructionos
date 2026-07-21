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
import threading
import urllib.parse

import db
import auth
import webrender as R

PAGE_SIZE = 50

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
    'payments': 'Payments', 'audit_log': 'Audit Log',
}
_GROUPS = [
    ('Project Management', ['projects', 'timeline_tasks']),
    ('Masters', ['sites', 'clients', 'vendors', 'materials', 'labour',
                 'equipment']),
    ('Billing', ['estimates', 'quotations', 'contracts', 'bills', 'ra_bills',
                 'variations', 'tax_invoices', 'takeoffs', 'bid_assessments']),
    ('Purchases', ['purchase_orders', 'grns', 'vendor_invoices',
                   'subcontracts']),
    ('Money', ['payments']),
]


# --------------------------------------------------------------- HTTP objects
class Request:
    def __init__(self, method, path, query=None, form=None, cookies=None,
                 headers=None, client=''):
        self.method = method
        self.path = path
        self.query = query or {}
        self.form = form or {}
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.client = client


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
        _SESSIONS[token] = {'username': username, 'role': role}
    return token


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
    nav = [('', [('/', 'Dashboard', 'dashboard')])]
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
    if path == '/login':
        return _login(request)
    if path == '/logout':
        return _logout(request)

    sess = _session(request.cookies.get('cosid'))
    if not sess:
        return _redirect('/login')

    if path == '/':
        return _dashboard(request, sess)
    if path == '/t' or path == '/t/':
        return _redirect('/')
    if path.startswith('/t/'):
        return _register(request, sess, path[3:])
    return _page('Not found', '<p class="muted">No such page.</p>', sess, conn=None)


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


def _page(title, body, sess, conn):
    warn = '' if can_write(sess['role']) else \
        'You are signed in as a Viewer — read-only access.'
    return Response(R.page(title, body, user='{} ({})'.format(
        sess['username'], sess['role']), nav=_nav(conn) if conn else [],
        active='dashboard', warning=warn))


def _dashboard(request, sess):
    import dashboard
    import advisory
    conn = db.get_conn()
    try:
        s = dashboard.collect(conn)
        nav = _nav(conn)
        cards = advisory.build(s)
        body = _dashboard_body(s, cards, advisory)
        warn = '' if can_write(sess['role']) else \
            'You are signed in as a Viewer — read-only access.'
        return Response(R.page('Dashboard', body, user='{} ({})'.format(
            sess['username'], sess['role']), nav=nav, active='dashboard',
            warning=warn))
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


def _register(request, sess, key):
    """List (or drill into) a whitelisted register."""
    parts = key.split('/', 1)
    table = parts[0]
    conn = db.get_conn()
    try:
        if table not in _viewable_tables(conn):
            return _page('Not found',
                         '<p class="muted">No such register.</p>', sess, conn)
        cols = _columns(conn, table)
        if len(parts) == 2 and parts[1]:
            return _record(conn, sess, table, cols, parts[1])
        return _register_list(request, conn, sess, table, cols)
    finally:
        conn.close()


def _register_list(request, conn, sess, table, cols):
    colnames = [c[0] for c in cols]
    text_cols = [c[0] for c in cols if 'CHAR' in c[1] or 'TEXT' in c[1]
                 or 'CLOB' in c[1] or c[1] == '']
    q = (request.query.get('q') or '').strip()
    try:
        page = max(1, int(request.query.get('p') or 1))
    except ValueError:
        page = 1

    where, params = '', []
    if q and text_cols:
        clauses = ' OR '.join('"{}" LIKE ?'.format(c) for c in text_cols)
        where = ' WHERE ' + clauses
        params = ['%{}%'.format(q)] * len(text_cols)

    total = conn.execute(
        'SELECT COUNT(*) AS c FROM "{}"{}'.format(table, where),
        params).fetchone()['c']
    offset = (page - 1) * PAGE_SIZE
    # Show a manageable width in the list; the record view has every field.
    show = colnames[:9]
    order = ' ORDER BY "{}" DESC'.format(_pk(cols)) if _pk(cols) else ''
    rows = conn.execute(
        'SELECT {} FROM "{}"{}{} LIMIT ? OFFSET ?'.format(
            ', '.join('"{}"'.format(c) for c in show), table, where, order),
        params + [PAGE_SIZE, offset]).fetchall()

    pk = _pk(cols)
    data = [[r[c] for c in show] for r in rows]
    link = None
    if pk:
        ids = [r[pk] for r in rows]
        link = lambda i: '/t/{}/{}'.format(table, ids[i])

    search = (
        '<div class="toolbar"><form method="get" action="/t/{tbl}">'
        '<input type="search" name="q" placeholder="Search {lbl}…" value="{q}">'
        '<button class="btn ghost" type="submit">Search</button></form>'
        '<span class="muted">{total} record(s)</span></div>'
    ).format(tbl=R.esc(table), lbl=R.esc(_label(table)), q=R.esc(q), total=total)

    body = ['<h1>{}</h1>'.format(R.esc(_label(table))), search,
            R.table([_label(c) for c in show], data, link=link)]

    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if pages > 1:
        nav = ['<div class="pager">']
        base = '/t/{}?{}p='.format(table, ('q=' + urllib.parse.quote(q) + '&') if q else '')
        if page > 1:
            nav.append('<a href="{}{}">‹ Prev</a>'.format(base, page - 1))
        nav.append('<span>Page {} of {}</span>'.format(page, pages))
        if page < pages:
            nav.append('<a href="{}{}">Next ›</a>'.format(base, page + 1))
        nav.append('</div>')
        body.append(''.join(nav))

    warn = '' if can_write(sess['role']) else \
        'You are signed in as a Viewer — read-only access.'
    return Response(R.page(_label(table), ''.join(body), user='{} ({})'.format(
        sess['username'], sess['role']), nav=_nav(conn), active=table,
        warning=warn))


def _record(conn, sess, table, cols, rid):
    pk = _pk(cols)
    if not pk:
        return _page('Not found', '<p class="muted">No record view.</p>',
                     sess, conn)
    row = conn.execute('SELECT * FROM "{}" WHERE "{}" = ?'.format(table, pk),
                       (rid,)).fetchone()
    if not row:
        return _page('Not found', '<p class="muted">Record not found.</p>',
                     sess, conn)
    items = ''.join('<dt>{}</dt><dd>{}</dd>'.format(R.esc(_label(c[0])),
                                                    R.esc(row[c[0]]))
                    for c in cols)
    body = ('<h1>{lbl} #{rid}</h1><p><a class="btn ghost" href="/t/{tbl}">'
            '‹ Back to {lbl}</a></p><dl class="dl">{items}</dl>').format(
        lbl=R.esc(_label(table)), rid=R.esc(rid), tbl=R.esc(table), items=items)
    warn = '' if can_write(sess['role']) else \
        'You are signed in as a Viewer — read-only access.'
    return Response(R.page(_label(table), body, user='{} ({})'.format(
        sess['username'], sess['role']), nav=_nav(conn), active=table,
        warning=warn))
