"""Pure cash / party-balance helpers (Phase 1 — cash-first for T2/T3 contractors).

No tkinter, no database. The contractor thinks in "paisa aaya / paisa gaya" and
"kitna baaki", so these helpers speak that language: signed cash movement, a
running balance for a day/cash book, and party outstanding. Testable with
``python -c``.
"""


def money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def signed_cash(direction, amount):
    """Money movement as a signed number: Receipt is +, Payment is -."""
    amt = money(amount)
    return amt if direction == 'Receipt' else -amt


def running_balance(signed_amounts, opening=0.0):
    """Turn a sequence of signed amounts into cumulative balances.

    Returns a list the same length as the input; element i is the balance after
    applying amounts[0..i] to ``opening``.
    """
    balance = money(opening)
    out = []
    for amt in signed_amounts:
        balance = money(balance + money(amt))
        out.append(balance)
    return out


def closing_balance(signed_amounts, opening=0.0):
    balances = running_balance(signed_amounts, opening)
    return balances[-1] if balances else money(opening)


def party_outstanding(billed, settled):
    """How much a party still owes (or is owed).

    For a client: billed = value of bills raised, settled = receipts collected;
    positive result = the client still owes us. For a vendor: billed = invoices
    booked, settled = payments made; positive = we still owe the vendor.
    """
    return money(money(billed) - money(settled))


def profit_margin(revenue, cost):
    """Profit and margin% for a site/job. Margin is profit as a % of revenue."""
    revenue = money(revenue)
    cost = money(cost)
    profit = money(revenue - cost)
    margin = round(profit / revenue * 100.0, 1) if revenue else None
    return {'revenue': revenue, 'cost': cost, 'profit': profit, 'margin_pct': margin}
