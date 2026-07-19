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


def statutory_deduction(gross, pf_pct=0.0, esi_pct=0.0, cess_pct=0.0):
    """Optional PF / ESI / labour-cess amounts on a gross wage.

    All percentages default to 0 (= off): most T2/T3 site labour is informal,
    so these only apply when the contractor sets them in the Tools settings.
    """
    gross = float(gross or 0)
    pf = round(gross * float(pf_pct or 0) / 100.0, 2)
    esi = round(gross * float(esi_pct or 0) / 100.0, 2)
    cess = round(gross * float(cess_pct or 0) / 100.0, 2)
    return {'pf': pf, 'esi': esi, 'cess': cess,
            'total': round(pf + esi + cess, 2)}


def wage_net_full(days, daily_wage, advance_balance=0.0, pf_pct=0.0,
                  esi_pct=0.0, cess_pct=0.0):
    """``wage_net`` plus the optional statutory deductions.

    Statutory amounts come off the gross first; the advance recovery is then
    capped at what remains, so net pay is never negative. With all
    percentages 0 this reduces exactly to ``wage_net`` (plus a ``statutory``
    key of 0.0). The ``deduction`` key is the advance recovered — callers rely
    on it to mark advances recovered — capped at the post-statutory balance.
    """
    days = float(days or 0)
    daily_wage = float(daily_wage or 0)
    gross = round(days * daily_wage, 2)
    stat = statutory_deduction(gross, pf_pct, esi_pct, cess_pct)
    after_stat = max(round(gross - stat['total'], 2), 0.0)
    deduction = round(min(max(float(advance_balance or 0), 0.0), after_stat), 2)
    return {'gross': gross, 'statutory': stat['total'],
            'deduction': deduction,
            'net': round(after_stat - deduction, 2)}
