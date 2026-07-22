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

    def _req(self, path, method='GET', form=None, cookies=None, multi=None):
        import webapp
        return webapp.Request(method, path, form=form or {},
                              form_multi=multi or {}, cookies=cookies or {})

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

    def test_earned_value_page_renders(self):
        import webapp
        sid = self._login_admin()
        conn = self.db.get_conn()
        conn.execute("INSERT INTO projects (name, contract_value, start_date, "
                     "end_date) VALUES ('Ward-7 Road', 1000000, '2026-01-01', "
                     "'2026-12-31')")
        conn.commit()
        conn.close()
        resp = webapp.handle(self._req('/evm', cookies={'cosid': sid}))
        self.assertEqual(resp.status, 200)
        self.assertIn(b'Earned Value', resp.body)
        self.assertIn(b'Ward-7 Road', resp.body)     # the project row
        self.assertIn(b'Portfolio CPI', resp.body)    # a KPI card rendered

    def test_earned_value_in_nav(self):
        import webapp
        sid = self._login_admin()
        resp = webapp.handle(self._req('/', cookies={'cosid': sid}))
        self.assertIn(b'/evm', resp.body)             # rail links to it

    def test_weekly_review_page_renders(self):
        import webapp
        sid = self._login_admin()
        resp = webapp.handle(self._req('/review', cookies={'cosid': sid}))
        self.assertEqual(resp.status, 200)
        self.assertIn(b'Weekly Review', resp.body)
        self.assertIn(b'Money at a glance', resp.body)
        self.assertIn(b'/review', resp.body)          # rail links to it

    def test_ra_bill_measurement_book_and_abstract_print(self):
        import webapp
        sid = self._login_admin()
        conn = self.db.get_conn()
        conn.execute("INSERT INTO contracts (contract_no, contract_value) "
                     "VALUES ('C/9', 2000000)")
        cid = conn.execute('SELECT id FROM contracts').fetchone()['id']
        conn.execute("INSERT INTO boq_items (contract_id, item_no, description, "
                     "unit, qty, rate) VALUES (?, '1', 'Earthwork in trench', "
                     "'cum', 50, 300)", (cid,))
        bid = conn.execute('SELECT id FROM boq_items').fetchone()['id']
        conn.execute("INSERT INTO measurements (boq_item_id, contract_id, "
                     "mb_ref, description, nos, length, breadth, depth, "
                     "quantity) VALUES (?, ?, 'MB-1', 'Trench T1', 1, 10, 1, 1, "
                     "10)", (bid, cid))
        conn.execute("INSERT INTO ra_bills (contract_id, bill_no, "
                     "this_bill_value) VALUES (?, 'RA-1', 3000)", (cid,))
        rbid = conn.execute('SELECT id FROM ra_bills').fetchone()['id']
        conn.execute("INSERT INTO ra_bill_items (ra_bill_id, boq_item_id, "
                     "upto_qty, current_qty, rate, current_amount) VALUES "
                     "(?, ?, 10, 10, 300, 3000)", (rbid, bid))
        conn.commit()
        conn.close()

        mbp = webapp.handle(self._req('/t/ra_bills/{}/mb'.format(rbid),
                                      cookies={'cosid': sid}))
        self.assertEqual(mbp.status, 200)
        self.assertIn(b'Measurement Book', mbp.body)
        self.assertIn(b'Trench T1', mbp.body)
        rap = webapp.handle(self._req('/t/ra_bills/{}/ra'.format(rbid),
                                      cookies={'cosid': sid}))
        self.assertEqual(rap.status, 200)
        self.assertIn(b'ABSTRACT OF WORK EXECUTED', rap.body)
        rec = webapp.handle(self._req('/t/ra_bills/{}'.format(rbid),
                                      cookies={'cosid': sid}))
        self.assertIn(b'Measured items', rec.body)    # items table on the record
        self.assertIn(b'/mb', rec.body)               # print links present

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

    def test_non_writable_register_has_no_create_route(self):
        # contracts is viewable but not a Master / estimate / money document,
        # so it has no browser create form (yet).
        import webapp
        sid = self._login_admin()
        r = webapp.handle(self._req('/t/contracts/new', cookies={'cosid': sid}))
        self.assertEqual(r.status, 404)

    # ---- Stage 3a: Estimates (header + line items, computed total) ------
    def _make_site(self):
        conn = self.db.get_conn()
        try:
            conn.execute("INSERT INTO sites (name, status) VALUES ('S1','Active')")
            conn.commit()
        finally:
            conn.close()

    def test_estimate_create_computes_total_and_edit_recomputes(self):
        import webapp
        self._make_site()
        sid = self._login_admin()
        csrf = self._scsrf(sid)
        ck = {'cosid': sid}
        # form renders with the dynamic line-item helper
        f = webapp.handle(self._req('/t/estimates/new', cookies=ck))
        self.assertIn(b'New Estimate', f.body)
        self.assertIn(b'addLine()', f.body)
        # 10*100 + 5*200 = 2000; +10% cont = 2200; +18% gst = 2596.0
        hdr = {'csrf': csrf, 'est_number': 'EST-1', 'title': 'Wall',
               'site_id': '1', 'estimate_date': '2026-07-21', 'status': 'Draft',
               'contingency_pct': '10', 'gst_pct': '18', 'notes': ''}
        multi = {'li_code': ['A', 'B'], 'li_desc': ['Exc', 'PCC'],
                 'li_unit': ['cum', 'cum'], 'li_qty': ['10', '5'],
                 'li_rate': ['100', '200']}
        r = webapp.handle(self._req('/t/estimates/new', 'POST', form=hdr,
                                    multi=multi, cookies=ck))
        self.assertEqual(r.status, 303)
        eid = r.headers['Location'].rsplit('/', 1)[1]
        conn = self.db.get_conn()
        try:
            total = conn.execute('SELECT total_estimate FROM estimates WHERE '
                                 'id=?', (eid,)).fetchone()[0]
            nlines = conn.execute('SELECT COUNT(*) FROM estimate_items WHERE '
                                  'estimate_id=?', (eid,)).fetchone()[0]
        finally:
            conn.close()
        self.assertAlmostEqual(total, 2596.0, places=2)
        self.assertEqual(nlines, 2)
        # record view shows the lines + grand total
        view = webapp.handle(self._req('/t/estimates/{}'.format(eid), cookies=ck))
        self.assertIn(b'Grand total', view.body)
        self.assertIn(b'Exc', view.body)
        # edit: qty 10 -> 20; 20*100 + 5*200 = 3000; +10% = 3300; +18% = 3894.0
        multi2 = dict(multi); multi2['li_qty'] = ['20', '5']
        r = webapp.handle(self._req('/t/estimates/{}/edit'.format(eid), 'POST',
                                    form=hdr, multi=multi2, cookies=ck))
        self.assertEqual(r.status, 303)
        conn = self.db.get_conn()
        try:
            total2 = conn.execute('SELECT total_estimate FROM estimates WHERE '
                                  'id=?', (eid,)).fetchone()[0]
            nlines2 = conn.execute('SELECT COUNT(*) FROM estimate_items WHERE '
                                   'estimate_id=?', (eid,)).fetchone()[0]
        finally:
            conn.close()
        self.assertAlmostEqual(total2, 3894.0, places=2)
        self.assertEqual(nlines2, 2)     # replaced, not duplicated

    def test_estimate_print_serves_a_document(self):
        import webapp
        self._make_site()
        sid = self._login_admin()
        csrf = self._scsrf(sid)
        ck = {'cosid': sid}
        r = webapp.handle(self._req(
            '/t/estimates/new', 'POST',
            form={'csrf': csrf, 'title': 'Boundary Wall', 'contingency_pct': '0',
                  'gst_pct': '18', 'status': 'Draft'},
            multi={'li_desc': ['Excavation'], 'li_qty': ['10'],
                   'li_rate': ['100']}, cookies=ck))
        eid = r.headers['Location'].rsplit('/', 1)[1]
        # record view offers the print link
        rec = webapp.handle(self._req('/t/estimates/{}'.format(eid), cookies=ck))
        self.assertIn('/t/estimates/{}/print'.format(eid).encode(), rec.body)
        # the print route serves the generated document (not the app chrome)
        doc = webapp.handle(self._req('/t/estimates/{}/print'.format(eid),
                                      cookies=ck))
        self.assertEqual(doc.status, 200)
        self.assertIn(b'Boundary Wall', doc.body)
        self.assertIn(b'Excavation', doc.body)

    def test_estimate_print_requires_login(self):
        import webapp
        # no cookie -> the gate bounces to /login
        r = webapp.handle(self._req('/t/estimates/1/print'))
        self.assertEqual(r.status, 303)

    def test_estimate_requires_title_and_a_line(self):
        import webapp
        sid = self._login_admin()
        csrf = self._scsrf(sid)
        r = webapp.handle(self._req(
            '/t/estimates/new', 'POST', form={'csrf': csrf, 'title': ''},
            multi={'li_desc': ['x'], 'li_qty': ['1'], 'li_rate': ['1']},
            cookies={'cosid': sid}))
        self.assertEqual(r.status, 200)
        self.assertIn(b'Title is required', r.body)

    def test_estimate_write_gated_for_viewer(self):
        import webapp
        tok = webapp._new_session('v', 'Viewer')
        r = webapp.handle(self._req(
            '/t/estimates/new', 'POST',
            form={'csrf': self._scsrf(tok), 'title': 'x'},
            cookies={'cosid': tok}))
        self.assertEqual(r.status, 403)

    # ---- Stage 3b: money documents that post to the ledger --------------
    def _journal(self):
        conn = self.db.get_conn()
        try:
            return conn.execute('SELECT source, source_id, total_debit, '
                                'total_credit FROM journal_entries '
                                'ORDER BY id').fetchall()
        finally:
            conn.close()

    def _post_doc(self, sid, table, form):
        import webapp
        form = dict(form); form['csrf'] = self._scsrf(sid)
        return webapp.handle(self._req('/t/{}/new'.format(table), 'POST',
                                       form=form, cookies={'cosid': sid}))

    def test_money_documents_post_balanced_entries(self):
        import webapp
        sid = self._login_admin()
        # a receipt, an outward invoice, an inward invoice, an approved bill
        self.assertEqual(self._post_doc(sid, 'payments', {
            'pay_date': '2026-07-21', 'direction': 'Receipt',
            'party_type': 'Client', 'party_name': 'C', 'mode': 'Cash',
            'amount': '5000'}).status, 303)
        self.assertEqual(self._post_doc(sid, 'tax_invoices', {
            'invoice_no': 'INV-1', 'invoice_date': '2026-07-21',
            'subtotal': '100000', 'gst_pct': '18', 'status': 'Issued'}).status,
            303)
        self.assertEqual(self._post_doc(sid, 'vendor_invoices', {
            'invoice_no': 'VI-1', 'invoice_date': '2026-07-21',
            'subtotal': '50000', 'gst_pct': '18', 'tds_pct': '2',
            'status': 'Approved'}).status, 303)
        self.assertEqual(self._post_doc(sid, 'bills', {
            'bill_no': 'RB-1', 'bill_date': '2026-07-21',
            'work_done_value': '200000', 'previous_billed': '50000',
            'retention_pct': '5', 'other_deductions': '0',
            'status': 'Approved'}).status, 303)

        entries = self._journal()
        self.assertEqual(len(entries), 4)
        for e in entries:                      # double entry must balance
            self.assertAlmostEqual(e['total_debit'], e['total_credit'], places=2)
        by = {e['source']: e['total_debit'] for e in entries}
        self.assertAlmostEqual(by['Payment'], 5000.0, places=2)
        self.assertAlmostEqual(by['TaxInvoice'], 118000.0, places=2)   # +18% GST
        self.assertAlmostEqual(by['VendorInvoice'], 59000.0, places=2)
        self.assertAlmostEqual(by['Bill'], 150000.0, places=2)         # 200k-50k

        # derived amounts stored on the documents
        conn = self.db.get_conn()
        try:
            vi = conn.execute('SELECT tax_amount, tds_amount, net_payable FROM '
                              'vendor_invoices').fetchone()
            b = conn.execute('SELECT retention_amt, net_payable FROM '
                             'bills').fetchone()
        finally:
            conn.close()
        self.assertAlmostEqual(vi['net_payable'], 58000.0, places=2)
        self.assertAlmostEqual(b['retention_amt'], 7500.0, places=2)
        self.assertAlmostEqual(b['net_payable'], 142500.0, places=2)

    def test_ra_bill_posts_form26_recoveries(self):
        import webapp
        sid = self._login_admin()
        # this=100000, prev=50000, SD 2.5%, TDS 2%, cess 1%
        #  -> retention 2500, tds 2000, cess 1000, net 94500, cumulative 150000
        r = self._post_doc(sid, 'ra_bills', {
            'bill_no': 'RA-1', 'bill_date': '2026-07-21',
            'this_bill_value': '100000', 'previous_value': '50000',
            'retention_pct': '2.5', 'tds_pct': '2', 'cess_pct': '1',
            'other_deductions': '0', 'status': 'Approved'})
        self.assertEqual(r.status, 303)
        conn = self.db.get_conn()
        try:
            row = conn.execute('SELECT retention_amt, tds_amt, cess_amt, '
                               'net_payable, cumulative_value FROM '
                               'ra_bills').fetchone()
            je = conn.execute('SELECT source, total_debit, total_credit FROM '
                              'journal_entries').fetchall()
        finally:
            conn.close()
        self.assertAlmostEqual(row['retention_amt'], 2500.0, places=2)
        self.assertAlmostEqual(row['tds_amt'], 2000.0, places=2)
        self.assertAlmostEqual(row['cess_amt'], 1000.0, places=2)
        self.assertAlmostEqual(row['net_payable'], 94500.0, places=2)
        self.assertAlmostEqual(row['cumulative_value'], 150000.0, places=2)
        self.assertEqual(len(je), 1)
        self.assertEqual(je[0]['source'], 'RABill')
        self.assertAlmostEqual(je[0]['total_debit'], je[0]['total_credit'],
                               places=2)

    def test_draft_bill_saves_but_does_not_post(self):
        import webapp
        sid = self._login_admin()
        r = self._post_doc(sid, 'bills', {
            'bill_no': 'RB-D', 'bill_date': '2026-07-21',
            'work_done_value': '10000', 'previous_billed': '0',
            'retention_pct': '5', 'status': 'Draft'})
        self.assertEqual(r.status, 303)
        self.assertEqual(self._journal(), [])     # nothing posted for a draft

    def test_money_document_write_gated_for_viewer(self):
        import webapp
        tok = webapp._new_session('v', 'Viewer')
        r = webapp.handle(self._req(
            '/t/payments/new', 'POST',
            form={'csrf': self._scsrf(tok), 'amount': '1'},
            cookies={'cosid': tok}))
        self.assertEqual(r.status, 403)


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


