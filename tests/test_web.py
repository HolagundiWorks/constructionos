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
        import db, webapp, company
        self.db = db
        fd, self.path = tempfile.mkstemp(suffix='.db')
        os.close(fd); os.remove(self.path)
        self.orig = db.DB_PATH
        db.DB_PATH = self.path
        db.init_db()
        # Isolate the multi-company registry too, or login's company resolution
        # would hijack db.DB_PATH to a real registered book (companies.json is
        # global) and break the fresh-DB isolation this test relies on.
        self.company = company
        self.orig_reg = company.REGISTRY_PATH
        company.REGISTRY_PATH = self.path + '.companies.json'
        webapp.reset_sessions()

    def tearDown(self):
        self.db.DB_PATH = self.orig
        self.company.REGISTRY_PATH = self.orig_reg
        for ext in ('', '-wal', '-shm', '.companies.json'):
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

    def test_measurement_entry_in_browser_derives_quantity(self):
        import webapp
        sid = self._login_admin()
        csrf = self._scsrf(sid)
        ck = {'cosid': sid}
        conn = self.db.get_conn()
        conn.execute("INSERT INTO contracts (contract_no) VALUES ('C/1')")
        cid = conn.execute('SELECT id FROM contracts').fetchone()['id']
        conn.execute("INSERT INTO boq_items (contract_id, item_no, description) "
                     "VALUES (?, '1', 'PCC')", (cid,))
        bid = conn.execute('SELECT id FROM boq_items').fetchone()['id']
        conn.commit()
        conn.close()
        # Nos 4 × L 2 × (breadth blank ⇒ factor 1) × D 0.5 = 4.0 — a blank
        # dimension must NOT zero the quantity.
        resp = webapp.handle(self._req(
            '/t/measurements/new', 'POST',
            form={'csrf': csrf, 'contract_id': str(cid), 'boq_item_id': str(bid),
                  'mb_date': '2026-07-01', 'mb_ref': 'MB-1', 'nos': '4',
                  'length': '2', 'breadth': '', 'depth': '0.5'}, cookies=ck))
        self.assertEqual(resp.status, 303)
        conn = self.db.get_conn()
        row = conn.execute('SELECT * FROM measurements').fetchone()
        conn.close()
        self.assertEqual(row['quantity'], 4.0)       # blank breadth ⇒ factor 1
        self.assertIsNone(row['breadth'])            # blank stays NULL, not 0

    def test_compliance_filing_in_browser_stores_obligation_key(self):
        import webapp
        sid = self._login_admin()
        csrf = self._scsrf(sid)
        resp = webapp.handle(self._req(
            '/t/compliance_filings/new', 'POST',
            form={'csrf': csrf, 'obligation': 'GSTR-1 (outward supplies)',
                  'period': '2026-04', 'due_date': '2026-05-11',
                  'ref_no': 'ARN123', 'amount': '5000'},
            cookies={'cosid': sid}))
        self.assertEqual(resp.status, 303)
        conn = self.db.get_conn()
        row = conn.execute('SELECT * FROM compliance_filings').fetchone()
        conn.close()
        self.assertEqual(row['obligation'], 'gstr1')  # display name → stable key
        self.assertEqual(row['period'], '2026-04')

    def test_gst_view_renders_read_only(self):
        import webapp
        sid = self._login_admin()
        # No query param (TestWebRouter._req has none); _gst defaults the month.
        resp = webapp.handle(self._req('/gst', cookies={'cosid': sid}))
        self.assertEqual(resp.status, 200)
        self.assertIn(b'GST', resp.body)
        self.assertIn(b'Outward supplies', resp.body)
        self.assertIn(b'TDS', resp.body)
        # rail links to it
        home = webapp.handle(self._req('/', cookies={'cosid': sid}))
        self.assertIn(b'/gst', home.body)

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

    def test_contracts_master_has_create_route(self):
        # Contracts are now a JSON + browser master (U0.7 billing spine).
        import webapp
        sid = self._login_admin()
        r = webapp.handle(self._req('/t/contracts/new', cookies={'cosid': sid}))
        self.assertEqual(r.status, 200)

    def test_variations_still_have_no_browser_create(self):
        # Variations remain desktop-only (not in web_masters / money docs).
        import webapp
        sid = self._login_admin()
        r = webapp.handle(self._req('/t/variations/new', cookies={'cosid': sid}))
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
        import db, webapp, company
        self.db = db
        self.webapp = webapp
        fd, self.path = tempfile.mkstemp(suffix='.db')
        os.close(fd); os.remove(self.path)
        self.orig = db.DB_PATH
        db.DB_PATH = self.path
        db.init_db()
        # Isolate the multi-company registry (see TestWebRouter.setUp): otherwise
        # login resolves the active company from the global companies.json and
        # switches db.DB_PATH away from this test's fresh DB.
        self.company = company
        self.orig_reg = company.REGISTRY_PATH
        company.REGISTRY_PATH = self.path + '.companies.json'
        webapp.reset_sessions()

    def tearDown(self):
        self.db.DB_PATH = self.orig
        self.company.REGISTRY_PATH = self.orig_reg
        for ext in ('', '-wal', '-shm', '.companies.json'):
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
        self.assertIn('company', me)
        resp = self.webapp.handle(self._req(
            '/api/me', cookies={'cosid': sid}))
        self.assertEqual(resp.status, 200)
        body = self._json(resp)
        self.assertEqual(body['username'], 'admin')
        self.assertEqual(body['csrf'], csrf)

    def test_api_companies_public_and_login_selects_company(self):
        import company
        other = os.path.join(tempfile.mkdtemp(), 'other.db')
        orig_reg = company.REGISTRY_PATH
        reg = os.path.join(os.path.dirname(self.path), 'companies.json')
        company.REGISTRY_PATH = reg
        try:
            # Register the setUp DB and a second book.
            data = company.load(reg)
            company.add(data, 'Main', self.path, make_active=True)
            company.save(data, reg)
            self.db.DB_PATH = other
            self.db.init_db()
            data = company.load(reg)
            company.add(data, 'Other', other)
            company.save(data, reg)
            # Point process back at Main before login.
            self.db.DB_PATH = self.path

            resp = self.webapp.handle(self._req('/api/companies'))
            self.assertEqual(resp.status, 200)
            payload = self._json(resp)
            names = {i['name'] for i in payload['items']}
            self.assertIn('Main', names)
            self.assertIn('Other', names)

            resp = self.webapp.handle(self._req(
                '/api/login', 'POST',
                json_body={'username': 'admin', 'password': STRONG,
                           'company': 'Other'}))
            self.assertEqual(resp.status, 200, resp.body)
            body = self._json(resp)
            self.assertTrue(body['company'].endswith('other.db'))
            self.assertTrue(self.db.DB_PATH.endswith('other.db'))
        finally:
            company.REGISTRY_PATH = orig_reg
            self.db.DB_PATH = self.path
            for p in (other, other + '-wal', other + '-shm'):
                try:
                    os.remove(p)
                except OSError:
                    pass

    def test_dashboard_menu_workflow_evm(self):
        sid, _csrf, _ = self._login()
        cookies = {'cosid': sid}
        for path, key in (('/api/health', 'ok'),
                          ('/api/dashboard', 'snapshot'),
                          ('/api/kpi', 'rows'),
                          ('/api/insight', 'site_profitability'),
                          ('/api/home', 'blocks'),
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

    def test_readonly_register_tables(self):
        # Every whitelisted read-only register table lists cleanly (200 + items),
        # even when empty. Writes are rejected (list-only).
        import webapi
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        self.assertTrue(webapi._API_TABLES)
        for table in webapi._API_TABLES:
            resp = self.webapp.handle(self._req('/api/' + table, cookies=cookies))
            self.assertEqual(resp.status, 200, table)
            body = self._json(resp)
            self.assertIn('items', body, table)
            self.assertIsInstance(body['items'], list, table)
            # No write route for these tables.
            resp = self.webapp.handle(self._req(
                '/api/' + table, 'POST', cookies=cookies,
                headers={'X-CSRF-Token': csrf}, json_body={'x': 1}))
            self.assertIn(resp.status, (404, 405), table)

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

    def test_parties_balances(self):
        """Cash & Parties — per-party receivable/payable balances + totals.

        A client billed via an Approved RA bill and partly received shows the
        remaining outstanding = billed - settled (the "baaki")."""
        import json as _json
        sid, csrf, _ = self._login()
        ck = {'cosid': sid}
        # Fresh DB -> the shape is right and everything is zero.
        resp = self.webapp.handle(self._req('/api/parties', cookies=ck))
        self.assertEqual(resp.status, 200, resp.body)
        body = self._json(resp)
        for k in ('receivable', 'payable', 'total_receivable', 'total_payable'):
            self.assertIn(k, body)
        self.assertEqual(body['receivable'], [])
        self.assertEqual(body['total_receivable'], 0.0)

        # Seed a client + contract + approved RA bill + a part receipt.
        conn = self.db.get_conn()
        try:
            cid = conn.execute(
                "INSERT INTO clients (name) VALUES ('Acme Infra')").lastrowid
            ctr = conn.execute(
                "INSERT INTO contracts (client_id, contract_no, contract_value) "
                "VALUES (?, 'C-1', 500000)", (cid,)).lastrowid
            conn.execute(
                "INSERT INTO ra_bills (contract_id, bill_date, net_payable, status) "
                "VALUES (?, '2026-07-01', 100000, 'Approved')", (ctr,))
            conn.execute(
                "INSERT INTO payments (pay_date, direction, party_type, party_id, "
                "party_name, mode, amount) VALUES "
                "('2026-07-10', 'Receipt', 'Client', ?, 'Acme Infra', 'Bank', 30000)",
                (cid,))
            conn.commit()
        finally:
            conn.close()

        resp = self.webapp.handle(self._req('/api/parties', cookies=ck))
        body = self._json(resp)
        recv = body['receivable']
        self.assertEqual(len(recv), 1)
        self.assertEqual(recv[0]['party'], 'Acme Infra')
        self.assertEqual(recv[0]['billed'], 100000.0)
        self.assertEqual(recv[0]['settled'], 30000.0)
        self.assertEqual(recv[0]['outstanding'], 70000.0)     # baaki
        self.assertEqual(body['total_receivable'], 70000.0)

    def test_bills_previous_excludes_draft(self):
        """Precision gate (research §4.1): only Approved/Paid bills count as
        previously billed — a Draft bill must not inflate previous_billed, or the
        next RA bill would double-count the work."""
        sid, csrf, _ = self._login()
        ck = {'cosid': sid}
        hdr = {'X-CSRF-Token': csrf}
        resp = self.webapp.handle(self._req(
            '/api/clients', 'POST', cookies=ck,
            json_body={'name': 'Client A'}, headers=hdr))
        self.assertEqual(resp.status, 201, resp.body)
        cl = self._json(resp)['id']
        resp = self.webapp.handle(self._req(
            '/api/contracts', 'POST', cookies=ck,
            json_body={'client_id': cl, 'contract_no': 'C-9',
                       'contract_value': 500000}, headers=hdr))
        self.assertEqual(resp.status, 201, resp.body)
        cid = self._json(resp)['id']
        # An Approved bill counts toward previous_billed.
        resp = self.webapp.handle(self._req(
            '/api/bills', 'POST', cookies=ck,
            json_body={'bill_no': 'RB-1', 'contract_id': cid,
                       'bill_date': '2026-07-01', 'work_done_value': 100000,
                       'previous_billed': 0, 'retention_pct': 5,
                       'status': 'Approved'}, headers=hdr))
        self.assertEqual(resp.status, 201, resp.body)
        resp = self.webapp.handle(self._req(
            '/api/bills/previous', cookies=ck, query={'contract_id': str(cid)}))
        approved_prev = self._json(resp)['previous_billed']
        self.assertGreater(approved_prev, 0)
        # A Draft bill must NOT change previous_billed.
        resp = self.webapp.handle(self._req(
            '/api/bills', 'POST', cookies=ck,
            json_body={'bill_no': 'RB-2', 'contract_id': cid,
                       'bill_date': '2026-07-15', 'work_done_value': 200000,
                       'previous_billed': approved_prev, 'retention_pct': 5,
                       'status': 'Draft'}, headers=hdr))
        self.assertEqual(resp.status, 201, resp.body)
        resp = self.webapp.handle(self._req(
            '/api/bills/previous', cookies=ck, query={'contract_id': str(cid)}))
        self.assertEqual(self._json(resp)['previous_billed'], approved_prev)

    def test_assistant_quick_and_ask(self):
        """Assistant endpoints — exact quick answers (no model) + the ask turn
        (returns a friendly error when the AI engine is off, never a fake answer)."""
        sid, csrf, _ = self._login()
        ck = {'cosid': sid}
        resp = self.webapp.handle(self._req('/api/assistant/quick', cookies=ck))
        self.assertEqual(resp.status, 200, resp.body)
        items = self._json(resp)['items']
        labels = [i['label'] for i in items]
        self.assertIn('Cash in Hand', labels)
        self.assertIn('Receivables (clients owe)', labels)
        for i in items:
            self.assertIsInstance(i['value'], (int, float))

        # Ask needs a question.
        resp = self.webapp.handle(self._req(
            '/api/assistant', 'POST', cookies=ck, json_body={'question': ''},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 400)
        # A real question: with no AI engine in the test env, an honest {error}
        # (never a fabricated answer). Read-only either way.
        resp = self.webapp.handle(self._req(
            '/api/assistant', 'POST', cookies=ck,
            json_body={'question': 'total cash in hand'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        body = self._json(resp)
        self.assertTrue('error' in body or 'sql' in body)

    def test_web_form_labels_are_bound_and_page_has_skip_link(self):
        """WCAG (UI principles §12 C5): a <label> must point at its input, and a
        keyboard user must be able to bypass the rail."""
        import webrender as R
        html = R.field_row('Site name', R.control('text', 'name', ''),
                           for_name='name')
        self.assertIn('<label for="f-name">', html)
        self.assertIn('id="f-name"', html)
        self.assertIn('name="name"', html)
        # Every control kind gets an id so it can be bound.
        for kind in ('text', 'number', 'date', 'textarea', 'combo', 'fk'):
            self.assertIn('id="f-k"', R.control(kind, 'k', '', [('a', 'A')]),
                          kind)
        # Unbound rows still render (callers that have no field name).
        self.assertIn('<label>', R.field_row('Plain', '<input>'))
        page = R.page('T', '<p>body</p>', user='admin')
        self.assertIn('class="skip" href="#main"', page)
        self.assertIn('id="main"', page)

    def test_date_fields_declare_a_date_kind(self):
        """Fluent 2 (UI principles §11.5): calendar fields must declare
        kind='date' so clients render a real date picker, not free text."""
        import web_masters, web_docs
        by_key = {f['key']: f['kind'] for f in web_masters.fields('milestones')}
        self.assertEqual(by_key['target_date'], 'date')
        self.assertEqual(by_key['actual_date'], 'date')
        self.assertEqual(by_key['name'], 'text')        # not over-eager
        self.assertEqual(by_key['project_id'], 'fk')    # explicit kinds win
        pay = {f['key']: f['kind'] for f in web_docs.fields('payments')}
        self.assertEqual(pay['pay_date'], 'date')
        self.assertEqual(pay['party_name'], 'text')

    def test_firm_and_modules_settings(self):
        """Tools endpoints — firm letterhead + module on/off, CSRF-gated."""
        sid, csrf, _ = self._login()
        ck = {'cosid': sid}

        # firm: the letterhead fields come back (empty by default).
        resp = self.webapp.handle(self._req('/api/firm', cookies=ck))
        self.assertEqual(resp.status, 200)
        keys = [f['key'] for f in self._json(resp)['fields']]
        self.assertIn('company_name', keys)
        self.assertIn('seller_gstin', keys)
        # save needs CSRF.
        resp = self.webapp.handle(self._req(
            '/api/firm', 'POST', cookies=ck,
            json_body={'company_name': 'Acme Build'}))
        self.assertEqual(resp.status, 403)
        # save with CSRF; unknown keys are ignored (whitelist to firm.FIELDS).
        resp = self.webapp.handle(self._req(
            '/api/firm', 'POST', cookies=ck,
            json_body={'company_name': 'Acme Build', 'firm_phone': '9999',
                       'evil': 'x'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        saved = {f['key']: f['value'] for f in self._json(resp)['fields']}
        self.assertEqual(saved['company_name'], 'Acme Build')
        self.assertEqual(saved['firm_phone'], '9999')
        self.assertNotIn('evil', saved)

        # modules: all enabled by default.
        resp = self.webapp.handle(self._req('/api/modules', cookies=ck))
        self.assertEqual(resp.status, 200)
        sections = self._json(resp)['sections']
        self.assertIn('Operations', [s['title'] for s in sections])
        self.assertTrue(all(t['enabled']
                            for s in sections for t in s['tabs']))
        # toggle one off (CSRF required); the change round-trips.
        resp = self.webapp.handle(self._req(
            '/api/modules', 'POST', cookies=ck,
            json_body={'states': {'Plant': False}}))
        self.assertEqual(resp.status, 403)
        resp = self.webapp.handle(self._req(
            '/api/modules', 'POST', cookies=ck,
            json_body={'states': {'Plant': False}},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        state = {t['label']: t['enabled']
                 for s in self._json(resp)['sections'] for t in s['tabs']}
        self.assertFalse(state['Plant'])
        self.assertTrue(state['Warehouse'])
        # an unknown label is not persisted as a module.
        resp = self.webapp.handle(self._req(
            '/api/modules', 'POST', cookies=ck,
            json_body={'states': {'Nonexistent Tab': False}},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 400)

    def test_api_writes_are_audited(self):
        # Every API write must leave an audit row — the store commits the change
        # AND the handler must commit the audit beside it (regression: risk
        # update/delete and all opportunity writes used to drop the audit).
        sid, csrf, _ = self._login()
        C, H = {'cosid': sid}, {'X-CSRF-Token': csrf}
        r = self.webapp.handle(self._req(
            '/api/risks', 'POST', cookies=C,
            json_body={'title': 'Audit me', 'likelihood': 3, 'impact': 3},
            headers=H))
        rid = self._json(r)['id']
        self.webapp.handle(self._req(
            '/api/risks/{}'.format(rid), 'PUT', cookies=C,
            json_body={'likelihood': 5}, headers=H))
        self.webapp.handle(self._req(
            '/api/risks/{}'.format(rid), 'DELETE', cookies=C, headers=H))
        r = self.webapp.handle(self._req(
            '/api/opportunities', 'POST', cookies=C,
            json_body={'title': 'Upside', 'likelihood': 2, 'impact': 4},
            headers=H))
        oid = self._json(r)['id']
        self.webapp.handle(self._req(
            '/api/opportunities/{}'.format(oid), 'PUT', cookies=C,
            json_body={'impact': 5}, headers=H))
        self.webapp.handle(self._req(
            '/api/opportunities/{}'.format(oid), 'DELETE', cookies=C, headers=H))

        resp = self.webapp.handle(self._req(
            '/api/audit', cookies=C, query={'limit': '50'}))
        self.assertEqual(resp.status, 200)
        seen = {(x['action'], x['entity']) for x in self._json(resp)['items']}
        for action in ('api_create', 'api_update', 'api_delete'):
            self.assertIn((action, 'risks'), seen)
            self.assertIn((action, 'opportunities'), seen)

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

    def test_contract_portfolio_forecast_docs_submittals(self):
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        resp = self.webapp.handle(self._req('/api/contract', cookies=cookies))
        self.assertEqual(resp.status, 200)
        c = self._json(resp)
        self.assertEqual(c['api'], 'u0.17')
        self.assertIn('payments', c['docs'])
        self.assertIn('sites', c['masters'])
        self.assertIn('contracts', c['masters'])
        self.assertIn('measurements', c['masters'])
        # Tools settings endpoints are advertised in the contract.
        self.assertIn('GET /api/firm', c['reads'])
        self.assertIn('GET /api/modules', c['reads'])
        self.assertIn('GET /api/assistant/quick', c['reads'])
        self.assertIn('GET /api/home', c['reads'])
        self.assertIn('GET /api/gst/export?month=', c['reads'])
        self.assertIn('GET /api/agents', c['reads'])
        self.assertIn('GET /api/agents/provider', c['reads'])
        self.assertIn('POST /api/agents/ask', c['writes'])
        self.assertIn('POST /api/agents/eval', c['writes'])
        self.assertIn('POST /api/ra_bills/generate', c['writes'])
        self.assertIn('POST /api/risks/accept', c['writes'])
        self.assertIn('GET /api/parties', c['reads'])
        self.assertIn('POST /api/firm', c['writes'])
        self.assertIn('POST /api/modules', c['writes'])
        self.assertIn('POST /api/assistant', c['writes'])

        resp = self.webapp.handle(self._req('/api/portfolio', cookies=cookies))
        self.assertEqual(resp.status, 200)
        self.assertIn('current', self._json(resp))

        resp = self.webapp.handle(self._req(
            '/api/forecast', 'POST', cookies=cookies,
            json_body={'series': [10, 20, 30, 40], 'periods_ahead': 1},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        self.assertEqual(self._json(resp)['kind'], 'trend')

        resp = self.webapp.handle(self._req(
            '/api/drift', 'POST', cookies=cookies,
            json_body={'ppc_series': [80, 70, 60], 'slip_series': [1, 2, 1, 3]},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        self.assertTrue(self._json(resp)['drifting'])

        resp = self.webapp.handle(self._req(
            '/api/payments', 'POST', cookies=cookies,
            json_body={'pay_date': '2026-07-22', 'direction': 'Receipt',
                       'party_type': 'Client', 'party_name': 'ACME',
                       'mode': 'Cash', 'amount': 5000},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        self.assertEqual(self._json(resp)['amount'], 5000.0)

        resp = self.webapp.handle(self._req(
            '/api/submittals', 'POST', cookies=cookies,
            json_body={'title': 'M30 admixture', 'status': 'Submitted',
                       'required_by': '2020-01-01'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201)
        sub = self._json(resp)
        self.assertTrue(sub['is_open'])
        self.assertTrue(sub['is_overdue'])

    def test_search_capture_and_mobile_field(self):
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}

        resp = self.webapp.handle(self._req(
            '/api/search', cookies=cookies, query={'q': 'risk'}))
        self.assertEqual(resp.status, 200)
        hits = self._json(resp)['hits']
        self.assertTrue(any('Risk Register' in h['label'] for h in hits))

        resp = self.webapp.handle(self._req(
            '/api/capture/draft', 'POST', cookies=cookies,
            json_body={'fields': {'activity': 'M20', 'qty': '12'},
                       'confidence': {'qty': 0.4}, 'source': 'ai'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        draft = self._json(resp)
        self.assertTrue(draft['needs_review'])
        self.assertEqual(draft['origin'], 'ai')

        resp = self.webapp.handle(self._req(
            '/api/capture/confirm', 'POST', cookies=cookies,
            json_body={'fields': {'activity': 'M20 Concrete', 'qty': '12',
                                  'unit': 'cum', 'entry_date': '2026-07-22'},
                       'overrides': {'qty': '12.5'}, 'source': 'ai'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        body = self._json(resp)
        self.assertEqual(body['record']['qty'], 12.5)
        # activity still AI-sourced → overall origin remains ai
        self.assertEqual(body['origin'], 'ai')

        resp = self.webapp.handle(self._req('/m/capture', cookies=cookies))
        self.assertEqual(resp.status, 200)
        self.assertIn(b'Field capture', resp.body)

        resp = self.webapp.handle(self._req(
            '/m/capture', 'POST', cookies=cookies,
            form={'csrf': csrf, 'activity': 'Plaster', 'qty': '3',
                  'unit': 'sqm', 'entry_date': '2026-07-22'}))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertIn(b'Saved work-done', resp.body)

        resp = self.webapp.handle(self._req(
            '/api/payments', 'POST', cookies=cookies,
            json_body={'pay_date': '2026-07-22', 'direction': 'Payment',
                       'party_type': 'Vendor', 'party_name': 'Steel Co',
                       'mode': 'Bank', 'amount': 1000},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        pay = self._json(resp)
        self.assertTrue(pay.get('followups'))
        self.assertGreaterEqual(pay.get('gated_count', 0), 1)

    def test_u02_search_records_match_filings_reconcile(self):
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        # Seed a searchable project
        resp = self.webapp.handle(self._req(
            '/api/projects', 'POST', cookies=cookies,
            json_body={'name': 'Alpha Bridge Job'},
            headers={'X-CSRF-Token': csrf}))
        self.assertIn(resp.status, (200, 201), resp.body)

        resp = self.webapp.handle(self._req(
            '/api/search', cookies=cookies, query={'q': 'Alpha'}))
        self.assertEqual(resp.status, 200)
        body = self._json(resp)
        self.assertTrue(body.get('records'))
        self.assertTrue(any('Alpha' in (r.get('label') or '')
                            for r in body['records']))

        resp = self.webapp.handle(self._req('/api/match', cookies=cookies))
        self.assertEqual(resp.status, 200)
        self.assertIn('narration', self._json(resp))

        resp = self.webapp.handle(self._req(
            '/api/reconcile', 'POST', cookies=cookies,
            json_body={'po_subtotal': 1000, 'invoice_subtotal': 1200,
                       'label': 'VI-1'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        self.assertIn('over-billed', self._json(resp)['narration'].lower())

        resp = self.webapp.handle(self._req('/api/filings/feed', cookies=cookies))
        self.assertEqual(resp.status, 200)
        self.assertIn('events', self._json(resp))

        resp = self.webapp.handle(self._req('/api/ageing', cookies=cookies))
        self.assertEqual(resp.status, 200)
        self.assertIn('ageing', self._json(resp))

        resp = self.webapp.handle(self._req(
            '/api/purchase_orders', cookies=cookies))
        self.assertEqual(resp.status, 200)

    def test_u03_intent_sidecar_narrative(self):
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}

        resp = self.webapp.handle(self._req(
            '/api/intent', 'POST', cookies=cookies,
            json_body={'text': 'run the three-way match on this GRN'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        body = self._json(resp)
        self.assertEqual(body.get('event'), 'grn_saved')
        self.assertTrue(body.get('followups'))

        resp = self.webapp.handle(self._req(
            '/api/sidecar/status', cookies=cookies))
        self.assertEqual(resp.status, 200)
        sides = self._json(resp)['sidecars']
        self.assertIn('ocr', sides)
        self.assertTrue(sides['ocr']['stub'])
        self.assertFalse(sides['ocr']['available'])  # no live sidecar here

        resp = self.webapp.handle(self._req(
            '/api/sidecar/extract', 'POST', cookies=cookies,
            json_body={'kind': 'ocr', 'payload': {'path': '/tmp/nope.jpg'}},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        ext = self._json(resp)
        self.assertFalse(ext['ok'])
        self.assertIn('draft', ext)

        resp = self.webapp.handle(self._req(
            '/api/narrative', cookies=cookies, query={'kind': 'kpi'}))
        self.assertEqual(resp.status, 200)
        self.assertEqual(self._json(resp)['kind'], 'kpi')
        self.assertTrue(self._json(resp)['text'])

    def test_u04_text_muster_boq_patterns(self):
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}

        resp = self.webapp.handle(self._req(
            '/api/text/extract', 'POST', cookies=cookies,
            json_body={'text': 'Poured 8 cum M25 slab 2026-07-22'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        body = self._json(resp)
        self.assertIn(body['target'], ('work_done', 'daily_progress'))

        # Seed labour + site for muster
        self.webapp.handle(self._req(
            '/api/sites', 'POST', cookies=cookies,
            json_body={'name': 'Site A'},
            headers={'X-CSRF-Token': csrf}))
        self.webapp.handle(self._req(
            '/api/labor', 'POST', cookies=cookies,
            json_body={'name': 'Ram Singh', 'status': 'Active', 'site_id': 1},
            headers={'X-CSRF-Token': csrf}))

        resp = self.webapp.handle(self._req(
            '/api/muster/draft', 'POST', cookies=cookies,
            json_body={'text': '1. Ram Singh\n2. Ghost Worker',
                       'att_date': '2026-07-22'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        md = self._json(resp)
        self.assertEqual(md['matched'], 1)

        matched = [r for r in md['rows'] if r.get('labor_id')]
        resp = self.webapp.handle(self._req(
            '/api/muster/confirm', 'POST', cookies=cookies,
            json_body={'att_date': '2026-07-22', 'rows': matched},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)

        resp = self.webapp.handle(self._req(
            '/api/boq/import/draft', 'POST', cookies=cookies,
            json_body={'text': 'item_no,description,unit,qty,rate\n'
                               '1,Excavation,cum,10,100'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        self.assertEqual(len(self._json(resp)['lines']), 1)

        # Contract for BOQ confirm
        self.webapp.handle(self._req(
            '/api/clients', 'POST', cookies=cookies,
            json_body={'name': 'Client A'},
            headers={'X-CSRF-Token': csrf}))
        resp = self.webapp.handle(self._req(
            '/api/contracts', 'POST', cookies=cookies,
            json_body={'contract_no': 'C-BOQ-1', 'client_id': 1,
                       'contract_value': 100000},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        cid = self._json(resp)['id']
        lines = self._json(self.webapp.handle(self._req(
            '/api/boq/import/draft', 'POST', cookies=cookies,
            json_body={'text': 'item_no,description,unit,qty,rate\n'
                               '1,Excavation,cum,10,100'},
            headers={'X-CSRF-Token': csrf})))['lines']
        resp = self.webapp.handle(self._req(
            '/api/boq/import/confirm', 'POST', cookies=cookies,
            json_body={'contract_id': cid, 'lines': lines},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        resp = self.webapp.handle(self._req(
            '/api/boq_items', cookies=cookies, query={'contract_id': str(cid)}))
        self.assertEqual(resp.status, 200)
        self.assertEqual(len(self._json(resp)['items']), 1)

        resp = self.webapp.handle(self._req(
            '/api/patterns/learn', 'POST', cookies=cookies,
            json_body={'min_count': 2, 'apply': False},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertIn('drafts', self._json(resp))

        resp = self.webapp.handle(self._req(
            '/api/signals/preview', 'POST', cookies=cookies,
            json_body={'drift': {
                'drifting': True,
                'score': 4,
                'signals': [{'signal': 'ppc', 'basis': 'falling PPC'}],
            }},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        self.assertIn('drafts', self._json(resp))

        resp = self.webapp.handle(self._req(
            '/api/capture/confirm', 'POST', cookies=cookies,
            json_body={'target': 'ncr', 'source': 'ai',
                       'fields': {'description': 'Honeycomb at C3',
                                  'severity': 'Major',
                                  'raised_date': '2026-07-22'}},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        self.assertEqual(self._json(resp)['target'], 'ncr')

    def test_u05_grn_draft_signals_suggest_mobile_modes(self):
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        self.webapp.handle(self._req(
            '/api/materials', 'POST', cookies=cookies,
            json_body={'name': 'OPC 53 Cement', 'unit': 'bags'},
            headers={'X-CSRF-Token': csrf}))

        resp = self.webapp.handle(self._req(
            '/api/grn/draft', 'POST', cookies=cookies,
            json_body={'text': 'Challan DC-1\n1. OPC 53 Cement 10 bags'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertGreaterEqual(self._json(resp)['matched'], 1)

        resp = self.webapp.handle(self._req(
            '/api/signals/suggest', 'POST', cookies=cookies,
            json_body={'apply': False},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertIn('drift', self._json(resp))

        resp = self.webapp.handle(self._req(
            '/m/capture', cookies=cookies, query={'mode': 'free_text'}))
        self.assertEqual(resp.status, 200)
        self.assertIn(b'Paste note', resp.body)

        resp = self.webapp.handle(self._req(
            '/api/text/extract', 'POST', cookies=cookies,
            json_body={'text': 'measurement nos 2 length 5 breadth 1 depth 1',
                       'target': 'measurement'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        self.assertEqual(self._json(resp)['fields']['quantity'], 10.0)

    def test_u06_grn_confirm_vendor_invoice_pdf(self):
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        self.webapp.handle(self._req(
            '/api/materials', 'POST', cookies=cookies,
            json_body={'name': 'OPC 53 Cement', 'unit': 'bags'},
            headers={'X-CSRF-Token': csrf}))

        draft = self._json(self.webapp.handle(self._req(
            '/api/grn/draft', 'POST', cookies=cookies,
            json_body={'text': 'Challan DC-2\n1. OPC 53 Cement 5 bags'},
            headers={'X-CSRF-Token': csrf})))
        resp = self.webapp.handle(self._req(
            '/api/grn/confirm', 'POST', cookies=cookies,
            json_body={'header': draft['header'], 'lines': draft['lines'],
                       'source': 'ai'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        body = self._json(resp)
        self.assertEqual(body['status'], 'Draft')
        self.assertTrue(body.get('followups'))

        resp = self.webapp.handle(self._req(
            '/api/vendor_invoice/draft', 'POST', cookies=cookies,
            json_body={'text': 'Invoice VI-1 2026-07-22\nCement 10 100'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        vd = self._json(resp)
        resp = self.webapp.handle(self._req(
            '/api/vendor_invoice/confirm', 'POST', cookies=cookies,
            json_body={'header': vd['header'], 'lines': vd['lines']},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        self.assertIn('totals', self._json(resp))

        resp = self.webapp.handle(self._req(
            '/api/pdf/extract', 'POST', cookies=cookies,
            json_body={'path': '/tmp/nope.pdf'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200)
        self.assertFalse(self._json(resp)['ok'])

        resp = self.webapp.handle(self._req(
            '/api/capture/confirm', 'POST', cookies=cookies,
            json_body={'target': 'snag', 'source': 'ai',
                       'fields': {'description': 'Lobby tile chip',
                                  'severity': 'Minor'}},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        self.assertTrue(self._json(resp).get('followups') is not None)

    def test_u07_fk_options_cashflow_alloc_po(self):
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        self.webapp.handle(self._req(
            '/api/sites', 'POST', cookies=cookies,
            json_body={'name': 'Plot A'},
            headers={'X-CSRF-Token': csrf}))
        self.webapp.handle(self._req(
            '/api/clients', 'POST', cookies=cookies,
            json_body={'name': 'BuildCo'},
            headers={'X-CSRF-Token': csrf}))
        self.webapp.handle(self._req(
            '/api/vendors', 'POST', cookies=cookies,
            json_body={'name': 'Steel Mart'},
            headers={'X-CSRF-Token': csrf}))

        resp = self.webapp.handle(self._req('/api/projects', cookies=cookies))
        self.assertEqual(resp.status, 200)
        fields = self._json(resp)['fields']
        site_f = next(f for f in fields if f['key'] == 'site_id')
        self.assertEqual(site_f['kind'], 'fk')
        self.assertTrue(any(o.get('label') == 'Plot A' for o in site_f['options']))

        resp = self.webapp.handle(self._req(
            '/api/contracts', 'POST', cookies=cookies,
            json_body={'contract_no': 'C-1', 'client_id': 1, 'site_id': 1,
                       'contract_value': 50000},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        cid = self._json(resp)['id']

        resp = self.webapp.handle(self._req(
            '/api/bills', 'POST', cookies=cookies,
            json_body={'bill_no': 'RB-1', 'contract_id': cid,
                       'bill_date': '2026-07-01', 'work_done_value': 10000,
                       'previous_billed': 0, 'retention_pct': 5,
                       'status': 'Approved'},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)

        resp = self.webapp.handle(self._req(
            '/api/bills/previous', cookies=cookies,
            query={'contract_id': str(cid)}))
        self.assertEqual(resp.status, 200)
        self.assertGreater(self._json(resp)['previous_billed'], 0)

        resp = self.webapp.handle(self._req('/api/cashflow', cookies=cookies,
                                           query={'periods': '4', 'mode': 'week'}))
        self.assertEqual(resp.status, 200)
        cf = self._json(resp)
        self.assertEqual(len(cf['buckets']), 4)
        self.assertIn('balance', cf['buckets'][0])

        resp = self.webapp.handle(self._req('/api/ageing', cookies=cookies))
        self.assertEqual(resp.status, 200)
        self.assertIn('buckets', self._json(resp))

        resp = self.webapp.handle(self._req(
            '/api/payments', 'POST', cookies=cookies,
            json_body={'pay_date': '2026-07-22', 'direction': 'Receipt',
                       'party_type': 'Client', 'party_name': 'BuildCo',
                       'mode': 'Bank', 'amount': 3000},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        pid = self._json(resp)['id']

        resp = self.webapp.handle(self._req(
            '/api/allocations', 'POST', cookies=cookies,
            json_body={'payment_id': pid, 'lines': [
                {'doc_type': 'Bill', 'doc_id': 1, 'amount': 2000}]},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        alloc = self._json(resp)
        self.assertEqual(alloc['allocated'], 2000.0)
        self.assertEqual(alloc['unallocated'], 1000.0)

        resp = self.webapp.handle(self._req(
            '/api/purchase_orders', 'POST', cookies=cookies,
            json_body={'po_no': 'PO-9', 'vendor_id': 1, 'site_id': 1,
                       'po_date': '2026-07-22', 'status': 'Draft',
                       'items': [{'description': 'TMT 12mm', 'unit': 'kg',
                                  'qty': 10, 'rate': 50}]},
            headers={'X-CSRF-Token': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        po = self._json(resp)
        self.assertEqual(po['total_amount'], 500.0)
        self.assertEqual(len(po['items']), 1)
        po_id = po['id']

        # u0.17 — single-PO read used by the GRN screen to record receipts
        # against ordered lines. Pure read: header + items, 404 when absent.
        resp = self.webapp.handle(self._req(
            '/api/purchase_orders/{}'.format(po_id), cookies=cookies))
        self.assertEqual(resp.status, 200, resp.body)
        detail = self._json(resp)
        self.assertEqual(detail['id'], po_id)
        self.assertEqual(len(detail['items']), 1)
        self.assertEqual(detail['items'][0]['description'], 'TMT 12mm')
        self.assertEqual(detail['items'][0]['qty'], 10)

        resp = self.webapp.handle(self._req(
            '/api/purchase_orders/999999', cookies=cookies))
        self.assertEqual(resp.status, 404)

        resp = self.webapp.handle(self._req(
            '/api/search', cookies=cookies, query={'q': 'BuildCo'}))
        self.assertEqual(resp.status, 200)
        recs = self._json(resp).get('records') or []
        self.assertTrue(any(r.get('nav') and r.get('tag') for r in recs))

    def test_ct_gst_measurements_chart_shapes_audit(self):
        """CT-2..CT-5 — /api/gst, measurements CRUD, chart labels, audit sweep."""
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        H = {'X-CSRF-Token': csrf}

        # Seed parties + contract for GST + measurements.
        self.webapp.handle(self._req(
            '/api/clients', 'POST', cookies=cookies,
            json_body={'name': 'PWD'}, headers=H))
        self.webapp.handle(self._req(
            '/api/vendors', 'POST', cookies=cookies,
            json_body={'name': 'Steel Co'}, headers=H))
        self.webapp.handle(self._req(
            '/api/contracts', 'POST', cookies=cookies,
            json_body={'contract_no': 'C-GST', 'client_id': 1},
            headers=H))

        conn = self.db.get_conn()
        conn.execute(
            "INSERT INTO tax_invoices (invoice_no, client_id, invoice_date, "
            "interstate, gst_pct, subtotal, tax_amount, total_amount, status) "
            "VALUES ('TI-CT', 1, '2026-07-10', 0, 18, 10000, 1800, 11800, 'Issued')")
        conn.execute(
            "INSERT INTO tax_invoice_items (tax_invoice_id, description, "
            "hsn_code, amount) VALUES (1, 'Work', '9954', 10000)")
        t = __import__('finance').invoice_totals(5000, 18, 2, False)
        conn.execute(
            "INSERT INTO vendor_invoices (invoice_no, vendor_id, invoice_date, "
            "interstate, gst_pct, tds_pct, subtotal, tax_amount, tds_amount, "
            "total_amount, net_payable) "
            "VALUES ('VI-CT', 1, '2026-07-12', 0, 18, 2, 5000, ?, ?, ?, ?)",
            (t['tax_amount'], t['tds_amount'], t['total_amount'], t['net_payable']))
        conn.execute(
            "INSERT INTO boq_items (contract_id, item_no, description, unit, "
            "qty, rate, amount) VALUES (1, '1', 'PCC', 'cum', 10, 100, 1000)")
        conn.commit()
        conn.close()

        # CT-2 — GST JSON report
        resp = self.webapp.handle(self._req(
            '/api/gst', cookies=cookies, query={'month': '2026-07'}))
        self.assertEqual(resp.status, 200, resp.body)
        g = self._json(resp)
        self.assertEqual(g['month'], '2026-07')
        for block in ('outward', 'hsn', 'inward', 'tds'):
            self.assertIn(block, g)
            self.assertIn('cols', g[block], block)
            if g[block]['rows']:
                self.assertEqual(
                    len(g[block]['cols']), len(g[block]['rows'][0]), block)
        self.assertEqual(g['outward']['totals']['taxable'], 10000.0)
        self.assertEqual(g['inward']['totals']['taxable'], 5000.0)
        self.assertEqual(g['tds']['total'], 100.0)

        # CT-3 — measurements CRUD; blank breadth stays NULL, qty = 4*2*1*0.5
        resp = self.webapp.handle(self._req(
            '/api/measurements', 'POST', cookies=cookies,
            json_body={'contract_id': 1, 'boq_item_id': 1,
                       'mb_date': '2026-07-01', 'mb_ref': 'MB-CT',
                       'nos': 4, 'length': 2, 'breadth': '', 'depth': 0.5},
            headers=H))
        self.assertEqual(resp.status, 201, resp.body)
        m = self._json(resp)
        mid = m['id']
        self.assertEqual(m['quantity'], 4.0)
        self.assertIsNone(m['breadth'])

        resp = self.webapp.handle(self._req(
            '/api/measurements', cookies=cookies,
            query={'contract_id': '1'}))
        self.assertEqual(resp.status, 200)
        self.assertEqual(len(self._json(resp)['items']), 1)

        resp = self.webapp.handle(self._req(
            '/api/measurements/{}'.format(mid), 'PUT', cookies=cookies,
            json_body={'nos': 5, 'length': 2, 'breadth': '', 'depth': 0.5},
            headers=H))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertEqual(self._json(resp)['quantity'], 5.0)

        # CT-4 — chart-ready labels/values
        for path in ('/api/cashflow', '/api/ageing', '/api/evm'):
            resp = self.webapp.handle(self._req(path, cookies=cookies))
            self.assertEqual(resp.status, 200, path)
            body = self._json(resp)
            self.assertIn('labels', body, path)
            self.assertIn('values', body, path)
            self.assertEqual(len(body['labels']), len(body['values']), path)
        cf = self._json(self.webapp.handle(self._req(
            '/api/cashflow', cookies=cookies, query={'periods': '3'})))
        self.assertIn('buckets', cf)  # detail unchanged
        self.assertIn('series', cf)
        self.assertEqual(len(cf['series']['balance']), len(cf['labels']))

        # CT-5 — audit rows for measurement writes + read sweep
        resp = self.webapp.handle(self._req(
            '/api/measurements/{}'.format(mid), 'DELETE', cookies=cookies,
            headers=H))
        self.assertEqual(resp.status, 200)

        resp = self.webapp.handle(self._req(
            '/api/audit', cookies=cookies, query={'limit': '100'}))
        self.assertEqual(resp.status, 200)
        actions = {i['action'] for i in self._json(resp)['items']}
        self.assertIn('api_create', actions)
        self.assertIn('api_update', actions)
        self.assertIn('api_delete', actions)

        read_paths = [
            '/api/health', '/api/me', '/api/contract', '/api/dashboard',
            '/api/kpi', '/api/review', '/api/portfolio',
            '/api/productivity', '/api/filings/feed', '/api/purchase_orders',
            '/api/goods_receipts', '/api/match', '/api/ageing', '/api/cashflow',
            '/api/gst', '/api/pnl', '/api/balance_sheet', '/api/lookahead',
            '/api/workflow', '/api/evm', '/api/risks',
            '/api/opportunities', '/api/lessons', '/api/submittals',
            '/api/audit', '/api/sidecar/status',
            '/api/measurements', '/api/sites', '/api/contracts',
            '/api/attendance', '/api/ncrs',
        ]
        for path in read_paths:
            resp = self.webapp.handle(self._req(path, cookies=cookies))
            self.assertEqual(resp.status, 200, path)
        # Endpoints that need a query param still return 200 with one.
        for path, query in (('/api/search', {'q': 'x'}),
                            ('/api/narrative', {'kind': 'kpi'}),
                            ('/api/menu', {'persona': 'Owner'})):
            resp = self.webapp.handle(self._req(
                path, cookies=cookies, query=query))
            self.assertEqual(resp.status, 200, path)


    def test_ct6_ct10_tables_reports_lookahead_company(self):
        """CT-6..CT-10 — rich table metadata, P&L/BS, lookahead, company audit."""
        import journal_post
        import company
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        H = {'X-CSRF-Token': csrf}

        # --- CT-6: curated columns + FK name on attendance ---
        self.webapp.handle(self._req(
            '/api/sites', 'POST', cookies=cookies,
            json_body={'name': 'Site Alpha'}, headers=H))
        conn = self.db.get_conn()
        conn.execute("INSERT INTO labor (name, daily_wage, status) "
                     "VALUES ('Ramu', 700, 'Active')")
        conn.execute(
            "INSERT INTO attendance (labor_id, att_date, status, hours) "
            "VALUES (1, '2026-07-01', 'Present', 8)")
        conn.commit()
        conn.close()
        resp = self.webapp.handle(self._req('/api/attendance', cookies=cookies))
        self.assertEqual(resp.status, 200, resp.body)
        body = self._json(resp)
        self.assertEqual(body['label'], 'Attendance')
        self.assertTrue(body['columns'])
        self.assertEqual(body['columns'][0]['key'], 'att_date')
        self.assertEqual(body['items'][0]['labor'], 'Ramu')

        # Fallback never 500 — purchase_orders already has a spec; use a
        # whitelist table and assert shape keys always present.
        resp = self.webapp.handle(self._req('/api/approvals', cookies=cookies))
        self.assertEqual(resp.status, 200)
        a = self._json(resp)
        self.assertIn('label', a)
        self.assertIn('columns', a)
        self.assertIn('items', a)

        # --- CT-7: P&L + Balance Sheet after posting an RA bill ---
        conn = self.db.get_conn()
        conn.execute("INSERT INTO clients (name) VALUES ('PWD')")
        conn.execute(
            "INSERT INTO contracts (contract_no, site_id, client_id, "
            "contract_value) VALUES ('C-1', 1, 1, 1000000)")
        conn.execute(
            "INSERT INTO ra_bills (contract_id, bill_no, bill_date, status, "
            "this_bill_value, previous_value, cumulative_value, retention_pct, "
            "retention_amt, other_deductions, net_payable) "
            "VALUES (1, 'RA-1', '2026-07-10', 'Approved', 150000, 0, 150000, "
            "5, 7500, 2000, 140500)")
        conn.commit()
        n = journal_post.post_all(conn)
        self.assertGreaterEqual(n, 1)
        conn.close()

        resp = self.webapp.handle(self._req('/api/pnl', cookies=cookies))
        self.assertEqual(resp.status, 200, resp.body)
        pl = self._json(resp)
        self.assertTrue(pl['sections'])
        self.assertEqual(pl['sections'][0]['cols'], ['Particulars', 'Amount'])
        self.assertGreater(pl['total_income'], 0)

        resp = self.webapp.handle(self._req(
            '/api/balance_sheet', cookies=cookies))
        self.assertEqual(resp.status, 200, resp.body)
        bs = self._json(resp)
        self.assertTrue(bs['balanced'], bs)
        self.assertIn('sections', bs)

        # --- CT-9: look-ahead / PPC ---
        conn = self.db.get_conn()
        conn.execute(
            "INSERT INTO projects (name, site_id) VALUES ('Proj A', 1)")
        conn.execute(
            "INSERT INTO commitments (site_id, week_start, task, status) "
            "VALUES (1, '2026-07-07', 'Pour slab', 'Done')")
        conn.execute(
            "INSERT INTO commitments (site_id, week_start, task, status, "
            "reason) VALUES (1, '2026-07-07', 'Fix formwork', 'Not done', "
            "'Material not available')")
        conn.commit()
        conn.close()
        resp = self.webapp.handle(self._req(
            '/api/lookahead', cookies=cookies,
            query={'project_id': '1', 'weeks': '4'}))
        self.assertEqual(resp.status, 200, resp.body)
        la = self._json(resp)
        self.assertEqual(la['promised'], 2)
        self.assertEqual(la['done'], 1)
        self.assertEqual(la['ppc'], 50.0)
        self.assertTrue(la['cols'])
        self.assertEqual(len(la['items']), 2)

        # --- CT-10: companies exists flags + audited create ---
        orig_reg = company.REGISTRY_PATH
        reg = os.path.join(tempfile.mkdtemp(), 'companies.json')
        company.REGISTRY_PATH = reg
        try:
            data = company.load(reg)
            company.add(data, 'Main', self.path, make_active=True)
            missing = os.path.join(os.path.dirname(self.path), 'gone.db')
            company.add(data, 'Gone', missing)
            company.save(data, reg)

            resp = self.webapp.handle(self._req('/api/companies'))
            self.assertEqual(resp.status, 200)
            payload = self._json(resp)
            by_name = {i['name']: i for i in payload['items']}
            self.assertTrue(by_name['Main']['exists'])
            self.assertIn('exists', by_name['Gone'])
            self.assertFalse(by_name['Gone']['exists'])

            ok, msg, path = company.create_company(
                'Audited Co', folder=os.path.dirname(self.path),
                make_active=True, db_module=self.db, registry_path=reg,
                actor='admin')
            self.assertTrue(ok, msg)
            conn = self.db.get_conn()
            try:
                rows = conn.execute(
                    "SELECT action, username FROM audit_log "
                    "WHERE action = 'company_create'").fetchall()
            finally:
                conn.close()
            self.assertTrue(rows)
            self.assertEqual(rows[0]['username'], 'admin')
        finally:
            company.REGISTRY_PATH = orig_reg
            self.db.DB_PATH = self.path


    def test_u013_cloud_roadmap_apis(self):
        """u0.13 — home, GST export, RA generate, WO/sub bills, muster, commitments, timeline, risks accept."""
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        headers = {'X-CSRF-Token': csrf}

        # Home aggregate
        resp = self.webapp.handle(self._req('/api/home', cookies=cookies))
        self.assertEqual(resp.status, 200, resp.body)
        home = self._json(resp)
        self.assertIn('snapshot', home)
        self.assertIn('advisories', home)
        self.assertIn('blocks', home)
        self.assertIn('match', home['blocks'])

        # GST export pack
        resp = self.webapp.handle(self._req(
            '/api/gst/export', cookies=cookies, query={'month': '2026-07'}))
        self.assertEqual(resp.status, 200)
        pack = self._json(resp)
        self.assertIn('csv', pack)
        self.assertIn('Outward GST', pack['csv'])
        self.assertIn('html', pack)

        # Key numbers vs insight split
        resp = self.webapp.handle(self._req('/api/kpi', cookies=cookies))
        self.assertEqual(resp.status, 200)
        kpi = self._json(resp)
        self.assertIn('rows', kpi)
        self.assertTrue(kpi['cols'])
        resp = self.webapp.handle(self._req('/api/insight', cookies=cookies))
        self.assertEqual(resp.status, 200)
        self.assertIn('site_profitability', self._json(resp))

        # Seed site + labour + contract/BOQ/MB for remaining flows
        conn = self.db.get_conn()
        conn.execute("INSERT INTO sites (name) VALUES ('Site A')")
        site_id = conn.execute('SELECT id FROM sites').fetchone()['id']
        conn.execute(
            "INSERT INTO labor (name, site_id, daily_wage, status) "
            "VALUES ('Ram', ?, 700, 'Active')", (site_id,))
        labor_id = conn.execute('SELECT id FROM labor').fetchone()['id']
        conn.execute(
            "INSERT INTO vendors (name) VALUES ('Sub Co')")
        vendor_id = conn.execute('SELECT id FROM vendors').fetchone()['id']
        conn.execute(
            "INSERT INTO contracts (contract_no, site_id, contract_value) "
            "VALUES ('C/U13', ?, 1000000)", (site_id,))
        cid = conn.execute('SELECT id FROM contracts').fetchone()['id']
        conn.execute(
            "INSERT INTO boq_items (contract_id, item_no, description, unit, "
            "qty, rate, amount) VALUES (?, '1', 'PCC', 'cum', 100, 500, 50000)",
            (cid,))
        bid = conn.execute('SELECT id FROM boq_items').fetchone()['id']
        conn.execute(
            "INSERT INTO measurements (boq_item_id, contract_id, mb_date, "
            "mb_ref, nos, length, breadth, depth, quantity) "
            "VALUES (?, ?, '2026-07-01', 'MB-1', 10, 1, 1, 1, 10)",
            (bid, cid))
        conn.execute(
            "INSERT INTO projects (name, site_id, start_date, status) "
            "VALUES ('P1', ?, '2026-06-01', 'Active')", (site_id,))
        pid = conn.execute('SELECT id FROM projects').fetchone()['id']
        conn.execute(
            "INSERT INTO timeline_tasks (project_id, task_name, start_date, "
            "end_date, duration_days, dependency) "
            "VALUES (?, 'Clear', '2026-06-01', '2026-06-05', 5, '')", (pid,))
        conn.execute(
            "INSERT INTO timeline_tasks (project_id, task_name, start_date, "
            "end_date, duration_days, dependency) "
            "VALUES (?, 'Excavate', '2026-06-06', '2026-06-12', 7, 'Clear')",
            (pid,))
        conn.commit()
        conn.close()

        # RA generate from MB
        resp = self.webapp.handle(self._req(
            '/api/ra_bills/generate', 'POST', cookies=cookies, headers=headers,
            json_body={'contract_id': cid, 'bill_date': '2026-07-10',
                       'retention_pct': 5, 'csrf': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        ra = self._json(resp)
        self.assertEqual(ra['bill_no'], 'RA-1')
        self.assertEqual(ra['line_count'], 1)
        self.assertAlmostEqual(ra['totals']['this_bill_value'], 5000.0, places=2)

        # Work order + sub bill
        resp = self.webapp.handle(self._req(
            '/api/work_orders', 'POST', cookies=cookies, headers=headers,
            json_body={
                'wo_no': 'WO-1', 'vendor_id': vendor_id, 'site_id': site_id,
                'retention_pct': 5, 'tds_pct': 1,
                'items': [{'description': 'Earthwork', 'unit': 'cum',
                           'qty': 10, 'rate': 200}],
                'csrf': csrf,
            }))
        self.assertEqual(resp.status, 201, resp.body)
        wo = self._json(resp)
        self.assertEqual(wo['total_amount'], 2000.0)
        resp = self.webapp.handle(self._req(
            '/api/sub_bills', 'POST', cookies=cookies, headers=headers,
            json_body={'work_order_id': wo['id'], 'bill_no': 'SB-1',
                       'bill_date': '2026-07-15', 'this_bill_value': 1000,
                       'csrf': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        sb = self._json(resp)
        self.assertAlmostEqual(sb['net_payable'], 1000 - 50 - 10, places=2)

        # Muster grid + save + payout
        resp = self.webapp.handle(self._req(
            '/api/muster', cookies=cookies,
            query={'site_id': str(site_id), 'att_date': '2026-07-01'}))
        self.assertEqual(resp.status, 200, resp.body)
        grid = self._json(resp)
        self.assertEqual(len(grid['rows']), 1)
        resp = self.webapp.handle(self._req(
            '/api/muster', 'POST', cookies=cookies, headers=headers,
            json_body={
                'site_id': site_id, 'att_date': '2026-07-01',
                'rows': [{'labor_id': labor_id, 'status': 'Present', 'hours': 8}],
                'csrf': csrf,
            }))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertEqual(self._json(resp)['saved'], 1)
        # Mark rest of week present for payout
        for d in ('2026-07-02', '2026-07-03', '2026-07-04', '2026-07-05',
                  '2026-07-06', '2026-07-07'):
            self.webapp.handle(self._req(
                '/api/muster', 'POST', cookies=cookies, headers=headers,
                json_body={
                    'site_id': site_id, 'att_date': d,
                    'rows': [{'labor_id': labor_id, 'status': 'Present',
                              'hours': 8}],
                    'csrf': csrf,
                }))
        resp = self.webapp.handle(self._req(
            '/api/muster/payout', cookies=cookies,
            query={'site_id': str(site_id), 'week_start': '2026-07-01'}))
        self.assertEqual(resp.status, 200, resp.body)
        pay = self._json(resp)
        self.assertEqual(pay['payable_count'], 1)
        self.assertAlmostEqual(pay['total_net'], 4900.0, places=2)  # 7*700
        resp = self.webapp.handle(self._req(
            '/api/muster/payout', 'POST', cookies=cookies, headers=headers,
            json_body={'site_id': site_id, 'week_start': '2026-07-01',
                       'csrf': csrf}))
        self.assertEqual(resp.status, 201, resp.body)
        rec = self._json(resp)
        self.assertEqual(rec['recorded'], 1)
        # Idempotent second run
        resp = self.webapp.handle(self._req(
            '/api/muster/payout', 'POST', cookies=cookies, headers=headers,
            json_body={'site_id': site_id, 'week_start': '2026-07-01',
                       'csrf': csrf}))
        self.assertEqual(self._json(resp)['skipped'], 1)

        # Commitments + lookahead reasons
        resp = self.webapp.handle(self._req(
            '/api/commitments', 'POST', cookies=cookies, headers=headers,
            json_body={
                'site_id': site_id, 'week_start': '2026-07-20',
                'task': 'Pour slab', 'status': 'Not done',
                'reason': 'Material not available', 'csrf': csrf,
            }))
        self.assertEqual(resp.status, 201, resp.body)
        cm = self._json(resp)
        resp = self.webapp.handle(self._req(
            '/api/lookahead', cookies=cookies,
            query={'site_id': str(site_id)}))
        self.assertEqual(resp.status, 200)
        la = self._json(resp)
        self.assertIn('reasons', la)
        self.assertIn('Material not available', la['reasons'])
        self.assertIn('ppc_note', la)
        resp = self.webapp.handle(self._req(
            '/api/commitments/{}'.format(cm['id']), 'POST',
            cookies=cookies, headers=headers,
            json_body={'done': True, 'csrf': csrf}))
        self.assertEqual(resp.status, 200)
        self.assertEqual(self._json(resp)['status'], 'Done')

        # Timeline / CPM
        resp = self.webapp.handle(self._req(
            '/api/timeline', cookies=cookies,
            query={'project_id': str(pid)}))
        self.assertEqual(resp.status, 200, resp.body)
        tl = self._json(resp)
        self.assertTrue(tl['summary']['ok'])
        self.assertEqual(len(tl['tasks']), 2)

        # Risk detect (no apply required) + accept path with empty ids is ok
        resp = self.webapp.handle(self._req(
            '/api/risks/detect', 'POST', cookies=cookies, headers=headers,
            json_body={'apply': False, 'csrf': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertIn('detected', self._json(resp))
        resp = self.webapp.handle(self._req(
            '/api/risks/accept', 'POST', cookies=cookies, headers=headers,
            json_body={'detect_and_apply': True, 'status': 'Accepted',
                       'csrf': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        acc = self._json(resp)
        self.assertIn('accepted_ids', acc)

        # Health version
        resp = self.webapp.handle(self._req('/api/health', cookies=cookies))
        self.assertEqual(self._json(resp)['api'], 'u0.17')

    def test_u014_foundry_agents_api(self):
        """u0.14 — multi-agent catalog, ask (deterministic), workflow handoffs."""
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        headers = {'X-CSRF-Token': csrf}

        resp = self.webapp.handle(self._req('/api/agents', cookies=cookies))
        self.assertEqual(resp.status, 200, resp.body)
        body = self._json(resp)
        ids = {a['id'] for a in body['items']}
        self.assertIn('estimation', ids)
        self.assertIn('executive', ids)
        self.assertTrue(body['workflows'])

        resp = self.webapp.handle(self._req(
            '/api/agents/finance', cookies=cookies))
        self.assertEqual(resp.status, 200)
        self.assertEqual(self._json(resp)['id'], 'finance')

        resp = self.webapp.handle(self._req(
            '/api/agents/ask', 'POST', cookies=cookies, headers=headers,
            json_body={
                'question': 'How much cash and receivable do I have?',
                'agent_id': 'finance',
                'use_model': False,
                'csrf': csrf,
            }))
        self.assertEqual(resp.status, 200, resp.body)
        ask = self._json(resp)
        self.assertTrue(ask['ok'])
        self.assertEqual(ask['agent_id'], 'finance')
        self.assertIn('money_snapshot', ask['tools'])
        self.assertTrue(ask['summary'])
        self.assertFalse(ask['model_used'])
        self.assertEqual(ask['provider'], 'deterministic')

        # Auto-route without agent_id
        resp = self.webapp.handle(self._req(
            '/api/agents/ask', 'POST', cookies=cookies, headers=headers,
            json_body={
                'question': 'Which POs are over-invoiced without a GRN?',
                'use_model': False,
                'csrf': csrf,
            }))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertEqual(self._json(resp)['agent_id'], 'procurement')

        resp = self.webapp.handle(self._req(
            '/api/agents/workflow', 'POST', cookies=cookies, headers=headers,
            json_body={
                'workflow_id': 'variation_impact',
                'context': {'notes': 'Change 200mm block to AAC'},
                'csrf': csrf,
            }))
        self.assertEqual(resp.status, 200, resp.body)
        wf = self._json(resp)
        self.assertTrue(wf['ok'])
        self.assertEqual(len(wf['steps']), 7)
        self.assertGreaterEqual(wf['gated_count'], 1)
        self.assertEqual(wf['steps'][0]['agent'], 'drawing')
        self.assertEqual(wf['steps'][-1]['agent'], 'executive')

        # Provider status + golden eval suite
        resp = self.webapp.handle(self._req(
            '/api/agents/provider', cookies=cookies))
        self.assertEqual(resp.status, 200, resp.body)
        prov = self._json(resp)
        self.assertIn(prov['active'], ('none', 'foundry_local', 'azure_foundry'))
        self.assertIn('foundry_local', prov)
        self.assertEqual(prov['azure_foundry']['phase'], 'C')

        resp = self.webapp.handle(self._req(
            '/api/agents/eval', cookies=cookies))
        self.assertEqual(resp.status, 200)
        self.assertGreaterEqual(len(self._json(resp)['cases']), 8)

        resp = self.webapp.handle(self._req(
            '/api/agents/eval', 'POST', cookies=cookies, headers=headers,
            json_body={'use_model': False, 'csrf': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        suite = self._json(resp)
        self.assertEqual(suite['failed'], 0, suite)
        self.assertEqual(suite['passed'], suite['total'])

    def test_u016_drawing_phase_d_api(self):
        """u0.16 — takeoff CRUD, element draft/confirm, revision-delta."""
        sid, csrf, _ = self._login()
        cookies = {'cosid': sid}
        headers = {'X-CSRF-Token': csrf}

        # Seed two drawing revisions via masters if available, else raw SQL.
        import db
        conn = db.get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO drawings (drawing_no, title, revision, scale, unit) "
                "VALUES ('P-01', 'Plan', 'A', 0.01, 'm')")
            d1 = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO drawings (drawing_no, title, revision, scale, unit) "
                "VALUES ('P-01', 'Plan', 'B', 0.01, 'm')")
            d2 = cur.lastrowid
            conn.commit()
        finally:
            conn.close()

        resp = self.webapp.handle(self._req(
            '/api/drawings/elements/draft', 'POST', cookies=cookies,
            headers=headers, json_body={
                'scale': 0.01, 'unit': 'm',
                'elements': [
                    {'type': 'wall', 'ref': 'W1', 'points': [[0, 0], [100, 0]]},
                ],
                'csrf': csrf,
            }))
        self.assertEqual(resp.status, 200, resp.body)
        draft = self._json(resp)
        self.assertTrue(draft['ok'])
        self.assertEqual(draft['count'], 1)
        self.assertAlmostEqual(draft['totals']['m'], 1.0, places=4)

        resp = self.webapp.handle(self._req(
            '/api/drawings/elements/confirm', 'POST', cookies=cookies,
            headers=headers, json_body={
                'drawing_id': d1, 'scale': 0.01, 'unit': 'm',
                'sync_takeoff': True,
                'elements': [
                    {'type': 'wall', 'ref': 'W1', 'points': [[0, 0], [100, 0]]},
                    {'type': 'door', 'ref': 'D1', 'points': [[10, 10]]},
                ],
                'csrf': csrf,
            }))
        self.assertEqual(resp.status, 200, resp.body)
        conf = self._json(resp)
        self.assertTrue(conf['ok'])
        self.assertEqual(conf['count'], 2)
        self.assertTrue(conf.get('takeoff', {}).get('ok'))
        tid = conf['takeoff']['takeoff_id']

        resp = self.webapp.handle(self._req(
            '/api/takeoffs/{}'.format(tid), cookies=cookies))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertEqual(len(self._json(resp)['items']), 2)

        resp = self.webapp.handle(self._req(
            '/api/takeoffs/{}/to-estimate'.format(tid), 'POST',
            cookies=cookies, headers=headers,
            json_body={'csrf': csrf}))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertTrue(self._json(resp)['ok'])

        # Confirm rev B elements and diff
        resp = self.webapp.handle(self._req(
            '/api/drawings/elements/confirm', 'POST', cookies=cookies,
            headers=headers, json_body={
                'drawing_id': d2, 'scale': 0.01, 'unit': 'm',
                'elements': [
                    {'type': 'wall', 'ref': 'W1', 'points': [[0, 0], [200, 0]]},
                ],
                'csrf': csrf,
            }))
        self.assertEqual(resp.status, 200, resp.body)

        resp = self.webapp.handle(self._req(
            '/api/drawings/revision-delta', 'POST', cookies=cookies,
            headers=headers, json_body={
                'from_drawing_id': d1, 'to_drawing_id': d2,
                'csrf': csrf,
            }))
        self.assertEqual(resp.status, 200, resp.body)
        delta = self._json(resp)
        self.assertTrue(delta['ok'])
        self.assertEqual(delta['diff']['summary']['modified'], 1)
        self.assertEqual(delta['diff']['summary']['removed'], 1)
        self.assertTrue(delta['variation_draft']['gated'])

        resp = self.webapp.handle(self._req(
            '/api/drawings/revision-delta/confirm', 'POST', cookies=cookies,
            headers=headers, json_body={
                'from_drawing_id': d1, 'to_drawing_id': d2,
                'csrf': csrf,
            }))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertTrue(self._json(resp)['ok'])

        resp = self.webapp.handle(self._req(
            '/api/drawings/{}/elements'.format(d1), cookies=cookies))
        self.assertEqual(resp.status, 200)
        self.assertEqual(self._json(resp)['count'], 2)

        resp = self.webapp.handle(self._req(
            '/api/drawings/elements/ingest', 'POST', cookies=cookies,
            headers=headers, json_body={
                'scale': 0.01,
                'elements': [
                    {'type': 'wall', 'points': [[0, 0], [50, 0]]},
                ],
                'csrf': csrf,
            }))
        self.assertEqual(resp.status, 200, resp.body)
        self.assertAlmostEqual(self._json(resp)['totals']['m'], 0.5, places=4)

        resp = self.webapp.handle(self._req('/api/health', cookies=cookies))
        self.assertEqual(self._json(resp)['api'], 'u0.17')


if __name__ == '__main__':
    unittest.main(verbosity=2)

