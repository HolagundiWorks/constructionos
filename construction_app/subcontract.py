"""Pure subcontractor / work-order billing maths (Phase 7).

No tkinter, no database. A subcontractor's running bill is like a client RA
bill but *payable by us*: from the value of work done this bill we withhold
retention and deduct TDS (works-contract TDS on the sub), plus any other
deduction, leaving the net payable to the subcontractor. Reuses ``civil`` for
the RA split and ``finance`` for the TDS. Testable with ``python -c``.
"""

import civil
import finance


def sub_bill_totals(this_bill_value, previous_value, retention_pct, tds_pct,
                    other_deductions=0):
    """Roll a subcontractor bill up to the payable figures.

        cumulative_value = previous_value + this_bill_value
        retention_amt    = this_bill_value * retention_pct / 100
        tds_amount       = this_bill_value * tds_pct / 100   (on the work value)
        net_payable      = this_bill_value - retention - tds - other_deductions
    """
    ra = civil.ra_bill_totals(this_bill_value, previous_value, retention_pct,
                              other_deductions)
    tds = finance.compute_tds(ra['this_bill_value'], tds_pct)
    net = finance.money(ra['net_payable'] - tds)
    return {
        'this_bill_value': ra['this_bill_value'],
        'previous_value': ra['previous_value'],
        'cumulative_value': ra['cumulative_value'],
        'retention_amt': ra['retention_amt'],
        'tds_amount': tds,
        'net_payable': net,
    }
