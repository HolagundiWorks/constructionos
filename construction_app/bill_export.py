"""Printable bill document generator.

``build_bill_html`` is a pure function (no tkinter, no database) that renders a
running bill — header, party details, BOQ line items, and the running-bill
computation summary — into a self-contained, printable HTML string. It is kept
separate from ``tab_billing`` so it can be unit-tested and exercised with
``python -c`` without a display.

The GUI side (``BillingTab.make_bill``) fetches the rows, calls this, writes the
result to a file, and opens it in the browser where the user can print or
"Save as PDF" — the stdlib-only way to fill the "no PDF/print export" gap noted
in AGENTS.md §12.
"""

from datetime import date
from html import escape

import finance
import numwords


def _money(value):
    """Format a number as a grouped 2-decimal amount (e.g. 1,234.50)."""
    try:
        return '{:,.2f}'.format(float(value or 0))
    except (TypeError, ValueError):
        return '0.00'


def _text(value):
    return escape('' if value is None else str(value))


def build_bill_html(bill, contract=None, client=None, site=None, items=None,
                    company_name='Contractor-OS'):
    """Render a bill to a printable HTML string.

    Every argument is a mapping (e.g. ``sqlite3.Row`` or dict) or ``None``.
    ``items`` is an iterable of row mappings with description/unit/qty/rate/
    amount keys. Missing pieces degrade gracefully to '-'.
    """
    bill = bill or {}
    items = list(items or [])

    def g(row, key, default=''):
        if row is None:
            return default
        try:
            val = row[key]
        except (KeyError, IndexError, TypeError):
            return default
        return default if val is None else val

    contract_no = g(contract, 'contract_no') or (
        'Contract #{}'.format(g(bill, 'contract_id')) if g(bill, 'contract_id')
        else '-')

    # --- line item rows ---
    if items:
        item_rows = []
        for idx, it in enumerate(items, start=1):
            item_rows.append(
                '<tr>'
                '<td class="num">{}</td>'
                '<td>{}</td>'
                '<td>{}</td>'
                '<td class="num">{}</td>'
                '<td class="num">{}</td>'
                '<td class="num">{}</td>'
                '</tr>'.format(
                    idx, _text(g(it, 'description')), _text(g(it, 'unit')),
                    _money(g(it, 'qty')), _money(g(it, 'rate')),
                    _money(g(it, 'amount'))))
        items_total = sum(float(g(it, 'amount', 0) or 0) for it in items)
        item_rows.append(
            '<tr class="items-total">'
            '<td colspan="5">Items Total</td>'
            '<td class="num">{}</td></tr>'.format(_money(items_total)))
        items_html = ''.join(item_rows)
    else:
        items_html = ('<tr><td colspan="6" class="muted">'
                      'No line items recorded.</td></tr>')

    # --- running-bill computation summary ---
    summary_rows = [
        ('Work Done Value', g(bill, 'work_done_value', 0), False),
        ('Less: Previously Billed', g(bill, 'previous_billed', 0), True),
        ('Less: Retention', g(bill, 'retention_amt', 0), True),
        ('Less: Other Deductions', g(bill, 'other_deductions', 0), True),
    ]
    summary_html = ''.join(
        '<tr><td>{}</td><td class="num">{}{}</td></tr>'.format(
            _text(label), '- ' if is_deduction and float(amount or 0) else '',
            _money(amount))
        for label, amount, is_deduction in summary_rows)

    generated = date.today().isoformat()

    return _TEMPLATE.format(
        company=_text(company_name),
        bill_no=_text(g(bill, 'bill_no') or '-'),
        bill_date=_text(g(bill, 'bill_date') or '-'),
        status=_text(g(bill, 'status') or '-'),
        contract_no=_text(contract_no),
        contract_value=_money(g(contract, 'contract_value', 0)),
        client_name=_text(g(client, 'name') or '-'),
        client_address=_text(g(client, 'address') or '-'),
        client_phone=_text(g(client, 'phone') or '-'),
        site_name=_text(g(site, 'name') or '-'),
        site_location=_text(g(site, 'location') or '-'),
        items_html=items_html,
        summary_html=summary_html,
        net_payable=_money(g(bill, 'net_payable', 0)),
        remarks=_text(g(bill, 'remarks') or ''),
        generated=_text(generated),
    )


