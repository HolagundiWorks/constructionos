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

import assets
import estimate as estimate_calc
import finance
import mb
import numwords

# Brand logo tag embedded in each document letterhead ('' if the file is
# missing). Computed once at import.
_LOGO_TAG = assets.logo_html(46)


def _money(value):
    """Format a number as a grouped 2-decimal amount (e.g. 1,234.50)."""
    try:
        return '{:,.2f}'.format(float(value or 0))
    except (TypeError, ValueError):
        return '0.00'


def _text(value):
    return escape('' if value is None else str(value))


def build_bill_html(bill, contract=None, client=None, site=None, items=None,
                    company_name='Construction OS'):
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
        logo=_LOGO_TAG,
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
                       company_name='Construction OS'):
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
        logo=_LOGO_TAG,
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
  <div>{logo}<h1>{company}</h1><div class="doc-title">RUNNING ACCOUNT BILL</div></div>
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

<div class="foot">Developed by Human Centric Works, Hospet · Powered by Construction OS<br>Generated by {company} on {generated}. Quantities from the
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
    {logo}
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

<div class="foot">Developed by Human Centric Works, Hospet · Powered by Construction OS<br>Generated by {company} on {generated}. Figures are in the
project's base currency.</div>
"""


def build_tax_invoice_html(invoice, client=None, items=None, seller=None,
                           company_name='Construction OS'):
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
        logo=_LOGO_TAG,
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
    {logo}
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

<div class="foot">Developed by Human Centric Works, Hospet · Powered by Construction OS<br>Generated by {company} on {generated}. This is a
computer-generated tax invoice.</div>
"""


