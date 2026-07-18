"""Pure wage maths (Phase 3 — labour).

Shared by the muster roll, weekly payout, and monthly payroll so the "days
present" rule and the gross/deduction/net computation live in exactly one
testable place (no tkinter, no database).
"""


def day_fraction(status, hours):
    """Attendance status -> fractional days present.

    Present = 1.0, Half Day = 0.5, Absent = 0.0, and Overtime = a full day plus
    a pro-rata bonus for hours beyond 8 (1 + max(0, hours-8)/8).
    """
    if status == 'Present':
        return 1.0
    if status == 'Half Day':
        return 0.5
    if status == 'Overtime':
        try:
            h = float(hours)
        except (TypeError, ValueError):
            h = 8.0
        return 1.0 + max(0.0, h - 8.0) / 8.0
    return 0.0


def wage_net(days, daily_wage, advance_balance=0.0):
    """Gross / deduction / net for one worker over a period.

    gross = days * daily_wage; deduction = min(open advance balance, gross) so
    net pay is never negative; net = gross - deduction.
    """
    days = float(days or 0)
    daily_wage = float(daily_wage or 0)
    gross = round(days * daily_wage, 2)
    deduction = round(min(max(float(advance_balance or 0), 0.0), gross), 2)
    return {'gross': gross, 'deduction': deduction,
            'net': round(gross - deduction, 2)}


def allocate_recovery(advances, deduction):
    """Split a payout's advance deduction across open advances, oldest first.

    ``advances`` is an iterable of ``(advance_id, amount, recovered)`` in the
    order recovery should apply (pass them oldest first). Returns a list of
    ``(advance_id, recover_now, new_recovered, closed)`` — one entry per
    advance that absorbs part of the deduction; already-covered advances are
    skipped and allocation stops once the deduction is used up. ``closed`` is
    True when the advance is fully recovered after this allocation.
    """
    remaining = round(max(float(deduction or 0), 0.0), 2)
    out = []
    for adv_id, amount, recovered in advances:
        if remaining <= 0:
            break
        amount = round(float(amount or 0), 2)
        recovered = round(float(recovered or 0), 2)
        open_amt = round(amount - recovered, 2)
        if open_amt <= 0:
            continue
        take = round(min(open_amt, remaining), 2)
        new_recovered = round(recovered + take, 2)
        out.append((adv_id, take, new_recovered, new_recovered >= amount))
        remaining = round(remaining - take, 2)
    return out
