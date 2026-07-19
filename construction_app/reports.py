"""Pure financial-statement builders on the double-entry ledger (Phase 7).

No tkinter, no database. Given per-account debit/credit totals (the same rows
the trial balance is built from), assemble a **Profit & Loss** and a **Balance
Sheet**. These are the "for the CA" statements — the contractor runs the
business on the cash-first views, but at year end the ledger should produce a
clean P&L and a balance sheet that ties out.

Account rows are dicts/tuples exposing ``type`` (Asset/Liability/Income/Expense/
Equity), ``name``, and ``debit`` / ``credit`` totals. Uses ``finance.account_net``
so the normal-balance sign convention matches the rest of the app. Testable with
``python -c``.
"""

import finance


def _get(row, key, idx):
    """Read a field from a dict-like row or a positional tuple."""
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return row[idx]


def _rows(accounts):
    """Normalise input rows to (name, type, debit, credit)."""
    out = []
    for a in accounts:
        out.append((_get(a, 'name', 0), _get(a, 'type', 1),
                    finance.money(_get(a, 'debit', 2)),
                    finance.money(_get(a, 'credit', 3))))
    return out


def profit_and_loss(accounts):
    """Income vs expense -> lines + totals + net_profit.

    Income lines carry their credit-normal balance, expense lines their
    debit-normal balance (both positive in the usual case). ``net_profit`` =
    total income - total expense (negative = loss).
    """
    income, expense = [], []
    total_income = total_expense = 0.0
    for name, typ, d, c in _rows(accounts):
        if typ == 'Income':
            amt = finance.account_net(d, c, 'Income')
            if amt:
                income.append((name, amt)); total_income += amt
        elif typ == 'Expense':
            amt = finance.account_net(d, c, 'Expense')
            if amt:
                expense.append((name, amt)); total_expense += amt
    total_income = finance.money(total_income)
    total_expense = finance.money(total_expense)
    return {
        'income': income,
        'expense': expense,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': finance.money(total_income - total_expense),
    }


def balance_sheet(accounts, net_profit=None):
    """Assets vs liabilities + equity -> lines + totals + a balance check.

    ``net_profit`` (from :func:`profit_and_loss`) is folded into equity as
    "Retained Earnings (current period)" so the sheet ties out; pass None to
    compute it from the same rows. ``balanced`` is True when total assets equal
    total liabilities + equity within a paisa.
    """
    if net_profit is None:
        net_profit = profit_and_loss(accounts)['net_profit']
    assets, liabilities, equity = [], [], []
    ta = tl = te = 0.0
    for name, typ, d, c in _rows(accounts):
        if typ == 'Asset':
            amt = finance.account_net(d, c, 'Asset')
            if amt:
                assets.append((name, amt)); ta += amt
        elif typ == 'Liability':
            amt = finance.account_net(d, c, 'Liability')
            if amt:
                liabilities.append((name, amt)); tl += amt
        elif typ == 'Equity':
            amt = finance.account_net(d, c, 'Equity')
            if amt:
                equity.append((name, amt)); te += amt
    net_profit = finance.money(net_profit)
    if net_profit:
        equity.append(('Retained Earnings (current period)', net_profit))
        te += net_profit
    ta = finance.money(ta); tl = finance.money(tl); te = finance.money(te)
    return {
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'total_assets': ta,
        'total_liabilities': tl,
        'total_equity': te,
        'total_liabilities_equity': finance.money(tl + te),
        'balanced': finance.is_balanced(ta, tl + te),
    }