def build_statement_html(title, meta_lines, headers, rows, summary='',
                         company_name='Construction OS'):
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
        logo=_LOGO_TAG,
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
<div class="brand">{logo}</div>
<div class="company">{company}</div>
<h1>{title}</h1>
<div class="meta">{meta}</div>
<table><thead><tr>{ths}</tr></thead><tbody>{rows}</tbody></table>
{summary}
<div class="foot">Developed by Human Centric Works, Hospet · Powered by Construction OS<br>Generated by {company} on {generated}.</div>
"""


def build_estimate_html(est, items=None, seller=None, company_name='Construction OS'):
    """Render a priced estimate (ported from CBS's estimate document).

    ``est`` carries est_number/title/estimate_date/status/contingency_pct/
    gst_pct/notes; ``items`` rows have item_code/description/unit/qty/rate/amount.
    Totals (subtotal -> contingency -> taxable -> GST -> grand total) come from
    ``estimate.estimate_totals``; the grand total is shown in words.
    """
    est = est or {}
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

    rows = []
    for idx, it in enumerate(items, start=1):
        rows.append(
            '<tr><td class="num">{}</td><td>{}</td><td>{}</td><td>{}</td>'
            '<td class="num">{}</td><td class="num">{}</td><td class="num">{}</td></tr>'.format(
                idx, _text(g(it, 'item_code')), _text(g(it, 'description')),
                _text(g(it, 'unit')), _money(g(it, 'qty')), _money(g(it, 'rate')),
                _money(g(it, 'amount'))))
    items_html = ''.join(rows) or (
        '<tr><td colspan="7" class="muted">No estimate items.</td></tr>')

    t = estimate_calc.estimate_totals(
        items, g(est, 'contingency_pct', 0), g(est, 'gst_pct', 0))

    cont_pct = float(g(est, 'contingency_pct', 0) or 0)
    gst_pct = float(g(est, 'gst_pct', 0) or 0)
    breakup = [('Items Subtotal', t['subtotal'])]
    if cont_pct:
        breakup.append(('Contingency @ {:g}%'.format(cont_pct), t['contingency']))
        breakup.append(('Taxable', t['taxable']))
    if gst_pct:
        breakup.append(('GST @ {:g}%'.format(gst_pct), t['gst']))
    breakup_html = ''.join(
        '<tr><td>{}</td><td class="num">{}</td></tr>'.format(_text(l), _money(v))
        for l, v in breakup)

    return _ESTIMATE_TEMPLATE.format(
        logo=_LOGO_TAG,
        company=_text(seller.get('name') or company_name),
        seller_gstin=_text(seller.get('gstin') or ''),
        seller_addr=_text(seller.get('address') or ''),
        est_number=_text(g(est, 'est_number') or '-'),
        title=_text(g(est, 'title') or ''),
        est_date=_text(g(est, 'estimate_date') or '-'),
        status=_text(g(est, 'status') or '-'),
        items_html=items_html,
        breakup_html=breakup_html,
        grand_total=_money(t['grand_total']),
        grand_words=_text(numwords.rupees_in_words(t['grand_total'])),
        notes=_text(g(est, 'notes') or ''),
        generated=_text(date.today().isoformat()),
    )


_ESTIMATE_TEMPLATE = """<meta charset="utf-8">
<title>Estimate {est_number}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color: #1a1a1a;
         margin: 28px; font-size: 12px; }}
  h1 {{ margin: 0; font-size: 20px; }}
  .doc-title {{ text-align: center; font-size: 14px; letter-spacing: 1px;
                border: 1px solid #333; padding: 4px; margin: 8px 0 6px; }}
  .subtitle {{ text-align: center; color: #555; margin-bottom: 12px; }}
  .head {{ display: flex; justify-content: space-between;
           border-bottom: 2px solid #333; padding-bottom: 10px; }}
  .meta td {{ padding: 2px 8px 2px 0; }}
  .meta td.k {{ color: #666; }}
  table.items {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  table.items th, table.items td {{ border: 1px solid #ccc; padding: 5px 7px;
                                    text-align: left; }}
  table.items th {{ background: #f2f4f7; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .muted {{ color: #999; text-align: center; font-style: italic; }}
  .summary {{ margin-top: 14px; width: 320px; margin-left: auto; }}
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
  <div>{logo}<h1>{company}</h1><div>GSTIN: {seller_gstin}</div><div>{seller_addr}</div></div>
  <table class="meta">
    <tr><td class="k">Estimate No</td><td>{est_number}</td></tr>
    <tr><td class="k">Date</td><td>{est_date}</td></tr>
    <tr><td class="k">Status</td><td>{status}</td></tr>
  </table>
</div>
<div class="doc-title">ESTIMATE</div>
<div class="subtitle">{title}</div>

<table class="items">
  <thead>
    <tr><th class="num">#</th><th>Code</th><th>Description</th><th>Unit</th>
    <th class="num">Qty</th><th class="num">Rate</th><th class="num">Amount</th></tr>
  </thead>
  <tbody>{items_html}</tbody>
</table>

<div class="summary">
  <table>
    {breakup_html}
    <tr class="total"><td>Grand Total</td><td class="num">{grand_total}</td></tr>
  </table>
</div>
<div class="words"><strong>Amount in words:</strong> {grand_words}</div>
<div class="words">{notes}</div>

<div class="foot">Developed by Human Centric Works, Hospet · Powered by Construction OS<br>Generated by {company} on {generated}. Estimate only — not a
tax invoice.</div>
"""


def _qty(value):
    """Measurement quantities carry 3 decimals; blanks print as a dash."""
    if value is None or str(value).strip() == '':
        return '&mdash;'
    try:
        return '{:,.3f}'.format(float(value))
    except (TypeError, ValueError):
        return '&mdash;'


def build_mb_html(contract=None, client=None, site=None, rows=None,
                  boq_items=None, company_name='Construction OS',
                  issues=None):
    """Render the Measurement Book in CPWA Form 23 layout.

    Entries are grouped into pages by ``mb_ref`` (``mb.group_pages``), each page
    closing with its total and the dated 'Measured by me' certificate, followed
    by an abstract of measured-versus-tendered quantity per BOQ item.

    When the contract value clears ``mb.CMB_THRESHOLD`` the document titles
    itself a Computerised Measurement Book and cites Works Manual Para 7.12,
    which is what makes it acceptable for departmental submission; below that
    threshold it prints as a plain measurement sheet, since claiming CMB status
    for a work that does not qualify would be a misrepresentation.

    ``rows`` need mb_date/mb_ref/description/nos/length/breadth/depth/quantity
    and optionally item_no/unit/measured_by/checked_by. ``issues`` is the list
    from ``mb.integrity_issues`` — printed as a record-check panel so the
    problems are visible before anyone signs, not after.
    """
    rows = list(rows or [])
    boq_items = list(boq_items or [])

    def g(row, key, default=''):
        if row is None:
            return default
        try:
            val = row[key]
        except (KeyError, IndexError, TypeError):
            return default
        return default if val is None else val

    is_cmb = mb.cmb_eligible(g(contract, 'contract_value', 0))
    summary = mb.summarise(rows)

    pages_html = []
    for ref, page_rows in mb.group_pages(rows):
        body = ''.join(
            '<tr><td>{}</td><td>{}</td><td>{}</td>'
            '<td class="num">{}</td><td class="num">{}</td>'
            '<td class="num">{}</td><td class="num">{}</td>'
            '<td class="num">{}</td><td>{}</td><td>{}</td></tr>'.format(
                _text(g(r, 'mb_date')), _text(g(r, 'item_no')),
                _text(g(r, 'description')),
                _qty(g(r, 'nos', None)), _qty(g(r, 'length', None)),
                _qty(g(r, 'breadth', None)), _qty(g(r, 'depth', None)),
                _qty(g(r, 'quantity', 0)), _text(g(r, 'unit')),
                _text(g(r, 'remarks')))
            for r in page_rows)
        measured_by = next((g(r, 'measured_by') for r in page_rows
                            if g(r, 'measured_by')), '')
        checked_by = next((g(r, 'checked_by') for r in page_rows
                           if g(r, 'checked_by')), '')
        last_date = max((g(r, 'mb_date') for r in page_rows if g(r, 'mb_date')),
                        default='')
        pages_html.append(_MB_PAGE_TEMPLATE.format(
            page_ref=_text(ref),
            entries=len(page_rows),
            entries_plural='y' if len(page_rows) == 1 else 'ies',
            rows_html=body,
            page_total=_qty(mb.page_total(page_rows)),
            certificate=_text(mb.certificate_text(
                measured_by, last_date, len(page_rows))),
            checked_by=_text(checked_by or '________________')))

    measured = mb.item_totals(rows)
    abstract_rows = []
    for it in boq_items:
        done = measured.get(g(it, 'id', None), 0.0)
        tendered = float(g(it, 'qty', 0) or 0)
        pct = (done / tendered * 100) if tendered else 0
        abstract_rows.append(
            '<tr><td>{}</td><td>{}</td><td>{}</td>'
            '<td class="num">{}</td><td class="num">{}</td>'
            '<td class="num">{}</td></tr>'.format(
                _text(g(it, 'item_no')), _text(g(it, 'description')),
                _text(g(it, 'unit')), _qty(tendered), _qty(done),
                '{:,.1f}%'.format(pct) if tendered else '&mdash;'))
    abstract_html = ''.join(abstract_rows) or (
        '<tr><td colspan="6" class="muted">No BOQ items.</td></tr>')

    issues = list(issues or [])
    if issues:
        issue_rows = ''.join(
            '<tr><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
                _text(i.get('id')), _text(i.get('severity', '').upper()),
                _text(i.get('issue')))
            for i in issues)
        checks_html = _MB_CHECKS_TEMPLATE.format(issue_rows=issue_rows)
    else:
        checks_html = ('<div class="ok-note">Record check passed: every entry '
                       'carries a date, particulars and a non-zero quantity, '
                       'and no measurement is duplicated.</div>')

    return _MB_TEMPLATE.format(
        company=_text(company_name),
        doc_title=('COMPUTERISED MEASUREMENT BOOK'
                   if is_cmb else 'MEASUREMENT SHEET'),
        cmb_note=('<div class="muted-note">Prepared under CPWD Works Manual '
                  'Para 7.12 (works of Rs 15 lakh and above may be measured on '
                  'a contractor-prepared computerised measurement book in '
                  'Form 23 format, on machine-numbered pages).</div>'
                  if is_cmb else
                  '<div class="muted-note">Form 23 layout. This work is below '
                  'the Rs 15 lakh computerised-measurement-book threshold, so '
                  'this sheet supplements rather than replaces the '
                  'departmental measurement book.</div>'),
        work_name=_text(g(contract, 'work_name') or g(site, 'name') or '-'),
        contract_no=_text(g(contract, 'contract_no') or '-'),
        agreement_date=_text(g(contract, 'agreement_date') or '-'),
        client_name=_text(g(client, 'name') or '-'),
        site_name=_text(g(site, 'name') or '-'),
        start_date=_text(g(contract, 'start_date') or '-'),
        end_date=_text(g(contract, 'end_date') or '-'),
        first_date=_text(summary['first_date'] or '-'),
        last_date=_text(summary['last_date'] or '-'),
        entries=summary['entries'],
        pages=summary['pages'],
        pages_html=''.join(pages_html) or (
            '<div class="muted">No measurements recorded.</div>'),
        abstract_html=abstract_html,
        checks_html=checks_html,
        generated=_text(date.today().isoformat()),
    )


_MB_PAGE_TEMPLATE = """
<div class="page">
  <div class="page-head">MB Page: <strong>{page_ref}</strong>
    <span class="muted-note">({entries} entr{entries_plural})</span></div>
  <table class="items">
    <thead>
      <tr>
        <th>Date</th><th>Item</th><th>Particulars / Location</th>
        <th class="num">Nos</th><th class="num">Length</th>
        <th class="num">Breadth</th><th class="num">Depth</th>
        <th class="num">Contents</th><th>Unit</th><th>Remarks</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
    <tfoot>
      <tr><td colspan="7" class="tot">Total this page</td>
          <td class="num tot">{page_total}</td><td colspan="2"></td></tr>
    </tfoot>
  </table>
  <div class="cert">{certificate}</div>
  <div class="cert-check">Checked by: {checked_by}</div>
</div>
"""

_MB_CHECKS_TEMPLATE = """
<div class="checks">
  <h2>RECORD CHECK</h2>
  <table class="items">
    <thead><tr><th>Entry</th><th>Severity</th><th>Finding</th></tr></thead>
    <tbody>{issue_rows}</tbody>
  </table>
  <div class="muted-note">An ERROR means the entry is not fit to bill against
  &mdash; a measurement book may not carry blank, void or duplicated entries
  (CPWD Works Manual Para 7.5).</div>
</div>
"""

_MB_TEMPLATE = """<meta charset="utf-8">
<title>Measurement Book &mdash; {contract_no}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color: #1a1a1a;
         margin: 24px; font-size: 11px; }}
  h1 {{ margin: 0; font-size: 18px; }}
  h2 {{ font-size: 12px; letter-spacing: .5px; margin: 18px 0 4px; }}
  .doc-title {{ text-align: center; font-size: 13px; letter-spacing: 1px;
                border: 1px solid #333; padding: 4px; margin: 8px 0 4px; }}
  .head {{ display: flex; justify-content: space-between;
           border-bottom: 2px solid #333; padding-bottom: 8px; }}
  .meta {{ width: 100%; border-collapse: collapse; margin: 10px 0 4px; }}
  .meta td {{ padding: 3px 8px; border: 1px solid #ddd; }}
  .meta td.k {{ color: #666; background: #fafbfc; width: 15%; }}
  table.items {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  table.items th, table.items td {{ border: 1px solid #ccc; padding: 4px 6px;
                                    text-align: left; }}
  table.items th {{ background: #f2f4f7; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.tot {{ font-weight: bold; background: #fafbfc; }}
  .page {{ margin-top: 14px; page-break-inside: avoid; }}
  .page-head {{ background: #eef1f5; border: 1px solid #ccc;
                border-bottom: none; padding: 4px 6px; font-size: 11px; }}
  .cert {{ border: 1px solid #ccc; border-top: none; padding: 6px;
           font-style: italic; background: #fcfcfd; }}
  .cert-check {{ padding: 4px 6px 0; color: #333; }}
  .muted {{ color: #999; text-align: center; font-style: italic;
            padding: 12px; }}
  .muted-note {{ color: #666; font-size: 10px; margin-top: 4px; }}
  .ok-note {{ color: #226622; font-size: 10px; margin-top: 8px;
              border-left: 3px solid #226622; padding-left: 8px; }}
  .checks {{ margin-top: 18px; }}
  .sig {{ display: flex; justify-content: space-between; margin-top: 48px; }}
  .sig div {{ border-top: 1px solid #333; padding-top: 4px; width: 30%;
              text-align: center; color: #333; }}
  .foot {{ margin-top: 24px; color: #999; font-size: 10px;
           border-top: 1px solid #eee; padding-top: 6px; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
<div class="head">
  <div><h1>{company}</h1>
    <div>Client: {client_name} &nbsp;|&nbsp; Site: {site_name}</div>
  </div>
  <div style="text-align:right">
    <div>Entries: <strong>{entries}</strong></div>
    <div>Pages: <strong>{pages}</strong></div>
  </div>
</div>
<div class="doc-title">{doc_title}</div>
{cmb_note}

<table class="meta">
  <tr><td class="k">Name of work</td><td colspan="3">{work_name}</td></tr>
  <tr><td class="k">Agreement No.</td><td>{contract_no}</td>
      <td class="k">Agreement date</td><td>{agreement_date}</td></tr>
  <tr><td class="k">Date of commencement</td><td>{start_date}</td>
      <td class="k">Date of completion</td><td>{end_date}</td></tr>
  <tr><td class="k">Measurements from</td><td>{first_date}</td>
      <td class="k">Measurements to</td><td>{last_date}</td></tr>
</table>

{pages_html}

<h2>ABSTRACT OF QUANTITIES</h2>
<table class="items">
  <thead>
    <tr><th>Item</th><th>Description</th><th>Unit</th>
        <th class="num">Tendered Qty</th><th class="num">Measured Qty</th>
        <th class="num">% Executed</th></tr>
  </thead>
  <tbody>{abstract_html}</tbody>
</table>

{checks_html}

<div class="sig">
  <div>Contractor</div>
  <div>Junior / Assistant Engineer</div>
  <div>Executive Engineer</div>
</div>

<div class="foot">Generated by {company} on {generated}. Entries are recorded in
order and grouped by measurement book page. Corrections must be made by crossing
out and initialling, never by erasure (CPWD Works Manual Para 7.5).</div>
"""


def build_ra_pwd_html(bill, contract=None, client=None, site=None, items=None,
                      company_name='Construction OS'):
    """Render a department-friendly (PWD-style) RA bill abstract.

    Compared to ``build_ra_bill_html`` this adds the tendered BOQ quantity and
    upto-date amount per item, marks part-rated items (billed rate below the
    BOQ rate), and closes with a Memorandum of Payments (value upto date, less
    previous payments, retention, and other recoveries) with the net payable
    in words. ``items`` rows need item_no/description/unit/boq_qty/boq_rate/
    upto_qty/previous_qty/current_qty/rate/current_amount.
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
    any_part_rate = False
    for it in items:
        rate = float(g(it, 'rate', 0) or 0)
        boq_rate = float(g(it, 'boq_rate', rate) or 0)
        part = boq_rate > 0 and rate < boq_rate
        any_part_rate = any_part_rate or part
        upto = float(g(it, 'upto_qty', 0) or 0)
        rows.append(
            '<tr><td>{}</td><td>{}{}</td><td>{}</td>'
            '<td class="num">{}</td><td class="num">{}</td>'
            '<td class="num">{}</td><td class="num">{}</td>'
            '<td class="num">{}</td><td class="num">{}</td>'
            '<td class="num">{}</td></tr>'.format(
                _text(g(it, 'item_no')), _text(g(it, 'description')),
                ' <strong>(PR)</strong>' if part else '',
                _text(g(it, 'unit')),
                _money(g(it, 'boq_qty')), _money(rate),
                _money(upto), _money(round(upto * rate, 2)),
                _money(g(it, 'previous_qty')), _money(g(it, 'current_qty')),
                _money(g(it, 'current_amount'))))
    items_html = ''.join(rows) or (
        '<tr><td colspan="10" class="muted">No billed items.</td></tr>')
    part_note = ('<div class="muted-note">(PR) = item paid at part rate '
                 '(below the BOQ rate) pending completion.</div>'
                 if any_part_rate else '')

    net = float(g(bill, 'net_payable', 0) or 0)
    return _RA_PWD_TEMPLATE.format(
        company=_text(company_name),
        bill_no=_text(g(bill, 'bill_no') or '-'),
        bill_date=_text(g(bill, 'bill_date') or '-'),
        status=_text(g(bill, 'status') or '-'),
        contract_no=_text(g(contract, 'contract_no') or '-'),
        contract_value=_money(g(contract, 'contract_value', 0)),
        client_name=_text(g(client, 'name') or '-'),
        site_name=_text(g(site, 'name') or '-'),
        items_html=items_html,
        part_note=part_note,
        cumulative_value=_money(g(bill, 'cumulative_value', 0)),
        previous_value=_money(g(bill, 'previous_value', 0)),
        this_bill_value=_money(g(bill, 'this_bill_value', 0)),
        retention_pct='{:g}'.format(float(g(bill, 'retention_pct', 0) or 0)),
        retention_amt=_money(g(bill, 'retention_amt', 0)),
        other_deductions=_money(g(bill, 'other_deductions', 0)),
        net_payable=_money(net),
        net_words=_text(numwords.rupees_in_words(net)),
        generated=_text(date.today().isoformat()),
    )


_RA_PWD_TEMPLATE = """<meta charset="utf-8">
<title>RA Bill {bill_no} (Abstract)</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color: #1a1a1a;
         margin: 24px; font-size: 11px; }}
  h1 {{ margin: 0; font-size: 18px; }}
  .doc-title {{ text-align: center; font-size: 13px; letter-spacing: 1px;
                border: 1px solid #333; padding: 4px; margin: 8px 0 12px; }}
  .head {{ display: flex; justify-content: space-between;
           border-bottom: 2px solid #333; padding-bottom: 8px; }}
  .meta td {{ padding: 2px 8px 2px 0; }}
  .meta td.k {{ color: #666; }}
  table.items {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  table.items th, table.items td {{ border: 1px solid #ccc; padding: 4px 6px;
                                    text-align: left; }}
  table.items th {{ background: #f2f4f7; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .muted {{ color: #999; text-align: center; font-style: italic; }}
  .muted-note {{ color: #666; font-size: 10px; margin-top: 4px; }}
  .memo {{ margin-top: 16px; width: 420px; margin-left: auto; }}
  .memo h2 {{ font-size: 12px; letter-spacing: .5px; margin: 0 0 4px; }}
  .memo table {{ width: 100%; border-collapse: collapse; }}
  .memo td {{ padding: 4px 8px; border-bottom: 1px solid #eee; }}
  .memo tr.net td {{ border-top: 2px solid #333; border-bottom: none;
                     font-size: 13px; font-weight: bold; }}
  .words {{ margin-top: 8px; font-style: italic; }}
  .sig {{ display: flex; justify-content: space-between; margin-top: 48px; }}
  .sig div {{ border-top: 1px solid #333; padding-top: 4px; width: 30%;
              text-align: center; color: #333; }}
  .foot {{ margin-top: 24px; color: #999; font-size: 10px;
           border-top: 1px solid #eee; padding-top: 6px; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
<div class="head">
  <div><h1>{company}</h1>
    <div>Client: {client_name} &nbsp;|&nbsp; Site: {site_name}</div>
    <div>Contract: {contract_no} &nbsp;|&nbsp; Contract Value: {contract_value}</div>
  </div>
  <table class="meta">
    <tr><td class="k">RA Bill No</td><td>{bill_no}</td></tr>
    <tr><td class="k">Date</td><td>{bill_date}</td></tr>
    <tr><td class="k">Status</td><td>{status}</td></tr>
  </table>
</div>
<div class="doc-title">RUNNING ACCOUNT BILL — ABSTRACT OF WORK EXECUTED</div>

<table class="items">
  <thead>
    <tr>
      <th>Item</th><th>Description</th><th>Unit</th>
      <th class="num">Tender Qty</th><th class="num">Rate</th>
      <th class="num">Qty Upto Date</th><th class="num">Amount Upto Date</th>
      <th class="num">Prev Qty</th><th class="num">This Bill Qty</th>
      <th class="num">This Bill Amount</th>
    </tr>
  </thead>
  <tbody>{items_html}</tbody>
</table>
{part_note}

<div class="memo">
  <h2>MEMORANDUM OF PAYMENTS</h2>
  <table>
    <tr><td>1. Total value of work done to date</td><td class="num">{cumulative_value}</td></tr>
    <tr><td>2. Deduct: value of previous bills</td><td class="num">{previous_value}</td></tr>
    <tr><td>3. Value of work since previous bill</td><td class="num">{this_bill_value}</td></tr>
    <tr><td>4. Deduct: retention @ {retention_pct}%</td><td class="num">{retention_amt}</td></tr>
    <tr><td>5. Deduct: other recoveries</td><td class="num">{other_deductions}</td></tr>
    <tr class="net"><td>Net amount now payable</td><td class="num">{net_payable}</td></tr>
  </table>
</div>
<div class="words"><strong>Net payable in words:</strong> {net_words}</div>

<div class="sig">
  <div>Prepared by</div>
  <div>Checked by</div>
  <div>Accepted / Engineer-in-charge</div>
</div>

<div class="foot">Generated by {company} on {generated}. Quantities from the
Measurement Book. This abstract follows the PWD running-account layout for
department submission.</div>
"""
