"""Test suite for the pure business maths and the posting engine.

Stdlib ``unittest`` only — no pytest, matching the project's no-pip rule.
Nothing here imports tkinter, so the whole suite runs headless.

Run from the repo root:

    python -m unittest discover -s tests -v

The GUI layer is deliberately not covered: these tests target the modules that
decide **money** — tax, civil quantities, wages, ageing and the double-entry
posting rules — because those are where a silent error costs a contractor real
rupees. ``test_journal_posting`` exercises the engine end-to-end against a real
temporary SQLite database.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, 'construction_app'))

import ageing
import analytics
import civil
import estimate
import finance
import money
import numbering
import numwords
import posting
import projman
import reports
import statutory
import subcontract
import wages


class TestFinance(unittest.TestCase):
    def test_gst_splits_in_half_intra_state(self):
        g = finance.split_gst(10000, 18, False)
        self.assertEqual(g['cgst'], 900)
        self.assertEqual(g['sgst'], 900)
        self.assertEqual(g['igst'], 0)
        self.assertEqual(g['total_tax'], 1800)

    def test_gst_is_single_igst_inter_state(self):
        g = finance.split_gst(10000, 18, True)
        self.assertEqual(g['igst'], 1800)
        self.assertEqual(g['cgst'], 0)
        self.assertEqual(g['sgst'], 0)

    def test_tds_is_on_the_pre_gst_base(self):
        self.assertEqual(finance.compute_tds(10000, 2), 200)

    def test_invoice_totals_withhold_tds_from_the_gross(self):
        t = finance.invoice_totals(10000, 18, 2, False)
        self.assertEqual(t['tax_amount'], 1800)
        self.assertEqual(t['total_amount'], 11800)
        self.assertEqual(t['tds_amount'], 200)
        self.assertEqual(t['net_payable'], 11600)

    def test_reconcile_flags_over_and_under_billing(self):
        self.assertEqual(finance.reconcile(10000, 10500, 100)['status'], 'Over-billed')
        self.assertEqual(finance.reconcile(10000, 9500, 100)['status'], 'Under-billed')
        self.assertEqual(finance.reconcile(10000, 10050, 100)['status'], 'Matched')

    def test_reconcile_reports_no_po(self):
        self.assertEqual(finance.reconcile(None, 5000, 0)['status'], 'No PO')

    def test_is_balanced_uses_a_tolerance_not_equality(self):
        self.assertTrue(finance.is_balanced(1500, 1500))
        self.assertFalse(finance.is_balanced(1500, 1400))
        self.assertTrue(finance.is_balanced(1500.001, 1500.002))


class TestCivil(unittest.TestCase):
    def test_blank_dimensions_count_as_one(self):
        # a running-metre item is Nos x Length, with breadth/depth left blank
        self.assertEqual(civil.measurement_quantity(4, 3, 2, ''), 24.0)
        self.assertEqual(civil.measurement_quantity(5, '', '', ''), 5.0)

    def test_ra_current_is_upto_minus_previous(self):
        self.assertEqual(civil.ra_current(120, 100, 250), (20, 5000.0))

    def test_ra_current_can_go_negative_on_a_downward_revision(self):
        qty, amount = civil.ra_current(80, 100, 250)
        self.assertEqual(qty, -20)
        self.assertEqual(amount, -5000.0)

    def test_ra_bill_totals_deduct_retention_and_other(self):
        t = civil.ra_bill_totals(100000, 400000, 5, 2000)
        self.assertEqual(t['retention_amt'], 5000)
        self.assertEqual(t['cumulative_value'], 500000)
        self.assertEqual(t['net_payable'], 93000)

    def test_deviation_row_prices_excess_and_saving(self):
        excess = civil.deviation_row(100, 120, 250)
        self.assertEqual(excess['deviation_qty'], 20.0)
        self.assertEqual(excess['deviation_pct'], 20.0)
        self.assertEqual(excess['amount_effect'], 5000.0)
        saving = civil.deviation_row(100, 80, 250)
        self.assertEqual(saving['deviation_qty'], -20.0)
        self.assertEqual(saving['amount_effect'], -5000.0)

    def test_deviation_pct_is_none_for_an_extra_item(self):
        # nothing was tendered, so a percentage would divide by zero
        self.assertIsNone(civil.deviation_row(0, 15, 100)['deviation_pct'])

    def test_cube_strength_and_result(self):
        self.assertEqual(civil.cube_strength(450, 22500), 20.0)
        self.assertEqual(civil.cube_result(20, 'M20'), 'Pass')
        self.assertEqual(civil.cube_result(19.9, 'M20'), 'Fail')
        self.assertEqual(civil.cube_result(20, ''), '-')


class TestMoney(unittest.TestCase):
    def test_running_balance_accumulates_over_the_opening(self):
        self.assertEqual(money.running_balance([1000, -400, 200], 100),
                         [1100, 700, 900])

    def test_closing_balance_matches_the_last_running_balance(self):
        self.assertEqual(money.closing_balance([1000, -400, 200], 100), 900)

    def test_party_outstanding(self):
        self.assertEqual(money.party_outstanding(50000, 30000), 20000)

    def test_profit_margin_handles_zero_revenue(self):
        # must not raise ZeroDivisionError on a site with cost but no billing
        self.assertIsNotNone(money.profit_margin(0, 5000))


class TestWages(unittest.TestCase):
    def test_day_fractions(self):
        self.assertEqual(wages.day_fraction('Present', 8), 1.0)
        self.assertEqual(wages.day_fraction('Half Day', 4), 0.5)
        self.assertEqual(wages.day_fraction('Absent', 0), 0.0)

    def test_overtime_is_pro_rata_beyond_eight_hours(self):
        self.assertEqual(wages.day_fraction('Overtime', 12), 1.5)
        self.assertEqual(wages.day_fraction('Overtime', 8), 1.0)

    def test_advance_recovery_never_makes_net_pay_negative(self):
        w = wages.wage_net(6, 700, 99999)
        self.assertEqual(w['gross'], 4200.0)
        self.assertEqual(w['deduction'], 4200.0)
        self.assertEqual(w['net'], 0.0)

    def test_partial_advance_recovery(self):
        self.assertEqual(wages.wage_net(6, 700, 1000),
                         {'gross': 4200.0, 'deduction': 1000.0, 'net': 3200.0})


class TestNumbering(unittest.TestCase):
    def test_financial_year_starts_in_april(self):
        self.assertEqual(numbering.financial_year('2026-04-01'),
                         numbering.financial_year('2026-12-31'))
        self.assertNotEqual(numbering.financial_year('2026-03-31'),
                            numbering.financial_year('2026-04-01'))

    def test_next_number_increments_from_the_maximum_not_the_count(self):
        # deleting an invoice must never cause a duplicate number
        existing = ['INV/2026-27/001', 'INV/2026-27/007']
        n = numbering.next_number(existing, 'INV', '2026-07-19', 3, True)
        self.assertIn('008', n)

    def test_next_number_ignores_foreign_series(self):
        n = numbering.next_number(['BILL-5', 'junk', None], 'INV',
                                  '2026-07-19', 3, False)
        self.assertIn('001', n)


class TestNumWords(unittest.TestCase):
    def test_indian_lakh_crore_grouping(self):
        self.assertIn('Lakh', numwords.rupees_in_words(150000))
        self.assertIn('Crore', numwords.rupees_in_words(20000000))

    def test_zero_is_rendered(self):
        self.assertTrue(numwords.rupees_in_words(0))


class TestStatutory(unittest.TestCase):
    def test_pf_and_esi_and_cess_are_positive_deductions(self):
        self.assertGreater(statutory.pf(10000), 0)
        self.assertGreater(statutory.labour_cess(1000000), 0)
        e = statutory.esi(10000)
        self.assertTrue(isinstance(e, dict) or e >= 0)


class TestAgeing(unittest.TestCase):
    def test_buckets_partition_the_age_range(self):
        self.assertEqual(ageing.bucket_for_days(0), ageing.bucket_for_days(15))
        self.assertNotEqual(ageing.bucket_for_days(15), ageing.bucket_for_days(45))
        self.assertNotEqual(ageing.bucket_for_days(75), ageing.bucket_for_days(120))

    def test_fifo_settles_the_oldest_bill_first(self):
        bills = [('2026-06-01', 1000), ('2026-01-01', 1000)]  # deliberately unordered
        out = ageing.apply_receipts_fifo(bills, 1000)
        # the January bill is cleared; only the June one stays open
        self.assertEqual(out, [('2026-06-01', 1000.0)])

    def test_fifo_partially_settles_the_oldest_bill(self):
        out = ageing.apply_receipts_fifo([('2026-01-01', 1000)], 400)
        self.assertEqual(out, [('2026-01-01', 600.0)])

    def test_over_receipt_leaves_nothing_outstanding(self):
        out = ageing.apply_receipts_fifo([('2026-01-01', 1000)], 5000)
        self.assertEqual(out, [])


class TestAnalytics(unittest.TestCase):
    def test_progress_is_measured_over_boq(self):
        self.assertEqual(analytics.contract_progress(1000, 250)['progress_pct'], 25.0)

    def test_progress_is_unclamped_so_overrun_is_visible(self):
        self.assertGreater(analytics.contract_progress(1000, 1200)['progress_pct'], 100)

    def test_progress_handles_zero_boq(self):
        self.assertIsNotNone(analytics.contract_progress(0, 100))


class TestEstimateAndSubcontract(unittest.TestCase):
    def test_item_amount(self):
        self.assertEqual(estimate.item_amount(100, 3), 300)

    def test_estimate_totals_apply_contingency_then_gst(self):
        t = estimate.estimate_totals([{'amount': 10000}], 10, 18)
        self.assertGreater(t['grand_total'], 10000)

    def test_sub_bill_net_deducts_retention_and_tds(self):
        t = subcontract.sub_bill_totals(100000, 0, 5, 2, 1000)
        self.assertLess(t['net_payable'], 100000)


class TestProjman(unittest.TestCase):
    def test_budget_status_handles_zero_budget(self):
        self.assertIsNotNone(projman.budget_status(0, 500))

    def test_milestone_progress_empty(self):
        self.assertIsNotNone(projman.milestone_progress([]))


class TestPostingRules(unittest.TestCase):
    """Every posting rule must produce balanced double-entry lines."""

    def test_tax_invoice_balances(self):
        self.assertTrue(posting.lines_balanced(
            posting.tax_invoice_lines(10000, 1800, 11800)))

    def test_vendor_invoice_balances(self):
        self.assertTrue(posting.lines_balanced(
            posting.vendor_invoice_lines(10000, 1800, 200, 11600)))

    def test_payments_balance_both_directions(self):
        self.assertTrue(posting.lines_balanced(
            posting.payment_lines('Receipt', 'Client', 'Cash', 5000)))
        self.assertTrue(posting.lines_balanced(
            posting.payment_lines('Payment', 'Vendor', 'Bank', 5000)))

    def test_sub_bill_balances(self):
        self.assertTrue(posting.lines_balanced(
            posting.sub_bill_lines(100000, 5000, 2000, 1000, 92000)))

    def test_payroll_balances(self):
        self.assertTrue(posting.lines_balanced(posting.payroll_lines(3200)))

    def test_ra_bill_balances_with_retention(self):
        lines = posting.ra_bill_lines(150000, 7500, 2000, 140500)
        self.assertTrue(posting.lines_balanced(lines))
        credits = sum(l['credit'] for l in lines)
        self.assertEqual(credits, 150000)  # full work value is revenue

    def test_ra_bill_balances_without_retention(self):
        lines = posting.ra_bill_lines(100000, 0, 0, 100000)
        self.assertTrue(posting.lines_balanced(lines))
        self.assertEqual(len(lines), 2)  # zero legs are dropped

    def test_ra_bill_retention_is_an_asset_not_an_expense(self):
        lines = posting.ra_bill_lines(150000, 7500, 0, 142500)
        retention = [l for l in lines
                     if l['code'] == posting.RETENTION_RECEIVABLE]
        self.assertEqual(len(retention), 1)
        self.assertEqual(retention[0]['debit'], 7500)


class TestReports(unittest.TestCase):
    ACCOUNTS = [
        {'name': 'Contract Revenue', 'type': 'Income', 'debit': 0, 'credit': 250000},
        {'name': 'Materials Consumed', 'type': 'Expense', 'debit': 100000, 'credit': 0},
        {'name': 'Accounts Receivable', 'type': 'Asset', 'debit': 250000, 'credit': 0},
        {'name': 'Accounts Payable', 'type': 'Liability', 'debit': 0, 'credit': 100000},
    ]

    def test_profit_and_loss_nets_income_against_expense(self):
        pl = reports.profit_and_loss(self.ACCOUNTS)
        self.assertEqual(pl['total_income'], 250000)
        self.assertEqual(pl['total_expense'], 100000)
        self.assertEqual(pl['net_profit'], 150000)

    def test_balance_sheet_ties_out(self):
        pl = reports.profit_and_loss(self.ACCOUNTS)
        bs = reports.balance_sheet(self.ACCOUNTS, pl['net_profit'])
        self.assertTrue(bs['balanced'])


class TestJournalPostingEndToEnd(unittest.TestCase):
    """The posting engine against a real database.

    Covers the bug where running/RA bills were never posted, so the P&L
    showed no revenue for a contractor billing the normal civil way.
    """

    def setUp(self):
        import db
        self.db = db
        fd, self.path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.remove(self.path)
        self._orig = db.DB_PATH
        db.DB_PATH = self.path
        db.init_db()
        self.conn = db.get_conn()
        self.conn.execute("INSERT INTO clients (name) VALUES ('PWD Division')")
        self.conn.execute("INSERT INTO sites (name) VALUES ('Site A')")
        self.conn.execute(
            "INSERT INTO contracts (contract_no, site_id, client_id, contract_value) "
            "VALUES ('C-1', 1, 1, 1000000)")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.db.DB_PATH = self._orig
        try:
            os.remove(self.path)
        except OSError:
            pass

    def _add_ra_bill(self, no, status, value, retention, other, net):
        self.conn.execute(
            "INSERT INTO ra_bills (contract_id, bill_no, bill_date, status, "
            "this_bill_value, previous_value, cumulative_value, retention_pct, "
            "retention_amt, other_deductions, net_payable) "
            "VALUES (1, ?, '2026-07-10', ?, ?, 0, ?, 5, ?, ?, ?)",
            (no, status, value, value, retention, other, net))
        self.conn.commit()

    def test_seeded_chart_includes_retention_receivable(self):
        row = self.conn.execute(
            "SELECT 1 FROM accounts WHERE code = ?",
            (posting.RETENTION_RECEIVABLE,)).fetchone()
        self.assertIsNotNone(row)

    def test_ra_bill_posts_and_lines_balance(self):
        import journal_post
        self._add_ra_bill('RA-1', 'Approved', 150000, 7500, 2000, 140500)
        self.assertEqual(journal_post.post_all(self.conn), 1)
        entry = self.conn.execute(
            "SELECT * FROM journal_entries WHERE source = 'RABill'").fetchone()
        self.assertIsNotNone(entry)
        d, c = self.conn.execute(
            'SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) '
            'FROM journal_lines WHERE journal_entry_id = ?',
            (entry['id'],)).fetchone()
        self.assertAlmostEqual(d, c, places=2)
        # header totals must match the lines — a dropped line would diverge
        self.assertAlmostEqual(d, entry['total_debit'], places=2)

    def test_draft_ra_bill_is_not_posted(self):
        import journal_post
        self._add_ra_bill('RA-D', 'Draft', 50000, 2500, 0, 47500)
        self.assertEqual(journal_post.post_all(self.conn), 0)

    def test_posting_is_idempotent(self):
        import journal_post
        self._add_ra_bill('RA-1', 'Approved', 150000, 7500, 2000, 140500)
        self.assertEqual(journal_post.post_all(self.conn), 1)
        self.assertEqual(journal_post.post_all(self.conn), 0)

    def test_running_bill_posts_only_its_incremental_value(self):
        import journal_post
        # work_done_value is cumulative; only 100000 is new in this bill
        self.conn.execute(
            "INSERT INTO bills (contract_id, bill_no, bill_date, status, "
            "work_done_value, previous_billed, retention_amt, other_deductions, "
            "net_payable) VALUES (1,'B-2','2026-07-15','Approved',250000,150000,"
            "5000,1000,94000)")
        self.conn.commit()
        self.assertEqual(journal_post.post_all(self.conn), 1)
        entry = self.conn.execute(
            "SELECT * FROM journal_entries WHERE source = 'Bill'").fetchone()
        self.assertAlmostEqual(entry['total_debit'], 100000, places=2)

    def test_ra_revenue_reaches_the_profit_and_loss(self):
        import journal_post
        self._add_ra_bill('RA-1', 'Approved', 150000, 7500, 2000, 140500)
        journal_post.post_all(self.conn)
        rows = self.conn.execute(
            'SELECT a.name, a.type, COALESCE(SUM(jl.debit),0) AS debit, '
            'COALESCE(SUM(jl.credit),0) AS credit FROM accounts a '
            'LEFT JOIN journal_lines jl ON jl.account_id = a.id '
            'GROUP BY a.id').fetchall()
        pl = reports.profit_and_loss(rows)
        self.assertAlmostEqual(pl['total_income'], 150000, places=2)
        bs = reports.balance_sheet(rows, pl['net_profit'])
        self.assertTrue(bs['balanced'])

    def test_missing_posting_account_is_created(self):
        """A database predating account 1400 must not silently drop the line."""
        import journal_post
        self.conn.execute("DELETE FROM accounts WHERE code = ?",
                          (posting.RETENTION_RECEIVABLE,))
        self.conn.commit()
        self._add_ra_bill('RA-1', 'Approved', 150000, 7500, 2000, 140500)
        journal_post.post_all(self.conn)
        self.assertIsNotNone(self.conn.execute(
            "SELECT 1 FROM accounts WHERE code = ?",
            (posting.RETENTION_RECEIVABLE,)).fetchone())
        entry = self.conn.execute(
            "SELECT * FROM journal_entries WHERE source = 'RABill'").fetchone()
        d, _c = self.conn.execute(
            'SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) '
            'FROM journal_lines WHERE journal_entry_id = ?',
            (entry['id'],)).fetchone()
        self.assertAlmostEqual(d, entry['total_debit'], places=2)


class TestSchema(unittest.TestCase):
    def test_init_db_is_idempotent_and_seeds_the_chart(self):
        import db
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.remove(path)
        orig = db.DB_PATH
        db.DB_PATH = path
        try:
            db.init_db()
            db.init_db()  # running twice must not raise or double-seed
            conn = db.get_conn()
            n = conn.execute('SELECT COUNT(*) FROM accounts').fetchone()[0]
            self.assertGreater(n, 0)
            codes = [r[0] for r in conn.execute('SELECT code FROM accounts')]
            self.assertEqual(len(codes), len(set(codes)), 'duplicate account codes')
            conn.close()
        finally:
            db.DB_PATH = orig
            try:
                os.remove(path)
            except OSError:
                pass


if __name__ == '__main__':
    unittest.main(verbosity=2)
