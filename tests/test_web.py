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
