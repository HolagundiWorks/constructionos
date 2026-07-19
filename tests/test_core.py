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
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, 'construction_app'))

import ageing
import allocation
import analytics
import cashflow
import civil
import company
import estimate
import finance
import money
import numbering
import numwords
import posting
import procurement
import projman
import reports
import retention
import statutory
import subcontract
import variation
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


class TestVariations(unittest.TestCase):
    """Variations decide whether extra work gets paid for, so the money
    questions are: what is agreed but unasked-for, and what is still at risk."""

    ROWS = [
        {'status': 'Raised', 'qty': 10, 'rate': 500, 'amount': 5000},
        {'status': 'Approved', 'qty': 4, 'rate': 2500, 'amount': 10000},
        {'status': 'Approved', 'qty': 1, 'rate': 2000, 'amount': 2000},
        {'status': 'Billed', 'qty': 2, 'rate': 1500, 'amount': 3000},
        {'status': 'Rejected', 'qty': 100, 'rate': 900, 'amount': 90000},
    ]

    def test_amount_is_qty_times_rate(self):
        self.assertEqual(variation.variation_amount(4, 2500), 10000)
        self.assertEqual(variation.variation_amount(0, 2500), 0)

    def test_approved_unbilled_is_the_headline(self):
        s = variation.summarise(self.ROWS)
        self.assertEqual(s['approved_unbilled'], 12000)   # the money to chase

    def test_pending_and_billed_are_separated(self):
        s = variation.summarise(self.ROWS)
        self.assertEqual(s['pending_approval'], 5000)
        self.assertEqual(s['billed'], 3000)

    def test_rejected_never_counts_as_revenue(self):
        s = variation.summarise(self.ROWS)
        self.assertEqual(s['rejected'], 90000)
        # a refused claim must not inflate the countable total
        self.assertEqual(s['counted_total'], 5000 + 12000 + 3000)

    def test_amount_falls_back_to_qty_times_rate(self):
        s = variation.summarise([{'status': 'Approved', 'qty': 3, 'rate': 100}])
        self.assertEqual(s['approved_unbilled'], 300)

    def test_unknown_status_is_treated_as_raised_not_dropped(self):
        s = variation.summarise([{'status': 'Weird', 'amount': 700}])
        self.assertEqual(s['pending_approval'], 700)

    def test_empty_register(self):
        s = variation.summarise([])
        self.assertEqual(s['counted_total'], 0)
        self.assertEqual(s['approved_unbilled'], 0)

    def test_contract_impact_counts_only_agreed_work(self):
        impact = variation.contract_impact(1000000, self.ROWS)
        # approved (12000) + billed (3000); the raised 5000 is not agreed yet
        self.assertEqual(impact['agreed_variations'], 15000)
        self.assertEqual(impact['revised_value'], 1015000)
        self.assertEqual(impact['pending_variations'], 5000)
        self.assertEqual(impact['variation_pct'], 1.5)

    def test_contract_impact_with_no_original_value(self):
        impact = variation.contract_impact(0, self.ROWS)
        self.assertIsNone(impact['variation_pct'])   # would divide by zero
        self.assertEqual(impact['revised_value'], 15000)

    def test_next_var_no_uses_max_not_count(self):
        # deleting VO-2 must not let VO-3 be reissued
        self.assertEqual(variation.next_var_no(['VO-1', 'VO-3']), 'VO-4')
        self.assertEqual(variation.next_var_no([]), 'VO-1')
        self.assertEqual(variation.next_var_no(['junk', None, 'VO-2']), 'VO-3')


