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

import ast
import glob
import os
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, 'construction_app'))
# Build-only tooling (e.g. the logo tinter) lives outside the shipped package.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, 'tools'))

import advisory
import refdata
import scheduler
import takeoff
import ageing
import allocation
import approval
import analytics
import assistant
import bidding
import cashflow
import civil
import closeout
import compliance
import cpm
import einvoice
import company
import estimate
import finance
import hse
import isodate
import mb
import money
import muster
import numbering
import numwords
import planning
import plant
import posting
import procurement
import programme
import projman
import projectcost
import quality
import rateanalysis
import reports
import retention
import sourcing
import statutory
import subcontract
import variation
import wages
import earnedvalue
import risk
import risk_store
import forecast
import risk_detect
import narrative
import review_pack


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


class TestIsoDate(unittest.TestCase):
    """The shared tolerant date parser (``isodate.parse``).

    Ten pure modules used to carry their own copy of this and had drifted
    apart; these tests pin the behaviour they now all share.
    """

    def test_parses_a_plain_iso_date(self):
        self.assertEqual(isodate.parse('2026-01-01'), date(2026, 1, 1))

    def test_blank_and_garbage_give_none_rather_than_raising(self):
        for bad in (None, '', 0, 'garbage', '2026-13-01', b'2026-01-01'):
            self.assertIsNone(isodate.parse(bad), repr(bad))

    def test_a_date_passes_through_unchanged(self):
        self.assertEqual(isodate.parse(date(2026, 1, 1)), date(2026, 1, 1))

    def test_a_datetime_is_narrowed_to_its_date(self):
        # The old per-module copies returned the datetime untouched, and the
        # caller's next comparison against a date raised TypeError.
        self.assertEqual(isodate.parse(datetime(2026, 1, 1, 10, 30)),
                         date(2026, 1, 1))

    def test_whitespace_is_always_stripped(self):
        # muster's copy stripped it; the others didn't. Now everyone does, in
        # both modes.
        self.assertEqual(isodate.parse('  2026-01-01  '), date(2026, 1, 1))
        self.assertEqual(isodate.parse('  2026-01-01  ', strict=True),
                         date(2026, 1, 1))

    def test_a_time_part_is_tolerated_by_default_but_refused_when_strict(self):
        # The one genuine policy difference, now an explicit flag rather than
        # per-module drift.
        self.assertEqual(isodate.parse('2026-01-01T10:30:00'), date(2026, 1, 1))
        self.assertIsNone(isodate.parse('2026-01-01T10:30:00', strict=True))

    def test_the_nine_lenient_modules_parse_dates_identically(self):
        parsers = [ageing._parse, cashflow._parse, closeout._parse,
                   compliance._parse, hse._parse, plant._parse,
                   programme._parse, quality._parse, retention._parse]
        for value in ('2026-01-01', '  2026-01-01  ', '2026-01-01T10:30:00',
                      datetime(2026, 1, 1, 10, 30), date(2026, 1, 1),
                      None, '', 'garbage'):
            expected = isodate.parse(value)
            for fn in parsers:
                self.assertEqual(fn(value), expected,
                                 '{} on {!r}'.format(fn.__module__, value))

    def test_muster_stays_strict_about_a_time_part(self):
        # muster is the deliberate exception: keyed by day, it refuses a value
        # carrying a time rather than truncating it. Everything else matches.
        self.assertIsNone(muster._d('2026-01-01T10:30:00'))
        for value in ('2026-01-01', '  2026-01-01  ',
                      datetime(2026, 1, 1, 10, 30), date(2026, 1, 1),
                      None, '', 'garbage'):
            self.assertEqual(muster._d(value), isodate.parse(value),
                             'muster._d on {!r}'.format(value))

    def test_a_datetime_as_on_does_not_break_date_comparisons(self):
        # The concrete failure the drift caused, at two of the call sites.
        permit = {'status': 'Open', 'valid_from': '2026-01-01',
                  'valid_to': '2026-06-01'}
        valid, _ = hse.permit_valid(permit, as_on=datetime(2026, 3, 1, 9, 0))
        self.assertTrue(valid)
        self.assertTrue(closeout.is_overdue({'status': 'Open',
                                             'target_date': '2026-01-01'},
                                            as_on=datetime(2026, 3, 1, 9, 0)))


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


class TestEarnedValue(unittest.TestCase):
    """EVM indices and forecast. The zero-denominator guards earn the module —
    a project with no cost booked yet must not divide by zero."""

    def test_over_budget_and_behind_schedule_reads(self):
        # BAC 100, planned 50 by now, earned only 40, cost already 50:
        # behind schedule (EV<PV) and over budget (AC>EV).
        e = earnedvalue.earned_value(bac=100, pv=50, ac=50, ev=40)
        self.assertEqual(e['sv'], -10.0)          # EV - PV
        self.assertEqual(e['cv'], -10.0)          # EV - AC
        self.assertEqual(e['spi'], 0.8)           # 40/50
        self.assertEqual(e['cpi'], 0.8)           # 40/50
        self.assertFalse(e['on_budget'])
        self.assertFalse(e['on_schedule'])

    def test_eac_by_cpi_projects_the_overrun(self):
        # CPI 0.8 → EAC = BAC/CPI = 125, so VAC = -25 (a forecast overspend).
        e = earnedvalue.earned_value(bac=100, pv=50, ac=50, ev=40)
        self.assertEqual(e['eac']['cpi'], 125.0)
        self.assertEqual(e['eac']['default'], 125.0)
        self.assertEqual(e['vac'], -25.0)
        self.assertEqual(e['etc'], 75.0)          # EAC - AC

    def test_indices_are_none_not_infinity_when_denominator_zero(self):
        e = earnedvalue.earned_value(bac=100, pv=0, ac=0, ev=0)
        self.assertIsNone(e['spi'])               # PV = 0
        self.assertIsNone(e['cpi'])               # AC = 0
        self.assertIsNone(e['on_budget'])
        # EAC still degrades gracefully to the budget method (BAC - EV added).
        self.assertEqual(e['eac']['default'], e['eac']['budget'])

    def test_percent_complete_is_value_over_budget(self):
        e = earnedvalue.earned_value(bac=200, pv=100, ac=90, ev=100)
        self.assertEqual(e['percent_complete'], 50.0)   # 100/200
        self.assertEqual(e['percent_spent'], 45.0)      # 90/200

    def test_ev_and_pv_derivations(self):
        self.assertEqual(earnedvalue.ev_from_progress(1000, 25), 250.0)
        self.assertEqual(earnedvalue.pv_from_planned(1000, 40), 400.0)

    def test_tcpi_flags_when_remaining_work_must_beat_budget(self):
        # BAC 100, EV 40, AC 50 → TCPI = (100-40)/(100-50) = 1.2 > 1: hard.
        self.assertEqual(earnedvalue.tcpi(100, 40, 50), 1.2)

    def test_portfolio_cpi_is_value_weighted(self):
        a = earnedvalue.earned_value(bac=100, pv=90, ac=100, ev=90)   # cpi 0.9
        b = earnedvalue.earned_value(bac=10, pv=10, ac=5, ev=10)      # cpi 2.0
        p = earnedvalue.portfolio([('A', a), ('B', b)])
        # Value-weighted: (90+10)/(100+5) ≈ 0.952, not the naive mean 1.45.
        self.assertEqual(p['cpi'], round(100 / 105, 3))
        self.assertEqual(p['worst_cpi'], 'A')
        self.assertIn('A', p['over_cost_names'])


class TestRisk(unittest.TestCase):
    """Likelihood x impact scoring, clamping, exposure and ranking."""

    def test_score_is_the_product(self):
        self.assertEqual(risk.score(4, 5), 20)

    def test_out_of_range_levels_are_clamped_not_trusted(self):
        # A mistyped 9 must not invent a score of 45.
        self.assertEqual(risk.score(9, 9), 25)
        self.assertEqual(risk.score(0, 3), 3)     # 0 floors to 1
        self.assertEqual(risk.score('x', 4), 4)   # garbage floors to 1

    def test_bands_cover_the_whole_range(self):
        self.assertEqual(risk.band(3), risk.LOW)
        self.assertEqual(risk.band(6), risk.MEDIUM)
        self.assertEqual(risk.band(12), risk.HIGH)
        self.assertEqual(risk.band(20), risk.CRITICAL)

    def test_a_severe_top_row_risk_is_never_merely_low(self):
        self.assertEqual(risk.assess(1, 5)['band'], risk.MEDIUM)  # 1x5 = 5
        self.assertEqual(risk.assess(5, 5)['band'], risk.CRITICAL)

    def test_expected_exposure_is_probability_weighted(self):
        # likelihood 5 → p 0.9; 0.9 x 200000 = 180000.
        self.assertEqual(risk.expected_exposure(5, 200000), 180000.0)

    def test_mitigation_benefit_is_never_negative(self):
        a = risk.assess(5, 5, residual_likelihood=2, residual_impact=3)
        self.assertEqual(a['residual']['score'], 6)
        self.assertEqual(a['mitigation_benefit'], 25 - 6)
        # A control that 'raises' the score is a data error, floored to 0.
        worse = risk.assess(2, 2, residual_likelihood=5, residual_impact=5)
        self.assertEqual(worse['mitigation_benefit'], 0)

    def test_rank_puts_the_worst_first(self):
        rs = [risk.assess(1, 2), risk.assess(5, 5), risk.assess(3, 3)]
        ranked = risk.rank(rs)
        self.assertEqual(ranked[0]['score'], 25)
        self.assertEqual(ranked[-1]['score'], 2)

    def test_register_summary_counts_and_sizes(self):
        rs = [risk.assess(5, 5, value=100000),   # critical
              risk.assess(4, 3, value=50000),    # high (12)
              risk.assess(1, 2)]                  # low
        s = risk.register_summary(rs, top_n=2)
        self.assertEqual(s['count'], 3)
        self.assertEqual(s['by_band'][risk.CRITICAL], 1)
        self.assertEqual(s['needs_action'], 2)    # critical + high
        self.assertEqual(len(s['top']), 2)
        self.assertGreater(s['total_expected_exposure'], 0)


class TestRiskStore(unittest.TestCase):
    """The risk register persistence, against a real temporary SQLite database
    (the same harness the posting engine uses). Proves the derive-on-save rule
    and that a project delete cascades to its risks."""

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
        self.conn.execute("INSERT INTO projects (name) VALUES ('Ward-7 Road')")
        self.conn.commit()
        self.project_id = 1

    def tearDown(self):
        self.conn.close()
        self.db.DB_PATH = self._orig
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_add_derives_score_band_and_exposure_on_save(self):
        rid = risk_store.add(
            self.conn, project_id=self.project_id, category='cost',
            title='Steel price spike', likelihood=4, impact=5,
            impact_value=200000)
        row = risk_store.get(self.conn, rid)
        self.assertEqual(row['score'], 20)              # 4 x 5
        self.assertEqual(row['band'], risk.CRITICAL)
        self.assertEqual(row['expected_exposure'], 140000.0)  # 0.7 x 200000
        self.assertEqual(row['source'], 'manual')       # defaulted
        self.assertTrue(row['created_date'])            # stamped today

    def test_update_re_derives_from_the_merged_row(self):
        rid = risk_store.add(self.conn, project_id=self.project_id,
                             likelihood=2, impact=2)
        self.assertEqual(risk_store.get(self.conn, rid)['band'], risk.LOW)
        risk_store.update(self.conn, rid, impact=5)     # only impact changes
        row = risk_store.get(self.conn, rid)
        self.assertEqual(row['score'], 10)              # 2 x 5, re-derived
        self.assertEqual(row['band'], risk.HIGH)

    def test_set_status_stamps_who_decided(self):
        rid = risk_store.add(self.conn, project_id=self.project_id,
                             likelihood=3, impact=3)
        risk_store.set_status(self.conn, rid, 'Accepted', decided_by='PM')
        row = risk_store.get(self.conn, rid)
        self.assertEqual(row['status'], 'Accepted')
        self.assertEqual(row['decided_by'], 'PM')
        self.assertTrue(row['decided_date'])

    def test_list_is_worst_first_and_filters(self):
        risk_store.add(self.conn, project_id=self.project_id,
                       title='small', likelihood=1, impact=2)
        risk_store.add(self.conn, project_id=self.project_id,
                       title='big', likelihood=5, impact=5)
        rows = risk_store.list_risks(self.conn, project_id=self.project_id)
        self.assertEqual(rows[0]['title'], 'big')       # highest score first
        opens = risk_store.list_risks(self.conn, status='Open')
        self.assertEqual(len(opens), 2)

    def test_summary_rolls_up_from_stored_rows(self):
        risk_store.add(self.conn, project_id=self.project_id,
                       likelihood=5, impact=5, impact_value=100000)  # critical
        risk_store.add(self.conn, project_id=self.project_id,
                       likelihood=4, impact=3, impact_value=50000)   # high (12)
        risk_store.add(self.conn, project_id=self.project_id,
                       likelihood=1, impact=2)                        # low
        s = risk_store.summary(self.conn, project_id=self.project_id)
        self.assertEqual(s['count'], 3)
        self.assertEqual(s['needs_action'], 2)          # critical + high
        self.assertGreater(s['total_expected_exposure'], 0)

    def test_summary_ignores_a_hand_edited_score(self):
        # Even if someone tampers with the stored derived score, the roll-up
        # re-assesses from the raw levels — so it stays honest.
        rid = risk_store.add(self.conn, project_id=self.project_id,
                             likelihood=5, impact=5)
        self.conn.execute("UPDATE risks SET score = 1, band = 'Low' "
                          "WHERE id = ?", (rid,))
        self.conn.commit()
        s = risk_store.summary(self.conn, project_id=self.project_id)
        self.assertEqual(s['by_band'][risk.CRITICAL], 1)  # re-derived, not 'Low'

    def test_deleting_a_project_cascades_to_its_risks(self):
        risk_store.add(self.conn, project_id=self.project_id,
                       likelihood=3, impact=3)
        self.conn.execute("DELETE FROM projects WHERE id = ?",
                          (self.project_id,))
        self.conn.commit()
        self.assertEqual(len(risk_store.list_risks(self.conn)), 0)


class TestForecast(unittest.TestCase):
    """Trend projection — honest bands and sample-driven confidence."""

    def test_falling_series_projects_downward(self):
        # A noisy downward series: still trends down, and the scatter gives a
        # real (non-zero) band — unlike a perfect line, which collapses it.
        p = forecast.project([70, 64, 62, 55, 49], periods_ahead=1)
        self.assertLess(p['value'], 49)           # trend continues down
        self.assertLess(p['slope'], 0)
        self.assertLess(p['low'], p['high'])      # a real band from the scatter

    def test_perfect_line_has_a_tight_band(self):
        p = forecast.project([10, 20, 30, 40], 1)
        self.assertAlmostEqual(p['value'], 50, places=6)
        self.assertAlmostEqual(p['low'], p['high'], places=6)  # RMSE ~ 0

    def test_confidence_grows_with_history(self):
        self.assertEqual(forecast.confidence_for(3), forecast.LOW)
        self.assertEqual(forecast.confidence_for(6), forecast.MEDIUM)
        self.assertEqual(forecast.confidence_for(10), forecast.HIGH)

    def test_too_few_points_is_none_not_a_guess(self):
        self.assertIsNone(forecast.project([42], 1))
        self.assertIsNone(forecast.linear_trend([]))

    def test_direction_words(self):
        self.assertEqual(forecast.direction([1, 2, 3]), 'rising')
        self.assertEqual(forecast.direction([3, 2, 1]), 'falling')
        self.assertEqual(forecast.direction([5, 5, 5]), 'flat')

    def test_schedule_forecast_stretches_when_behind(self):
        f = forecast.schedule_forecast(baseline_duration=100, spi=0.8)
        self.assertEqual(f['forecast_duration'], 125.0)
        self.assertEqual(f['slip'], 25.0)
        self.assertIsNone(forecast.schedule_forecast(100, None))


class TestRiskDetect(unittest.TestCase):
    """Snapshot → scored, ranked, register-ready risks."""

    def test_detects_a_loss_making_project_as_a_critical_cost_risk(self):
        rs = risk_detect.detect({'projects_at_loss': 1,
                                 'projects_worst_margin': -800000})
        self.assertTrue(rs)
        top = rs[0]
        self.assertEqual(top['category'], risk_detect.COST)
        self.assertEqual(top['source'], 'ai')
        self.assertEqual(top['band'], risk.CRITICAL)   # likelihood 5, big value
        self.assertIn('basis', top)                    # never a bare flag

    def test_quiet_snapshot_flags_nothing(self):
        self.assertEqual(risk_detect.detect({'cash': 50000}), [])

    def test_worst_is_ranked_first(self):
        rs = risk_detect.detect({
            'rfis_open': 2, 'rfis_oldest_days': 10,          # small external
            'projects_at_loss': 1, 'projects_worst_margin': -900000,  # critical
        })
        self.assertEqual(rs[0]['category'], risk_detect.COST)

    def test_programme_delay_uses_ld_for_impact(self):
        rs = risk_detect.detect({'programme_delay_days': 30,
                                 'programme_ld': 600000})
        sched = [r for r in rs if r['category'] == risk_detect.SCHEDULE]
        self.assertTrue(sched)
        self.assertEqual(sched[0]['value'], 600000)

    def test_summary_matches_the_register_shape(self):
        s = risk_detect.summary({'projects_at_loss': 1,
                                 'projects_worst_margin': -600000,
                                 'compliance_overdue': 2})
        self.assertGreaterEqual(s['count'], 2)
        self.assertIn('by_band', s)
        self.assertGreaterEqual(s['needs_action'], 1)


class TestNarrative(unittest.TestCase):
    """Deterministic narration — every sentence over a real number."""

    def test_kpi_briefing_leads_with_cash(self):
        lines = narrative.kpi_briefing({'cash': 125000, 'receivable': 300000})
        self.assertTrue(any('1,25,000' in ln or '125,000' in ln
                            for ln in lines))

    def test_negative_cash_is_called_out(self):
        lines = narrative.kpi_briefing({'cash': -5000})
        self.assertTrue(any('negative' in ln.lower() for ln in lines))

    def test_risk_briefing_is_empty_message_when_clean(self):
        txt = narrative.risk_briefing({'cash': 10000})
        self.assertIn('No risks', txt)

    def test_risk_briefing_lists_the_top_risks(self):
        txt = narrative.risk_briefing({'projects_at_loss': 1,
                                       'projects_worst_margin': -700000})
        self.assertIn('exposure', txt.lower())
        self.assertIn('•', txt)


class TestReviewPack(unittest.TestCase):
    """The assembled review pack and portfolio roll-up."""

    def test_build_assembles_every_section(self):
        snap = {'cash': 200000, 'receivable_90plus': 150000,
                'projects_at_loss': 1, 'projects_worst_margin': -400000}
        pack = review_pack.build(snap, generated='2026-07-21')
        self.assertEqual(pack['generated'], '2026-07-21')
        for key in ('kpis', 'advisories', 'risks', 'narrative'):
            self.assertIn(key, pack)
        self.assertIn('cards', pack['advisories'])
        self.assertGreaterEqual(pack['risks']['count'], 1)

    def test_build_includes_optional_evm_and_forecast(self):
        evm = earnedvalue.earned_value(bac=100, pv=60, ac=55, ev=50)
        pack = review_pack.build({'cash': 1000}, evm=evm,
                                 ppc_series=[80, 75, 70, 65])
        self.assertIn('evm', pack)
        self.assertIn('ppc_forecast', pack)
        self.assertIsNotNone(pack['ppc_forecast'])

    def test_portfolio_pools_risk_and_points_at_the_worst(self):
        a = {'name': 'A', 'snapshot': {'projects_at_loss': 1,
                                       'projects_worst_margin': -900000},
             'evm': earnedvalue.earned_value(bac=100, pv=90, ac=100, ev=90)}
        b = {'name': 'B', 'snapshot': {'cash': 50000},
             'evm': earnedvalue.earned_value(bac=10, pv=10, ac=5, ev=10)}
        roll = review_pack.portfolio([a, b])
        self.assertEqual(roll['projects'], 2)
        self.assertGreaterEqual(roll['risk_summary']['count'], 1)
        self.assertEqual(roll['evm']['worst_cpi'], 'A')


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


