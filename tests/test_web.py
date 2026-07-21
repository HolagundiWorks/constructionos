"""Tests for the browser/LAN layer — the pure renderers and the router, plus one
real-socket integration check.

The router (``webapp.handle``) is exercised without any socket: a ``Request`` in,
a ``Response`` out. That covers the login gate, the CSRF check, the first-run
admin bootstrap, the whitelist (the ``users`` table must never be reachable) and
the read views. A final test binds a real ``WebServer`` on an ephemeral port and
fetches ``/login`` over HTTP to prove the plumbing agrees with the router.
"""

import os
import sys
import tempfile
import unittest
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, 'construction_app'))

STRONG = 'BuildSite#2026'


def cookie_val(resp, name):
    for c in resp.cookies:
        first = c.split(';', 1)[0]
        if first.startswith(name + '='):
            return first[len(name) + 1:]
    return None


class TestNetinfo(unittest.TestCase):
    def test_urls_shape(self):
        import netinfo
        urls = netinfo.urls(8080)
        self.assertTrue(urls)
        for u in urls:
            self.assertTrue(u.startswith('http://'))
            self.assertTrue(u.endswith(':8080/'))
        self.assertIn('http://127.0.0.1:8080/', urls)

    def test_local_ips_is_a_list_without_loopback(self):
        import netinfo
        ips = netinfo.local_ips()
        self.assertIsInstance(ips, list)
        self.assertNotIn('127.0.0.1', ips)


class TestWebRender(unittest.TestCase):
    def test_escaping(self):
        import webrender as R
        self.assertEqual(R.esc('<a>&"'), '&lt;a&gt;&amp;&quot;')
        self.assertEqual(R.esc(None), '')

    def test_table_and_login(self):
        import webrender as R
        html = R.table(['A', 'B'], [[1, '<x>'], [3, 4]])
        self.assertIn('<table>', html)
        self.assertIn('&lt;x&gt;', html)          # cell value escaped
        login = R.login_page(first_run=True, csrf='tok')
        self.assertIn('name="csrf" value="tok"', login)
        self.assertIn('name="username"', login)
        self.assertIn('Create the first admin', login)


