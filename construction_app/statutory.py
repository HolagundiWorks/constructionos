"""Pure statutory labour-deduction maths (Phase 3 — optional, off by default).

Most T2/T3 site labour is informal, so these never touch the day-to-day muster
or payout. They exist for the contractor who *does* have to file: EPF, ESI, and
the BOCW (building & other construction workers) welfare cess. All plain
functions with standard default rates the caller can override; exercised with
``python -c``.

Defaults reflect common Indian rates (rates/ceilings change — treat as editable):
    PF   12% of wages, on a wage ceiling of 15,000.
    ESI  0.75% employee + 3.25% employer, only if monthly wage <= 21,000.
    Cess 1% of the cost of construction (BOCW welfare cess).
"""


def money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def pf(wage, rate=12.0, ceiling=15000.0):
    """Provident-fund contribution = rate% of wages, capped at ``ceiling``.

    A ``ceiling`` of 0/None means no cap. Returns the employee contribution
    (the employer matches it separately in practice).
    """
    wage = money(wage)
    base = min(wage, money(ceiling)) if ceiling else wage
    return money(base * float(rate or 0) / 100.0)


def esi(wage, employee_rate=0.75, employer_rate=3.25, threshold=21000.0):
    """ESI split. Applies only when monthly wage <= ``threshold`` (0 = always).

    Returns employee, employer, and total contributions (all 0 above threshold).
    """
    wage = money(wage)
    if threshold and wage > money(threshold):
        return {'employee': 0.0, 'employer': 0.0, 'total': 0.0}
    ee = money(wage * float(employee_rate or 0) / 100.0)
    er = money(wage * float(employer_rate or 0) / 100.0)
    return {'employee': ee, 'employer': er, 'total': money(ee + er)}


def labour_cess(construction_value, rate=1.0):
    """BOCW welfare cess = rate% of the cost of construction."""
    return money(money(construction_value) * float(rate or 0) / 100.0)