class TestQualityGate(unittest.TestCase):
    """The gate answers 'may the work proceed', which is not the same
    question as 'did anything fail'."""

    def _item(self, check_type, result):
        return {'check_type': check_type, 'result': result}

    def test_unanswered_hold_point_blocks_even_with_no_failure(self):
        items = [self._item(quality.HOLD, quality.PENDING),
                 self._item(quality.RECORD, quality.PASS)]
        allowed, reason = quality.may_proceed(items)
        self.assertFalse(allowed)
        self.assertIn('not yet signed off', reason)

    def test_failed_hold_point_blocks_with_a_different_reason(self):
        allowed, reason = quality.may_proceed(
            [self._item(quality.HOLD, quality.FAIL)])
        self.assertFalse(allowed)
        self.assertIn('FAILED', reason)

    def test_all_holds_cleared_allows_work(self):
        items = [self._item(quality.HOLD, quality.PASS),
                 self._item(quality.HOLD, quality.NA)]
        allowed, _ = quality.may_proceed(items)
        self.assertTrue(allowed)

    def test_witness_point_does_not_block(self):
        """A contractor cannot be held hostage by an engineer who did not attend."""
        allowed, _ = quality.may_proceed(
            [self._item(quality.WITNESS, quality.PENDING),
             self._item(quality.HOLD, quality.PASS)])
        self.assertTrue(allowed)

    def test_blank_checklist_is_pending_not_a_pass(self):
        """Unrecorded is exactly how an inspection gets skipped."""
        self.assertEqual(quality.inspection_result([]), quality.PENDING)

    def test_result_is_pending_until_every_hold_and_witness_answered(self):
        items = [self._item(quality.HOLD, quality.PASS),
                 self._item(quality.WITNESS, quality.PENDING)]
        self.assertEqual(quality.inspection_result(items), quality.PENDING)

    def test_any_failure_fails_the_inspection(self):
        items = [self._item(quality.HOLD, quality.PASS),
                 self._item(quality.RECORD, quality.FAIL)]
        self.assertEqual(quality.inspection_result(items), quality.FAIL)

    def test_all_answered_passes(self):
        items = [self._item(quality.HOLD, quality.PASS),
                 self._item(quality.WITNESS, quality.NA),
                 self._item(quality.RECORD, quality.PENDING)]
        self.assertEqual(quality.inspection_result(items), quality.PASS)

    def test_first_time_pass_rate_excludes_reinspections(self):
        rows = [{'result': quality.PASS, 'reinspection': 0},
                {'result': quality.PASS, 'reinspection': 1},   # a repeat
                {'result': quality.FAIL, 'reinspection': 0},
                {'result': quality.PENDING, 'reinspection': 0}]  # not counted
        self.assertEqual(quality.first_time_pass_rate(rows), 33.33)

    def test_first_time_pass_rate_is_none_with_nothing_inspected(self):
        self.assertIsNone(quality.first_time_pass_rate([]))

    def test_ncr_age_and_summary(self):
        ncrs = [{'status': 'Open', 'raised_date': '2026-01-01'},
                {'status': 'Open', 'raised_date': '2026-07-01'},
                {'status': 'Closed', 'raised_date': '2026-01-01'}]
        s = quality.ncr_summary(ncrs, as_on='2026-07-20')
        self.assertEqual(s['open'], 2)
        self.assertEqual(s['closed'], 1)
        self.assertEqual(s['oldest_open_days'], 200)
        self.assertAlmostEqual(s['closure_rate'], 33.33, places=1)

    def test_closed_ncr_age_stops_at_closure(self):
        self.assertEqual(
            quality.ncr_age_days('2026-01-01', '2026-01-11', '2026-07-20'), 10)


class TestPlanning(unittest.TestCase):
    """PPC and CVR both exist to show trouble while it can still be fixed."""

    WEEK = [{'status': 'Done'}, {'status': 'Done'},
            {'status': 'Not done', 'reason': 'Material not available'},
            {'status': 'Not done', 'reason': 'Material not available'},
            {'status': 'Not done', 'reason': 'Labour short'}]

    def test_ppc_counts_only_finished_work(self):
        self.assertEqual(planning.ppc(self.WEEK), 40.0)

    def test_partial_work_is_a_miss_not_progress(self):
        """Counting part-done as progress is how a programme slips quietly."""
        self.assertEqual(planning.ppc([{'status': 'Partial'},
                                       {'status': 'Done'}]), 50.0)

    def test_ppc_is_none_when_nothing_was_promised(self):
        self.assertIsNone(planning.ppc([]))

    def test_reasons_are_ranked_worst_first(self):
        reasons = planning.reasons_for_misses(self.WEEK)
        self.assertEqual(reasons[0], ('Material not available', 2))
        self.assertEqual(reasons[1], ('Labour short', 1))

    def test_missing_reason_is_named_not_dropped(self):
        reasons = planning.reasons_for_misses([{'status': 'Not done'}])
        self.assertEqual(reasons, [('Not stated', 1)])

    def test_ppc_trend_averages_only_scored_weeks(self):
        t = planning.ppc_trend({'2026-07-06': [{'status': 'Done'}],
                                '2026-07-13': [{'status': 'Not done'}],
                                '2026-07-20': []})
        self.assertEqual(t['average'], 50.0)     # the empty week is ignored
        self.assertEqual(len(t['weeks']), 3)

    def test_cvr_margins_and_loss_detection(self):
        result = planning.cvr({'Material': (100000, 90000),
                               'Labour': (50000, 70000)})
        self.assertEqual(result['cost'], 150000)
        self.assertEqual(result['value'], 160000)
        self.assertEqual(result['margin'], 10000)
        self.assertEqual(result['losing'], ['Material'])

    def test_cvr_sorts_the_worst_head_first(self):
        result = planning.cvr({'Good': (10, 100), 'Bad': (100, 10)})
        self.assertEqual(result['rows'][0]['head'], 'Bad')

    def test_cvr_handles_zero_value_without_dividing_by_zero(self):
        result = planning.cvr({'Material': (100000, 0)})
        self.assertIsNone(result['margin_pct'])
        self.assertEqual(result['margin'], -100000)


class TestApproval(unittest.TestCase):
    """An approval is a status PLUS who and when; the status alone is not
    evidence, which is the gap this closes."""

    def test_pending_when_never_decided(self):
        self.assertEqual(approval.status_for('Bill', 1, {}), approval.PENDING)

    def test_latest_decision_wins(self):
        """Rejected then approved reads as approved, not the other way round."""
        rows = [
            {'doc_type': 'Bill', 'doc_id': 1, 'action': 'Rejected',
             'approved_at': '2026-07-01T10:00:00'},
            {'doc_type': 'Bill', 'doc_id': 1, 'action': 'Approved',
             'approved_at': '2026-07-05T09:00:00'},
        ]
        idx = approval.latest_by_doc(rows)
        self.assertEqual(approval.status_for('Bill', 1, idx), approval.APPROVED)
        self.assertTrue(approval.is_approved('Bill', 1, idx))

    def test_out_of_order_rows_still_resolve_to_the_newest(self):
        rows = [
            {'doc_type': 'Bill', 'doc_id': 1, 'action': 'Approved',
             'approved_at': '2026-07-05T09:00:00'},
            {'doc_type': 'Bill', 'doc_id': 1, 'action': 'Rejected',
             'approved_at': '2026-07-01T10:00:00'},
        ]
        idx = approval.latest_by_doc(rows)
        self.assertEqual(approval.status_for('Bill', 1, idx), approval.APPROVED)

    def test_documents_are_tracked_separately(self):
        rows = [{'doc_type': 'Bill', 'doc_id': 1, 'action': 'Approved',
                 'approved_at': '2026-07-05T09:00:00'}]
        idx = approval.latest_by_doc(rows)
        self.assertFalse(approval.is_approved('Bill', 2, idx))
        self.assertFalse(approval.is_approved('RABill', 1, idx))

    def test_summarise_reports_value_not_just_count(self):
        """Twenty small POs waiting is a nuisance; one big bill is a problem."""
        pending = [{'label': 'Purchase order', 'amount': 5000},
                   {'label': 'Purchase order', 'amount': 3000},
                   {'label': 'RA bill', 'amount': 400000}]
        s = approval.summarise(pending)
        self.assertEqual(s['count'], 3)
        self.assertEqual(s['amount'], 408000)
        self.assertEqual(s['largest'], 400000)
        self.assertEqual(s['by_type']['Purchase order']['count'], 2)
        self.assertEqual(s['by_type']['RA bill']['amount'], 400000)

    def test_summarise_empty(self):
        s = approval.summarise([])
        self.assertEqual(s['count'], 0)
        self.assertEqual(s['amount'], 0)
        self.assertEqual(s['largest'], 0)

    def test_every_approvable_type_has_a_complete_mapping(self):
        """A half-filled mapping would crash only when that document appeared."""
        for doc_type, spec in approval.APPROVABLE.items():
            self.assertEqual(len(spec), 6, doc_type)
            table, _num, status_col, pending, new_status, label = spec
            self.assertTrue(table and status_col and new_status and label)
            self.assertTrue(pending, doc_type)


class TestWriteGuards(unittest.TestCase):
    """Every user-triggered write must be behind a role check.

    This is a source-level test rather than a behavioural one on purpose: it
    catches a *new* unguarded write the moment it is added, which is how the
    gap arose in the first place. It is deliberately narrow — derived-value
    helpers (``_recalc``, ``_compute_*``, CrudFrame ``on_save`` hooks) are
    reached only from callers that already checked, so guarding them again
    would be noise.
    """

    APP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       os.pardir, 'construction_app')
    WRITE_SQL = re.compile(r'\b(INSERT|UPDATE|DELETE)\b', re.I)

    # Reached only from an already-guarded caller, or from first-run setup
    # that must work before any account exists.
    EXEMPT = {
        ('tab_accounting.py', '_recalc'), ('tab_documents.py', '_recalc_total'),
        ('tab_estimate.py', '_recalc'), ('tab_tax_invoice.py', '_recalc'),
        ('tab_vendor_invoice.py', '_recalc'),
        ('tab_equipment_hire.py', '_compute_hire_total'),
        ('tab_site_reports.py', '_compute_cube'),
        ('tab_timeline.py', '_compute_duration'),
        ('tab_variations.py', '_compute_amount'),
        ('tab_muster.py', '_recover_advances'),
        ('tab_allocate.py', 'save_allocations'),
        ('tab_approvals.py', 'record'),
        ('tab_retention.py', 'save'),
        ('tab_quality.py', '_update_gate'),
        ('tab_wizard.py', '_finish'), ('tab_wizard.py', '_skip'),
    }

    def _writers(self, path):
        """(function name, guarded?) for every function containing write SQL."""
        tree = ast.parse(open(path, encoding='utf-8').read())
        out = []
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            writes = False
            for call in [n for n in ast.walk(fn) if isinstance(n, ast.Call)]:
                if getattr(call.func, 'attr', '') not in ('execute', 'executemany'):
                    continue
                for c in ast.walk(call):
                    if (isinstance(c, ast.Constant) and isinstance(c.value, str)
                            and self.WRITE_SQL.search(c.value)):
                        writes = True
            if not writes:
                continue
            guarded = any(isinstance(n, ast.Name) and n.id in ('can_write',)
                          for n in ast.walk(fn))
            out.append((fn.name, guarded))
        return out

    def test_no_unguarded_write_paths(self):
        offenders = []
        for path in sorted(glob.glob(os.path.join(self.APP, 'tab_*.py'))):
            name = os.path.basename(path)
            for fn, guarded in self._writers(path):
                if not guarded and (name, fn) not in self.EXEMPT:
                    offenders.append('{}::{}'.format(name, fn))
        self.assertEqual(offenders, [],
                         'unguarded write paths (add can_write() or justify in '
                         'EXEMPT): {}'.format(offenders))

    def test_settings_saves_are_guarded(self):
        """The gap that was actually shipped: a Viewer could rewrite firm
        details, the invoice series and the cash opening balance."""
        tools = dict(self._writers(os.path.join(self.APP, 'tab_tools.py')))
        for fn in ('save_firm', 'save_ai', 'save_series', 'save_language',
                   'choose_sync_folder'):
            self.assertTrue(tools.get(fn), 'tab_tools.{} is unguarded'.format(fn))
        money = dict(self._writers(os.path.join(self.APP, 'tab_money.py')))
        self.assertTrue(money.get('save_opening'), 'save_opening is unguarded')

    def test_exempt_list_stays_honest(self):
        """An exemption for a function that no longer writes is stale, and a
        stale exemption is how a real gap gets hidden later."""
        live = set()
        for path in glob.glob(os.path.join(self.APP, 'tab_*.py')):
            name = os.path.basename(path)
            for fn, _g in self._writers(path):
                live.add((name, fn))
        self.assertEqual(self.EXEMPT - live, set(),
                         'EXEMPT lists functions that no longer write SQL')


class TestCloseout(unittest.TestCase):
    """Readiness decides when handover happens, which decides when the DLP
    clock starts, which decides when retention comes back."""

    def _snag(self, status=closeout.OPEN, severity=closeout.MINOR,
              trade='Painting', target=None):
        return {'status': status, 'severity': severity, 'trade': trade,
                'target_date': target}

    def test_only_verified_counts_toward_readiness(self):
        """Fixed is the contractor's claim; Verified is the client agreeing."""
        snags = [self._snag(closeout.VERIFIED), self._snag(closeout.FIXED),
                 self._snag(closeout.OPEN), self._snag(closeout.VERIFIED)]
        self.assertEqual(closeout.readiness(snags), 50.0)

    def test_readiness_is_none_with_no_snags(self):
        """An empty list may be a perfect job or an inspection nobody did."""
        self.assertIsNone(closeout.readiness([]))

    def test_open_snags_block_handover(self):
        allowed, reason = closeout.may_hand_over([self._snag(closeout.OPEN)])
        self.assertFalse(allowed)
        self.assertIn('not yet fixed', reason)

    def test_a_blocker_stops_handover_on_its_own(self):
        snags = [self._snag(closeout.FIXED, closeout.BLOCKER)]
        allowed, reason = closeout.may_hand_over(snags)
        self.assertFalse(allowed)
        self.assertIn('blocker', reason.lower())

    def test_fixed_but_unverified_does_not_block(self):
        """Waiting on the client's walk-round is scheduling, not a defect."""
        allowed, reason = closeout.may_hand_over([self._snag(closeout.FIXED)])
        self.assertTrue(allowed)
        self.assertIn('awaiting', reason)

    def test_all_verified_is_clear(self):
        allowed, reason = closeout.may_hand_over([self._snag(closeout.VERIFIED)])
        self.assertTrue(allowed)
        self.assertIn('verified', reason.lower())

    def test_no_snags_allows_handover(self):
        allowed, _ = closeout.may_hand_over([])
        self.assertTrue(allowed)

    def test_overdue_needs_a_target_date_and_ignores_verified(self):
        self.assertTrue(closeout.is_overdue(
            self._snag(target='2026-01-01'), as_on='2026-07-20'))
        self.assertFalse(closeout.is_overdue(
            self._snag(target='2027-01-01'), as_on='2026-07-20'))
        self.assertFalse(closeout.is_overdue(self._snag(), as_on='2026-07-20'))
        self.assertFalse(closeout.is_overdue(
            self._snag(closeout.VERIFIED, target='2026-01-01'), as_on='2026-07-20'))

    def test_by_trade_ranks_who_to_chase_and_drops_verified(self):
        snags = [self._snag(trade='Plumbing'), self._snag(trade='Plumbing'),
                 self._snag(trade='Tiling'),
                 self._snag(closeout.VERIFIED, trade='Painting')]
        self.assertEqual(closeout.by_trade(snags),
                         [('Plumbing', 2), ('Tiling', 1)])

    def test_summary_pulls_it_together(self):
        snags = [self._snag(closeout.OPEN, closeout.BLOCKER, target='2026-01-01'),
                 self._snag(closeout.VERIFIED)]
        s = closeout.summarise(snags, as_on='2026-07-20')
        self.assertEqual(s['total'], 2)
        self.assertEqual(s['open'], 1)
        self.assertEqual(s['blockers'], 1)
        self.assertEqual(s['overdue'], 1)
        self.assertEqual(s['readiness'], 50.0)
        self.assertFalse(s['may_hand_over'])


class TestHSE(unittest.TestCase):
    """A permit is only meaningful while it is open and in date."""

    def _permit(self, status=hse.OPEN, frm='2026-07-01', to='2026-07-31'):
        return {'status': status, 'valid_from': frm, 'valid_to': to}

    def test_permit_valid_inside_its_dates(self):
        ok, _ = hse.permit_valid(self._permit(), as_on='2026-07-20')
        self.assertTrue(ok)

    def test_expired_permit_is_no_permit(self):
        ok, reason = hse.permit_valid(self._permit(to='2026-07-10'),
                                      as_on='2026-07-20')
        self.assertFalse(ok)
        self.assertIn('expired', reason.lower())

    def test_permit_not_yet_started(self):
        ok, reason = hse.permit_valid(self._permit(frm='2026-08-01'),
                                      as_on='2026-07-20')
        self.assertFalse(ok)
        self.assertIn('does not start', reason)

    def test_closed_permit_is_not_valid(self):
        ok, reason = hse.permit_valid(self._permit(status=hse.CLOSED),
                                      as_on='2026-07-20')
        self.assertFalse(ok)
        self.assertIn('closed', reason.lower())

    def test_expiring_soon_is_flagged_before_work_stops(self):
        permits = [self._permit(to='2026-07-21'),   # tomorrow
                   self._permit(to='2026-08-30')]   # far off
        soon = hse.expiring_permits(permits, within_days=2, as_on='2026-07-20')
        self.assertEqual(len(soon), 1)
        self.assertEqual(soon[0][1], 1)

    def test_ltifr_needs_enough_hours_to_mean_anything(self):
        """One injury in a fortnight would otherwise look catastrophic."""
        incidents = [{'severity': hse.LOST_TIME}]
        self.assertIsNone(hse.ltifr(incidents, 500))
        self.assertIsNotNone(hse.ltifr(incidents, 200000))

    def test_ltifr_is_per_200000_hours(self):
        incidents = [{'severity': hse.LOST_TIME}, {'severity': hse.REPORTABLE},
                     {'severity': hse.NEAR_MISS}]
        # 2 lost-time events in exactly 200,000 hours = 2.0
        self.assertEqual(hse.ltifr(incidents, 200000), 2.0)

    def test_near_miss_ratio_and_lost_days(self):
        incidents = [{'severity': hse.NEAR_MISS}, {'severity': hse.NEAR_MISS},
                     {'severity': hse.LOST_TIME, 'lost_days': 5},
                     {'severity': hse.FIRST_AID}]
        s = hse.summarise(incidents, [], 0)
        self.assertEqual(s['total'], 4)
        self.assertEqual(s['lost_time'], 1)
        self.assertEqual(s['lost_days'], 5)
        self.assertEqual(s['near_miss_ratio'], 50.0)
        self.assertIsNone(s['ltifr'])          # no hours given

    def test_summary_counts_expired_permits_separately(self):
        permits = [self._permit(), self._permit(to='2026-07-01')]
        s = hse.summarise([], permits, 0, as_on='2026-07-20')
        self.assertEqual(s['open_permits'], 1)
        self.assertEqual(s['expired_permits'], 1)


class TestSourcing(unittest.TestCase):
    """Cheapest is a recommendation, not a decision — late material costs
    more in idle labour than the price difference."""

    QUOTES = [
        {'id': 1, 'vendor': 'A', 'amount': 100000, 'delivery_date': '2026-09-01'},
        {'id': 2, 'vendor': 'B', 'amount': 110000, 'delivery_date': '2026-07-25'},
        {'id': 3, 'vendor': 'C', 'amount': 130000, 'delivery_date': '2026-07-20'},
    ]

    def test_compare_ranks_cheapest_first_and_quantifies_the_spread(self):
        r = sourcing.compare_quotes(self.QUOTES)
        self.assertEqual(r['cheapest']['vendor'], 'A')
        self.assertEqual(r['highest']['vendor'], 'C')
        self.assertEqual(r['saving_vs_highest'], 30000)
        self.assertEqual(r['spread_pct'], 30.0)

    def test_unpriced_quotes_are_counted_but_not_ranked(self):
        """A quote with no price is an enquiry, not an offer."""
        r = sourcing.compare_quotes(self.QUOTES + [{'id': 4, 'amount': 0}])
        self.assertEqual(r['count'], 4)
        self.assertEqual(r['priced'], 3)
        self.assertEqual(len(r['ranked']), 3)

    def test_no_priced_quotes(self):
        r = sourcing.compare_quotes([{'id': 1, 'amount': 0}])
        self.assertIsNone(r['cheapest'])
        self.assertEqual(r['saving_vs_highest'], 0)

    def test_recommends_cheapest_when_no_deadline(self):
        best, note = sourcing.recommendation(self.QUOTES)
        self.assertEqual(best['vendor'], 'A')
        self.assertIn('Lowest price', note)

    def test_recommends_the_cheapest_that_can_actually_deliver(self):
        best, note = sourcing.recommendation(self.QUOTES, needed_by='2026-07-26')
        self.assertEqual(best['vendor'], 'B')      # A is cheaper but too late
        self.assertIn('idle labour', note)

    def test_cheapest_wins_when_it_also_meets_the_date(self):
        best, note = sourcing.recommendation(self.QUOTES, needed_by='2026-09-30')
        self.assertEqual(best['vendor'], 'A')
        self.assertIn('meets the required date', note)

    def test_says_so_when_nothing_can_meet_the_date(self):
        best, note = sourcing.recommendation(self.QUOTES, needed_by='2026-07-01')
        self.assertEqual(best['vendor'], 'A')
        self.assertIn('No quote meets', note)

    def test_vendor_score_skips_unrated_factors(self):
        """An unrated factor is unknown, not zero."""
        self.assertEqual(sourcing.vendor_score({'quality': 4, 'delivery': 5,
                                                'price': 3}), 4.0)
        self.assertEqual(sourcing.vendor_score({'quality': 4, 'price': None}), 4.0)
        self.assertIsNone(sourcing.vendor_score({}))

    def test_unrated_vendors_sort_last_not_worst(self):
        ranked = sourcing.rank_vendors([
            {'name': 'Unrated'},
            {'name': 'Good', 'quality': 5, 'delivery': 5, 'price': 5},
            {'name': 'Poor', 'quality': 1, 'delivery': 1, 'price': 1}])
        self.assertEqual([v['name'] for v, _s in ranked],
                         ['Good', 'Poor', 'Unrated'])


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