class TestWebApi(unittest.TestCase):
    """U0 JSON API — socket-free via ``webapp.handle``, same session gate."""

    def setUp(self):
        import db, webapp
        self.db = db
        self.webapp = webapp
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

    def _req(self, path, method='GET', form=None, cookies=None,
             json_body=None, query=None, headers=None):
        return self.webapp.Request(
            method, path, query=query or {}, form=form or {},
            cookies=cookies or {}, json_body=json_body,
            headers=headers or {})

    def _login(self, username='admin', password=STRONG):
        import json
        resp = self.webapp.handle(self._req(
            '/api/login', 'POST',
            json_body={'username': username, 'password': password}))
        self.assertEqual(resp.status, 200, resp.body)
        sid = cookie_val(resp, 'cosid')
        self.assertTrue(sid)
        data = json.loads(resp.body.decode('utf-8'))
        return sid, data['csrf'], data

    def _json(self, resp):
        import json
        return json.loads(resp.body.decode('utf-8'))

    def test_api_requires_auth(self):
        resp = self.webapp.handle(self._req('/api/dashboard'))
        self.assertEqual(resp.status, 401)
        self.assertIn('application/json', resp.headers['Content-Type'])
        self.assertIn('Authentication', self._json(resp)['error'])

    def test_api_login_and_me(self):
        sid, csrf, me = self._login()
        self.assertEqual(me['role'], 'Admin')
        self.assertTrue(me['can_write'])
        resp = self.webapp.handle(self._req(
            '/api/me', cookies={'cosid': sid}))
        self.assertEqual(resp.status, 200)
        body = self._json(resp)
        self.assertEqual(body['username'], 'admin')
        self.assertEqual(body['csrf'], csrf)

    def test_dashboard_menu_workflow_evm(self):
        sid, _csrf, _ = self._login()
        cookies = {'cosid': sid}
        for path, key in (('/api/health', 'ok'),
                          ('/api/dashboard', 'snapshot'),
                          ('/api/kpi', 'advisories'),
                          ('/api/workflow', 'workflows'),
                          ('/api/evm', 'portfolio'),
                          ('/api/review', 'narrative'),
                          ('/api/risks', 'items'),
                          ('/api/opportunities', 'items')):
            resp = self.webapp.handle(self._req(path, cookies=cookies))
            self.assertEqual(resp.status, 200, path)
            self.assertIn(key, self._json(resp))
        resp = self.webapp.handle(self._req(
            '/api/menu', cookies=cookies, query={'persona': 'Owner'}))
        self.assertEqual(resp.status, 200)
        menu = self._json(resp)
        self.assertEqual(menu['persona'], 'Owner')
        self.assertTrue(menu['sections'])
        titles = [s['title'] for s in menu['sections']]
        self.assertIn('Project Management', titles)

    def test_risk_crud_and_csrf(self):
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        # Missing CSRF → 403
        resp = self.webapp.handle(self._req(
            '/api/risks', 'POST', cookies=cookies,
            json_body={'title': 'No token', 'likelihood': 2, 'impact': 2}))
        self.assertEqual(resp.status, 403)
        # Create
        resp = self.webapp.handle(self._req(
            '/api/risks', 'POST', cookies=cookies,
            json_body={'title': 'Cash gap', 'likelihood': 3, 'impact': 4,
                       'impact_value': 50000},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201)
        risk = self._json(resp)
        self.assertEqual(risk['title'], 'Cash gap')
        self.assertEqual(risk['band'], 'High')
        rid = risk['id']
        # Update
        resp = self.webapp.handle(self._req(
            '/api/risks/{}'.format(rid), 'PUT', cookies=cookies,
            json_body={'likelihood': 5},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        self.assertEqual(self._json(resp)['score'], 20.0)
        # Get + list
        resp = self.webapp.handle(self._req(
            '/api/risks/{}'.format(rid), cookies=cookies))
        self.assertEqual(resp.status, 200)
        resp = self.webapp.handle(self._req('/api/risks', cookies=cookies))
        self.assertEqual(len(self._json(resp)['items']), 1)
        # Delete
        resp = self.webapp.handle(self._req(
            '/api/risks/{}'.format(rid), 'DELETE', cookies=cookies,
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        resp = self.webapp.handle(self._req(
            '/api/risks/{}'.format(rid), cookies=cookies))
        self.assertEqual(resp.status, 404)

    def test_master_create_and_viewer_denied(self):
        import auth
        sid, csrf, _ = self._login()
        resp = self.webapp.handle(self._req(
            '/api/sites', 'POST', cookies={'cosid': sid},
            json_body={'name': 'Ward-7', 'location': 'Pune'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201)
        self.assertEqual(self._json(resp)['name'], 'Ward-7')

        conn = self.db.get_conn()
        try:
            auth.create_user(conn, 'viewer', STRONG, role='Viewer',
                             actor='admin')
        finally:
            conn.close()
        vsid, vcsrf, vme = self._login('viewer', STRONG)
        self.assertFalse(vme['can_write'])
        resp = self.webapp.handle(self._req(
            '/api/sites', 'POST', cookies={'cosid': vsid},
            json_body={'name': 'Nope'},
            headers={'X-CSRF-Token': vcsrf}))
        self.assertEqual(resp.status, 403)

    def test_project_evm_endpoint(self):
        sid, _csrf, _ = self._login()
        conn = self.db.get_conn()
        try:
            conn.execute(
                "INSERT INTO projects (name, contract_value, start_date, "
                "end_date) VALUES ('Road', 1000000, '2026-01-01', '2026-12-31')")
            conn.commit()
            pid = conn.execute('SELECT id FROM projects').fetchone()[0]
        finally:
            conn.close()
        resp = self.webapp.handle(self._req(
            '/api/project/{}/evm'.format(pid), cookies={'cosid': sid}))
        self.assertEqual(resp.status, 200)
        body = self._json(resp)
        self.assertEqual(body['bac'], 1000000.0)
        self.assertEqual(body['name'], 'Road')
        resp = self.webapp.handle(self._req(
            '/api/project/999/evm', cookies={'cosid': sid}))
        self.assertEqual(resp.status, 404)

    def test_lessons_crud(self):
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        resp = self.webapp.handle(self._req(
            '/api/lessons', 'POST', cookies=cookies,
            json_body={'title': 'Tag costs early', 'outcome': 'positive',
                       'recommendation': 'Always tag project_id on issues'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        lesson = self._json(resp)
        self.assertEqual(lesson['title'], 'Tag costs early')
        lid = lesson['id']
        resp = self.webapp.handle(self._req('/api/lessons', cookies=cookies))
        self.assertEqual(resp.status, 200)
        self.assertEqual(len(self._json(resp)['items']), 1)
        resp = self.webapp.handle(self._req(
            '/api/lessons/{}'.format(lid), 'PUT', cookies=cookies,
            json_body={'status': 'Applied'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        self.assertEqual(self._json(resp)['status'], 'Applied')

    def test_events_and_signal_feed(self):
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        resp = self.webapp.handle(self._req(
            '/api/events', 'POST', cookies=cookies,
            json_body={'event': 'grn_saved', 'payload': {'grn_id': 1}},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        body = self._json(resp)
        self.assertTrue(body['followups'])
        self.assertEqual(body['gated_count'], 0)

        resp = self.webapp.handle(self._req(
            '/api/signals/feed', 'POST', cookies=cookies,
            json_body={
                'drift': {
                    'drifting': True, 'score': 4, 'confidence': 'Low',
                    'signals': [{'signal': 'plan reliability falling',
                                 'basis': '4 periods'}],
                },
                'apply': True,
            },
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        body = self._json(resp)
        self.assertEqual(len(body['drafts']), 1)
        self.assertEqual(len(body['applied_ids']), 1)

        resp = self.webapp.handle(self._req(
            '/api/audit', cookies=cookies, query={'origin': 'ai'}))
        self.assertEqual(resp.status, 200)
        self.assertTrue(self._json(resp)['items'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
