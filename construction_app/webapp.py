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

import db
import auth
import bill_export
import estimate
import journal_post
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
                 cookies=None, headers=None, client=''):
        self.method = method
        self.path = path
        self.query = query or {}
        self.form = form or {}
        # Repeated fields kept as lists (line-item rows: li_qty=[..], ...).
        self.form_multi = form_multi or {}
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
        return _table_route(request, sess, path[3:])
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