class TestPaths(unittest.TestCase):
    """Where the app keeps its files, run from source vs installed (frozen)."""

    def setUp(self):
        import paths
        self.paths = paths
        self._frozen = getattr(sys, 'frozen', None)
        self._meipass = getattr(sys, '_MEIPASS', None)

    def tearDown(self):
        for attr, val in (('frozen', self._frozen), ('_MEIPASS', self._meipass)):
            if val is None:
                if hasattr(sys, attr):
                    delattr(sys, attr)
            else:
                setattr(sys, attr, val)

    def test_from_source_data_stays_next_to_the_code(self):
        # Running from source must not move an existing construction.db.
        if hasattr(sys, 'frozen'):
            del sys.frozen
        self.assertFalse(self.paths.is_frozen())
        here = os.path.dirname(os.path.abspath(self.paths.__file__))
        self.assertEqual(self.paths.data_dir(), here)
        self.assertEqual(self.paths.resource_base(), here)

    def test_frozen_build_redirects_data_to_a_per_user_folder(self):
        sys.frozen = True
        sys._MEIPASS = os.path.join('X:', 'app', '_internal')
        try:
            self.assertTrue(self.paths.is_frozen())
            # resources come from the bundle
            self.assertEqual(self.paths.resource_base(), sys._MEIPASS)
            # data goes to a writable per-user dir, NOT the read-only bundle
            data = self.paths.data_dir()
            self.assertNotEqual(data, sys._MEIPASS)
            self.assertIn(self.paths.APP_DIR_NAME, data)
        finally:
            del sys.frozen, sys._MEIPASS

    def test_data_and_resource_path_helpers_join_correctly(self):
        self.assertTrue(self.paths.data_path('construction.db')
                        .endswith('construction.db'))
        rp = self.paths.resource_path('resources', 'app.ico')
        self.assertTrue(rp.endswith(os.path.join('resources', 'app.ico')))

    def test_db_and_registry_route_through_paths(self):
        # The two writable globals must derive from paths, not a hard-coded
        # source-dir join, or an installed build writes into Program Files.
        import db, company
        self.assertEqual(db.DB_PATH, self.paths.data_path('construction.db'))
        self.assertEqual(company.REGISTRY_PATH,
                         self.paths.data_path('companies.json'))


class TestAssistantRetrieval(unittest.TestCase):
    """TF-IDF retrieval ranks the distinctive table first, and a follow-up
    inherits context from the previous question."""

    def _tables(self, question, context='', k=4):
        docs, _ex = assistant.retrieve(question, k_tables=k, context=context)
        return [d['table'] for d in docs]

    def test_distinctive_word_finds_its_table(self):
        # 'retention' is rare and specific; it should pull the RA-bill / bill
        # tables, not a table that merely shares a common word.
        top = self._tables('how much retention have I withheld?')
        self.assertTrue(any(t in ('ra_bills', 'bills', 'sub_bills')
                            for t in top[:2]))

    def test_muster_question_finds_attendance_and_labour(self):
        top = self._tables('show muster attendance days for labour')
        self.assertTrue(any(t in ('attendance', 'labor') for t in top[:3]))

    def test_a_common_word_does_not_dominate(self):
        # 'site' appears in most tables; a question about vendors owed money
        # should still surface the vendor tables, not just anything site-ish.
        top = self._tables('which vendors do I owe money to on this site?')
        self.assertTrue(any('vendor' in t for t in top[:3]))

    def test_retrieval_always_returns_something(self):
        # Even a question with no catalog words falls back rather than empty.
        docs, exs = assistant.retrieve('xyzzy plugh frobnicate')
        self.assertTrue(docs)

    def test_follow_up_context_changes_retrieval(self):
        # A terse follow-up on its own is ambiguous; with the prior question as
        # context it should retrieve the same subject area.
        alone = self._tables('and last month?')
        withctx = self._tables('and last month?',
                               context='how much GST did I collect')
        gst_words = ('tax_invoices', 'vendor_invoices')
        self.assertTrue(any(t in gst_words for t in withctx))
        # context genuinely moved the ranking
        self.assertNotEqual(alone, withctx)

    def test_prompt_includes_recent_questions_for_follow_ups(self):
        docs, exs = assistant.retrieve('and for site B?')
        prompt = assistant.build_sql_prompt(
            'and for site B?', docs, exs,
            history=[{'question': 'what did I spend on cement?'},
                     {'question': 'and on steel?'}])
        self.assertIn('Earlier questions', prompt)
        self.assertIn('what did I spend on cement?', prompt)
        # only the last two are carried
        big = [{'question': 'q{}'.format(i)} for i in range(5)]
        p2 = assistant.build_sql_prompt('now?', docs, exs, history=big)
        self.assertIn('q4', p2)
        self.assertNotIn('q0', p2)

    def test_prompt_without_history_is_unchanged(self):
        docs, exs = assistant.retrieve('cash in hand')
        prompt = assistant.build_sql_prompt('cash in hand', docs, exs)
        self.assertNotIn('Earlier questions', prompt)

    def test_tfidf_index_covers_every_catalog_doc(self):
        self.assertEqual(len(assistant._DOC_VECS), len(assistant.SCHEMA_DOCS))

    def test_module_uses_no_neural_embedding_dependency(self):
        # The stdlib-only rule forbids a model dependency; this is TF-IDF, not
        # neural embeddings, and must stay that way.
        src = open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), os.pardir,
            'construction_app', 'assistant.py'), encoding='utf-8').read()
        for banned in ('import numpy', 'import torch', 'sentence_transformers',
                       'import openai'):
            self.assertNotIn(banned, src)


class TestProjectCost(unittest.TestCase):
    """Per-project rollup. The attribution rule is what earns the module."""

    def _row(self, category, amount, project_id=None, site_id=1):
        return {'category': category, 'amount': amount,
                'project_id': project_id, 'site_id': site_id}

    # --- attribution ---
    def test_tagged_row_always_counts(self):
        r = self._row('material', 100, project_id=5, site_id=9)
        self.assertEqual(
            projectcost.attribution(r, 5, project_site_id=1, sole_on_site=False),
            'tagged')

    def test_tag_to_another_project_never_counts_even_on_our_site(self):
        # An explicit tag wins over the site — otherwise tagging would be
        # pointless the moment two projects shared a plot.
        r = self._row('material', 100, project_id=7, site_id=1)
        self.assertEqual(
            projectcost.attribution(r, 5, project_site_id=1, sole_on_site=True),
            'other')

    def test_untagged_counts_by_site_only_when_sole_project_on_site(self):
        r = self._row('material', 100, project_id=None, site_id=1)
        self.assertEqual(
            projectcost.attribution(r, 5, project_site_id=1, sole_on_site=True),
            'by-site')
        self.assertEqual(
            projectcost.attribution(r, 5, project_site_id=1, sole_on_site=False),
            'ambiguous')

    def test_untagged_on_a_different_site_is_not_ours(self):
        r = self._row('material', 100, project_id=None, site_id=2)
        self.assertEqual(
            projectcost.attribution(r, 5, project_site_id=1, sole_on_site=True),
            'other')

    # --- rollup, sole project on site (reproduces the old site rollup) ---
    def test_sole_project_rolls_up_untagged_rows_by_site(self):
        rows = [self._row('revenue', 500000),
                self._row('material', 120000),
                self._row('labour', 80000),
                self._row('hire', 20000)]
        r = projectcost.rollup(rows, project_id=5, project_site_id=1,
                               sole_on_site=True, budget=300000)
        self.assertEqual(r['total_cost'], 220000)
        self.assertEqual(r['revenue'], 500000)
        self.assertEqual(r['margin'], 280000)
        self.assertEqual(r['margin_pct'], 56.0)
        self.assertEqual(r['unattributed_cost'], 0)

    def test_shared_site_does_not_guess_untagged_costs(self):
        # Two projects on one site: untagged cost cannot be split, so it is
        # reported unattributed, never assigned.
        rows = [self._row('material', 100000, project_id=5),   # tagged to us
                self._row('labour', 40000, project_id=None),   # untagged, shared
                self._row('material', 25000, project_id=7)]    # other project
        r = projectcost.rollup(rows, project_id=5, project_site_id=1,
                               sole_on_site=False, budget=0)
        self.assertEqual(r['total_cost'], 100000)          # only the tagged row
        self.assertEqual(r['unattributed_cost'], 40000)
        self.assertEqual(r['unattributed_count'], 1)

    def test_budget_and_over_budget_flag(self):
        rows = [self._row('material', 350000)]
        r = projectcost.rollup(rows, 5, 1, True, budget=300000)
        self.assertTrue(r['over_budget'])
        self.assertGreater(r['budget_used_pct'], 100)

    def test_loss_making_project_has_negative_margin(self):
        rows = [self._row('revenue', 100000), self._row('material', 130000)]
        r = projectcost.rollup(rows, 5, 1, True)
        self.assertEqual(r['margin'], -30000)

    def test_no_revenue_leaves_margin_pct_undefined(self):
        r = projectcost.rollup([self._row('material', 1000)], 5, 1, True)
        self.assertIsNone(r['margin_pct'])

    def test_unknown_cost_category_falls_into_other(self):
        rows = [self._row('mystery', 500, project_id=5)]
        r = projectcost.rollup(rows, 5, 1, False)
        self.assertEqual(r['by_category']['other'], 500)

    def test_empty_rollup(self):
        r = projectcost.rollup([], 5, 1, True, budget=100000)
        self.assertEqual(r['total_cost'], 0)
        self.assertEqual(r['margin'], 0)
        self.assertFalse(r['over_budget'])

    # --- portfolio ---
    def test_portfolio_points_at_the_worst_project(self):
        a = projectcost.rollup([self._row('revenue', 100000, site_id=1),
                                self._row('material', 90000, site_id=1)],
                               1, 1, True)
        b = projectcost.rollup([self._row('revenue', 100000, site_id=2),
                                self._row('material', 130000, site_id=2)],
                               2, 2, True, budget=100000)
        p = projectcost.portfolio([('Alpha', a), ('Beta', b)])
        self.assertEqual(p['projects'], 2)
        self.assertEqual(p['at_a_loss'], 1)
        self.assertEqual(p['worst'], 'Beta')
        self.assertEqual(p['worst_margin'], -30000)
        self.assertEqual(p['over_budget'], 1)


class TestCriticalPath(unittest.TestCase):
    """CPM over a known network. The float values are the whole point."""

    def _net(self, by='name'):
        # A(3) -> B(4), C(2); B -> D(5); C -> E(1); D,E -> F(2).
        # Critical path A-B-D-F, duration 14; C and E carry 6 days of float.
        def dep(*names):
            if by == 'id':
                ids = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6}
                return ', '.join(str(ids[n]) for n in names)
            return ', '.join(names)
        return [
            {'id': 1, 'task_name': 'A', 'duration_days': 3, 'dependency': ''},
            {'id': 2, 'task_name': 'B', 'duration_days': 4, 'dependency': dep('A')},
            {'id': 3, 'task_name': 'C', 'duration_days': 2, 'dependency': dep('A')},
            {'id': 4, 'task_name': 'D', 'duration_days': 5, 'dependency': dep('B')},
            {'id': 5, 'task_name': 'E', 'duration_days': 1, 'dependency': dep('C')},
            {'id': 6, 'task_name': 'F', 'duration_days': 2,
             'dependency': dep('D', 'E')},
        ]

    def _run(self, by='name'):
        resolved, unresolved = cpm.resolve_predecessors(self._net(by))
        self.assertEqual(unresolved, [])
        return cpm.analyse(resolved)

    def test_project_duration(self):
        self.assertEqual(self._run()['project_duration'], 14)

    def test_critical_path_is_a_b_d_f(self):
        self.assertEqual(self._run()['critical_path'], ['A', 'B', 'D', 'F'])

    def test_early_and_late_times(self):
        t = self._run()['tasks']
        self.assertEqual((t[1]['early_start'], t[1]['early_finish']), (0, 3))
        self.assertEqual((t[4]['early_start'], t[4]['early_finish']), (7, 12))
        self.assertEqual((t[6]['early_start'], t[6]['early_finish']), (12, 14))
        # C runs early but its late start is pushed out by its float
        self.assertEqual((t[3]['early_start'], t[3]['late_start']), (3, 9))

    def test_float_is_zero_on_the_critical_path_and_six_off_it(self):
        t = self._run()['tasks']
        for cid in (1, 2, 4, 6):
            self.assertEqual(t[cid]['total_float'], 0)
            self.assertTrue(t[cid]['critical'])
        self.assertEqual(t[3]['total_float'], 6)     # C
        self.assertEqual(t[5]['total_float'], 6)     # E
        self.assertFalse(t[3]['critical'])

    def test_free_float_distinguishes_from_total_float(self):
        # E can slip 6 days without disturbing anything (free float 6); C can
        # slip 6 in total but 0 freely, because that would delay E.
        t = self._run()['tasks']
        self.assertEqual(t[5]['free_float'], 6)      # E
        self.assertEqual(t[3]['free_float'], 0)      # C
        self.assertEqual(t[3]['total_float'], 6)

    def test_resolution_by_id_matches_resolution_by_name(self):
        self.assertEqual(self._run('id')['critical_path'],
                         self._run('name')['critical_path'])

    # --- the honesty constraints ---
    def test_a_cycle_yields_no_schedule(self):
        tasks = [{'id': 1, 'task_name': 'A', 'duration_days': 2,
                  'dependency': 'B'},
                 {'id': 2, 'task_name': 'B', 'duration_days': 2,
                  'dependency': 'A'}]
        resolved, _ = cpm.resolve_predecessors(tasks)
        result = cpm.analyse(resolved)
        self.assertEqual(set(result['cycle']), {1, 2})
        self.assertIsNone(result['project_duration'])
        self.assertEqual(result['critical_path'], [])
        self.assertFalse(cpm.summarise(result)['ok'])

    def test_unknown_dependency_is_reported_not_dropped(self):
        tasks = [{'id': 1, 'task_name': 'A', 'duration_days': 2,
                  'dependency': 'Ghost Task'}]
        resolved, unresolved = cpm.resolve_predecessors(tasks)
        self.assertEqual(unresolved, [(1, 'Ghost Task')])
        self.assertEqual(resolved[0]['predecessors'], [])

    def test_self_dependency_is_unresolved_not_a_loop(self):
        tasks = [{'id': 1, 'task_name': 'A', 'duration_days': 2,
                  'dependency': 'A'}]
        resolved, unresolved = cpm.resolve_predecessors(tasks)
        self.assertEqual(unresolved, [(1, 'A')])
        self.assertEqual(cpm.analyse(resolved)['project_duration'], 2)

    def test_dependencies_split_on_commas_not_spaces(self):
        # Task names contain spaces; splitting on space would fragment them.
        tasks = [{'id': 1, 'task_name': 'Site clearance', 'duration_days': 2,
                  'dependency': ''},
                 {'id': 2, 'task_name': 'Foundation work', 'duration_days': 5,
                  'dependency': 'Site clearance'}]
        resolved, unresolved = cpm.resolve_predecessors(tasks)
        self.assertEqual(unresolved, [])
        self.assertEqual(resolved[1]['predecessors'], [1])

    # --- durations ---
    def test_duration_falls_back_to_the_date_span(self):
        self.assertEqual(cpm.task_duration(
            {'start_date': '2026-04-01', 'end_date': '2026-04-10'}), 10)
        self.assertEqual(cpm.task_duration({'duration_days': 4}), 4)
        self.assertEqual(cpm.task_duration({}), 0)      # a milestone

    def test_schedule_maps_early_times_to_dates(self):
        result = cpm.schedule_from(self._net(), project_start='2026-04-01')
        t = result['tasks']
        self.assertEqual(t[1]['start_date'], '2026-04-01')     # A, ES 0
        self.assertEqual(t[1]['finish_date'], '2026-04-03')    # 3 days incl.
        self.assertEqual(t[4]['start_date'], '2026-04-08')     # D, ES 7

    def test_empty_programme(self):
        result = cpm.analyse([])
        self.assertEqual(result['project_duration'], 0)
        self.assertEqual(result['critical_path'], [])
        self.assertTrue(cpm.summarise(result)['ok'])


class TestEInvoice(unittest.TestCase):
    """Format validation and readiness for e-invoice / e-way-bill fields."""

    _GOOD_IRN = 'a' * 64

    def test_blank_fields_never_warn(self):
        # Absence is not an error: the module does not know a field is required.
        self.assertEqual(einvoice.validate_irn(''), (True, ''))
        self.assertEqual(einvoice.validate_eway(''), (True, ''))
        self.assertEqual(einvoice.validate_vehicle(''), (True, ''))
        self.assertEqual(einvoice.validate({}), [])

    def test_irn_must_be_64_hex(self):
        self.assertTrue(einvoice.validate_irn(self._GOOD_IRN)[0])
        self.assertTrue(einvoice.validate_irn('9F' * 32)[0])
        self.assertFalse(einvoice.validate_irn('abc123')[0])       # too short
        self.assertFalse(einvoice.validate_irn('z' * 64)[0])       # not hex

    def test_eway_is_twelve_digits_ignoring_grouping(self):
        self.assertTrue(einvoice.validate_eway('123456789012')[0])
        self.assertTrue(einvoice.validate_eway('1234 5678 9012')[0])
        self.assertTrue(einvoice.validate_eway('1234-5678-9012')[0])
        self.assertFalse(einvoice.validate_eway('12345')[0])
        self.assertFalse(einvoice.validate_eway('12345678901A')[0])

    def test_eway_normalises_to_bare_digits(self):
        self.assertEqual(einvoice.normalise_eway('1234 5678 9012'),
                         '123456789012')
        # something that is not 12 digits is left as the user typed it
        self.assertEqual(einvoice.normalise_eway('pending'), 'pending')

    def test_vehicle_check_is_lenient_and_only_warns(self):
        self.assertTrue(einvoice.validate_vehicle('KA25AB1234')[0])
        self.assertTrue(einvoice.validate_vehicle('ka 25 ab 1234')[0])
        self.assertTrue(einvoice.validate_vehicle('MH12A1234')[0])
        ok, msg = einvoice.validate_vehicle('lorry')
        self.assertFalse(ok)
        self.assertIn('Recorded as entered', msg)   # warns, does not reject

    def test_validate_collects_every_bad_field(self):
        warns = einvoice.validate({'irn': 'nope', 'eway_bill_no': '12',
                                   'vehicle_no': 'truck'})
        self.assertEqual(len(warns), 3)

    def test_summarise_reports_presence_and_shape(self):
        s = einvoice.summarise({'irn': self._GOOD_IRN,
                                'eway_bill_no': '1234 5678 9012',
                                'vehicle_no': 'ka25ab1234',
                                'transporter': 'VRL Logistics'})
        self.assertTrue(s['has_einvoice'])
        self.assertTrue(s['has_eway'])
        self.assertEqual(s['eway_bill_no'], '123456789012')   # normalised
        self.assertEqual(s['vehicle_no'], 'KA25AB1234')       # upper-cased
        self.assertTrue(s['well_formed'])

    def test_summarise_flags_malformed_but_still_reports_presence(self):
        s = einvoice.summarise({'irn': 'bad', 'eway_bill_no': '999'})
        self.assertTrue(s['has_einvoice'])       # present, even if malformed
        self.assertFalse(s['well_formed'])
        self.assertTrue(s['warnings'])

    def test_empty_invoice_is_well_formed_and_empty(self):
        s = einvoice.summarise({})
        self.assertFalse(s['has_einvoice'])
        self.assertFalse(s['has_eway'])
        self.assertTrue(s['well_formed'])

    def test_module_does_not_decide_what_is_required(self):
        # It reports shape and presence, never obligation — a works contract is
        # a service and may need no e-way bill at all.
        src = ' '.join(dir(einvoice)).lower()
        for banned in ('required', 'mandatory', 'threshold', 'turnover',
                       'penalty'):
            self.assertNotIn(banned, src)


class TestBrandedDocuments(unittest.TestCase):
    """The shared letterhead and bank block, and that internal reports are
    left exactly as they were."""

    def setUp(self):
        import bill_export
        self.be = bill_export
        self.firm = {'name': 'Sri Venkateswara Constructions',
                     'gstin': '29ABCDE1234F1Z5',
                     'address': 'Plot 14, Industrial Area, Hospet 583201',
                     'phone': '9812345678', 'email': 'svc@example.com',
                     'bank_name': 'SBI, Hospet', 'bank_account': '3012345678',
                     'bank_ifsc': 'SBIN0001234'}

    def test_letterhead_shows_every_detail_present(self):
        html = self.be.letterhead_html(self.firm)
        for part in ('Sri Venkateswara Constructions', '29ABCDE1234F1Z5',
                     'Industrial Area', '9812345678', 'svc@example.com'):
            self.assertIn(part, html)

    def test_letterhead_drops_missing_lines_rather_than_printing_blanks(self):
        # An empty "GSTIN:" on an unregistered firm looks like a mistake.
        html = self.be.letterhead_html({'name': 'Small Firm'})
        self.assertIn('Small Firm', html)
        self.assertNotIn('GSTIN', html)
        self.assertNotIn('Ph:', html)

    def test_letterhead_falls_back_to_a_name(self):
        self.assertIn('Construction OS', self.be.letterhead_html({}))
        self.assertIn('Construction OS', self.be.letterhead_html(None))

    def test_bank_block_needs_account_and_ifsc(self):
        self.assertIn('3012345678', self.be.bank_block_html(self.firm))
        self.assertIn('SBIN0001234', self.be.bank_block_html(self.firm))
        # a half-filled block is worse than none — someone will try to use it
        self.assertEqual(self.be.bank_block_html(
            {'bank_name': 'SBI', 'bank_account': '30123'}), '')
        self.assertEqual(self.be.bank_block_html({}), '')

    def test_statement_with_firm_carries_letterhead_and_bank(self):
        html = self.be.build_statement_html(
            'Quotation', ['Quote No: Q-1'], ['Item', 'Amount'],
            [('Brickwork', '50,000.00')], summary='Total: 50,000.00',
            firm=self.firm)
        self.assertIn('29ABCDE1234F1Z5', html)      # letterhead
        self.assertIn('Payment to:', html)          # bank block
        self.assertIn('3012345678', html)

    def test_statement_without_firm_is_unchanged(self):
        # The ~20 internal reports pass no firm and must render as before:
        # bare name, no letterhead rule, no bank block.
        html = self.be.build_statement_html(
            'Cash Book', ['Site: Ward 7'], ['Date', 'Amount'],
            [('2026-04-01', '1,000.00')], company_name='My Firm')
        self.assertIn('My Firm', html)
        self.assertNotIn('Payment to:', html)
        # the branded header element must be absent (the CSS rule of the same
        # name is always in the stylesheet, so match the div, not the word)
        self.assertNotIn('<div class="letterhead">', html)
        self.assertIn('<div class="company">My Firm</div>', html)

    def test_firm_details_html_is_escaped(self):
        html = self.be.letterhead_html({'name': '<script>x</script>'})
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)