class TestAllocation(unittest.TestCase):
    """Allocation is what turns ageing from a FIFO guess into a reconciled
    position, so the tests focus on the guard rails and the hybrid fallback."""

    DOCS = [
        {'doc_type': 'Bill', 'doc_id': 1, 'date': '2026-01-10',
         'number': 'B-1', 'amount': 100000},
        {'doc_type': 'Bill', 'doc_id': 2, 'date': '2026-05-10',
         'number': 'B-2', 'amount': 50000},
    ]

    def test_open_documents_reduces_by_allocation(self):
        allocs = [{'doc_type': 'Bill', 'doc_id': 1, 'amount': 40000}]
        docs = allocation.open_documents(self.DOCS, allocs)
        self.assertEqual(docs[0]['open'], 60000)
        self.assertEqual(docs[1]['open'], 50000)

    def test_over_allocation_cannot_drive_open_negative(self):
        allocs = [{'doc_type': 'Bill', 'doc_id': 1, 'amount': 999999}]
        docs = allocation.open_documents(self.DOCS, allocs)
        self.assertEqual(docs[0]['open'], 0)

    def test_unallocated_amount(self):
        allocs = [{'amount': 30000}, {'amount': 20000}]
        self.assertEqual(allocation.unallocated_amount(100000, allocs), 50000)
        # never negative, even if data is inconsistent
        self.assertEqual(allocation.unallocated_amount(10000, allocs), 0)

    def test_validate_rejects_allocating_more_than_the_payment(self):
        ok, msg = allocation.validate(50000, [
            {'amount': 40000, 'open': 100000, 'number': 'B-1'},
            {'amount': 20000, 'open': 100000, 'number': 'B-2'}])
        self.assertFalse(ok)
        self.assertIn('50,000', msg)

    def test_validate_rejects_allocating_more_than_a_doc_is_worth(self):
        ok, msg = allocation.validate(100000, [
            {'amount': 80000, 'open': 60000, 'number': 'B-1'}])
        self.assertFalse(ok)
        self.assertIn('B-1', msg)

    def test_validate_rejects_negative(self):
        ok, _ = allocation.validate(100, [{'amount': -5, 'open': 100}])
        self.assertFalse(ok)

    def test_validate_accepts_a_clean_split(self):
        ok, msg = allocation.validate(100000, [
            {'amount': 60000, 'open': 100000, 'number': 'B-1'},
            {'amount': 40000, 'open': 50000, 'number': 'B-2'}])
        self.assertTrue(ok, msg)

    def test_suggest_fifo_fills_oldest_first(self):
        docs = allocation.open_documents(self.DOCS, [])
        proposal = allocation.suggest_fifo(docs, 120000)
        self.assertEqual(proposal[allocation.doc_key('Bill', 1)], 100000)
        self.assertEqual(proposal[allocation.doc_key('Bill', 2)], 20000)

    def test_suggest_fifo_stops_when_money_runs_out(self):
        docs = allocation.open_documents(self.DOCS, [])
        proposal = allocation.suggest_fifo(docs, 30000)
        self.assertEqual(proposal, {allocation.doc_key('Bill', 1): 30000})

    def test_explicit_allocation_beats_fifo_for_ageing(self):
        """A client paying the NEW bill while disputing the old one is exactly
        the case FIFO gets wrong."""
        allocs = [{'doc_type': 'Bill', 'doc_id': 2, 'amount': 50000}]
        items = allocation.open_items_for_ageing(self.DOCS, allocs)
        # the old bill is still fully open; the new one is settled
        self.assertEqual(items, [('2026-01-10', 100000.0)])

    def test_unallocated_receipts_still_apply_fifo(self):
        """A half-migrated ledger must still add up."""
        items = allocation.open_items_for_ageing(self.DOCS, [], 100000)
        self.assertEqual(items, [('2026-05-10', 50000.0)])

    def test_no_allocation_matches_the_old_behaviour_exactly(self):
        pairs = [(d['date'], d['amount']) for d in self.DOCS]
        self.assertEqual(
            allocation.open_items_for_ageing(self.DOCS, [], 60000),
            ageing.apply_receipts_fifo(pairs, 60000))

    def test_party_position_totals(self):
        allocs = [{'doc_type': 'Bill', 'doc_id': 1, 'amount': 100000}]
        pos = allocation.party_position(self.DOCS, allocs, as_on='2026-06-10')
        self.assertEqual(pos['billed'], 150000)
        self.assertEqual(pos['allocated'], 100000)
        self.assertEqual(pos['outstanding'], 50000)