def build_ra_bill_html(bill, contract=None, client=None, site=None, items=None,
                       company_name='Contractor-OS'):
    """Render a measurement-driven RA (Running Account) bill abstract.

    ``items`` is an iterable of row mappings with item_no/description/unit/
    upto_qty/previous_qty/current_qty/rate/current_amount keys (as produced by
    ``ra_bill_items`` joined to ``boq_items``).
    """
    bill = bill or {}
    items = list(items or [])

    def g(row, key, default=''):
        if row is None:
            return default
        try:
            val = row[key]
        except (KeyError, IndexError, TypeError):
            return default
        return default if val is None else val

    rows = []
    for it in items:
        rows.append(
            '<tr>'
            '<td>{}</td><td>{}</td><td>{}</td>'
            '<td class="num">{}</td><td class="num">{}</td>'
            '<td class="num">{}</td><td class="num">{}</td>'
            '<td class="num">{}</td>'
            '</tr>'.format(
                _text(g(it, 'item_no')), _text(g(it, 'description')),
                _text(g(it, 'unit')),
                _money(g(it, 'upto_qty')), _money(g(it, 'previous_qty')),
                _money(g(it, 'current_qty')), _money(g(it, 'rate')),
                _money(g(it, 'current_amount'))))
    items_html = ''.join(rows) or (
        '<tr><td colspan="8" class="muted">No billed items.</td></tr>')

    return _RA_TEMPLATE.format(
        company=_text(company_name),
        bill_no=_text(g(bill, 'bill_no') or '-'),
        bill_date=_text(g(bill, 'bill_date') or '-'),
        status=_text(g(bill, 'status') or '-'),
        contract_no=_text(g(contract, 'contract_no') or '-'),
        client_name=_text(g(client, 'name') or '-'),
        site_name=_text(g(site, 'name') or '-'),
        items_html=items_html,
        this_bill_value=_money(g(bill, 'this_bill_value', 0)),
        previous_value=_money(g(bill, 'previous_value', 0)),
        cumulative_value=_money(g(bill, 'cumulative_value', 0)),
        retention_amt=_money(g(bill, 'retention_amt', 0)),
        other_deductions=_money(g(bill, 'other_deductions', 0)),
        net_payable=_money(g(bill, 'net_payable', 0)),
        generated=_text(date.today().isoformat()),
    )


_RA_TEMPLATE = """<meta charset="utf-8">
<title>RA Bill {bill_no}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color: #1a1a1a;
         margin: 28px; font-size: 12px; }}
  h1 {{ margin: 0; font-size: 20px; }}
  .doc-title {{ color: #555; font-size: 13px; letter-spacing: .5px; }}
  .head {{ display: flex; justify-content: space-between;
           border-bottom: 2px solid #333; padding-bottom: 10px;
           margin-bottom: 14px; }}
  .meta td {{ padding: 2px 8px 2px 0; }}
  .meta td.k {{ color: #666; }}
  table.items {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  table.items th, table.items td {{ border: 1px solid #ccc; padding: 5px 7px;
                                    text-align: left; }}
  table.items th {{ background: #f2f4f7; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .muted {{ color: #999; text-align: center; font-style: italic; }}
  .summary {{ margin-top: 18px; width: 320px; margin-left: auto; }}
  .summary table {{ width: 100%; border-collapse: collapse; }}
  .summary td {{ padding: 4px 8px; border-bottom: 1px solid #eee; }}
  .summary tr.net td {{ border-top: 2px solid #333; border-bottom: none;
                        font-size: 14px; font-weight: bold; }}
  .foot {{ margin-top: 36px; color: #999; font-size: 11px;
           border-top: 1px solid #eee; padding-top: 8px; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
<div class="head">
  <div><h1>{company}</h1><div class="doc-title">RUNNING ACCOUNT BILL</div></div>
  <table class="meta">
    <tr><td class="k">RA Bill No</td><td>{bill_no}</td></tr>
    <tr><td class="k">Date</td><td>{bill_date}</td></tr>
    <tr><td class="k">Status</td><td>{status}</td></tr>
    <tr><td class="k">Contract</td><td>{contract_no}</td></tr>
    <tr><td class="k">Client</td><td>{client_name}</td></tr>
    <tr><td class="k">Site</td><td>{site_name}</td></tr>
  </table>
</div>

<table class="items">
  <thead>
    <tr>
      <th>Item</th><th>Description</th><th>Unit</th>
      <th class="num">Qty Upto Date</th><th class="num">Prev Qty</th>
      <th class="num">This Bill Qty</th><th class="num">Rate</th>
      <th class="num">Amount</th>
    </tr>
  </thead>
  <tbody>{items_html}</tbody>
</table>

<div class="summary">
  <table>
    <tr><td>Value of Work This Bill</td><td class="num">{this_bill_value}</td></tr>
    <tr><td>Previous Value</td><td class="num">{previous_value}</td></tr>
    <tr><td>Cumulative Value</td><td class="num">{cumulative_value}</td></tr>
    <tr><td>Less: Retention</td><td class="num">{retention_amt}</td></tr>
    <tr><td>Less: Other Deductions</td><td class="num">{other_deductions}</td></tr>
    <tr class="net"><td>Net Payable</td><td class="num">{net_payable}</td></tr>
  </table>
</div>

<div class="foot">Generated by {company} on {generated}. Quantities from the
Measurement Book; figures in the project's base currency.</div>
"""