class TestFirmDetails(unittest.TestCase):
    """The firm-details reader over app_settings."""

    def setUp(self):
        import sqlite3
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('CREATE TABLE app_settings '
                          '(key TEXT PRIMARY KEY, value TEXT)')

    def tearDown(self):
        self.conn.close()

    def _set(self, **kw):
        for k, v in kw.items():
            self.conn.execute('INSERT OR REPLACE INTO app_settings VALUES (?, ?)',
                              (k, v))
        self.conn.commit()

    def test_maps_settings_keys_to_letterhead_keys(self):
        import firm
        self._set(company_name='ACME Builders', seller_gstin='29AAA',
                  firm_bank_account='123', firm_bank_ifsc='SBIN0001')
        d = firm.details(self.conn)
        self.assertEqual(d['name'], 'ACME Builders')
        self.assertEqual(d['gstin'], '29AAA')
        self.assertTrue(firm.has_bank(d))

    def test_absent_values_are_empty_not_missing(self):
        import firm
        d = firm.details(self.conn)
        self.assertEqual(d['name'], 'Construction OS')   # falls back
        self.assertEqual(d['gstin'], '')
        self.assertFalse(firm.has_bank(d))

    def test_panel_fields_and_reader_map_stay_in_step(self):
        # tab_tools builds its panel from firm.FIELDS; every field key must be
        # one the reader knows how to map, or the panel would save settings the
        # letterhead never reads.
        import firm
        field_keys = {k for k, _ in firm.FIELDS}
        self.assertTrue(field_keys.issubset(set(firm._MAP)))


class TestBidding(unittest.TestCase):
    """Scorecard, evidence, and the vetoes that override the score."""

    def _all(self, value):
        return {f['key']: value for f in bidding.FACTORS}

    def test_weights_sum_to_one_hundred(self):
        self.assertEqual(sum(f['weight'] for f in bidding.FACTORS), 100)

    def test_every_factor_has_both_anchors(self):
        # A bare 1-5 scale invites everyone to pick 3; the anchors are what
        # make two people score the same tender the same way.
        for f in bidding.FACTORS:
            self.assertTrue(f['low'].strip(), f['key'])
            self.assertTrue(f['high'].strip(), f['key'])

    def test_score_endpoints(self):
        self.assertEqual(bidding.score(self._all(5)), 100.0)
        self.assertEqual(bidding.score(self._all(1)), 0.0)
        self.assertEqual(bidding.score(self._all(3)), 50.0)

    def test_unscored_factors_are_excluded_not_treated_as_zero(self):
        # A half-filled card should read as "what we know so far", not be
        # punished as though the blanks were terrible.
        partial = {'capability': 5, 'margin': 5}
        self.assertEqual(bidding.score(partial), 100.0)
        pct, done, of = bidding.completeness(partial)
        self.assertEqual(done, 2)
        self.assertEqual(of, len(bidding.FACTORS))

    def test_nothing_scored_gives_no_score(self):
        self.assertIsNone(bidding.score({}))
        self.assertIsNone(bidding.score(None))

    def test_out_of_range_scores_are_clamped(self):
        self.assertEqual(bidding.score({'capability': 99}), 100.0)
        self.assertEqual(bidding.score({'capability': -5}), 0.0)

    def test_weighting_favours_the_heavier_factors(self):
        heavy = {'capability': 5, 'logistics': 1}     # 25 vs 10
        light = {'capability': 1, 'logistics': 5}
        self.assertGreater(bidding.score(heavy), bidding.score(light))

    # --- evidence ---
    def test_client_evidence_sums_exposure_and_ages_it(self):
        pos = {'outstanding': 500000,
               'buckets': {'0-30': 100000, '30-60': 100000,
                           '60-90': 150000, '90+': 150000}}
        ev = bidding.client_evidence(pos, retention_held=200000,
                                     tender_value=2000000)
        self.assertEqual(ev['outstanding'], 500000)
        self.assertEqual(ev['exposure'], 700000)        # incl. retention
        self.assertEqual(ev['aged_overdue'], 300000)    # 60-90 and 90+
        self.assertEqual(ev['exposure_pct_of_tender'], 35.0)

    def test_aged_buckets_match_the_ageing_module_exactly(self):
        # Substring matching got this wrong once: '30-60' contains '60'. If
        # ageing.BUCKETS is ever renamed, this fails rather than silently
        # counting current debt as overdue.
        for label in bidding.AGED_BUCKETS:
            self.assertIn(label, ageing.BUCKETS)
        self.assertEqual(bidding.AGED_BUCKETS, ageing.BUCKETS[-2:])

    def test_current_debt_is_not_counted_as_overdue(self):
        pos = {'outstanding': 200000,
               'buckets': {'0-30': 100000, '30-60': 100000}}
        ev = bidding.client_evidence(pos, 0, 1000000)
        self.assertEqual(ev['aged_overdue'], 0)
        self.assertEqual(bidding.vetoes({}, ev, {}), [])

    def test_no_client_history_is_flagged_not_assumed_good(self):
        ev = bidding.client_evidence({}, 0, 1000000)
        self.assertFalse(ev['has_history'])
        warns = bidding.warnings({}, ev, {})
        self.assertTrue(any('No trading history' in w for w in warns))

    def test_workload_utilisation(self):
        w = bidding.workload_evidence(8000000, 10000000, 3000000)
        self.assertEqual(w['utilisation_pct'], 80.0)
        self.assertEqual(w['utilisation_with_this_pct'], 110.0)

    def test_workload_without_a_capacity_reports_none_not_zero(self):
        w = bidding.workload_evidence(5000000, 0, 1000000)
        self.assertIsNone(w['utilisation_pct'])

    # --- vetoes: the reason this module exists ---
    def test_a_veto_overrides_a_high_score(self):
        # Five comfortable scores must not drown out one fatal factor.
        good = self._all(5)
        good['cashflow'] = 1
        total = bidding.score(good)
        self.assertGreater(total, bidding.MIN_SCORE_TO_BID)
        result = bidding.assess(good, {}, {})
        self.assertEqual(result['verdict'], bidding.NO_BID)
        self.assertTrue(result['vetoes'])

    def test_aged_debt_with_this_client_vetoes(self):
        ev = bidding.client_evidence(
            {'outstanding': 420000, 'buckets': {'90+': 420000}}, 0, 5000000)
        v = bidding.vetoes(self._all(5), ev, {})
        self.assertTrue(any('60 days old' in x for x in v))

    def test_concentrated_exposure_vetoes(self):
        ev = bidding.client_evidence({'outstanding': 900000, 'buckets': {}},
                                     0, 2000000)         # 45% of tender
        v = bidding.vetoes(self._all(5), ev, {})
        self.assertTrue(any('already tied up' in x for x in v))

    def test_full_order_book_vetoes(self):
        w = bidding.workload_evidence(14000000, 10000000, 2000000)   # 160%
        v = bidding.vetoes(self._all(5), {}, w)
        self.assertTrue(any('capacity' in x for x in v))

    def test_veto_thresholds_are_overridable(self):
        ev = bidding.client_evidence({'outstanding': 900000, 'buckets': {}},
                                     0, 2000000)
        self.assertTrue(bidding.vetoes(self._all(5), ev, {},
                                       exposure_veto_pct=25))
        self.assertFalse(bidding.vetoes(self._all(5), ev, {},
                                        exposure_veto_pct=60))

    def test_clean_client_and_light_book_produce_no_vetoes(self):
        ev = bidding.client_evidence({'outstanding': 0, 'buckets': {}},
                                     0, 2000000)
        w = bidding.workload_evidence(2000000, 10000000, 2000000)
        self.assertEqual(bidding.vetoes(self._all(4), ev, w), [])

    def test_vetoes_cite_evidence_rather_than_a_number(self):
        # "Score 42" is not arguable; a figure and a reason is.
        ev = bidding.client_evidence(
            {'outstanding': 420000, 'buckets': {'90+': 420000}}, 0, 5000000)
        v = bidding.vetoes(self._all(5), ev, {})
        self.assertTrue(any('420,000' in x for x in v))

    # --- verdict ---
    def test_verdict_bands(self):
        self.assertEqual(bidding.verdict(85, []), bidding.BID)
        self.assertEqual(bidding.verdict(50, []), bidding.CONDITIONAL)
        self.assertEqual(bidding.verdict(20, []), bidding.NO_BID)
        self.assertEqual(bidding.verdict(95, ['fatal']), bidding.NO_BID)

    def test_full_assessment_shape(self):
        r = bidding.assess(self._all(4), bidding.client_evidence({}, 0, 0),
                           bidding.workload_evidence(0, 0, 0))
        self.assertEqual(r['verdict'], bidding.BID)
        self.assertEqual(r['score'], 75.0)
        self.assertEqual(r['completeness_pct'], 100)

    # --- learning from outcomes ---
    def test_outcome_review_compares_scoring_with_reality(self):
        rows = [{'score': 80, 'verdict': bidding.BID, 'decision': 'Bid',
                 'outcome': 'Won'},
                {'score': 75, 'verdict': bidding.BID, 'decision': 'Bid',
                 'outcome': 'Lost'},
                {'score': 30, 'verdict': bidding.NO_BID, 'decision': 'Bid',
                 'outcome': 'Won'},
                {'score': 50, 'verdict': bidding.CONDITIONAL,
                 'decision': 'No bid', 'outcome': 'Pending'}]
        rev = bidding.outcome_review(rows)
        self.assertEqual(rev['assessed'], 4)
        self.assertEqual(rev['won'], 2)
        self.assertEqual(rev['lost'], 1)
        self.assertAlmostEqual(rev['win_rate'], 66.7, places=1)
        self.assertEqual(rev['bid_against_advice'], 1)

    def test_outcome_review_of_nothing(self):
        rev = bidding.outcome_review([])
        self.assertEqual(rev['assessed'], 0)
        self.assertIsNone(rev['win_rate'])


class TestProgrammeBaseline(unittest.TestCase):
    """Frozen plan vs actual, delay attribution, and LD exposure."""

    def _task(self, tid, name, b_end, end, cause='', actual_end=None,
              b_start='2026-04-01', start='2026-04-01'):
        return {'id': tid, 'task_name': name, 'baseline_start': b_start,
                'baseline_end': b_end, 'start_date': start, 'end_date': end,
                'actual_start': None, 'actual_end': actual_end,
                'delay_cause': cause, 'delay_note': '', 'status': 'In Progress'}

    # --- slip ---
    def test_slip_is_signed_and_early_is_negative(self):
        self.assertEqual(programme.slip_days('2026-05-01', '2026-05-11'), 10)
        self.assertEqual(programme.slip_days('2026-05-01', '2026-04-28'), -3)
        self.assertEqual(programme.slip_days('2026-05-01', '2026-05-01'), 0)

    def test_missing_baseline_gives_none_not_zero(self):
        # "No baseline" and "on time" are different states; reporting the first
        # as the second makes an unbaselined programme look healthy.
        self.assertIsNone(programme.slip_days(None, '2026-05-01'))
        self.assertIsNone(programme.slip_days('2026-05-01', None))

    def test_actual_finish_beats_planned_finish(self):
        t = self._task(1, 'Footings', '2026-05-01', '2026-05-20',
                       actual_end='2026-05-10')
        v = programme.task_variance(t)
        self.assertEqual(v['finish'], '2026-05-10')
        self.assertEqual(v['finish_slip'], 9)
        self.assertTrue(v['complete'])

    # --- programme level ---
    def test_programme_finish_is_the_latest_task(self):
        tasks = [self._task(1, 'A', '2026-05-01', '2026-05-05'),
                 self._task(2, 'B', '2026-06-01', '2026-06-20')]
        self.assertEqual(programme.programme_finish(tasks, 'baseline_end')
                         .isoformat(), '2026-06-01')
        self.assertEqual(programme.programme_finish(tasks, 'effective')
                         .isoformat(), '2026-06-20')

    def test_total_delay_is_the_programme_finish_slip(self):
        tasks = [self._task(1, 'A', '2026-05-01', '2026-05-05'),
                 self._task(2, 'B', '2026-06-01', '2026-06-20')]
        s = programme.delay_summary(tasks)
        self.assertEqual(s['total_delay_days'], 19)
        self.assertEqual(s['late_tasks'], 2)

    def test_claimable_days_take_the_largest_not_the_sum(self):
        # Three tasks each a fortnight late for the same late drawings is a
        # fortnight of delay, not six weeks. Summing is the commonest way an
        # EOT claim gets inflated to the point of being rejected whole.
        tasks = [self._task(i, 'T{}'.format(i), '2026-05-01', '2026-05-15',
                            cause=programme.CLIENT) for i in (1, 2, 3)]
        s = programme.delay_summary(tasks)
        self.assertEqual(s['claimable_days'], 14)

    def test_only_excusable_causes_are_claimable(self):
        own = [self._task(1, 'A', '2026-05-01', '2026-05-15',
                          cause=programme.OWN)]
        self.assertEqual(programme.delay_summary(own)['claimable_days'], 0)

        client = [self._task(1, 'A', '2026-05-01', '2026-05-15',
                             cause=programme.CLIENT)]
        self.assertEqual(programme.delay_summary(client)['claimable_days'], 14)

        sub = [self._task(1, 'A', '2026-05-01', '2026-05-15',
                          cause=programme.SUBCONTRACTOR)]
        self.assertEqual(programme.delay_summary(sub)['claimable_days'], 0)

    def test_excusable_set_is_overridable_for_a_harsher_contract(self):
        tasks = [self._task(1, 'A', '2026-05-01', '2026-05-15',
                            cause=programme.WEATHER)]
        self.assertEqual(programme.delay_summary(tasks)['claimable_days'], 14)
        strict = programme.delay_summary(tasks, excusable={programme.CLIENT})
        self.assertEqual(strict['claimable_days'], 0)

    def test_late_tasks_without_a_cause_are_counted_separately(self):
        tasks = [self._task(1, 'A', '2026-05-01', '2026-05-15', cause=''),
                 self._task(2, 'B', '2026-05-01', '2026-05-10',
                            cause=programme.CLIENT)]
        s = programme.delay_summary(tasks)
        self.assertEqual(s['unattributed_tasks'], 1)

    def test_unbaselined_tasks_are_reported_not_silently_ignored(self):
        tasks = [self._task(1, 'A', '2026-05-01', '2026-05-15'),
                 self._task(2, 'B', None, '2026-06-01')]
        s = programme.delay_summary(tasks)
        self.assertEqual(s['baselined'], 1)
        self.assertEqual(s['unbaselined'], 1)

    def test_early_programme_reports_negative_delay_and_no_late_tasks(self):
        tasks = [self._task(1, 'A', '2026-05-10', '2026-05-01')]
        s = programme.delay_summary(tasks)
        self.assertEqual(s['total_delay_days'], -9)
        self.assertEqual(s['late_tasks'], 0)

    # --- liquidated damages ---
    def test_part_weeks_count_as_whole_weeks(self):
        ld = programme.ld_exposure(10000000, 8, pct_per_week=0.5, cap_pct=10)
        self.assertEqual(ld['weeks_charged'], 2)      # 8 days -> 2 weeks
        self.assertEqual(ld['exposure'], 100000)      # 2 x 0.5% x 1 crore

    def test_exactly_seven_days_is_one_week(self):
        self.assertEqual(
            programme.ld_exposure(10000000, 7)['weeks_charged'], 1)

    def test_cap_is_applied_last_and_reported(self):
        # 60 weeks at 0.5% would be 30%; the 10% cap must bite.
        ld = programme.ld_exposure(10000000, 420, pct_per_week=0.5, cap_pct=10)
        self.assertEqual(ld['raw'], 3000000)
        self.assertEqual(ld['exposure'], 1000000)
        self.assertTrue(ld['at_cap'])

    def test_no_delay_no_exposure(self):
        ld = programme.ld_exposure(10000000, 0)
        self.assertEqual(ld['exposure'], 0)
        self.assertEqual(ld['weeks_charged'], 0)

    def test_negative_delay_cannot_produce_a_credit(self):
        self.assertEqual(programme.ld_exposure(10000000, -30)['exposure'], 0)

    def test_net_delay_subtracts_the_extension_already_granted(self):
        self.assertEqual(programme.net_delay(40, 15), 25)
        self.assertEqual(programme.net_delay(10, 30), 0)   # never negative

    # --- the whole position ---
    def test_position_shows_what_a_successful_claim_would_save(self):
        tasks = [self._task(1, 'A', '2026-05-01', '2026-05-29',
                            cause=programme.CLIENT)]      # 28 days late
        pos = programme.position(tasks, contract_value=10000000,
                                 eot_granted_days=0,
                                 pct_per_week=0.5, cap_pct=10)
        self.assertEqual(pos['total_delay_days'], 28)
        self.assertEqual(pos['net_delay_days'], 28)
        self.assertEqual(pos['claimable_days'], 28)
        self.assertEqual(pos['ld']['exposure'], 200000)    # 4 weeks
        self.assertEqual(pos['exposure_if_claim_succeeds'], 0)

    def test_granted_extension_reduces_exposure(self):
        tasks = [self._task(1, 'A', '2026-05-01', '2026-05-29')]
        pos = programme.position(tasks, contract_value=10000000,
                                 eot_granted_days=14)
        self.assertEqual(pos['net_delay_days'], 14)
        self.assertEqual(pos['ld']['exposure'], 100000)    # 2 weeks

    def test_position_on_an_empty_or_unbaselined_programme(self):
        self.assertEqual(programme.position([])['baselined'], 0)
        tasks = [self._task(1, 'A', None, '2026-06-01')]
        pos = programme.position(tasks, contract_value=10000000)
        self.assertEqual(pos['baselined'], 0)
        self.assertEqual(pos['ld']['exposure'], 0)

    # --- freezing ---
    def test_baseline_payload_skips_tasks_with_no_planned_finish(self):
        tasks = [self._task(1, 'A', None, '2026-05-01'),
                 self._task(2, 'B', None, None)]
        payload = programme.baseline_payload(tasks)
        self.assertEqual([p[0] for p in payload], [1])

    def test_rebaseline_warning_quotes_what_would_be_erased(self):
        tasks = [self._task(1, 'A', '2026-05-01', '2026-05-29',
                            cause=programme.CLIENT)]
        warn = programme.rebaseline_warning(tasks)
        self.assertEqual(warn['already_baselined'], 1)
        self.assertEqual(warn['delay_days_erased'], 28)
        self.assertEqual(warn['claimable_days_erased'], 28)

    def test_nothing_baselined_means_nothing_to_warn_about(self):
        tasks = [self._task(1, 'A', None, '2026-05-29')]
        self.assertEqual(
            programme.rebaseline_warning(tasks)['already_baselined'], 0)