class TestCashFlow(unittest.TestCase):
    """The forecast's job is to name the week the money runs out."""

    TODAY = '2026-07-06'          # a Monday

    def test_expected_date_applies_the_payment_lag(self):
        self.assertEqual(
            cashflow.expected_date('2026-07-06', 45, self.TODAY),
            date(2026, 8, 20))

    def test_an_overdue_bill_lands_today_not_in_the_past(self):
        # money you are still waiting for must stay in the forecast
        self.assertEqual(
            cashflow.expected_date('2026-01-01', 30, self.TODAY),
            date(2026, 7, 6))

    def test_bucket_start_snaps_to_monday_or_first(self):
        self.assertEqual(cashflow.bucket_start('2026-07-09'), date(2026, 7, 6))
        self.assertEqual(
            cashflow.bucket_start('2026-07-09', cashflow.BUCKET_MONTH),
            date(2026, 7, 1))

    def test_running_balance_and_first_negative(self):
        inflows = [('2026-07-27', 50000, 'client')]
        outflows = [('2026-07-13', 80000, 'vendor')]
        r = cashflow.forecast(inflows, outflows, opening_balance=10000,
                              today=self.TODAY, periods=4)
        self.assertEqual(r['buckets'][0]['balance'], 10000)
        self.assertEqual(r['buckets'][1]['balance'], -70000)   # 10k - 80k
        self.assertEqual(r['first_negative'], date(2026, 7, 13))
        self.assertEqual(r['closing_balance'], -20000)         # +50k later

    def test_no_shortfall_reports_none(self):
        r = cashflow.forecast([('2026-07-13', 90000, 'c')], [], 0,
                              self.TODAY, 4)
        self.assertIsNone(r['first_negative'])

    def test_money_beyond_the_horizon_is_not_lost(self):
        """Folding late items into the last bucket keeps totals reconciling."""
        r = cashflow.forecast([('2027-01-01', 25000, 'c')], [], 0,
                              self.TODAY, 4)
        self.assertEqual(r['total_in'], 25000)
        self.assertEqual(r['buckets'][-1]['in'], 25000)

    def test_wage_outflows_repeat_across_the_horizon(self):
        out = cashflow.wage_outflows(20000, self.TODAY, 4)
        self.assertEqual(len(out), 4)
        self.assertEqual(sum(a for _d, a, _l in out), 80000)

    def test_no_wage_bill_means_no_wage_rows(self):
        self.assertEqual(cashflow.wage_outflows(0, self.TODAY, 4), [])

    def test_monthly_buckets_scale_the_weekly_wage(self):
        out = cashflow.wage_outflows(10000, self.TODAY, 2, cashflow.BUCKET_MONTH)
        self.assertEqual(len(out), 2)
        self.assertAlmostEqual(out[0][1], round(10000 * 52 / 12.0, 2), places=2)


class TestProcurement(unittest.TestCase):
    """The three-way match exists to stop paying for goods that never came."""

    def test_rejected_material_never_enters_stock(self):
        self.assertEqual(procurement.accepted_qty(100, 15), 85)
        # rejecting more than arrived is nonsense, not a negative stock movement
        self.assertEqual(procurement.accepted_qty(10, 50), 0)

    def test_over_invoiced_is_flagged_and_quantified(self):
        m = procurement.three_way(ordered_value=100000, received_value=60000,
                                  invoiced_value=90000)
        self.assertEqual(m['status'], procurement.OVER_INVOICED)
        self.assertEqual(m['over_invoiced'], 30000)   # billed with no receipt
        self.assertFalse(m['ok'])

    def test_over_invoice_outranks_other_problems(self):
        """Worst problem wins: paying for phantom goods beats a short delivery."""
        m = procurement.three_way(100000, 60000, 90000)
        self.assertEqual(m['status'], procurement.OVER_INVOICED)

    def test_part_delivery_is_not_an_error(self):
        m = procurement.three_way(100000, 60000, 60000)
        self.assertEqual(m['status'], procurement.PART_RECEIVED)
        self.assertEqual(m['pending_receipt'], 40000)
        self.assertEqual(m['over_invoiced'], 0)

    def test_over_delivery_is_flagged(self):
        m = procurement.three_way(100000, 120000, 0)
        self.assertEqual(m['status'], procurement.OVER_RECEIVED)
        self.assertEqual(m['over_received'], 20000)

    def test_received_but_not_invoiced_is_fine(self):
        m = procurement.three_way(100000, 100000, 0)
        self.assertEqual(m['status'], procurement.NOT_INVOICED)
        self.assertTrue(m['ok'])
        self.assertEqual(m['pending_invoice'], 100000)

    def test_fully_matched(self):
        m = procurement.three_way(100000, 100000, 100000)
        self.assertEqual(m['status'], procurement.MATCHED)
        self.assertTrue(m['ok'])

    def test_tolerance_absorbs_small_differences(self):
        """Sand and aggregate never tally exactly; crying wolf gets ignored."""
        m = procurement.three_way(100000, 99950, 100000, tolerance=100)
        self.assertEqual(m['status'], procurement.MATCHED)

    def test_nothing_received_yet(self):
        m = procurement.three_way(100000, 0, 0)
        self.assertEqual(m['status'], procurement.NOT_RECEIVED)

    def test_summarise_totals_the_money_at_risk(self):
        matches = [procurement.three_way(100000, 60000, 90000),
                   procurement.three_way(50000, 50000, 50000),
                   procurement.three_way(80000, 40000, 40000)]
        s = procurement.summarise(matches)
        self.assertEqual(s['at_risk'], 30000)
        self.assertEqual(s['awaiting_delivery'], 80000)   # 40k + 40k
        self.assertEqual(s['problem_count'], 2)
        self.assertEqual(s['total_count'], 3)

    def test_doc_numbering_is_max_based(self):
        self.assertEqual(procurement.next_doc_no(['GRN-1', 'GRN-7'], 'GRN'),
                         'GRN-8')
        self.assertEqual(procurement.next_doc_no([], 'GRN'), 'GRN-1')