_TEMPLATE = """<meta charset="utf-8">
<title>Bill {bill_no}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color: #1a1a1a;
         margin: 32px; font-size: 13px; }}
  h1 {{ margin: 0; font-size: 22px; }}
  .doc-title {{ color: #555; font-size: 14px; letter-spacing: .5px; }}
  .head {{ display: flex; justify-content: space-between;
           align-items: flex-start; border-bottom: 2px solid #333;
           padding-bottom: 12px; margin-bottom: 16px; }}
  .meta td {{ padding: 2px 8px 2px 0; }}
  .meta td.k {{ color: #666; }}
  .parties {{ display: flex; gap: 24px; margin: 16px 0; }}
  .parties .box {{ flex: 1; border: 1px solid #ddd; border-radius: 6px;
                   padding: 10px 12px; }}
  .parties h3 {{ margin: 0 0 6px; font-size: 12px; text-transform: uppercase;
                 color: #666; letter-spacing: .5px; }}
  table.items {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  table.items th, table.items td {{ border: 1px solid #ccc; padding: 6px 8px;
                                    text-align: left; }}
  table.items th {{ background: #f2f4f7; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tr.items-total td {{ font-weight: bold; background: #fafafa; }}
  .muted {{ color: #999; text-align: center; font-style: italic; }}
  .summary {{ margin-top: 20px; width: 340px; margin-left: auto; }}
  .summary table {{ width: 100%; border-collapse: collapse; }}
  .summary td {{ padding: 5px 8px; border-bottom: 1px solid #eee; }}
  .summary tr.net td {{ border-top: 2px solid #333; border-bottom: none;
                        font-size: 15px; font-weight: bold; padding-top: 8px; }}
  .remarks {{ margin-top: 20px; padding: 10px 12px; background: #f8f8f8;
              border-left: 3px solid #bbb; white-space: pre-wrap; }}
  .foot {{ margin-top: 40px; color: #999; font-size: 11px;
           border-top: 1px solid #eee; padding-top: 8px; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
<div class="head">
  <div>
    <h1>{company}</h1>
    <div class="doc-title">RUNNING BILL</div>
  </div>
  <table class="meta">
    <tr><td class="k">Bill No</td><td>{bill_no}</td></tr>
    <tr><td class="k">Date</td><td>{bill_date}</td></tr>
    <tr><td class="k">Status</td><td>{status}</td></tr>
  </table>
</div>

<div class="parties">
  <div class="box">
    <h3>Client</h3>
    <div><strong>{client_name}</strong></div>
    <div>{client_address}</div>
    <div>{client_phone}</div>
  </div>
  <div class="box">
    <h3>Contract / Site</h3>
    <div><strong>{contract_no}</strong></div>
    <div>Contract Value: {contract_value}</div>
    <div>Site: {site_name}</div>
    <div>{site_location}</div>
  </div>
</div>

<table class="items">
  <thead>
    <tr>
      <th class="num">#</th><th>Description</th><th>Unit</th>
      <th class="num">Qty</th><th class="num">Rate</th><th class="num">Amount</th>
    </tr>
  </thead>
  <tbody>{items_html}</tbody>
</table>

<div class="summary">
  <table>
    {summary_html}
    <tr class="net"><td>Net Payable</td><td class="num">{net_payable}</td></tr>
  </table>
</div>

<div class="remarks">Remarks: {remarks}</div>

<div class="foot">Generated by {company} on {generated}. Figures are in the
project's base currency.</div>
"""


