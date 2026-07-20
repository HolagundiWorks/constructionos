"""Pure civil-engineering / contracting maths.

No tkinter, no database — measurement-book quantity calc, RA (Running Account)
bill quantity splitting, material consumption reconciliation, and concrete-cube
strength. Kept separate from ``finance.py`` (tax/accounting) so the civil
formulas can be unit-tested and exercised with ``python -c``.

Money/qty are floats throughout; these helpers round at their boundaries.
"""


def dim_factor(value):
    """One dimension of a measurement-book line.

    Blank/None means "not applicable" and contributes a factor of 1 (so a
    running-metre item measured as Nos x Length leaves Breadth/Depth blank). A
    supplied number — including 0 — is used as-is.
    """
    if value is None:
        return 1.0
    s = str(value).strip()
    if s == '':
        return 1.0
    return float(s)


def measurement_quantity(nos, length, breadth, depth):
    """Measurement-book content = Nos x L x B x D, blanks counting as 1."""
    q = (dim_factor(nos) * dim_factor(length)
         * dim_factor(breadth) * dim_factor(depth))
    return round(q, 3)


def ra_current(upto_qty, previous_qty, rate):
    """Current-bill quantity & amount for one BOQ item in an RA bill.

    ``upto_qty`` is the cumulative measured quantity to date; ``previous_qty``
    is what earlier RA bills already billed. Current = upto - previous (may be
    negative if a measurement was revised down). Returns (current_qty, amount).
    """
    current = round(float(upto_qty or 0) - float(previous_qty or 0), 3)
    amount = round(current * float(rate or 0), 2)
    return current, amount


def ra_bill_totals(this_bill_value, previous_value, retention_pct,
                   other_deductions, tds_pct=0, cess_pct=0):
    """Roll RA-bill item amounts up to the payable figures.

        cumulative_value = previous_value + this_bill_value
        retention_amt    = this_bill_value * retention_pct / 100
        tds_amt          = this_bill_value * tds_pct / 100
        cess_amt         = this_bill_value * cess_pct / 100
        net_payable      = this_bill_value
                           - retention_amt - tds_amt - cess_amt
                           - other_deductions

    The three percentage recoveries make up the statutory recovery block of a
    CPWA Form 26 running account bill: taxes (income-tax TDS and labour cess),
    security deposit (the retention line), and other. All three are charged on
    the value of work done **in this bill**, not the cumulative value, because
    earlier bills already recovered against their own value.

    ``tds_pct`` and ``cess_pct`` default to zero so bills raised before those
    columns existed roll up exactly as they did before.
    """
    this_bill_value = round(float(this_bill_value or 0), 2)
    previous_value = round(float(previous_value or 0), 2)
    retention = round(this_bill_value * float(retention_pct or 0) / 100.0, 2)
    tds = round(this_bill_value * float(tds_pct or 0) / 100.0, 2)
    cess = round(this_bill_value * float(cess_pct or 0) / 100.0, 2)
    other = round(float(other_deductions or 0), 2)
    net = round(this_bill_value - retention - tds - cess - other, 2)
    return {
        'this_bill_value': this_bill_value,
        'previous_value': previous_value,
        'cumulative_value': round(previous_value + this_bill_value, 2),
        'retention_amt': retention,
        'tds_amt': tds,
        'cess_amt': cess,
        'other_deductions': other,
        'total_recoveries': round(retention + tds + cess + other, 2),
        'net_payable': net,
    }


def deviation_row(boq_qty, executed_qty, rate):
    """Deviation of executed vs tendered quantity for one BOQ item.

    ``executed_qty`` is the cumulative (upto-date) measured quantity. Positive
    deviation = excess over tender, negative = saving. ``deviation_pct`` is
    against the tendered quantity (None when the tendered qty is 0, e.g. an
    extra item). ``amount_effect`` prices the deviation at the BOQ rate.
    """
    boq_qty = round(float(boq_qty or 0), 3)
    executed_qty = round(float(executed_qty or 0), 3)
    dev = round(executed_qty - boq_qty, 3)
    pct = round(dev / boq_qty * 100.0, 2) if boq_qty else None
    return {'boq_qty': boq_qty, 'executed_qty': executed_qty,
            'deviation_qty': dev, 'deviation_pct': pct,
            'amount_effect': round(dev * float(rate or 0), 2)}


def reconcile_consumption(theoretical, actual):
    """Theoretical vs actual material consumption.

    variance = actual - theoretical (positive => over-consumption / wastage);
    wastage_pct is variance as a percentage of theoretical (None if no
    theoretical basis).
    """
    theoretical = round(float(theoretical or 0), 3)
    actual = round(float(actual or 0), 3)
    variance = round(actual - theoretical, 3)
    pct = round(variance / theoretical * 100.0, 2) if theoretical else None
    return {'theoretical': theoretical, 'actual': actual,
            'variance': variance, 'wastage_pct': pct}


def deviation(tender_qty, executed_qty, rate):
    """PWD deviation statement line: tendered vs executed for one BOQ item.

        deviation_qty    = executed_qty - tender_qty  (+ excess / - saving)
        tender_amount    = tender_qty  * rate
        executed_amount  = executed_qty * rate
        deviation_amount = deviation_qty * rate
        status           = 'Excess' / 'Saving' / 'As per BOQ'
    """
    tq = round(float(tender_qty or 0), 3)
    eq = round(float(executed_qty or 0), 3)
    rate = round(float(rate or 0), 2)
    dq = round(eq - tq, 3)
    if dq > 0:
        status = 'Excess'
    elif dq < 0:
        status = 'Saving'
    else:
        status = 'As per BOQ'
    return {
        'tender_qty': tq, 'executed_qty': eq, 'deviation_qty': dq,
        'tender_amount': round(tq * rate, 2),
        'executed_amount': round(eq * rate, 2),
        'deviation_amount': round(dq * rate, 2),
        'status': status,
    }


def cube_area(side_mm=150):
    """Cross-section area of a standard concrete test cube (default 150 mm)."""
    return float(side_mm) * float(side_mm)


def cube_strength(load_kn, area_mm2):
    """Compressive strength (MPa = N/mm^2) from failure load (kN) and area.

    strength = load(N) / area(mm^2) = load_kn * 1000 / area_mm2.
    """
    area = float(area_mm2 or 0)
    if not area:
        return 0.0
    return round(float(load_kn or 0) * 1000.0 / area, 2)


def grade_target(grade):
    """Characteristic strength (MPa) parsed from a grade label like 'M20'.

    Returns the leading integer after the 'M' (or 0 if unparseable).
    """
    if grade is None:
        return 0.0
    digits = ''.join(ch for ch in str(grade) if ch.isdigit())
    return float(digits) if digits else 0.0


def cube_result(strength_mpa, grade):
    """Pass/Fail against the grade's characteristic strength.

    A simple per-cube check (strength >= target); statistical acceptance over a
    sample set is out of scope. Returns 'Pass', 'Fail', or '-' (no target).
    """
    target = grade_target(grade)
    if not target:
        return '-'
    return 'Pass' if float(strength_mpa or 0) >= target else 'Fail'