class TestRetention(unittest.TestCase):
    """Retention is money already earned that nobody chases, so the tests
    focus on when it becomes claimable."""

    def test_dlp_is_added_in_calendar_months(self):
        self.assertEqual(retention.release_due_date('2026-03-15', 12),
                         date(2027, 3, 15))
        self.assertEqual(retention.release_due_date('2026-01-31', 6),
                         date(2026, 7, 31))

    def test_short_month_clamps_instead_of_raising(self):
        # 31 Aug + 6 months has no 31st; the end of February is correct
        self.assertEqual(retention.release_due_date('2025-08-31', 6),
                         date(2026, 2, 28))

    def test_no_completion_date_gives_no_release_date(self):
        """Work that has not finished cannot have a release date, and
        inventing one would be worse than saying nothing."""
        self.assertIsNone(retention.release_due_date(None, 12))
        self.assertIsNone(retention.release_due_date('', 12))

    def test_outstanding_never_goes_negative(self):
        self.assertEqual(retention.outstanding(5000, 1000), 4000)
        self.assertEqual(retention.outstanding(5000, 9000), 0)

    def test_is_due_only_after_the_date(self):
        self.assertTrue(retention.is_due('2026-01-01', '2026-07-19'))
        self.assertFalse(retention.is_due('2027-01-01', '2026-07-19'))
        self.assertFalse(retention.is_due(None, '2026-07-19'))

    def test_line_status(self):
        self.assertEqual(
            retention.line_status(5000, 0, '2026-01-01', '2026-07-19'),
            'DUE for release')
        self.assertEqual(
            retention.line_status(5000, 0, '2027-01-01', '2026-07-19'), 'Held')
        self.assertEqual(retention.line_status(5000, 5000, '2026-01-01'),
                         'Released')
        self.assertEqual(retention.line_status(5000, 0, None),
                         'Held (no completion date)')

    def test_summarise_reports_what_is_claimable_now(self):
        lines = [
            {'withheld': 5000, 'released': 0, 'due_date': '2026-01-01'},
            {'withheld': 3000, 'released': 3000, 'due_date': '2026-01-01'},
            {'withheld': 2000, 'released': 0, 'due_date': '2027-01-01'},
        ]
        s = retention.summarise(lines, as_on='2026-07-19')
        self.assertEqual(s['withheld'], 10000)
        self.assertEqual(s['released'], 3000)
        self.assertEqual(s['outstanding'], 7000)
        self.assertEqual(s['due_now'], 5000)      # only the overdue, unreleased
        self.assertEqual(s['max_overdue_days'], 199)

    def test_upcoming_finds_releases_before_they_land(self):
        lines = [{'withheld': 5000, 'released': 0, 'due_date': '2026-08-01'},
                 {'withheld': 5000, 'released': 0, 'due_date': '2027-01-01'},
                 {'withheld': 5000, 'released': 5000, 'due_date': '2026-08-01'}]
        soon = retention.upcoming(lines, 60, as_on='2026-07-19')
        self.assertEqual(len(soon), 1)            # settled line excluded