class TestPlantFuel(unittest.TestCase):
    """Fuel analysis. The baseline choice is the whole design here."""

    def _log(self, day, hours, diesel, name='JCB', eid=1, operator='Ravi',
             downtime=0):
        return {'log_date': day, 'equipment': name, 'equipment_id': eid,
                'hours_run': hours, 'diesel_ltr': diesel,
                'downtime_hrs': downtime, 'operator': operator}

    def _steady(self, n=6, lph=5.0, eid=1, name='JCB'):
        return [self._log('2026-04-{:02d}'.format(i + 1), 8, 8 * lph,
                          name=name, eid=eid) for i in range(n)]

    def test_litres_per_hour(self):
        self.assertEqual(plant.litres_per_hour(8, 40), 5.0)

    def test_no_hours_gives_no_rate_rather_than_infinity(self):
        # A machine that sat still is not infinitely thirsty; that case is
        # fuel_without_work's job, where it means something specific.
        self.assertIsNone(plant.litres_per_hour(0, 40))
        self.assertIsNone(plant.litres_per_hour(None, 40))

    def test_availability(self):
        self.assertEqual(plant.availability(6, 2), 75.0)
        self.assertIsNone(plant.availability(0, 0))

    def test_machine_grouping_prefers_the_id_and_folds_name_case(self):
        rows = [self._log('2026-04-01', 8, 40, name='JCB', eid=7),
                self._log('2026-04-02', 8, 40, name='jcb', eid=None),
                self._log('2026-04-03', 8, 40, name='JCB', eid=None)]
        groups = plant.group_by_machine(rows)
        self.assertEqual(len(groups), 2)              # id 7, and 'jcb'
        self.assertEqual(len(groups[('name', 'jcb')]), 2)

    # --- outliers ---
    def test_outlier_flagged_against_the_machines_own_median(self):
        logs = self._steady(6, lph=5.0)
        logs.append(self._log('2026-04-07', 8, 8 * 9.0))    # 9 L/hr, +80%
        flagged = plant.fuel_outliers(logs)
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]['log_date'], '2026-04-07')
        self.assertEqual(flagged[0]['baseline'], 5.0)
        self.assertEqual(flagged[0]['excess_pct'], 80.0)

    def test_thirsty_machine_is_not_flagged_against_a_thrifty_one(self):
        # A JCB and a vibrator have nothing to say to each other. Judged
        # against a fleet average the JCB would be flagged every single day.
        logs = self._steady(6, lph=2.0, eid=1, name='Vibrator')
        logs += self._steady(6, lph=12.0, eid=2, name='JCB')
        self.assertEqual(plant.fuel_outliers(logs), [])

    def test_no_outliers_reported_below_the_minimum_sample(self):
        # With three logs "unusual" means nothing, and crying wolf early is
        # how a useful signal gets ignored.
        # The wild day counts toward the sample too, so build one short of the
        # threshold in total, not one short before adding it.
        logs = self._steady(plant.MIN_SAMPLE - 2, lph=5.0)
        logs.append(self._log('2026-04-20', 8, 8 * 20.0))
        self.assertEqual(len(logs), plant.MIN_SAMPLE - 1)
        self.assertEqual(plant.fuel_outliers(logs), [])

        # one more usable day and the same wild reading is reported
        logs.append(self._log('2026-04-21', 8, 8 * 5.0))
        self.assertEqual(len(plant.fuel_outliers(logs)), 1)

    def test_median_baseline_resists_the_outliers_being_hunted(self):
        # Two wild days would drag a mean up far enough to hide themselves.
        logs = self._steady(6, lph=5.0)
        logs.append(self._log('2026-04-07', 8, 8 * 30.0))
        logs.append(self._log('2026-04-08', 8, 8 * 30.0))
        flagged = plant.fuel_outliers(logs)
        self.assertEqual(len(flagged), 2)
        self.assertEqual(flagged[0]['baseline'], 5.0)

    def test_tolerance_is_configurable(self):
        logs = self._steady(6, lph=5.0)
        logs.append(self._log('2026-04-07', 8, 8 * 6.0))    # +20%
        self.assertEqual(plant.fuel_outliers(logs, tolerance_pct=30), [])
        self.assertEqual(len(plant.fuel_outliers(logs, tolerance_pct=10)), 1)

    def test_outliers_sorted_worst_first(self):
        logs = self._steady(6, lph=5.0)
        logs.append(self._log('2026-04-07', 8, 8 * 7.0))
        logs.append(self._log('2026-04-08', 8, 8 * 12.0))
        flagged = plant.fuel_outliers(logs)
        self.assertEqual([f['log_date'] for f in flagged],
                         ['2026-04-08', '2026-04-07'])

    def test_fuel_without_work_is_its_own_signal(self):
        logs = self._steady(6, lph=5.0)
        logs.append(self._log('2026-04-07', 0, 60))
        nowork = plant.fuel_without_work(logs)
        self.assertEqual(len(nowork), 1)
        self.assertEqual(nowork[0]['diesel_ltr'], 60)
        # and it does not also appear as a rate outlier
        self.assertEqual(plant.fuel_outliers(logs), [])

    def test_excess_litres_sizes_the_question(self):
        logs = self._steady(6, lph=5.0)
        logs.append(self._log('2026-04-07', 8, 8 * 9.0))
        flagged = plant.fuel_outliers(logs)
        self.assertEqual(plant.excess_litres(flagged), 32.0)   # (9-5) x 8

    def test_machine_summary(self):
        s = plant.summarise_machine(self._steady(4, lph=5.0))
        self.assertEqual(s['logs'], 4)
        self.assertEqual(s['hours'], 32)
        self.assertEqual(s['diesel'], 160)
        self.assertEqual(s['litres_per_hour'], 5.0)

    def test_empty_logs_summarise_without_error(self):
        s = plant.summarise_machine([])
        self.assertEqual(s['logs'], 0)
        self.assertIsNone(s['litres_per_hour'])
        self.assertEqual(plant.fuel_outliers([]), [])


class TestPlantMaintenance(unittest.TestCase):
    """Service falls due on hours or days, whichever comes first."""

    def _machine(self, **kw):
        m = {'id': 1, 'name': 'JCB 3DX', 'service_interval_hours': 250,
             'service_interval_days': 0, 'last_service_date': '2026-04-01'}
        m.update(kw)
        return m

    def _logs(self, days, hours_each, start='2026-04-02'):
        # Real consecutive dates — an earlier version of this helper produced
        # '2026-04-42', which the module correctly refused to parse.
        d0 = date.fromisoformat(start)
        return [{'log_date': (d0 + timedelta(days=i)).isoformat(),
                 'hours_run': hours_each, 'diesel_ltr': 0, 'downtime_hrs': 0}
                for i in range(days)]

    def test_hours_counted_only_after_the_last_service(self):
        logs = [{'log_date': '2026-03-20', 'hours_run': 100},
                {'log_date': '2026-04-05', 'hours_run': 30}]
        self.assertEqual(
            plant.hours_since_service(logs, '2026-04-01'), 30)

    def test_never_serviced_counts_everything(self):
        logs = [{'log_date': '2026-03-20', 'hours_run': 100}]
        self.assertEqual(plant.hours_since_service(logs, None), 100)

    def test_ok_then_due_then_overdue_on_hours(self):
        m = self._machine(service_interval_hours=250)
        ok = plant.service_status(m, self._logs(10, 8), as_on='2026-04-20')
        self.assertEqual(ok['status'], plant.OK)
        self.assertEqual(ok['hours_left'], 250 - 80)

        due = plant.service_status(m, self._logs(29, 8), as_on='2026-04-30')
        self.assertEqual(due['status'], plant.DUE)      # 18 hrs left of 250

        over = plant.service_status(m, self._logs(40, 8), as_on='2026-05-15')
        self.assertEqual(over['status'], plant.OVERDUE)

    def test_idle_machine_still_falls_due_on_elapsed_days(self):
        # The monsoon case: no hours at all, but the oil still ages.
        m = self._machine(service_interval_hours=0, service_interval_days=90)
        over = plant.service_status(m, [], as_on='2026-08-01')
        self.assertEqual(over['status'], plant.OVERDUE)
        self.assertLess(over['days_left'], 0)

    def test_whichever_comes_first_wins(self):
        m = self._machine(service_interval_hours=250, service_interval_days=90)
        # plenty of days left, but the hours are gone
        s = plant.service_status(m, self._logs(40, 8), as_on='2026-04-30')
        self.assertEqual(s['status'], plant.OVERDUE)

    def test_machine_with_no_schedule_is_not_claimed_to_be_fine(self):
        m = self._machine(service_interval_hours=0, service_interval_days=0)
        s = plant.service_status(m, self._logs(40, 8), as_on='2026-05-01')
        self.assertEqual(s['status'], plant.UNKNOWN)
        self.assertNotEqual(s['status'], plant.OK)

    def test_days_interval_without_a_last_service_date_cannot_be_judged(self):
        m = self._machine(service_interval_hours=0, service_interval_days=90,
                          last_service_date='')
        s = plant.service_status(m, [], as_on='2026-08-01')
        self.assertEqual(s['status'], plant.UNKNOWN)
        self.assertIsNone(s['days_left'])

    def test_due_list_is_ordered_most_urgent_first(self):
        a = plant.service_status(self._machine(id=1, name='A'),
                                 self._logs(40, 8), as_on='2026-05-15')
        b = plant.service_status(self._machine(id=2, name='B'),
                                 self._logs(31, 8), as_on='2026-05-05')
        due = plant.due_for_service([b, a])
        self.assertEqual([d['name'] for d in due], ['A', 'B'])

    def test_fleet_summary_counts_each_state(self):
        statuses = [
            plant.service_status(self._machine(id=1), self._logs(40, 8),
                                 as_on='2026-05-15'),                 # overdue
            plant.service_status(self._machine(id=2), self._logs(5, 8),
                                 as_on='2026-04-10'),                 # ok
            plant.service_status(self._machine(id=3,
                                               service_interval_hours=0),
                                 [], as_on='2026-04-10'),             # unknown
        ]
        s = plant.fleet_summary(statuses)
        self.assertEqual(s['machines'], 3)
        self.assertEqual(s['overdue'], 1)
        self.assertEqual(s['unscheduled'], 1)


class TestComplianceCalendar(unittest.TestCase):
    """Statutory due dates. The March exceptions are the point of this suite."""

    # --- financial year ---
    def test_financial_year_runs_april_to_march(self):
        self.assertEqual(compliance.current_fy('2026-04-01'), 2026)
        self.assertEqual(compliance.current_fy('2027-03-31'), 2026)
        self.assertEqual(compliance.current_fy('2026-03-31'), 2025)
        self.assertEqual(compliance.fy_label(2026), 'FY 2026-27')

    def test_fy_label_pads_the_century_rollover(self):
        self.assertEqual(compliance.fy_label(2099), 'FY 2099-00')

    def test_monthly_periods_run_april_to_march(self):
        p = compliance.periods_for_fy(compliance.MONTHLY, 2026)
        self.assertEqual(len(p), 12)
        self.assertEqual(p[0], ('2026-04', 2026, 4))
        self.assertEqual(p[-1], ('2027-03', 2027, 3))

    def test_quarters_end_jun_sep_dec_mar(self):
        p = compliance.periods_for_fy(compliance.QUARTERLY, 2026)
        self.assertEqual([(y, m) for _l, y, m in p],
                         [(2026, 6), (2026, 9), (2026, 12), (2027, 3)])

    # --- ordinary due dates ---
    def test_gst_monthly_returns(self):
        # April 2026 supplies: GSTR-1 by 11 May, GSTR-3B by 20 May.
        self.assertEqual(compliance.due_date('gstr1', 2026, 4).isoformat(),
                         '2026-05-11')
        self.assertEqual(compliance.due_date('gstr3b', 2026, 4).isoformat(),
                         '2026-05-20')

    def test_pf_and_esi_are_the_fifteenth_of_the_next_month(self):
        for key in ('pf_ecr', 'esi'):
            self.assertEqual(compliance.due_date(key, 2026, 4).isoformat(),
                             '2026-05-15')

    def test_advance_tax_falls_inside_its_own_quarter(self):
        # 15 June / 15 Sep / 15 Dec / 15 March — offset zero, not one.
        due = [compliance.due_date('advance_tax', y, m).isoformat()
               for _l, y, m in compliance.periods_for_fy(
                   compliance.QUARTERLY, 2026)]
        self.assertEqual(due, ['2026-06-15', '2026-09-15', '2026-12-15',
                               '2027-03-15'])

    def test_annual_returns(self):
        # FY 2026-27 ends March 2027: ITR 31 Jul 2027, GSTR-9 31 Dec 2027.
        self.assertEqual(compliance.due_date('itr', 2027, 3).isoformat(),
                         '2027-07-31')
        self.assertEqual(compliance.due_date('gstr9', 2027, 3).isoformat(),
                         '2027-12-31')

    # --- the exceptions people get wrong ---
    def test_march_tds_payment_is_30_april_not_7_april(self):
        self.assertEqual(compliance.due_date('tds_payment', 2026, 2).isoformat(),
                         '2026-03-07')          # ordinary month
        self.assertEqual(compliance.due_date('tds_payment', 2027, 3).isoformat(),
                         '2027-04-30')          # the March exception

    def test_q4_tds_return_is_31_may_not_30_april(self):
        self.assertEqual(compliance.due_date('tds_26q', 2026, 6).isoformat(),
                         '2026-07-31')          # Q1
        self.assertEqual(compliance.due_date('tds_26q', 2027, 3).isoformat(),
                         '2027-05-31')          # Q4

    def test_due_day_clamps_into_short_months(self):
        # A 30th-of-next-month rule against a January period lands on 28/29 Feb,
        # never rolling forward into March.
        due = compliance.due_date('bocw_cess', 2027, 1)
        self.assertEqual(due.month, 2)
        self.assertIn(due.day, (28, 29))

    def test_unknown_obligation_returns_none_rather_than_raising(self):
        self.assertIsNone(compliance.due_date('not_a_filing', 2026, 4))

    # --- applicability ---
    def test_calendar_only_includes_ticked_regimes(self):
        gst_only = compliance.calendar_for_fy(2026, {compliance.GST})
        keys = {r['obligation'] for r in gst_only}
        self.assertEqual(keys, {'gstr1', 'gstr3b', 'gstr9'})
        self.assertNotIn('pf_ecr', keys)

    def test_nothing_ticked_yields_nothing_not_everything(self):
        # Showing a sole proprietor their ESI obligations trains them to
        # ignore the calendar.
        self.assertEqual(compliance.calendar_for_fy(2026, set()), [])
        self.assertEqual(compliance.calendar_for_fy(2026, None), [])

    def test_calendar_is_sorted_by_due_date(self):
        rows = compliance.calendar_for_fy(
            2026, {compliance.GST, compliance.TDS, compliance.PF})
        self.assertEqual([r['due_date'] for r in rows],
                         sorted(r['due_date'] for r in rows))

    def test_gst_registered_firm_gets_twelve_of_each_monthly_return(self):
        rows = compliance.calendar_for_fy(2026, {compliance.GST})
        self.assertEqual(len([r for r in rows if r['obligation'] == 'gstr3b']), 12)
        self.assertEqual(len([r for r in rows if r['obligation'] == 'gstr9']), 1)

    # --- status ---
    def test_status_transitions(self):
        self.assertEqual(
            compliance.status('2026-05-20', None, as_on='2026-04-01'),
            compliance.UPCOMING)
        self.assertEqual(
            compliance.status('2026-05-20', None, as_on='2026-05-15'),
            compliance.DUE)
        self.assertEqual(
            compliance.status('2026-05-20', None, as_on='2026-05-21'),
            compliance.OVERDUE)

    def test_filed_beats_overdue_even_when_filed_late(self):
        # The calendar's job is what still needs doing; lateness is preserved
        # on the row, not in the status.
        self.assertEqual(
            compliance.status('2026-05-20', '2026-06-01', as_on='2026-07-01'),
            compliance.FILED)
        self.assertEqual(
            compliance.days_late('2026-05-20', '2026-06-01'), 12)

    def test_days_late_is_zero_when_on_time_and_none_when_unknowable(self):
        self.assertEqual(compliance.days_late('2026-05-20', '2026-05-19'), 0)
        self.assertIsNone(compliance.days_late(None))

    def test_due_on_the_day_itself_is_not_yet_overdue(self):
        self.assertEqual(
            compliance.status('2026-05-20', None, as_on='2026-05-20'),
            compliance.DUE)

    # --- roll-ups ---
    def _rows(self):
        return [{'obligation': 'gstr1', 'due_date': '2026-04-11',
                 'filed_date': '2026-04-10', 'name': 'GSTR-1'},
                {'obligation': 'gstr3b', 'due_date': '2026-04-20',
                 'filed_date': None, 'name': 'GSTR-3B'},
                {'obligation': 'pf_ecr', 'due_date': '2026-05-15',
                 'filed_date': None, 'name': 'PF'},
                {'obligation': 'esi', 'due_date': '2026-07-15',
                 'filed_date': None, 'name': 'ESI'}]

    def test_overdue_and_upcoming_partition_the_unfiled(self):
        late = compliance.overdue(self._rows(), as_on='2026-05-01')
        self.assertEqual([r['name'] for r in late], ['GSTR-3B'])

        soon = compliance.upcoming(self._rows(), within_days=30,
                                   as_on='2026-05-01')
        self.assertEqual([r['name'] for r in soon], ['PF'])   # ESI is 75 days out

    def test_summary_counts(self):
        s = compliance.summarise(self._rows(), as_on='2026-05-01')
        self.assertEqual(s['total'], 4)
        self.assertEqual(s['filed'], 1)
        self.assertEqual(s['overdue'], 1)
        self.assertEqual(s['due_soon'], 1)
        self.assertEqual(s['max_days_late'], 11)      # 20 Apr -> 1 May
        self.assertEqual(s['next']['name'], 'PF')

    def test_summary_of_an_empty_calendar(self):
        s = compliance.summarise([])
        self.assertEqual(s['total'], 0)
        self.assertEqual(s['overdue'], 0)
        self.assertIsNone(s['next'])

    def test_module_computes_no_penalties(self):
        # Late-fee and interest rates change often and vary by return; a
        # confident wrong figure is worse than days-late plus an accountant.
        src = ' '.join(dir(compliance)).lower()
        for banned in ('penalty', 'late_fee', 'latefee', 'interest'):
            self.assertNotIn(banned, src)


class TestRateAnalysis(unittest.TestCase):
    """The CPWD DAR build-up: inputs -> water -> CPOH -> per unit."""

    def _pcc_lines(self):
        # A DAR-style analysis written for 10 cum of PCC 1:4:8.
        return [{'kind': 'Material', 'description': 'Cement', 'qty': 22,
                 'rate': 380},
                {'kind': 'Material', 'description': 'Sand', 'qty': 4.6,
                 'rate': 1200},
                {'kind': 'Material', 'description': 'Aggregate', 'qty': 9.2,
                 'rate': 1400},
                {'kind': 'Labour', 'description': 'Mason', 'qty': 2,
                 'rate': 700},
                {'kind': 'Labour', 'description': 'Coolie', 'qty': 12,
                 'rate': 450}]

    def test_amounts_group_by_kind(self):
        by = rateanalysis.subtotal_by_kind(self._pcc_lines())
        self.assertEqual(by['Material'], 8360 + 5520 + 12880)
        self.assertEqual(by['Labour'], 1400 + 5400)
        self.assertEqual(by['Machinery'], 0)

    def test_unknown_kind_falls_into_sundries_rather_than_vanishing(self):
        # Silently dropping a cost line would understate the rate.
        by = rateanalysis.subtotal_by_kind(
            [{'kind': 'Mystery', 'qty': 1, 'rate': 500}])
        self.assertEqual(by['Sundries'], 500)

    def test_stated_amount_beats_qty_times_rate(self):
        by = rateanalysis.subtotal_by_kind(
            [{'kind': 'Material', 'qty': 2, 'rate': 100, 'amount': 250}])
        self.assertEqual(by['Material'], 250)

    def test_full_build_up_in_dar_order(self):
        res = rateanalysis.analyse(self._pcc_lines(), analysis_qty=10,
                                   apply_water=True)
        inputs = 8360 + 5520 + 12880 + 1400 + 5400
        self.assertEqual(res['inputs'], inputs)
        self.assertEqual(res['water'], round(inputs * 0.01, 2))
        subtotal = round(inputs * 1.01, 2)
        self.assertEqual(res['subtotal'], subtotal)
        self.assertEqual(res['cpoh'], round(subtotal * 0.15, 2))
        self.assertEqual(res['total'], round(subtotal * 1.15, 2))
        self.assertEqual(res['rate_per_unit'], round(subtotal * 1.15 / 10, 2))

    def test_water_is_off_by_default(self):
        # Defaulting water on would silently inflate every dry item by 1%.
        res = rateanalysis.analyse(self._pcc_lines(), analysis_qty=10)
        self.assertEqual(res['water'], 0)
        self.assertFalse(res['water_applied'])

    def test_cpoh_splits_into_profit_and_overhead(self):
        res = rateanalysis.analyse([{'kind': 'Material', 'amount': 10000}],
                                   analysis_qty=1)
        self.assertEqual(res['cpoh'], 1500)
        self.assertEqual(res['profit'], 750)
        self.assertEqual(res['overhead'], 750)
        self.assertEqual(res['profit'] + res['overhead'], res['cpoh'])

    def test_non_default_cpoh_still_splits_in_proportion(self):
        res = rateanalysis.analyse([{'kind': 'Material', 'amount': 10000}],
                                   analysis_qty=1, cpoh_pct=10)
        self.assertEqual(res['cpoh'], 1000)
        self.assertEqual(res['profit'] + res['overhead'], res['cpoh'])

    def test_scaffolding_is_a_lump_sum_into_sundries(self):
        res = rateanalysis.analyse([{'kind': 'Material', 'amount': 10000}],
                                   analysis_qty=1, scaffolding=500)
        self.assertEqual(res['by_kind']['Sundries'], 500)
        self.assertEqual(res['inputs'], 10500)

    def test_division_happens_once_at_the_end(self):
        # Analysing per-unit and rounding each step would drift; the DAR
        # analyses a block and divides once.
        res = rateanalysis.analyse([{'kind': 'Material', 'amount': 10000}],
                                   analysis_qty=3)
        self.assertEqual(res['total'], 11500)
        self.assertEqual(res['rate_per_unit'], round(11500 / 3, 2))

    def test_zero_analysis_quantity_gives_no_rate_rather_than_zero(self):
        # Zero would read as a real, free rate; None reads as incomplete.
        res = rateanalysis.analyse([{'kind': 'Material', 'amount': 10000}],
                                   analysis_qty=0)
        self.assertIsNone(res['rate_per_unit'])
        self.assertFalse(rateanalysis.is_complete(res))

    def test_empty_analysis_is_incomplete_not_an_error(self):
        res = rateanalysis.analyse([], analysis_qty=10)
        self.assertEqual(res['inputs'], 0)
        self.assertFalse(rateanalysis.is_complete(res))

    def test_completeness(self):
        res = rateanalysis.analyse(self._pcc_lines(), analysis_qty=10)
        self.assertTrue(rateanalysis.is_complete(res))

    # --- sanity checks ---
    def test_labour_share(self):
        res = rateanalysis.analyse(self._pcc_lines(), analysis_qty=10)
        self.assertAlmostEqual(rateanalysis.labour_share_pct(res),
                               round(6800 / 33560 * 100, 2), places=1)

    def test_warnings_catch_a_missing_cost_category(self):
        no_labour = rateanalysis.analyse(
            [{'kind': 'Material', 'amount': 1000}], analysis_qty=1)
        self.assertTrue(any('No labour' in w
                            for w in rateanalysis.warnings(no_labour)))

        no_material = rateanalysis.analyse(
            [{'kind': 'Labour', 'amount': 1000}], analysis_qty=1)
        self.assertTrue(any('No material' in w
                            for w in rateanalysis.warnings(no_material)))

    def test_warning_for_missing_analysis_quantity(self):
        res = rateanalysis.analyse([{'kind': 'Material', 'amount': 1000},
                                    {'kind': 'Labour', 'amount': 500}],
                                   analysis_qty=0)
        self.assertTrue(any('analysis quantity' in w
                            for w in rateanalysis.warnings(res)))

    def test_empty_analysis_warns_once_and_stops(self):
        res = rateanalysis.analyse([], analysis_qty=0)
        warns = rateanalysis.warnings(res)
        self.assertEqual(len(warns), 1)
        self.assertIn('No input costs', warns[0])

    def test_module_ships_no_rate_data(self):
        # The DAR's published rates are 2014-dated; shipping them as
        # authoritative would be worse than shipping none.
        # Only module scope matters: a bundled schedule would be a top-level
        # constant. Function-local structures (analyse's result dict) are
        # arithmetic, not data.
        with open(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), os.pardir,
                'construction_app', 'rateanalysis.py'), encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        big = []
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            value = node.value
            if isinstance(value, (ast.Dict, ast.List, ast.Tuple)):
                size = len(value.keys if isinstance(value, ast.Dict)
                           else value.elts)
                if size > 6:
                    big.append(node.targets[0].id)
        self.assertEqual(big, [], 'rateanalysis.py should hold arithmetic, '
                                  'not a bundled rate schedule')