class TestWebRouter(unittest.TestCase):
    # A fresh, schema-only DB per test so the first-run/login state is
    # deterministic regardless of test order.
    def setUp(self):
        import db, webapp
        self.db = db
        fd, self.path = tempfile.mkstemp(suffix='.db')
        os.close(fd); os.remove(self.path)
        self.orig = db.DB_PATH
        db.DB_PATH = self.path
        db.init_db()
        webapp.reset_sessions()

    def tearDown(self):
        self.db.DB_PATH = self.orig
        for ext in ('', '-wal', '-shm'):
            try:
                os.remove(self.path + ext)
            except OSError:
                pass

    def _req(self, path, method='GET', form=None, cookies=None):
        import webapp
        return webapp.Request(method, path, form=form or {}, cookies=cookies or {})

    def _login_admin(self):
        """Run the first-run bootstrap through the router; return the cosid."""
        import webapp
        get = webapp.handle(self._req('/login'))
        csrf = cookie_val(get, 'coscsrf')
        self.assertTrue(csrf)
        post = webapp.handle(self._req(
            '/login', 'POST',
            form={'csrf': csrf, 'username': 'admin', 'password': STRONG},
            cookies={'coscsrf': csrf}))
        self.assertEqual(post.status, 303)
        self.assertEqual(post.headers.get('Location'), '/')
        sid = cookie_val(post, 'cosid')
        self.assertTrue(sid)
        return sid

    def test_gate_redirects_anonymous(self):
        import webapp
        resp = webapp.handle(self._req('/'))
        self.assertEqual(resp.status, 303)
        self.assertEqual(resp.headers.get('Location'), '/login')

    def test_first_run_shows_create_admin(self):
        import webapp
        resp = webapp.handle(self._req('/login'))
        self.assertEqual(resp.status, 200)
        self.assertIn(b'Create the first admin', resp.body)

    def test_csrf_mismatch_is_rejected(self):
        import webapp
        webapp.handle(self._req('/login'))
        resp = webapp.handle(self._req(
            '/login', 'POST',
            form={'csrf': 'x', 'username': 'admin', 'password': STRONG},
            cookies={'coscsrf': 'y'}))
        # Re-renders the form rather than creating a session.
        self.assertIsNone(cookie_val(resp, 'cosid'))
        self.assertIn(b'try again', resp.body)

    def test_login_then_dashboard(self):
        import webapp
        sid = self._login_admin()
        resp = webapp.handle(self._req('/', cookies={'cosid': sid}))
        self.assertEqual(resp.status, 200)
        self.assertIn(b'Cash in hand', resp.body)   # a KPI card rendered

    def test_users_table_is_never_exposed(self):
        import webapp
        sid = self._login_admin()
        resp = webapp.handle(self._req('/t/users', cookies={'cosid': sid}))
        self.assertIn(b'No such register', resp.body)

    def test_a_real_register_lists(self):
        import webapp
        sid = self._login_admin()
        resp = webapp.handle(self._req('/t/sites', cookies={'cosid': sid}))
        self.assertEqual(resp.status, 200)
        self.assertIn(b'Sites', resp.body)

    def test_viewer_role_cannot_write(self):
        import webapp
        self.assertFalse(webapp.can_write('Viewer'))
        self.assertTrue(webapp.can_write('Operator'))
        self.assertTrue(webapp.can_write('Admin'))

    # ---- Stage 2: Masters data entry -----------------------------------
    def _scsrf(self, sid):
        import webapp
        return webapp._session(sid)['csrf']

    def test_master_create_view_edit_delete(self):
        import webapp
        sid = self._login_admin()
        csrf = self._scsrf(sid)
        ck = {'cosid': sid}
        # blank new form
        form = webapp.handle(self._req('/t/sites/new', cookies=ck))
        self.assertEqual(form.status, 200)
        self.assertIn(b'New Site', form.body)
        # create
        r = webapp.handle(self._req(
            '/t/sites/new', 'POST',
            form={'csrf': csrf, 'name': 'Test Site', 'location': 'Hospet',
                  'site_type': 'Site', 'status': 'Active'}, cookies=ck))
        self.assertEqual(r.status, 303)
        loc = r.headers['Location']
        rid = loc.rsplit('/', 1)[1]
        # it persisted and shows
        view = webapp.handle(self._req(loc, cookies=ck))
        self.assertIn(b'Test Site', view.body)
        # edit
        r = webapp.handle(self._req(
            '/t/sites/{}/edit'.format(rid), 'POST',
            form={'csrf': csrf, 'name': 'Renamed', 'location': 'Bellary',
                  'site_type': 'Site', 'status': 'Closed'}, cookies=ck))
        self.assertEqual(r.status, 303)
        view = webapp.handle(self._req(loc, cookies=ck))
        self.assertIn(b'Renamed', view.body)
        self.assertIn(b'Bellary', view.body)
        # delete (no rows reference this site -> succeeds)
        r = webapp.handle(self._req(
            '/t/sites/{}/delete'.format(rid), 'POST',
            form={'csrf': csrf}, cookies=ck))
        self.assertEqual(r.status, 303)
        self.assertEqual(r.headers['Location'], '/t/sites')
        view = webapp.handle(self._req(loc, cookies=ck))
        self.assertEqual(view.status, 404)

    def test_master_required_field_rejected(self):
        import webapp
        sid = self._login_admin()
        r = webapp.handle(self._req(
            '/t/sites/new', 'POST',
            form={'csrf': self._scsrf(sid), 'name': ''}, cookies={'cosid': sid}))
        self.assertEqual(r.status, 200)              # re-render, not a redirect
        self.assertIn(b'is required', r.body)

    def test_master_write_needs_csrf(self):
        import webapp
        sid = self._login_admin()
        r = webapp.handle(self._req(
            '/t/sites/new', 'POST',
            form={'csrf': 'wrong', 'name': 'X'}, cookies={'cosid': sid}))
        self.assertEqual(r.status, 403)

    def test_viewer_cannot_reach_write_routes(self):
        import webapp
        tok = webapp._new_session('bob', 'Viewer')
        csrf = self._scsrf(tok)
        r = webapp.handle(self._req(
            '/t/sites/new', 'POST',
            form={'csrf': csrf, 'name': 'Nope'}, cookies={'cosid': tok}))
        self.assertEqual(r.status, 403)

    def test_non_master_has_no_write_route(self):
        import webapp
        sid = self._login_admin()
        r = webapp.handle(self._req('/t/payments/new', cookies={'cosid': sid}))
        self.assertEqual(r.status, 404)


class TestWebMastersSpec(unittest.TestCase):
    """Guard against the web master specs drifting from the real schema."""
    def setUp(self):
        import db
        self.db = db
        fd, self.path = tempfile.mkstemp(suffix='.db')
        os.close(fd); os.remove(self.path)
        self.orig = db.DB_PATH
        db.DB_PATH = self.path
        db.init_db()

    def tearDown(self):
        self.db.DB_PATH = self.orig
        for ext in ('', '-wal', '-shm'):
            try:
                os.remove(self.path + ext)
            except OSError:
                pass

    def test_every_field_is_a_real_column(self):
        import web_masters
        conn = self.db.get_conn()
        try:
            for table, spec in web_masters.MASTERS.items():
                cols = {r['name'] for r in
                        conn.execute('PRAGMA table_info("{}")'.format(table))}
                self.assertTrue(cols, 'table {} does not exist'.format(table))
                for f in spec['fields']:
                    self.assertIn(f['key'], cols,
                                  '{}.{} is not a column'.format(table, f['key']))
                # fk dropdown queries must actually run
                for f in spec['fields']:
                    if f['kind'] == 'fk':
                        conn.execute(f['fk_sql']).fetchall()
        finally:
            conn.close()


class TestWebServerIntegration(unittest.TestCase):
    def test_server_answers_login_over_http(self):
        import db, webserver, webapp
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd); os.remove(path)
        orig = db.DB_PATH
        db.DB_PATH = path
        db.init_db()
        webapp.reset_sessions()
        srv = webserver.WebServer(host='127.0.0.1', port=0)
        srv.start()
        try:
            with urllib.request.urlopen(
                    'http://127.0.0.1:{}/login'.format(srv.port),
                    timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertIn(b'name="username"', r.read())
        finally:
            srv.stop()
            db.DB_PATH = orig
            for ext in ('', '-wal', '-shm'):
                try:
                    os.remove(path + ext)
                except OSError:
                    pass


if __name__ == '__main__':
    unittest.main(verbosity=2)
