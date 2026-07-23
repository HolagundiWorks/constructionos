"""DB bridge for P&L / Balance Sheet (CT-7).

``reports.py`` is pure (no DB). This module loads per-account debit/credit
totals from the journal — optionally filtered by period or as-of date — and
hands them to ``reports.profit_and_loss`` / ``reports.balance_sheet``.

No tkinter.
"""

from datetime import date
import re

import numbering
import reports


def _fy_bounds(fy_label):
    """'2025-26' → ('2025-04-01', '2026-03-31'). Empty on bad input."""
    m = re.match(r'^(\d{4})-(\d{2})$', str(fy_label or '').strip())
    if not m:
        return None, None
    start_y = int(m.group(1))
    return '{}-04-01'.format(start_y), '{}-03-31'.format(start_y + 1)


def account_totals(conn, period=None, as_of=None):
    """Per-account debit/credit totals, optionally date-filtered.

    ``period``:
      - ``YYYY-MM`` — journal entry dates in that month
      - ``FY`` / ``fy`` — current financial year (Apr–Mar)
      - ``YYYY-YY`` (e.g. ``2025-26``) — that FY
      - blank — all posted lines (desktop parity)

    ``as_of`` (``YYYY-MM-DD``) further restricts to ``entry_date <= as_of``
    (Balance Sheet point-in-time). Ignored when empty.
    """
    period = (period or '').strip()
    as_of = (as_of or '').strip() or None
    filters = []
    params = []
    if period:
        if period.upper() == 'FY':
            period = numbering.financial_year(date.today().isoformat())
        if len(period) == 7 and period[4] == '-':  # YYYY-MM
            filters.append("substr(je.entry_date, 1, 7) = ?")
            params.append(period)
        else:
            start, end = _fy_bounds(period)
            if start and end:
                filters.append('je.entry_date >= ? AND je.entry_date <= ?')
                params.extend([start, end])
    if as_of:
        filters.append('je.entry_date <= ?')
        params.append(as_of)

    if filters:
        # Subquery keeps accounts with zero activity in-range (LEFT JOIN).
        sub = (
            'SELECT jl.account_id AS account_id, jl.debit AS debit, '
            'jl.credit AS credit FROM journal_lines jl '
            'JOIN journal_entries je ON je.id = jl.journal_entry_id '
            'WHERE ' + ' AND '.join(filters)
        )
        sql = (
            'SELECT a.code, a.name, a.type, '
            'COALESCE(SUM(x.debit), 0) AS debit, '
            'COALESCE(SUM(x.credit), 0) AS credit '
            'FROM accounts a LEFT JOIN ({}) x ON x.account_id = a.id '
            'GROUP BY a.id ORDER BY a.code'
        ).format(sub)
        return conn.execute(sql, params).fetchall()

    return conn.execute(
        'SELECT a.code, a.name, a.type, '
        'COALESCE(SUM(jl.debit), 0) AS debit, '
        'COALESCE(SUM(jl.credit), 0) AS credit '
        'FROM accounts a LEFT JOIN journal_lines jl ON jl.account_id = a.id '
        'GROUP BY a.id ORDER BY a.code'
    ).fetchall()


def _section(title, lines, total):
    return {
        'title': title,
        'cols': ['Particulars', 'Amount'],
        'rows': [[name, amt] for name, amt in lines],
        'total': total,
    }


def pnl_payload(conn, period=None):
    """JSON-ready P&L: sections + grand_total (net profit)."""
    pl = reports.profit_and_loss(account_totals(conn, period=period))
    sections = [
        _section('Income', pl['income'], pl['total_income']),
        _section('Expenses', pl['expense'], pl['total_expense']),
    ]
    return {
        'period': period or '',
        'sections': sections,
        'total_income': pl['total_income'],
        'total_expense': pl['total_expense'],
        'grand_total': pl['net_profit'],
        'net_profit': pl['net_profit'],
    }


def balance_sheet_payload(conn, as_of=None, period=None):
    """JSON-ready Balance Sheet; ``balanced`` mirrors reports.balance_sheet."""
    rows = account_totals(conn, period=period, as_of=as_of)
    bs = reports.balance_sheet(rows)
    sections = [
        _section('Assets', bs['assets'], bs['total_assets']),
        _section('Liabilities', bs['liabilities'], bs['total_liabilities']),
        _section('Equity', bs['equity'], bs['total_equity']),
    ]
    return {
        'as_of': as_of or '',
        'period': period or '',
        'sections': sections,
        'total_assets': bs['total_assets'],
        'total_liabilities': bs['total_liabilities'],
        'total_equity': bs['total_equity'],
        'total_liabilities_equity': bs['total_liabilities_equity'],
        'grand_total': bs['total_assets'],
        'balanced': bs['balanced'],
    }