class TestSecurityDeposit(unittest.TestCase):
    """The CPWD two-part security regime: guarantee up front, deposit per bill."""

    def _bills(self):
        return [{'bill_no': 'RA-1', 'value': 400000},
                {'bill_no': 'RA-2', 'value': 600000},
                {'bill_no': 'RA-3', 'value': 1000000}]

    def test_defaults_match_the_works_manual(self):
        self.assertEqual(retention.PERFORMANCE_GUARANTEE_PCT, 5.0)
        self.assertEqual(retention.SECURITY_DEPOSIT_PCT, 2.5)
        self.assertEqual(retention.BG_RELEASE_THRESHOLD, 500000.0)

    def test_performance_guarantee_is_on_the_tendered_value(self):
        self.assertEqual(retention.performance_guarantee(10000000), 500000)
        # state variation must be expressible
        self.assertEqual(retention.performance_guarantee(10000000, 10), 1000000)

    def test_deposit_accumulates_bill_by_bill(self):
        rows = retention.deposit_accrual(self._bills())
        self.assertEqual([r['deducted'] for r in rows], [10000, 15000, 25000])
        self.assertEqual([r['cumulative'] for r in rows], [10000, 25000, 50000])

    def test_a_recorded_deduction_beats_the_nominal_rate(self):
        # A part rate or a departmental adjustment makes the actual deduction
        # differ; the register must show what was really withheld.
        rows = retention.deposit_accrual(
            [{'bill_no': 'RA-1', 'value': 400000, 'deducted': 7500}])
        self.assertEqual(rows[0]['deducted'], 7500)

    def test_state_rate_of_ten_percent_is_expressible(self):
        rows = retention.deposit_accrual([{'value': 100000}], pct=10)
        self.assertEqual(rows[0]['deducted'], 10000)

    def test_no_bills_gives_an_empty_accrual_not_an_error(self):
        self.assertEqual(retention.deposit_accrual([]), [])
        self.assertEqual(retention.deposit_accrual(None), [])

    # --- bank guarantee threshold ---
    def test_bank_guarantee_threshold(self):
        under = retention.bg_release(450000)
        self.assertFalse(under['eligible'])
        self.assertEqual(under['shortfall'], 50000)

        at = retention.bg_release(500000)
        self.assertTrue(at['eligible'])           # inclusive at the mark
        self.assertEqual(at['shortfall'], 0)

    # --- the whole position ---
    def test_position_separates_guarantee_from_deposit(self):
        pos = retention.deposit_position(
            10000000, self._bills(), pg_furnished=500000)
        self.assertEqual(pos['sd_accrued'], 50000)
        self.assertEqual(pos['sd_held'], 50000)
        self.assertEqual(pos['pg_required'], 500000)
        self.assertEqual(pos['pg_shortfall'], 0)
        # both are the contractor's money tied up against the same work
        self.assertEqual(pos['total_secured'], 550000)

    def test_position_flags_a_short_performance_guarantee(self):
        pos = retention.deposit_position(10000000, [], pg_furnished=200000)
        self.assertEqual(pos['pg_shortfall'], 300000)

    def test_released_deposit_reduces_what_is_held_but_not_what_accrued(self):
        pos = retention.deposit_position(
            10000000, self._bills(), pg_furnished=500000, released=20000)
        self.assertEqual(pos['sd_accrued'], 50000)   # history is unchanged
        self.assertEqual(pos['sd_held'], 30000)
        self.assertEqual(pos['bg']['accumulated'], 30000)

    def test_over_release_never_shows_negative_held(self):
        pos = retention.deposit_position(1000000, [{'value': 100000}],
                                         released=999999)
        self.assertEqual(pos['sd_held'], 0)

    def test_bank_guarantee_eligibility_uses_what_is_still_held(self):
        # Releasing money should be able to drop you back below the threshold.
        bills = [{'value': 30000000}]              # 2.5% = 750000
        self.assertTrue(retention.deposit_position(0, bills)['bg']['eligible'])
        released = retention.deposit_position(0, bills, released=400000)
        self.assertFalse(released['bg']['eligible'])
        self.assertEqual(released['bg']['shortfall'], 150000)


class TestMusterRoll(unittest.TestCase):
    """CPWA Form 21: the nominal roll, the day grid, and unpaid wages."""

    def _worker(self, wid, name, wage=600, father='', skill='Mason'):
        return {'id': wid, 'name': name, 'father_name': father,
                'skill': skill, 'daily_wage': wage}

    def _att(self, wid, day, status='Present', hours=8):
        return {'labor_id': wid, 'att_date': day, 'status': status,
                'hours': hours}

    # --- period ---
    def test_period_is_inclusive_of_both_ends(self):
        days = muster.period_dates('2026-04-01', '2026-04-07')
        self.assertEqual(len(days), 7)
        self.assertEqual(days[0].isoformat(), '2026-04-01')
        self.assertEqual(days[-1].isoformat(), '2026-04-07')

    def test_bad_or_inverted_dates_give_an_empty_period(self):
        # A mistyped date must not spin a loop or raise mid-payroll.
        self.assertEqual(muster.period_dates('2026-04-07', '2026-04-01'), [])
        self.assertEqual(muster.period_dates('not a date', '2026-04-07'), [])
        self.assertEqual(muster.period_dates(None, None), [])

    def test_single_day_period(self):
        self.assertEqual(len(muster.period_dates('2026-04-01', '2026-04-01')), 1)

    # --- the roll ---
    def test_roll_grid_marks_each_day_and_totals_the_days(self):
        workers = [self._worker(1, 'Ramesh', 600)]
        atts = [self._att(1, '2026-04-01'),
                self._att(1, '2026-04-02', 'Half Day'),
                self._att(1, '2026-04-03', 'Absent'),
                self._att(1, '2026-04-04', 'Overtime', hours=12)]
        lines = muster.roll_lines(workers, atts, '2026-04-01', '2026-04-05')
        line = lines[0]
        self.assertEqual(line['cells'], ['P', '½', 'A', 'O', '-'])
        self.assertEqual(line['days'], 1 + 0.5 + 0 + 1.5)
        self.assertEqual(line['gross'], round(3.0 * 600, 2))

    def test_unmarked_days_show_a_dash_not_an_absence(self):
        # "Not marked" and "marked absent" are different claims on a document
        # that gets signed; the grid must not silently convert one to the other.
        lines = muster.roll_lines([self._worker(1, 'Ramesh')], [],
                                  '2026-04-01', '2026-04-03')
        self.assertEqual(lines[0]['cells'], ['-', '-', '-'])
        self.assertEqual(lines[0]['days'], 0)

    def test_worker_with_no_attendance_still_appears_on_the_roll(self):
        lines = muster.roll_lines(
            [self._worker(1, 'Ramesh'), self._worker(2, 'Suresh')],
            [self._att(1, '2026-04-01')], '2026-04-01', '2026-04-01')
        self.assertEqual([l['name'] for l in lines], ['Ramesh', 'Suresh'])

    def test_advance_is_deducted_but_never_makes_pay_negative(self):
        lines = muster.roll_lines(
            [self._worker(1, 'Ramesh', 600)],
            [self._att(1, '2026-04-01')], '2026-04-01', '2026-04-01',
            advances={1: 5000})
        self.assertEqual(lines[0]['gross'], 600)
        self.assertEqual(lines[0]['deduction'], 600)
        self.assertEqual(lines[0]['net'], 0)

    def test_roll_totals(self):
        workers = [self._worker(1, 'Ramesh', 600), self._worker(2, 'Suresh', 500)]
        atts = [self._att(1, '2026-04-01'), self._att(2, '2026-04-01')]
        total = muster.summarise_roll(
            muster.roll_lines(workers, atts, '2026-04-01', '2026-04-01'))
        self.assertEqual(total['workers'], 2)
        self.assertEqual(total['days'], 2)
        self.assertEqual(total['gross'], 1100)
        self.assertEqual(total['net'], 1100)

    # --- Form 21A ---
    def test_unpaid_register_lists_only_earners_without_a_payment(self):
        workers = [self._worker(1, 'Ramesh'), self._worker(2, 'Suresh'),
                   self._worker(3, 'Absent Ali')]
        atts = [self._att(1, '2026-04-01'), self._att(2, '2026-04-01')]
        lines = muster.roll_lines(workers, atts, '2026-04-01', '2026-04-01')

        unpaid = muster.unpaid_lines(lines, paid_ids=[1])
        self.assertEqual([l['name'] for l in unpaid], ['Suresh'])
        self.assertEqual(muster.unpaid_total(lines, [1]), 600)

    def test_absent_worker_is_not_an_unpaid_wage(self):
        # Zero earnings is an absence, not a liability; listing it would bury
        # the real unpaid amounts.
        lines = muster.roll_lines([self._worker(1, 'Ali')], [],
                                  '2026-04-01', '2026-04-01')
        self.assertEqual(muster.unpaid_lines(lines, paid_ids=[]), [])

    def test_paid_ids_match_across_int_and_string(self):
        lines = muster.roll_lines([self._worker(1, 'Ramesh')],
                                  [self._att(1, '2026-04-01')],
                                  '2026-04-01', '2026-04-01')
        self.assertEqual(muster.unpaid_lines(lines, paid_ids=['1']), [])
        self.assertEqual(muster.unpaid_lines(lines, paid_ids=[1]), [])

    # --- Part II ---
    def test_reconciliation_ratio_and_threshold(self):
        r = muster.work_reconciliation(30000, 100000)
        self.assertEqual(r['ratio_pct'], 30.0)
        self.assertEqual(r['difference'], 70000)
        self.assertFalse(r['needs_explanation'])

        high = muster.work_reconciliation(80000, 100000)
        self.assertEqual(high['ratio_pct'], 80.0)
        self.assertTrue(high['needs_explanation'])

    def test_wages_with_nothing_measured_is_flagged_not_divided_by_zero(self):
        r = muster.work_reconciliation(30000, 0)
        self.assertIsNone(r['ratio_pct'])       # undefined, not infinite
        self.assertTrue(r['unmeasured'])

    def test_no_wages_and_no_measurement_is_not_flagged(self):
        r = muster.work_reconciliation(0, 0)
        self.assertFalse(r['unmeasured'])
        self.assertFalse(r['needs_explanation'])


class TestMusterRollExport(unittest.TestCase):
    def setUp(self):
        import bill_export
        self.be = bill_export
        self.workers = [{'id': 1, 'name': 'Ramesh Kumar',
                         'father_name': 'Shyam Lal', 'skill': 'Mason',
                         'daily_wage': 600},
                        {'id': 2, 'name': 'Suresh', 'father_name': '',
                         'skill': 'Coolie', 'daily_wage': 450}]
        self.atts = [{'labor_id': 1, 'att_date': '2026-04-01',
                      'status': 'Present', 'hours': 8},
                     {'labor_id': 2, 'att_date': '2026-04-01',
                      'status': 'Half Day', 'hours': 4}]
        self.lines = muster.roll_lines(self.workers, self.atts,
                                       '2026-04-01', '2026-04-03')

    def _html(self, **kw):
        params = {'lines': self.lines,
                  'dates': muster.period_dates('2026-04-01', '2026-04-03'),
                  'start': '2026-04-01', 'end': '2026-04-03',
                  'site_name': 'Ward 7',
                  'reconciliation': muster.work_reconciliation(825, 20000)}
        params.update(kw)
        return self.be.build_muster_roll_html(**params)

    def test_roll_has_both_parts_and_the_signature_column(self):
        html = self._html()
        self.assertIn('PART I (NOMINAL ROLL)', html)
        self.assertIn('WAGES AGAINST WORK MEASURED', html)
        self.assertIn('Signature / Thumb', html)
        self.assertIn("Father's name", html)
        self.assertIn('Shyam Lal', html)

    def test_signature_column_is_left_blank_to_be_signed_on_paper(self):
        # A pre-filled acknowledgement would be worthless as evidence.
        html = self._html()
        self.assertIn('<td class="sign"></td>', html)

    def test_day_columns_match_the_period_length(self):
        html = self._html()
        header = html[html.index('<thead>'):html.index('</thead>')]
        self.assertEqual(header.count('<th class="day">'), 3)
        body = html[html.index('<tbody>'):html.index('</tbody>')]
        self.assertEqual(body.count('<td class="day">'), 6)   # 2 workers x 3

    def test_totals_row_lines_up_under_its_columns(self):
        html = self._html()
        foot = html[html.index('<tfoot>'):html.index('</tfoot>')]
        # TOTAL spans the 4 identity columns + 3 day columns
        self.assertIn('colspan="7"', foot)

    def test_unmeasured_period_is_called_out(self):
        html = self._html(reconciliation=muster.work_reconciliation(825, 0))
        self.assertIn('no work was measured', html)

    def test_high_labour_ratio_asks_for_a_reason(self):
        html = self._html(reconciliation=muster.work_reconciliation(9000, 10000))
        self.assertIn('Record the reason below', html)

    def test_empty_roll_renders(self):
        html = self._html(lines=[])
        self.assertIn('No labour on this roll', html)

    def test_names_are_escaped(self):
        lines = muster.roll_lines(
            [{'id': 1, 'name': '<b>x</b>', 'daily_wage': 100}], [],
            '2026-04-01', '2026-04-01')
        html = self._html(lines=lines)
        self.assertNotIn('<b>x</b>', html)

    # --- Form 21A ---
    def test_unpaid_register_totals_and_words(self):
        unpaid = muster.unpaid_lines(self.lines, paid_ids=[1])
        html = self.be.build_unpaid_wages_html(
            unpaid, '2026-04-01', '2026-04-03', site_name='Ward 7')
        self.assertIn('REGISTER OF UNPAID WAGES', html)
        self.assertIn('Suresh', html)
        self.assertNotIn('Ramesh', html)
        self.assertIn('225.00', html)            # 0.5 day x 450
        self.assertIn('remain payable', html)

    def test_empty_unpaid_register_says_so_plainly(self):
        html = self.be.build_unpaid_wages_html(
            [], '2026-04-01', '2026-04-03')
        self.assertIn('Nothing outstanding', html)


class TestForm26Recoveries(unittest.TestCase):
    """The RA-bill recovery block: (i) taxes (ii) security deposit (iii) other.

    The invariant that matters is that the recoveries and the net payable
    always reconstruct the bill value — if they drift, the printed memorandum
    stops adding up and the ledger posting stops balancing.
    """

    def test_all_recoveries_are_charged_on_this_bill_not_the_cumulative(self):
        t = civil.ra_bill_totals(100000, 400000, 2.5, 0, tds_pct=2, cess_pct=1)
        self.assertEqual(t['cumulative_value'], 500000)
        self.assertEqual(t['retention_amt'], 2500)   # 2.5% of 100000, not 500000
        self.assertEqual(t['tds_amt'], 2000)
        self.assertEqual(t['cess_amt'], 1000)

    def test_net_payable_is_value_less_every_recovery(self):
        t = civil.ra_bill_totals(100000, 0, 2.5, 500, tds_pct=2, cess_pct=1)
        self.assertEqual(t['total_recoveries'], 2500 + 2000 + 1000 + 500)
        self.assertEqual(t['net_payable'], 100000 - 6000)
        self.assertEqual(round(t['net_payable'] + t['total_recoveries'], 2),
                         t['this_bill_value'])

    def test_omitting_the_tax_rates_reproduces_the_old_arithmetic(self):
        # Bills raised before the tax columns existed must roll up unchanged.
        old = civil.ra_bill_totals(100000, 0, 5, 1000)
        self.assertEqual(old['tds_amt'], 0)
        self.assertEqual(old['cess_amt'], 0)
        self.assertEqual(old['net_payable'], 100000 - 5000 - 1000)

    def test_cpwd_default_security_deposit_is_two_and_a_half_percent(self):
        t = civil.ra_bill_totals(200000, 0, 2.5, 0)
        self.assertEqual(t['retention_amt'], 5000)

    # --- the posting side ---
    def test_posting_splits_recoveries_between_assets_and_expense(self):
        t = civil.ra_bill_totals(100000, 0, 2.5, 500, tds_pct=2, cess_pct=1)
        lines = posting.ra_bill_lines(
            t['this_bill_value'], t['retention_amt'], t['other_deductions'],
            t['net_payable'], tds_amt=t['tds_amt'], cess_amt=t['cess_amt'])
        by_code = {l['code']: l for l in lines}

        # retention and TDS are recoverable, so they are assets, not costs
        self.assertEqual(by_code[posting.RETENTION_RECEIVABLE]['debit'], 2500)
        self.assertEqual(by_code[posting.TDS_RECEIVABLE]['debit'], 2000)
        # cess and other genuinely are costs the contractor bears
        self.assertEqual(by_code[posting.OTHER_EXPENSE]['debit'], 1000 + 500)
        self.assertEqual(by_code[posting.RECEIVABLE]['debit'], 94000)
        self.assertEqual(by_code[posting.REVENUE]['credit'], 100000)

    def test_posting_balances_across_a_range_of_rates(self):
        for value in (1, 12345.67, 100000, 987654.32):
            for sd, tds, cess, other in ((0, 0, 0, 0), (2.5, 2, 1, 0),
                                         (10, 2, 1, 5000), (5, 0, 1, 0.01)):
                t = civil.ra_bill_totals(value, 0, sd, other,
                                         tds_pct=tds, cess_pct=cess)
                lines = posting.ra_bill_lines(
                    t['this_bill_value'], t['retention_amt'],
                    t['other_deductions'], t['net_payable'],
                    tds_amt=t['tds_amt'], cess_amt=t['cess_amt'])
                self.assertTrue(
                    posting.lines_balanced(lines),
                    'unbalanced at value={} sd={} tds={} cess={} other={}'
                    .format(value, sd, tds, cess, other))

    def test_tds_receivable_is_not_the_tds_payable_account(self):
        # Tax the client withholds from us is an asset we reclaim; tax we
        # withhold from a vendor is a liability we owe. Same word, opposite
        # side of the balance sheet.
        self.assertNotEqual(posting.TDS_RECEIVABLE, posting.TDS_PAYABLE)
        self.assertEqual(posting.TDS_RECEIVABLE, '1500')

    def test_zero_recoveries_emit_no_empty_lines(self):
        lines = posting.ra_bill_lines(100000, 0, 0, 100000)
        self.assertEqual(len(lines), 2)          # receivable + revenue only
        self.assertTrue(posting.lines_balanced(lines))


