"""Per-party balances — billed vs settled ("baaki"), receivable or payable.

Lifts the aggregation out of the ``tab_insight`` GUI callback into a pure,
testable store so the desktop, web and WinUI all read the same figures. No
tkinter. All arithmetic goes through ``money`` (rounds at the boundary; returns
an honest number, never a fake zero for "undefined").

  - **receivable** — clients: (approved/paid bills + RA bills) vs client receipts
  - **payable**   — vendors: vendor invoices vs vendor payments

A party with no billing and no settlement is dropped (nothing to show). Rows are
sorted by outstanding, largest first.
"""

import money


def _sum_map(conn, sql):
    out = {}
    for pid, total in conn.execute(sql):
        if pid is not None:
            out[pid] = total or 0
    return out


def party_balances(conn, mode='receivable'):
    """``[{party_id, party, billed, settled, outstanding}]`` for one side."""
    if (mode or 'receivable').lower() == 'payable':
        parties = conn.execute(
            'SELECT id, name FROM vendors ORDER BY name').fetchall()
        billed = _sum_map(
            conn,
            "SELECT vendor_id, SUM(net_payable) FROM vendor_invoices "
            "GROUP BY vendor_id")
        settled = _sum_map(
            conn,
            "SELECT party_id, SUM(amount) FROM payments "
            "WHERE direction = 'Payment' AND party_type = 'Vendor' "
            "AND party_id IS NOT NULL GROUP BY party_id")
    else:
        parties = conn.execute(
            'SELECT id, name FROM clients ORDER BY name').fetchall()
        billed = _sum_map(
            conn,
            "SELECT c.client_id, SUM(b.net_payable) FROM bills b "
            "JOIN contracts c ON c.id = b.contract_id "
            "WHERE b.status IN ('Approved','Paid') GROUP BY c.client_id")
        for k, v in _sum_map(
                conn,
                "SELECT c.client_id, SUM(r.net_payable) FROM ra_bills r "
                "JOIN contracts c ON c.id = r.contract_id "
                "WHERE r.status IN ('Approved','Paid') "
                "GROUP BY c.client_id").items():
            billed[k] = (billed.get(k, 0) or 0) + (v or 0)
        settled = _sum_map(
            conn,
            "SELECT party_id, SUM(amount) FROM payments "
            "WHERE direction = 'Receipt' AND party_type = 'Client' "
            "AND party_id IS NOT NULL GROUP BY party_id")

    rows = []
    for p in parties:
        billed_amt = billed.get(p['id'], 0) or 0
        settled_amt = settled.get(p['id'], 0) or 0
        if billed_amt == 0 and settled_amt == 0:
            continue
        rows.append({
            'party_id': p['id'],
            'party': p['name'],
            'billed': money.money(billed_amt),
            'settled': money.money(settled_amt),
            'outstanding': money.party_outstanding(billed_amt, settled_amt),
        })
    rows.sort(key=lambda r: r['outstanding'], reverse=True)
    return rows


def summary(conn):
    """Both sides + their totals, for the Cash & Parties page."""
    recv = party_balances(conn, 'receivable')
    pay = party_balances(conn, 'payable')
    return {
        'receivable': recv,
        'payable': pay,
        'total_receivable': money.money(sum(r['outstanding'] for r in recv)),
        'total_payable': money.money(sum(r['outstanding'] for r in pay)),
    }