class TestCompanyRegistry(unittest.TestCase):
    """Multi-firm / multi-year company file registry."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.reg = os.path.join(self.dir, 'companies.json')

    def test_missing_registry_is_empty_not_an_error(self):
        self.assertEqual(company.load(self.reg), {'active': None, 'files': []})

    def test_corrupt_registry_degrades_gracefully(self):
        with open(self.reg, 'w', encoding='utf-8') as fh:
            fh.write('{ not json at all')
        # must never block the app from starting
        self.assertEqual(company.load(self.reg), {'active': None, 'files': []})

    def test_round_trip(self):
        data = company.load(self.reg)
        company.add(data, 'Sharma Constructions', os.path.join(self.dir, 'a.db'),
                    make_active=True)
        self.assertTrue(company.save(data, self.reg))
        back = company.load(self.reg)
        self.assertEqual(len(back['files']), 1)
        self.assertTrue(back['active'].endswith('a.db'))

    def test_re_adding_a_path_renames_instead_of_duplicating(self):
        data = company.load(self.reg)
        p = os.path.join(self.dir, 'a.db')
        company.add(data, 'Old Name', p)
        company.add(data, 'New Name', p)
        self.assertEqual(len(data['files']), 1)
        self.assertEqual(company.find(data, p)['name'], 'New Name')

    def test_remove_clears_active_but_not_the_file(self):
        data = company.load(self.reg)
        p = os.path.join(self.dir, 'a.db')
        open(p, 'w').close()
        company.add(data, 'A', p, make_active=True)
        company.remove(data, p)
        self.assertEqual(data['files'], [])
        self.assertIsNone(data['active'])
        self.assertTrue(os.path.exists(p), 'removing from the list must not delete data')

    def test_active_path_ignores_a_missing_file(self):
        data = company.load(self.reg)
        company.add(data, 'Gone', os.path.join(self.dir, 'nope.db'), make_active=True)
        self.assertIsNone(company.active_path(data))

    def test_safe_filename_keeps_financial_year_hyphens(self):
        self.assertEqual(company.safe_filename('Sharma Constructions 25-26'),
                         'sharma_constructions_25-26.db')
        self.assertEqual(company.safe_filename('A/B: C'), 'a_b_c.db')
        self.assertEqual(company.safe_filename(''), 'company.db')

    def test_suggest_path_does_not_overwrite(self):
        first = company.suggest_path(self.dir, 'Acme')
        open(first, 'w').close()
        second = company.suggest_path(self.dir, 'Acme')
        self.assertNotEqual(first, second)

    def test_next_year_label(self):
        self.assertEqual(company.next_year_label('2025-26'), '2026-27')
        self.assertEqual(company.next_year_label('2099-00'), '2100-01')
        self.assertEqual(company.next_year_label('junk'), '')


class TestCarryForward(unittest.TestCase):
    """Starting a new year must copy the setup and none of the history."""

    def setUp(self):
        import db
        self.db = db
        self.dir = tempfile.mkdtemp()
        self._orig = db.DB_PATH
        self.src_path = os.path.join(self.dir, 'src.db')
        self.dst_path = os.path.join(self.dir, 'dst.db')

        db.DB_PATH = self.src_path
        db.init_db()
        self.src = db.get_conn()
        self.src.execute("INSERT INTO clients (name) VALUES ('PWD Division')")
        self.src.execute("INSERT INTO sites (name) VALUES ('Site A')")
        self.src.execute("INSERT INTO materials (name, unit) VALUES ('Cement','bag')")
        self.src.execute("INSERT INTO accounts (code, name, type) "
                         "VALUES ('9001','Custom Head','Expense')")
        self.src.execute("INSERT INTO app_settings (key, value) "
                         "VALUES ('company_name','Sharma')")
        self.src.execute("INSERT INTO payments (pay_date, direction, party_type, "
                         "amount) VALUES ('2026-01-01','Receipt','Client',5000)")
        self.src.commit()
        self.seeded_accounts = self.src.execute(
            'SELECT COUNT(*) FROM accounts').fetchone()[0]

        db.DB_PATH = self.dst_path
        db.init_db()
        self.dst = db.get_conn()

    def tearDown(self):
        self.src.close()
        self.dst.close()
        self.db.DB_PATH = self._orig

    def test_masters_are_copied(self):
        company.carry_forward(self.src, self.dst)
        self.assertEqual(self.dst.execute('SELECT COUNT(*) FROM clients').fetchone()[0], 1)
        self.assertEqual(self.dst.execute('SELECT COUNT(*) FROM sites').fetchone()[0], 1)
        self.assertEqual(
            self.dst.execute("SELECT value FROM app_settings WHERE key='company_name'")
            .fetchone()[0], 'Sharma')

    def test_custom_accounts_survive_and_the_chart_is_not_duplicated(self):
        company.carry_forward(self.src, self.dst)
        self.assertIsNotNone(
            self.dst.execute("SELECT 1 FROM accounts WHERE code='9001'").fetchone())
        self.assertEqual(
            self.dst.execute('SELECT COUNT(*) FROM accounts').fetchone()[0],
            self.seeded_accounts,
            'seeded chart was duplicated instead of replaced')

    def test_transactions_do_not_leak_into_the_new_year(self):
        company.carry_forward(self.src, self.dst)
        for table in ('payments', 'bills', 'ra_bills', 'journal_entries'):
            self.assertEqual(
                self.dst.execute('SELECT COUNT(*) FROM {}'.format(table)).fetchone()[0],
                0, '{} leaked into the new company file'.format(table))

    def test_unknown_table_is_skipped_not_fatal(self):
        copied = company.carry_forward(self.src, self.dst,
                                       tables=['clients', 'no_such_table'])
        self.assertEqual(copied.get('clients'), 1)
        self.assertNotIn('no_such_table', copied)


class TestSchemaMigration(unittest.TestCase):
    """Opening an OLDER data file must work.

    Every other test starts from a fresh database, which is exactly why this
    class exists: a released build once could not open any pre-existing file
    because an index referenced a column that a migration had not yet added,
    and the failing index aborted the script before the migration ran.
    """

    def setUp(self):
        import db
        self.db = db
        fd, self.path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.remove(self.path)
        self._orig = db.DB_PATH
        db.DB_PATH = self.path

    def tearDown(self):
        self.db.DB_PATH = self._orig
        try:
            os.remove(self.path)
        except OSError:
            pass

    def _make_legacy_file(self):
        """A database from before timeline_tasks.project_id existed."""
        import sqlite3 as sq
        conn = sq.connect(self.path)
        conn.execute('CREATE TABLE timeline_tasks ('
                     'id INTEGER PRIMARY KEY AUTOINCREMENT, '
                     'site_id INTEGER, task_name TEXT, start_date TEXT, '
                     'end_date TEXT, duration_days REAL DEFAULT 0, '
                     'status TEXT, dependency TEXT)')
        conn.execute("INSERT INTO timeline_tasks (task_name) VALUES ('Old task')")
        conn.commit()
        conn.close()

    def test_init_db_opens_a_legacy_file(self):
        self._make_legacy_file()
        self.db.init_db()          # must not raise "no such column: project_id"
        conn = self.db.get_conn()
        try:
            cols = [r['name'] for r in conn.execute(
                'PRAGMA table_info(timeline_tasks)')]
            self.assertIn('project_id', cols, 'migration did not run')
            # the user's existing row must survive the migration
            self.assertEqual(
                conn.execute('SELECT COUNT(*) FROM timeline_tasks').fetchone()[0], 1)
        finally:
            conn.close()

    def test_indexes_exist_after_migrating_a_legacy_file(self):
        self._make_legacy_file()
        self.db.init_db()
        conn = self.db.get_conn()
        try:
            idx = [r['name'] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'")]
            self.assertIn('idx_timeline_project', idx,
                          'index on the migrated column was never created')
        finally:
            conn.close()

    def test_init_db_is_repeatable_on_a_legacy_file(self):
        self._make_legacy_file()
        self.db.init_db()
        self.db.init_db()          # reopening the app must stay clean
        conn = self.db.get_conn()
        try:
            cols = [r['name'] for r in conn.execute(
                'PRAGMA table_info(timeline_tasks)')]
            self.assertEqual(cols.count('project_id'), 1)
        finally:
            conn.close()


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