class TestForm26Memorandum(unittest.TestCase):
    """The printed memorandum must itemise recoveries and still reconcile."""

    def _html(self, **over):
        import bill_export
        bill = {'bill_no': 'RA-2', 'bill_date': '2026-05-01', 'status': 'Approved',
                'this_bill_value': 100000, 'previous_value': 400000,
                'cumulative_value': 500000, 'retention_pct': 2.5,
                'retention_amt': 2500, 'tds_pct': 2, 'tds_amt': 2000,
                'cess_pct': 1, 'cess_amt': 1000, 'other_deductions': 500,
                'net_payable': 94000}
        bill.update(over)
        return bill_export.build_ra_pwd_html(
            bill, {'contract_no': 'AG/1', 'contract_value': 5000000},
            {'name': 'PWD'}, {'name': 'Ward 7'},
            [{'item_no': '2.1', 'description': 'PCC', 'unit': 'cum',
              'boq_qty': 40, 'boq_rate': 4850, 'upto_qty': 20,
              'previous_qty': 0, 'current_qty': 20, 'rate': 4850,
              'current_amount': 97000}])

    def test_recovery_block_is_itemised_in_form_26_order(self):
        html = self._html()
        for part in ('(i) Taxes', 'Income tax deducted at source @ 2%',
                     'Labour cess @ 1%', '(ii) Security deposit @ 2.5%',
                     '(iii) Other recoveries', 'Total recoveries'):
            self.assertIn(part, html)
        self.assertLess(html.index('(i) Taxes'), html.index('(ii) Security'))
        self.assertLess(html.index('(ii) Security'), html.index('(iii) Other'))

    def test_printed_recovery_total_matches_the_parts(self):
        html = self._html()
        self.assertIn('6,000.00', html)          # 2500 + 2000 + 1000 + 500
        self.assertIn('94,000.00', html)         # net payable

    def test_bill_without_tax_columns_still_renders(self):
        # A bill row from before the migration has no tds_amt at all.
        import bill_export
        html = bill_export.build_ra_pwd_html(
            {'bill_no': 'RA-1', 'this_bill_value': 50000,
             'retention_amt': 2500, 'other_deductions': 0,
             'net_payable': 47500},
            items=[])
        self.assertIn('MEMORANDUM OF PAYMENTS', html)
        self.assertIn('2,500.00', html)


class TestMeasurementBook(unittest.TestCase):
    """Measurement book structure and the Works Manual record rules.

    The duplicate check is the one carrying money: a measurement entered twice
    is billed twice, and nothing else in the app would catch it.
    """

    def _row(self, rid, ref='12', item=1, date_='2026-04-01', desc='Footing F1',
             nos=2, length=3.0, breadth=2.0, depth=1.5, qty=None):
        return {'id': rid, 'mb_ref': ref, 'boq_item_id': item, 'mb_date': date_,
                'description': desc, 'nos': nos, 'length': length,
                'breadth': breadth, 'depth': depth,
                'quantity': qty if qty is not None else
                civil.measurement_quantity(nos, length, breadth, depth)}

    # --- CMB eligibility (Works Manual Para 7.12) ---
    def test_cmb_threshold_is_fifteen_lakh(self):
        self.assertEqual(mb.CMB_THRESHOLD, 1500000.0)
        self.assertTrue(mb.cmb_eligible(1500000))       # inclusive at the mark
        self.assertTrue(mb.cmb_eligible(2500000))
        self.assertFalse(mb.cmb_eligible(1499999))
        self.assertFalse(mb.cmb_eligible(0))
        self.assertFalse(mb.cmb_eligible(None))
        self.assertFalse(mb.cmb_eligible('not a number'))

    # --- page grouping ---
    def test_pages_keep_entry_order_not_lexical_order(self):
        rows = [self._row(1, ref='9'), self._row(2, ref='10'),
                self._row(3, ref='9'), self._row(4, ref='8A')]
        pages = mb.group_pages(rows)
        self.assertEqual([ref for ref, _ in pages], ['9', '10', '8A'])
        self.assertEqual([r['id'] for r in pages[0][1]], [1, 3])

    def test_blank_page_reference_groups_under_unnumbered(self):
        pages = mb.group_pages([self._row(1, ref=''), self._row(2, ref=None)])
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0][0], mb.UNNUMBERED)
        self.assertEqual(len(pages[0][1]), 2)

    def test_page_and_item_totals(self):
        rows = [self._row(1, item=1), self._row(2, item=1, nos=1),
                self._row(3, item=2, nos=1, length=1.0, breadth=1.0, depth=1.0)]
        self.assertEqual(mb.page_total(rows), round(18.0 + 9.0 + 1.0, 3))
        self.assertEqual(mb.item_totals(rows), {1: 27.0, 2: 1.0})

    def test_empty_book_summarises_without_error(self):
        s = mb.summarise([])
        self.assertEqual(s['entries'], 0)
        self.assertEqual(s['pages'], 0)
        self.assertEqual(s['total_quantity'], 0)
        self.assertIsNone(s['first_date'])
        self.assertTrue(mb.may_certify([]))

    # --- record integrity (Para 7.5) ---
    def test_clean_book_raises_no_issues(self):
        rows = [self._row(1), self._row(2, desc='Footing F2', item=2)]
        self.assertEqual(mb.integrity_issues(rows), [])
        self.assertTrue(mb.may_certify(rows))

    def test_identical_entry_on_same_page_is_flagged_as_duplicate(self):
        rows = [self._row(1), self._row(2)]        # same page, item, dims, desc
        dupes = [i for i in mb.integrity_issues(rows) if 'twice' in i['issue']]
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0]['id'], 2)        # the later entry is flagged
        self.assertEqual(dupes[0]['severity'], 'error')
        self.assertFalse(mb.may_certify(rows))

    def test_same_dimensions_on_a_different_page_is_not_a_duplicate(self):
        # Two identical footings genuinely measured on separate pages are
        # normal; only a repeat within one page is the double-entry error.
        rows = [self._row(1, ref='12'), self._row(2, ref='13')]
        self.assertEqual(mb.integrity_issues(rows), [])

    def test_same_dimensions_different_location_is_not_a_duplicate(self):
        rows = [self._row(1, desc='Footing F1'), self._row(2, desc='Footing F2')]
        self.assertEqual(mb.integrity_issues(rows), [])

    def test_zero_quantity_is_a_blocking_error(self):
        rows = [self._row(1, qty=0)]
        issues = mb.blocking_issues(rows)
        self.assertEqual(len(issues), 1)
        self.assertIn('blank entries', issues[0]['issue'])
        self.assertFalse(mb.may_certify(rows))

    def test_negative_quantity_is_a_blocking_error(self):
        self.assertEqual(len(mb.blocking_issues([self._row(1, qty=-5)])), 1)

    def test_missing_date_blocks_but_missing_page_ref_only_warns(self):
        undated = mb.integrity_issues([self._row(1, date_='')])
        self.assertEqual([i['severity'] for i in undated], ['error'])

        unnumbered = mb.integrity_issues([self._row(1, ref='')])
        self.assertEqual([i['severity'] for i in unnumbered], ['warning'])
        # a warning is a record lapse, not grounds to refuse the measurement
        self.assertTrue(mb.may_certify([self._row(1, ref='')]))

    def test_missing_particulars_warns(self):
        issues = mb.integrity_issues([self._row(1, desc='')])
        self.assertEqual([i['severity'] for i in issues], ['warning'])
        self.assertIn('particulars', issues[0]['issue'])

    def test_summary_counts_errors_and_warnings_separately(self):
        # Each row must be distinct in location, or the duplicate check fires
        # too and the counts under test stop meaning what they say.
        rows = [self._row(1, qty=0, desc='Footing F1'),
                self._row(2, ref='', desc='Footing F2'),
                self._row(3, desc='Footing F3')]
        s = mb.summarise(rows)
        self.assertEqual(s['entries'], 3)
        self.assertEqual(s['errors'], 1)
        self.assertEqual(s['warnings'], 1)
        self.assertEqual(s['first_date'], '2026-04-01')

    def test_date_range_spans_the_book(self):
        rows = [self._row(1, date_='2026-05-10'), self._row(2, date_='2026-04-02'),
                self._row(3, date_='2026-06-30')]
        self.assertEqual(mb.date_range(rows), ('2026-04-02', '2026-06-30'))

    def test_certificate_falls_back_to_blank_rules_when_unsigned(self):
        text = mb.certificate_text('', '', 3)
        self.assertIn('____', text)                  # a line to sign on
        self.assertIn('3 measurements', text)
        signed = mb.certificate_text('R. Kumar, AE', '2026-04-30', 1)
        self.assertIn('R. Kumar, AE', signed)
        self.assertIn('1 measurement ', signed)      # singular, not "1 measurements"

    def test_rows_may_be_sqlite_rows_with_missing_optional_columns(self):
        # The module reads rows straight from a SELECT; a data file that
        # predates the measured_by migration must not crash the check.
        import sqlite3 as sq
        conn = sq.connect(':memory:')
        conn.row_factory = sq.Row
        conn.execute('CREATE TABLE m (id INTEGER, mb_ref TEXT, mb_date TEXT, '
                     'boq_item_id INTEGER, description TEXT, nos REAL, '
                     'length REAL, breadth REAL, depth REAL, quantity REAL)')
        conn.execute("INSERT INTO m VALUES (1,'12','2026-04-01',1,'F1',2,3,2,1.5,18)")
        rows = conn.execute('SELECT * FROM m').fetchall()
        try:
            self.assertEqual(mb.integrity_issues(rows), [])
            self.assertEqual(mb.summarise(rows)['entries'], 1)
        finally:
            conn.close()


class TestMeasurementBookExport(unittest.TestCase):
    """The Form 23 document. Rendering is checked, not styled."""

    def setUp(self):
        import bill_export
        self.be = bill_export
        self.rows = [{'id': 1, 'mb_ref': '12', 'boq_item_id': 1,
                      'mb_date': '2026-04-01', 'description': 'Footing F1',
                      'nos': 2, 'length': 3.0, 'breadth': 2.0, 'depth': 1.5,
                      'quantity': 18.0, 'item_no': '2.1', 'unit': 'cum',
                      'measured_by': 'R. Kumar, AE', 'checked_by': 'S. Rao, EE',
                      'remarks': ''}]
        self.boq = [{'id': 1, 'item_no': '2.1', 'description': 'PCC 1:4:8',
                     'unit': 'cum', 'qty': 40.0}]

    def _html(self, contract_value=2500000, **kw):
        contract = {'contract_no': 'AG/2026/07', 'contract_value': contract_value,
                    'work_name': 'Construction of Anganwadi Centre',
                    'agreement_date': '2026-03-15', 'start_date': '2026-04-01',
                    'end_date': '2026-10-01'}
        params = {'contract': contract, 'client': {'name': 'PWD Division II'},
                  'site': {'name': 'Ward 7'}, 'rows': self.rows,
                  'boq_items': self.boq}
        params.update(kw)
        return self.be.build_mb_html(**params)

    def test_large_work_prints_as_a_computerised_measurement_book(self):
        html = self._html(contract_value=2500000)
        self.assertIn('COMPUTERISED MEASUREMENT BOOK', html)
        self.assertIn('Para 7.12', html)

    def test_small_work_does_not_claim_cmb_status(self):
        # Claiming CMB status below the threshold would misrepresent the
        # document to the department.
        html = self._html(contract_value=800000)
        self.assertNotIn('COMPUTERISED MEASUREMENT BOOK', html)
        self.assertIn('MEASUREMENT SHEET', html)
        self.assertIn('below the Rs 15 lakh', html)

    def test_header_carries_the_form_23_fields(self):
        html = self._html()
        for expected in ('Construction of Anganwadi Centre', 'AG/2026/07',
                         '2026-03-15', 'Name of work', 'Date of commencement'):
            self.assertIn(expected, html)

    def test_entries_totals_and_certificate_render(self):
        html = self._html()
        self.assertIn('Footing F1', html)
        self.assertIn('18.000', html)
        self.assertIn('R. Kumar, AE', html)
        self.assertIn('S. Rao, EE', html)
        self.assertIn('Measured by me on 2026-04-01', html)

    def test_abstract_shows_measured_against_tendered(self):
        html = self._html()
        self.assertIn('40.000', html)     # tendered
        self.assertIn('45.0%', html)      # 18 of 40

    def test_issues_panel_appears_only_when_there_are_issues(self):
        clean = self._html(issues=[])
        self.assertIn('Record check passed', clean)
        self.assertNotIn('RECORD CHECK', clean)

        flagged = self._html(issues=mb.integrity_issues(
            [dict(self.rows[0]), dict(self.rows[0], id=2)]))
        self.assertIn('RECORD CHECK', flagged)
        self.assertIn('billed twice', flagged)

    def test_description_is_html_escaped(self):
        rows = [dict(self.rows[0], description='<script>alert(1)</script>')]
        html = self._html(rows=rows)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_empty_book_renders_without_crashing(self):
        html = self._html(rows=[])
        self.assertIn('No measurements recorded', html)


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


class TestAdvisory(unittest.TestCase):
    """The dashboard's rule engine: severity, confidence and ranking."""

    def test_empty_snapshot_reassures_rather_than_blanks(self):
        cards = advisory.build({})
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['severity'], advisory.GOOD)
        self.assertIn('Nothing needs an action', cards[0]['title'])

    def test_overdue_receivables_is_act_high_with_a_basis(self):
        c = advisory.r_overdue_receivables(
            {'receivable_90plus': 250000, 'receivable_aged_count': 3})
        self.assertEqual(c['severity'], advisory.ACT)
        self.assertEqual(c['confidence'], advisory.HIGH)
        self.assertIn('3 invoice', c['basis'])
        self.assertTrue(c['where'])

    def test_receivables_mid_band_is_only_a_watch(self):
        c = advisory.r_overdue_receivables(
            {'receivable_90plus': 0, 'receivable_60_90': 40000})
        self.assertEqual(c['severity'], advisory.WATCH)

    def test_cash_negative_beats_thin_cash(self):
        c = advisory.r_cash_position({'cash': -5000, 'payable': 100000})
        self.assertEqual(c['severity'], advisory.ACT)
        self.assertIn('negative', c['title'].lower())

    def test_thin_cash_is_medium_confidence(self):
        # cash positive but below payables -> a soft, medium-confidence call
        c = advisory.r_cash_position({'cash': 30000, 'payable': 100000})
        self.assertEqual(c['confidence'], advisory.MEDIUM)
        self.assertIn(c['severity'], (advisory.ACT, advisory.WATCH))

    def test_plan_reliability_confidence_scales_with_weeks(self):
        thin = advisory.r_plan_reliability({'ppc_last': 50, 'ppc_weeks': 2})
        deep = advisory.r_plan_reliability({'ppc_last': 50, 'ppc_weeks': 8})
        self.assertEqual(thin['confidence'], advisory.LOW)
        self.assertEqual(deep['confidence'], advisory.MEDIUM)

    def test_good_ppc_says_nothing(self):
        self.assertIsNone(
            advisory.r_plan_reliability({'ppc_last': 92, 'ppc_weeks': 6}))

    def test_ranking_puts_act_before_watch_before_good(self):
        snap = {
            'receivable_90plus': 100000, 'receivable_aged_count': 2,  # ACT
            'approvals_count': 4, 'approvals_amount': 500000,          # WATCH
        }
        cards = advisory.build(snap)
        sev = [c['severity'] for c in cards]
        self.assertEqual(sev[0], advisory.ACT)
        self.assertLess(sev.index(advisory.ACT), sev.index(advisory.WATCH))

    def test_build_never_raises_on_a_bad_field(self):
        # a rule hitting a bad type must be skipped, not blow up the board
        cards = advisory.build({'cash': None, 'receivable_90plus': 'oops'})
        self.assertTrue(cards)   # still returns the reassuring card

    def test_counts_tallies_by_severity(self):
        cards = [{'severity': advisory.ACT, 'confidence': advisory.HIGH},
                 {'severity': advisory.ACT, 'confidence': advisory.HIGH},
                 {'severity': advisory.WATCH, 'confidence': advisory.MEDIUM}]
        tally = advisory.counts(cards)
        self.assertEqual(tally[advisory.ACT], 2)
        self.assertEqual(tally[advisory.WATCH], 1)

    def test_compliance_overdue_outranks_due_soon(self):
        overdue = advisory.r_compliance(
            {'compliance_overdue': 2, 'compliance_max_days_late': 9})
        soon = advisory.r_compliance(
            {'compliance_overdue': 0, 'compliance_due_soon': 3})
        self.assertEqual(overdue['severity'], advisory.ACT)
        self.assertEqual(soon['severity'], advisory.WATCH)


class TestReferenceData(unittest.TestCase):
    """The CPWD starter library: coherent data, correct mapping, idempotent."""

    def test_every_norm_material_exists_in_the_material_master(self):
        # a typo in a norm's material name would orphan it — catch it statically
        names = {m[0] for m in refdata.MATERIALS}
        for activity, _unit, material, _qty, _remark in refdata.NORMS:
            self.assertIn(material, names,
                          '{} references unknown material {!r}'.format(
                              activity, material))

    def test_coefficients_are_the_standard_nominal_mix_values(self):
        norm = {(a, m): q for a, _u, m, q, _r in refdata.NORMS}
        # M20 (1:1.5:3), dry-volume 1.54 -> 8.06 bags cement, 0.42/0.84 cum
        self.assertAlmostEqual(
            norm[('RCC M20 (1:1.5:3)', 'OPC 53 Grade Cement')], 8.06, places=2)
        self.assertAlmostEqual(
            norm[('RCC M20 (1:1.5:3)', 'River Sand')], 0.42, places=2)
        # 1 cum of 230mm brickwork ~ 500 modular bricks
        self.assertEqual(
            norm[('Brick masonry 230mm (CM 1:6)', 'Red Clay Brick (modular)')],
            500)

    def test_load_is_idempotent_and_maps_norms_to_real_materials(self):
        import db
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.remove(path)
        orig = db.DB_PATH
        db.DB_PATH = path
        try:
            db.init_db()
            conn = db.get_conn()
            first = refdata.load(conn)
            self.assertGreater(first['materials'], 0)
            self.assertGreater(first['norms'], 0)
            self.assertGreater(first['rate_book'], 0)
            self.assertEqual(first['analyses'], len(refdata.ANALYSES))

            # second load must add nothing
            second = refdata.load(conn)
            self.assertEqual(second,
                             {'materials': 0, 'norms': 0, 'rate_book': 0,
                              'analyses': 0})

            # no norm points at a missing material
            orphans = conn.execute(
                'SELECT COUNT(*) FROM consumption_norms n '
                'LEFT JOIN materials m ON m.id = n.material_id '
                'WHERE m.id IS NULL').fetchone()[0]
            self.assertEqual(orphans, 0)

            # every seeded analysis derived a positive per-unit rate + has items
            for r in conn.execute('SELECT id, rate_per_unit FROM rate_analysis'):
                self.assertGreater(r['rate_per_unit'], 0)
                items = conn.execute(
                    'SELECT COUNT(*) FROM rate_analysis_items '
                    'WHERE analysis_id = ?', (r['id'],)).fetchone()[0]
                self.assertGreater(items, 0)
            conn.close()
        finally:
            db.DB_PATH = orig
            for ext in ('', '-wal', '-shm'):
                try:
                    os.remove(path + ext)
                except OSError:
                    pass

    def test_load_layers_onto_existing_materials_without_duplicating(self):
        import db
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.remove(path)
        orig = db.DB_PATH
        db.DB_PATH = path
        try:
            db.init_db()
            conn = db.get_conn()
            # a book that already has one of the reference materials by name
            conn.execute("INSERT INTO materials (name, unit, category, rate) "
                         "VALUES ('OPC 53 Grade Cement', 'bag', 'Cement', 999)")
            conn.commit()
            refdata.load(conn)
            n = conn.execute("SELECT COUNT(*) FROM materials "
                             "WHERE name = 'OPC 53 Grade Cement'").fetchone()[0]
            self.assertEqual(n, 1, 'existing material was duplicated')
            conn.close()
        finally:
            db.DB_PATH = orig
            for ext in ('', '-wal', '-shm'):
                try:
                    os.remove(path + ext)
                except OSError:
                    pass


class TestPasswordSecurity(unittest.TestCase):
    """Versioned PBKDF2 hashing: round-trip, legacy upgrade, policy."""

    def test_hash_verify_roundtrip_and_versioned_format(self):
        import security
        salt, enc = security.hash_password('Correct Horse 9')
        self.assertTrue(enc.startswith('pbkdf2_sha256$600000$'))
        self.assertTrue(security.verify_password('Correct Horse 9', salt, enc))
        self.assertFalse(security.verify_password('wrong', salt, enc))
        self.assertFalse(security.needs_rehash(enc))

    def test_legacy_bare_hex_verifies_and_wants_rehash(self):
        import hashlib
        import security
        salt = os.urandom(16)
        legacy = hashlib.pbkdf2_hmac('sha256', b'oldpass', salt, 120000).hex()
        self.assertTrue(security.verify_password('oldpass', salt.hex(), legacy))
        self.assertFalse(security.verify_password('nope', salt.hex(), legacy))
        self.assertTrue(security.needs_rehash(legacy))

    def test_garbage_and_empty_are_safe(self):
        import security
        self.assertFalse(security.verify_password('x', 'zz', 'not$a$hash'))
        self.assertFalse(security.verify_password('x', '', ''))
        self.assertTrue(security.needs_rehash(''))

    def test_password_policy(self):
        import security
        self.assertTrue(security.password_issues('12345'))       # too short
        self.assertTrue(security.password_issues('99999999'))    # all digits
        self.assertTrue(security.password_issues('admin'))       # common
        self.assertEqual(security.password_issues('sitewala99'), [])