def build_tax_invoice_html(invoice, client=None, items=None, seller=None,
                           company_name='Contractor-OS'):
    """Render a GST tax invoice (outward, to a client).

    ``invoice`` needs invoice_no/invoice_date/place_of_supply/interstate/gst_pct/
    subtotal/notes. ``items`` rows carry description/hsn_code/unit/qty/rate/
    amount. GST is split into CGST+SGST (intra-state) or IGST (inter-state) via
    ``finance.split_gst``; the total is shown in words via ``numwords``.
    ``seller`` is an optional dict of the contractor's own details (name/gstin/
    address).
    """
    invoice = invoice or {}
    items = list(items or [])
    seller = seller or {}

    def g(row, key, default=''):
        if row is None:
            return default
        try:
            val = row[key]
        except (KeyError, IndexError, TypeError):
            return default
        return default if val is None else val

    interstate = bool(g(invoice, 'interstate', 0))
    subtotal = 0.0
    rows = []
    for idx, it in enumerate(items, start=1):
        amt = float(g(it, 'amount', 0) or 0)
        subtotal += amt
        rows.append(
            '<tr><td class="num">{}</td><td>{}</td><td>{}</td><td>{}</td>'
            '<td class="num">{}</td><td class="num">{}</td><td class="num">{}</td></tr>'.format(
                idx, _text(g(it, 'description')), _text(g(it, 'hsn_code')),
                _text(g(it, 'unit')), _money(g(it, 'qty')), _money(g(it, 'rate')),
                _money(amt)))
    items_html = ''.join(rows) or (
        '<tr><td colspan="7" class="muted">No items.</td></tr>')

    gst = finance.split_gst(subtotal, g(invoice, 'gst_pct', 0), interstate)
    total = round(subtotal + gst['total_tax'], 2)

    if interstate:
        tax_rows = ('<tr><td>IGST</td><td class="num">{}</td></tr>'.format(
            _money(gst['igst'])))
    else:
        tax_rows = ('<tr><td>CGST</td><td class="num">{}</td></tr>'
                    '<tr><td>SGST</td><td class="num">{}</td></tr>'.format(
                        _money(gst['cgst']), _money(gst['sgst'])))

    return _TAX_TEMPLATE.format(
        company=_text(company_name),
        seller_gstin=_text(g(seller, 'gstin') or '—'),
        seller_addr=_text(g(seller, 'address') or ''),
        invoice_no=_text(g(invoice, 'invoice_no') or '-'),
        invoice_date=_text(g(invoice, 'invoice_date') or '-'),
        place_of_supply=_text(g(invoice, 'place_of_supply') or '-'),
        supply_type='Inter-state (IGST)' if interstate else 'Intra-state (CGST+SGST)',
        client_name=_text(g(client, 'name') or '-'),
        client_addr=_text(g(client, 'address') or ''),
        client_gstin=_text(g(client, 'gst_no') or '—'),
        items_html=items_html,
        subtotal=_money(subtotal),
        tax_rows=tax_rows,
        total=_money(total),
        total_words=_text(numwords.rupees_in_words(total)),
        notes=_text(g(invoice, 'notes') or ''),
        generated=_text(date.today().isoformat()),
    )