class TestAuthLogin(unittest.TestCase):
    """Login flow: create-guard, lockout, transparent hash upgrade."""

    def _db(self):
        import db
        fd, self._path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.remove(self._path)
        self._db_mod = db
        self._orig = db.DB_PATH
        db.DB_PATH = self._path
        db.init_db()
        return db.get_conn()

    def tearDown(self):
        mod = getattr(self, '_db_mod', None)
        if mod is not None:
            mod.DB_PATH = self._orig
            for ext in ('', '-wal', '-shm'):
                try:
                    os.remove(self._path + ext)
                except OSError:
                    pass

    def test_create_rejects_password_equal_to_username(self):
        import auth
        conn = self._db()
        try:
            ok, _msg = auth.create_user(conn, 'ramesh', 'ramesh', 'Admin')
            self.assertFalse(ok)
        finally:
            conn.close()

    def test_login_upgrades_a_legacy_hash_in_place(self):
        import hashlib
        import auth
        conn = self._db()
        try:
            salt = os.urandom(16)
            legacy = hashlib.pbkdf2_hmac('sha256', b'StrongPass1', salt,
                                         120000).hex()
            conn.execute(
                "INSERT INTO users (username, password_hash, salt, role, "
                "is_active, created_at) VALUES ('boss', ?, ?, 'Admin', 1, "
                "'2026-01-01')", (legacy, salt.hex()))
            conn.commit()
            ok, _msg, _u = auth.authenticate(conn, 'boss', 'StrongPass1')
            self.assertTrue(ok)
            row = conn.execute("SELECT password_hash FROM users WHERE "
                               "username = 'boss'").fetchone()
            self.assertTrue(row['password_hash'].startswith(
                'pbkdf2_sha256$600000$'))
            self.assertTrue(auth.authenticate(conn, 'boss', 'StrongPass1')[0])
        finally:
            conn.close()

    def test_lockout_after_max_failed(self):
        import auth
        conn = self._db()
        try:
            auth.create_user(conn, 'boss', 'StrongPass1', 'Admin')
            for _ in range(auth.MAX_FAILED):
                auth.authenticate(conn, 'boss', 'wrong')
            ok, _msg, _u = auth.authenticate(conn, 'boss', 'StrongPass1')
            self.assertFalse(ok, 'a locked account must reject even the right '
                                 'password')
        finally:
            conn.close()


class TestTakeoff(unittest.TestCase):
    """On-drawing quantity takeoff: geometry + scale conversion."""

    SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]

    def test_distance_and_polyline(self):
        self.assertAlmostEqual(takeoff.distance((0, 0), (3, 4)), 5.0)
        # three points -> two segments of 100 px = 200 px
        self.assertAlmostEqual(
            takeoff.polyline_length([(0, 0), (100, 0), (100, 100)]), 200.0)

    def test_shoelace_area_is_orientation_independent(self):
        self.assertAlmostEqual(takeoff.polygon_area(self.SQUARE), 10000.0)
        self.assertAlmostEqual(
            takeoff.polygon_area(list(reversed(self.SQUARE))), 10000.0)
        # a triangle: base 100, height 100 -> 5000
        self.assertAlmostEqual(
            takeoff.polygon_area([(0, 0), (100, 0), (0, 100)]), 5000.0)

    def test_scale_calibration_and_length(self):
        # a 100 px line spans 5 real metres -> 0.05 m/px
        scale = takeoff.scale_from(100, 5)
        self.assertAlmostEqual(scale, 0.05)
        self.assertAlmostEqual(
            takeoff.measure(takeoff.LENGTH, [(0, 0), (100, 0)], scale), 5.0)
        self.assertEqual(takeoff.scale_from(0, 5), 0.0)     # degenerate

    def test_area_scales_by_the_square(self):
        scale = takeoff.scale_from(100, 5)                  # 0.05 m/px
        # 10000 px^2 * 0.05^2 = 25 sqm
        self.assertAlmostEqual(
            takeoff.measure(takeoff.AREA, self.SQUARE, scale), 25.0)

    def test_volume_is_area_times_depth(self):
        scale = takeoff.scale_from(100, 5)
        self.assertAlmostEqual(
            takeoff.measure(takeoff.VOLUME, self.SQUARE, scale, depth=0.15),
            3.75)

    def test_count_and_units_and_totals(self):
        self.assertEqual(
            takeoff.measure(takeoff.COUNT, [(1, 1), (2, 2), (3, 3)]), 3.0)
        self.assertEqual(takeoff.unit_for(takeoff.AREA, 'm'), 'sqm')
        self.assertEqual(takeoff.unit_for(takeoff.VOLUME, 'ft'), 'cft')
        self.assertEqual(takeoff.unit_for(takeoff.COUNT, 'mm'), 'nos')
        totals = takeoff.totals_by_unit([
            {'unit': 'sqm', 'quantity': 25}, {'unit': 'sqm', 'quantity': 15},
            {'unit': 'nos', 'quantity': 3}])
        self.assertEqual(totals, {'sqm': 40.0, 'nos': 3.0})


class TestDesignSystem(unittest.TestCase):
    """One HCW-UI design system governs both the desktop and the web (a strict
    project rule). These lock the shared tokens to the kit and prove both skins
    are driven from them — so the two can't drift apart."""

    def test_tokens_match_the_kit(self):
        # Canonical values from hcwux/src/tokens.ts (the kit's single source of
        # truth): Radiant-Orange accent, Fog-Gray canvas, Coal ink, slate links,
        # square surfaces with 4px buttons / 8px dialogs / 3px tab alert rule.
        import tokens
        self.assertEqual(tokens.LIGHT['accent'], '#FF4F18')
        self.assertEqual(tokens.LIGHT['canvas'], '#F2F4F7')
        self.assertEqual(tokens.LIGHT['surface'], '#FFFFFF')
        self.assertEqual(tokens.LIGHT['ink'], '#141517')
        self.assertEqual(tokens.LIGHT['info'], '#3B5568')      # links = slate
        self.assertEqual(tokens.DARK['accent'], '#FF5C28')
        self.assertEqual(tokens.RADIUS, 0)
        self.assertEqual(tokens.BUTTON_RADIUS, 4)
        self.assertEqual(tokens.DIALOG_RADIUS, 8)
        self.assertEqual(tokens.TAB_ALERT_WIDTH, 3)

    def test_desktop_theme_is_token_sourced(self):
        import theme
        import tokens
        self.assertIs(theme.PALETTES['light'], tokens.LIGHT)
        self.assertIs(theme.PALETTES['dark'], tokens.DARK)

    def test_web_css_is_token_sourced(self):
        import webrender
        import tokens
        css = webrender._CSS
        # the emitted CSS must carry the token values, not hand-picked hex
        for val in (tokens.LIGHT['accent'], tokens.LIGHT['canvas'],
                    tokens.LIGHT['ink'], tokens.LIGHT['surface'],
                    tokens.DARK['accent'], tokens.DARK['canvas']):
            self.assertIn(val, css)
        # shape law: square inputs, 4px buttons, 8px dialogs
        self.assertIn('border-radius:0', css)
        self.assertIn('--r-btn:4px', css)
        self.assertIn('--r-dialog:8px', css)

    def test_no_adhoc_foreground_hex_in_app(self):
        # Every text colour must come from the palette, so it flips with the
        # theme. `tokens.py` is the one place literal hex may live.
        import glob
        pat = re.compile(r"(?:foreground|fg)\s*=\s*['\"]#[0-9A-Fa-f]{3,6}['\"]")
        app = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           os.pardir, 'construction_app')
        offenders = []
        for f in glob.glob(os.path.join(app, '*.py')):
            if os.path.basename(f) in ('tokens.py',):
                continue
            for i, line in enumerate(open(f, encoding='utf-8'), 1):
                if pat.search(line):
                    offenders.append('{}:{}'.format(os.path.basename(f), i))
        self.assertEqual(offenders, [], 'ad-hoc foreground hex (use '
                         'theme.palette()[role]): {}'.format(offenders))


class TestOllamaCatalog(unittest.TestCase):
    """The model catalogue folded in from the Ollama Manager."""

    def test_choices_and_tag_roundtrip(self):
        import ollama_catalog as cat
        self.assertTrue(cat.MODELS)
        choices = cat.choices()
        self.assertEqual(len(choices), len(cat.MODELS))
        # a dropdown label round-trips back to its bare tag
        for (tag, _sz, _note), choice in zip(cat.MODELS, choices):
            self.assertEqual(cat.tag_from_choice(choice), tag)
        # a hand-typed bare tag survives
        self.assertEqual(cat.tag_from_choice('llama3.1:8b'), 'llama3.1:8b')
        self.assertEqual(cat.tag_from_choice(''), '')
        self.assertIn(':', cat.SUGGESTED)

    def test_api_base_url_normalises(self):
        import ollama_api as api
        self.assertEqual(api.base_url('localhost'),
                         'http://localhost:11434')
        self.assertEqual(api.base_url('http://127.0.0.1:11434'),
                         'http://127.0.0.1:11434')
        self.assertEqual(api.human_size(0), '0 B')
        self.assertTrue(api.human_size(5 * 1024 ** 3).endswith('GB'))

    def test_suggested_is_the_inbuilt_default(self):
        # The catalogue's default and the assistant's default must be the same
        # model, and it must be a real entry in the list.
        import ollama_catalog as cat
        import ollama_client as client
        self.assertEqual(cat.SUGGESTED, client.DEFAULT_MODEL)
        self.assertIn(cat.SUGGESTED, [tag for tag, _s, _n in cat.MODELS])


class TestModelProvision(unittest.TestCase):
    """Offline registration of the inbuilt model — the pure, Ollama-free parts:
    locating the bundle, building the import command, deciding 'already there'."""

    def test_registered_matches_tag_or_bare_base(self):
        import model_provision as mp
        self.assertTrue(mp.is_registered(['qwen2.5-coder:1.5b']))
        self.assertTrue(mp.is_registered(['qwen2.5-coder']))          # bare base
        self.assertTrue(mp.is_registered(['llama3.2:1b',
                                          'qwen2.5-coder:1.5b']))
        self.assertFalse(mp.is_registered(['llama3.2:1b']))
        self.assertFalse(mp.is_registered([]))
        self.assertFalse(mp.is_registered(None))

    def test_create_command_shape(self):
        import model_provision as mp
        cmd = mp.create_command(ollama='C:/x/ollama.exe')
        self.assertEqual(cmd[:3], ['C:/x/ollama.exe', 'create', mp.MODEL_NAME])
        self.assertIn('-f', cmd)

    def test_bundled_detects_modelfile_plus_gguf(self):
        import model_provision as mp
        import shutil
        d = tempfile.mkdtemp()
        orig = mp.ai_dir
        try:
            mp.ai_dir = lambda: d            # point the locator at a temp dir
            self.assertFalse(mp.bundled())   # nothing there yet
            open(os.path.join(d, mp.MODELFILE_NAME), 'w').close()
            self.assertFalse(mp.bundled())   # Modelfile alone is not enough
            open(os.path.join(d, mp.GGUF_NAME), 'w').close()
            self.assertTrue(mp.bundled())    # both present -> this build has it
            self.assertTrue(mp.modelfile_path().startswith(d))
            self.assertTrue(mp.gguf_path().endswith(mp.GGUF_NAME))
        finally:
            mp.ai_dir = orig                 # undo the monkeypatch
            shutil.rmtree(d, ignore_errors=True)

    def test_modelfile_is_committed_and_points_at_the_gguf(self):
        # The Modelfile ships in the repo (installer\ai); the GGUF does not.
        import model_provision as mp
        here = os.path.dirname(os.path.abspath(__file__))
        mf = os.path.join(here, os.pardir, 'installer', 'ai', 'Modelfile')
        self.assertTrue(os.path.exists(mf))
        text = open(mf, encoding='utf-8').read()
        self.assertIn(mp.GGUF_NAME, text)
        self.assertIn('FROM', text)


class TestScheduler(unittest.TestCase):
    """The working-calendar scheduling engine: calendar, typed deps, critical
    path, WBS, cycles."""

    START = '2026-01-05'      # a Monday; default work week is Mon-Sat

    def _sched(self, tasks, **kw):
        kw.setdefault('project_start', self.START)
        return scheduler.schedule(tasks, **kw)

    def test_fs_chain_skips_sundays_and_finds_critical_path(self):
        r = self._sched([
            {'id': 1, 'task_name': 'A', 'duration_days': 5, 'dependency': ''},
            {'id': 2, 'task_name': 'B', 'duration_days': 3, 'dependency': '1'},
            {'id': 3, 'task_name': 'C', 'duration_days': 1, 'dependency': '1'},
            {'id': 4, 'task_name': 'D', 'duration_days': 2, 'dependency': '2,3'},
        ])
        t = r['tasks']
        self.assertEqual(t[1]['start_date'], '2026-01-05')
        self.assertEqual(t[1]['finish_date'], '2026-01-09')
        # B starts the working day after A — Sat 10 (Sun 11 is off)
        self.assertEqual(t[2]['start_date'], '2026-01-10')
        self.assertEqual(t[2]['finish_date'], '2026-01-13')  # Sat,Mon,Tue
        self.assertEqual(sorted(r['critical_ids']), [1, 2, 4])
        self.assertFalse(t[3]['critical'])
        self.assertAlmostEqual(t[3]['total_float'], 2.0)

    def test_start_to_start_with_lag(self):
        r = self._sched([
            {'id': 1, 'task_name': 'A', 'duration_days': 5, 'dependency': ''},
            {'id': 2, 'task_name': 'B', 'duration_days': 2,
             'dependency': '1SS+1'},
        ])
        self.assertEqual(r['tasks'][2]['start_date'], '2026-01-06')

    def test_predecessor_parsing(self):
        self.assertEqual(
            scheduler.parse_predecessors('3FS+2, 5SS-1; 7'),
            [('3', 'FS', 2), ('5', 'SS', -1), ('7', 'FS', 0)])

    def test_milestone_is_zero_length(self):
        r = self._sched([
            {'id': 1, 'task_name': 'A', 'duration_days': 4, 'dependency': ''},
            {'id': 2, 'task_name': 'M', 'duration_days': 0, 'dependency': '1'},
        ])
        m = r['tasks'][2]
        self.assertTrue(m['milestone'])
        self.assertEqual(m['start_date'], m['finish_date'])

    def test_holiday_is_skipped(self):
        r = self._sched(
            [{'id': 1, 'task_name': 'A', 'duration_days': 3, 'dependency': ''}],
            holidays=['2026-01-07'])
        # Mon 5, Tue 6, [Wed 7 holiday], Thu 8 -> finish Thu 8
        self.assertEqual(r['tasks'][1]['finish_date'], '2026-01-08')

    def test_wbs_parent_spans_children_and_weights_progress(self):
        r = self._sched([
            {'id': 10, 'task_name': 'Phase', 'duration_days': 0,
             'dependency': ''},
            {'id': 11, 'task_name': 'x', 'duration_days': 4, 'dependency': '',
             'parent_id': 10, 'pct_complete': 100},
            {'id': 12, 'task_name': 'y', 'duration_days': 6, 'dependency': '11',
             'parent_id': 10, 'pct_complete': 50},
        ])
        p = r['tasks'][10]
        self.assertTrue(p.get('is_summary'))
        self.assertEqual(p['start_date'], r['tasks'][11]['start_date'])
        self.assertEqual(p['finish_date'], r['tasks'][12]['finish_date'])
        self.assertAlmostEqual(p['pct'], 70.0)      # (4*100 + 6*50) / 10

    def test_cycle_is_reported_not_scheduled(self):
        r = self._sched([
            {'id': 1, 'task_name': 'A', 'duration_days': 2, 'dependency': '2'},
            {'id': 2, 'task_name': 'B', 'duration_days': 2, 'dependency': '1'},
        ])
        self.assertEqual(sorted(r['cycle']), [1, 2])
        self.assertEqual(r['tasks'], {})

    def test_name_reference_and_unresolved(self):
        r = self._sched([
            {'id': 1, 'task_name': 'Excavation', 'duration_days': 3,
             'dependency': ''},
            {'id': 2, 'task_name': 'PCC', 'duration_days': 2,
             'dependency': 'Excavation, Ghost'},
        ])
        # Excavation (dur 3) runs Mon-Wed 5-7; PCC starts the next working day
        self.assertEqual(r['tasks'][2]['start_date'], '2026-01-08')
        self.assertIn((2, 'Ghost'), r['unresolved'])


class TestFirmLogo(unittest.TestCase):
    """The firm's uploaded logo overrides the bundled logo on printed docs."""

    def setUp(self):
        import assets
        self.assets = assets
        self._tmp = tempfile.mkdtemp()
        # point the data dir at a throwaway folder so we never touch the source
        self._orig_data_dir = assets.paths.data_dir
        assets.paths.data_dir = lambda: self._tmp

    def tearDown(self):
        self.assets.paths.data_dir = self._orig_data_dir
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _png_bytes(self):
        # a valid 1x1 PNG (signature + minimal chunks) is enough for the check
        import assets
        with open(assets.LOGO_SQUARE, 'rb') as fh:
            return fh.read()

    def test_set_get_clear_and_signature_check(self):
        import os as _os
        src = _os.path.join(self._tmp, 'src.png')
        with open(src, 'wb') as fh:
            fh.write(self._png_bytes())
        self.assertIsNone(self.assets.firm_logo_path())
        ok, _msg = self.assets.set_firm_logo(src)
        self.assertTrue(ok)
        self.assertIsNotNone(self.assets.firm_logo_path())
        self.assertIn('data:image/png;base64,', self.assets.brand_logo_html())
        self.assets.clear_firm_logo()
        self.assertIsNone(self.assets.firm_logo_path())

    def test_rejects_non_image(self):
        import os as _os
        bad = _os.path.join(self._tmp, 'notimage.png')
        with open(bad, 'wb') as fh:
            fh.write(b'this is not an image')
        ok, msg = self.assets.set_firm_logo(bad)
        self.assertFalse(ok)
        self.assertIn('PNG', msg)

    def test_brand_logo_falls_back_to_bundled_when_unset(self):
        # no firm logo -> the bundled app logo is used (non-empty <img>)
        self.assertIn('<img', self.assets.brand_logo_html())

    def test_mime_sniffing(self):
        self.assertEqual(self.assets._mime_for(b'\xff\xd8\xff\xe0'), 'image/jpeg')
        self.assertEqual(self.assets._mime_for(b'GIF89a...'), 'image/gif')
        self.assertEqual(
            self.assets._mime_for(b'\x89PNG\r\n\x1a\n'), 'image/png')


class TestLogoTint(unittest.TestCase):
    """The stdlib PNG recolour that makes the dark logo readable on the dark
    rail — lift dark pixels to near-white, keep the alpha."""

    def test_dark_logo_lifts_to_near_white_keeping_alpha(self):
        import struct
        import zlib
        import assets
        import logo_tint
        fd, dst = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        try:
            lifted = logo_tint.tint_dark_to_light(assets.LOGO_RECT, dst)
            self.assertGreater(lifted, 0)
            with open(dst, 'rb') as fh:
                ihdr, idat = logo_tint._read_chunks(fh.read())
            w, h, bd, ct, _c, _f, it = struct.unpack('>IIBBBBB', ihdr)
            self.assertEqual((bd, ct, it), (8, 6, 0))     # still 8-bit RGBA
            px = logo_tint._unfilter(zlib.decompress(idat), w, h, 4)
            opaque = [px[i] for i in range(0, len(px), 4) if px[i + 3] > 200]
            transparent = sum(1 for i in range(0, len(px), 4)
                              if px[i + 3] == 0)
            self.assertTrue(opaque)
            self.assertTrue(all(v >= 200 for v in opaque),
                            'opaque pixels should be lifted, not left dark')
            self.assertGreater(transparent, 0, 'alpha must be preserved')
        finally:
            try:
                os.remove(dst)
            except OSError:
                pass

    def test_unsupported_input_raises(self):
        import logo_tint
        fd, p = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        with open(p, 'wb') as fh:
            fh.write(b'this is not a png')
        try:
            with self.assertRaises(logo_tint.Unsupported):
                logo_tint.tint_dark_to_light(p, p + '.out')
        finally:
            for q in (p, p + '.out'):
                try:
                    os.remove(q)
                except OSError:
                    pass


class TestTabModuleImports(unittest.TestCase):
    """Guard against a module using a distinctive analytics module it forgot to
    import — a bug that stays hidden until data reaches that code path (as the
    KPI tab's ``projectcost.portfolio`` call did until a project existed).

    Uses the AST so only real ``module.attr`` code counts — the same word in a
    docstring or string literal is ignored."""

    # Distinctive enough to never plausibly be a local variable.
    RISKY = frozenset(('projectcost', 'cashflow', 'programme', 'cpm'))

    def test_distinctive_modules_are_imported_where_used(self):
        app = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           os.pardir, 'construction_app')
        for path in glob.glob(os.path.join(app, '*.py')):
            stem = os.path.splitext(os.path.basename(path))[0]
            with open(path, encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
            used, imported = set(), set()
            for node in ast.walk(tree):
                if (isinstance(node, ast.Attribute)
                        and isinstance(node.value, ast.Name)
                        and node.value.id in self.RISKY):
                    used.add(node.value.id)         # a real `module.attr` call
                elif isinstance(node, ast.Import):  # covers nested imports too
                    for a in node.names:
                        imported.add((a.asname or a.name).split('.')[0])
            for mod in used:
                if mod == stem:
                    continue
                self.assertIn(
                    mod, imported,
                    '{}.py uses {}. but never imports it'.format(stem, mod))


if __name__ == '__main__':
    unittest.main(verbosity=2)