_TAX_TEMPLATE = """<meta charset="utf-8">
<title>Tax Invoice {invoice_no}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color: #1a1a1a;
         margin: 28px; font-size: 12px; }}
  h1 {{ margin: 0; font-size: 20px; }}
  .doc-title {{ text-align: center; font-size: 14px; letter-spacing: 1px;
                border: 1px solid #333; padding: 4px; margin: 8px 0 14px; }}
  .head {{ display: flex; justify-content: space-between;
           border-bottom: 2px solid #333; padding-bottom: 10px; }}
  .meta td {{ padding: 2px 8px 2px 0; }}
  .meta td.k {{ color: #666; }}
  .parties {{ display: flex; gap: 20px; margin: 14px 0; }}
  .parties .box {{ flex: 1; border: 1px solid #ddd; border-radius: 6px;
                   padding: 8px 10px; }}
  .parties h3 {{ margin: 0 0 4px; font-size: 11px; text-transform: uppercase;
                 color: #666; }}
  table.items {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  table.items th, table.items td {{ border: 1px solid #ccc; padding: 5px 7px;
                                    text-align: left; }}
  table.items th {{ background: #f2f4f7; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .muted {{ color: #999; text-align: center; font-style: italic; }}
  .summary {{ margin-top: 14px; width: 300px; margin-left: auto; }}
  .summary table {{ width: 100%; border-collapse: collapse; }}
  .summary td {{ padding: 4px 8px; border-bottom: 1px solid #eee; }}
  .summary tr.total td {{ border-top: 2px solid #333; font-size: 14px;
                          font-weight: bold; }}
  .words {{ margin-top: 10px; font-style: italic; }}
  .foot {{ margin-top: 30px; color: #999; font-size: 11px;
           border-top: 1px solid #eee; padding-top: 8px; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
<div class="head">
  <div>
    <h1>{company}</h1>
    <div>GSTIN: {seller_gstin}</div>
    <div>{seller_addr}</div>
  </div>
  <table class="meta">
    <tr><td class="k">Invoice No</td><td>{invoice_no}</td></tr>
    <tr><td class="k">Date</td><td>{invoice_date}</td></tr>
    <tr><td class="k">Place of Supply</td><td>{place_of_supply}</td></tr>
    <tr><td class="k">Supply</td><td>{supply_type}</td></tr>
  </table>
</div>
<div class="doc-title">TAX INVOICE</div>

<div class="parties">
  <div class="box">
    <h3>Bill To</h3>
    <div><strong>{client_name}</strong></div>
    <div>{client_addr}</div>
    <div>GSTIN: {client_gstin}</div>
  </div>
</div>

<table class="items">
  <thead>
    <tr><th class="num">#</th><th>Description</th><th>HSN/SAC</th><th>Unit</th>
    <th class="num">Qty</th><th class="num">Rate</th><th class="num">Amount</th></tr>
  </thead>
  <tbody>{items_html}</tbody>
</table>

<div class="summary">
  <table>
    <tr><td>Taxable Value</td><td class="num">{subtotal}</td></tr>
    {tax_rows}
    <tr class="total"><td>Total</td><td class="num">{total}</td></tr>
  </table>
</div>
<div class="words"><strong>Amount in words:</strong> {total_words}</div>
<div class="words">{notes}</div>

<div class="foot">Generated by {company} on {generated}. This is a
computer-generated tax invoice.</div>
"""


def build_statement_html(title, meta_lines, headers, rows, summary='',
                         company_name='Contractor-OS'):
    """Generic printable statement (party ledger, cash book, etc.).

    ``meta_lines`` is a list of strings shown under the title; ``headers`` a list
    of column titles; ``rows`` a list of same-length string tuples (pre-formatted
    by the caller); ``summary`` an optional bold footer line. Columns whose
    header looks numeric (Amount/Balance/In/Out/Debit/Credit/Received/Paid/Cash)
    are right-aligned.
    """
    numeric_hints = ('amount', 'balance', 'in', 'out', 'debit', 'credit',
                     'received', 'paid', 'cash', 'value', 'qty')

    def is_num(h):
        return any(k in h.lower() for k in numeric_hints)

    ths = ''.join('<th class="{}">{}</th>'.format(
        'num' if is_num(h) else '', _text(h)) for h in headers)
    body = []
    for row in rows:
        cells = ''.join('<td class="{}">{}</td>'.format(
            'num' if is_num(headers[i]) else '', _text(c))
            for i, c in enumerate(row))
        body.append('<tr>{}</tr>'.format(cells))
    body_html = ''.join(body) or (
        '<tr><td colspan="{}" class="muted">No entries.</td></tr>'.format(
            len(headers)))
    meta_html = ''.join('<div>{}</div>'.format(_text(x)) for x in meta_lines)
    summary_html = ('<div class="summary">{}</div>'.format(_text(summary))
                    if summary else '')

    return _STATEMENT_TEMPLATE.format(
        company=_text(company_name), title=_text(title), meta=meta_html,
        ths=ths, rows=body_html, summary=summary_html,
        generated=_text(date.today().isoformat()))


_STATEMENT_TEMPLATE = """<meta charset="utf-8">
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color: #1a1a1a;
         margin: 28px; font-size: 12px; }}
  h1 {{ margin: 0 0 2px; font-size: 18px; }}
  .company {{ color: #666; margin-bottom: 8px; }}
  .meta {{ margin: 6px 0 12px; color: #333; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  th, td {{ border: 1px solid #ccc; padding: 5px 8px; text-align: left; }}
  th {{ background: #f2f4f7; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .muted {{ color: #999; text-align: center; font-style: italic; }}
  .summary {{ margin-top: 12px; font-weight: bold; font-size: 13px; }}
  .foot {{ margin-top: 28px; color: #999; font-size: 11px;
           border-top: 1px solid #eee; padding-top: 8px; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
<div class="company">{company}</div>
<h1>{title}</h1>
<div class="meta">{meta}</div>
<table><thead><tr>{ths}</tr></thead><tbody>{rows}</tbody></table>
{summary}
<div class="foot">Generated by {company} on {generated}.</div>
"""
