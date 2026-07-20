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
import einvoice
import estimate as estimate_calc
import finance
import mb
import muster
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

    # E-invoice / e-way panel: shown only when the portal fields are present.
    # No QR is drawn — a real e-invoice QR encodes the portal's signed payload,
    # which cannot be reproduced offline; the IRN is shown instead.
    einv = einvoice.summarise(invoice)
    einv_rows = []
    if einv['irn']:
        einv_rows.append('<tr><td class="k">IRN</td><td class="mono">{}</td>'
                         '</tr>'.format(_text(einv['irn'])))
        ack = ' '.join(x for x in (_text(g(invoice, 'irn_ack_no')),
                                   _text(g(invoice, 'irn_ack_date'))) if x)
        if ack.strip():
            einv_rows.append('<tr><td class="k">Ack</td><td>{}</td></tr>'.format(
                ack))
    if einv['has_eway']:
        einv_rows.append('<tr><td class="k">E-way Bill</td><td>{}</td>'
                         '</tr>'.format(_text(einv['eway_bill_no'])))
        transport = ' &nbsp;|&nbsp; '.join(
            x for x in (_text(einv['transporter']),
                        _text(einv['vehicle_no'])) if x)
        if transport:
            einv_rows.append('<tr><td class="k">Transport</td><td>{}</td>'
                             '</tr>'.format(transport))
    einv_html = ('<table class="einv"><tr><th colspan="2">E-invoice / E-way '
                 'bill</th></tr>{}</table>'.format(''.join(einv_rows))
                 if einv_rows else '')

    return _TAX_TEMPLATE.format(
        logo=_LOGO_TAG,
        company=_text(company_name),
        einv=einv_html,
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
  table.einv {{ width: 100%; border-collapse: collapse; margin: 0 0 14px;
                font-size: 11px; }}
  table.einv th {{ background: #f2f4f7; text-align: left; padding: 4px 8px;
                   border: 1px solid #ccc; }}
  table.einv td {{ padding: 3px 8px; border: 1px solid #e0e3e8; }}
  table.einv td.k {{ color: #666; width: 20%; }}
  table.einv td.mono {{ font-family: 'Courier New', monospace;
                        word-break: break-all; }}
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
{einv}
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


def letterhead_html(firm):
    """The firm's branded letterhead: logo, name, then address / GSTIN /
    contact as available. A pure helper shared by every document so they look
    like they came from the same office.

    Lines with no value are dropped rather than printed blank — an empty
    "GSTIN:" label on a firm that has not registered looks like a mistake.
    """
    firm = firm or {}
    name = _text(firm.get('name') or 'Construction OS')
    lines = []
    if firm.get('address'):
        lines.append(_text(firm['address']))
    contact = []
    if firm.get('gstin'):
        contact.append('GSTIN: ' + _text(firm['gstin']))
    if firm.get('phone'):
        contact.append('Ph: ' + _text(firm['phone']))
    if firm.get('email'):
        contact.append(_text(firm['email']))
    if contact:
        lines.append(' &nbsp;|&nbsp; '.join(contact))
    detail = ''.join('<div>{}</div>'.format(x) for x in lines)
    return ('<div class="letterhead"><div class="lh-brand">{logo}</div>'
            '<div class="lh-text"><div class="lh-name">{name}</div>{detail}'
            '</div></div>').format(logo=_LOGO_TAG, name=name, detail=detail)


def bank_block_html(firm):
    """Payment instructions for a document that asks for money. Empty when the
    firm has not entered enough bank detail to pay into — a half-filled block
    is worse than none, because someone will try to use it."""
    if not (firm and firm.get('bank_account') and firm.get('bank_ifsc')):
        return ''
    parts = []
    if firm.get('bank_name'):
        parts.append(_text(firm['bank_name']))
    parts.append('A/c ' + _text(firm['bank_account']))
    parts.append('IFSC ' + _text(firm['bank_ifsc']))
    return ('<div class="bank"><strong>Payment to:</strong> {}</div>'.format(
        ' &nbsp;|&nbsp; '.join(parts)))


def build_statement_html(title, meta_lines, headers, rows, summary='',
                         company_name='Construction OS', firm=None):
    """Generic printable statement (party ledger, cash book, etc.).

    ``meta_lines`` is a list of strings shown under the title; ``headers`` a list
    of column titles; ``rows`` a list of same-length string tuples (pre-formatted
    by the caller); ``summary`` an optional bold footer line. Columns whose
    header looks numeric (Amount/Balance/In/Out/Debit/Credit/Received/Paid/Cash)
    are right-aligned.

    ``firm`` is an optional ``firm.details`` dict. When given, the document
    carries the full branded letterhead (address, GSTIN, contact) and, if the
    firm has bank details, a payment block — used for outward documents like
    quotations. When absent the header is just the company name, exactly as
    before, so the ~20 internal reports that call this are unchanged.
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

    if firm:
        header_html = letterhead_html(firm)
        bank_html = bank_block_html(firm)
        company = _text(firm.get('name') or company_name)
    else:
        # Unchanged behaviour for internal reports: bare logo + name line.
        header_html = ('<div class="brand">{}</div>'
                       '<div class="company">{}</div>').format(
            _LOGO_TAG, _text(company_name))
        bank_html = ''
        company = _text(company_name)

    return _STATEMENT_TEMPLATE.format(
        header=header_html, bank=bank_html,
        company=company, title=_text(title), meta=meta_html,
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
  .letterhead {{ display: flex; align-items: center; gap: 12px;
                 border-bottom: 2px solid #333; padding-bottom: 8px;
                 margin-bottom: 8px; }}
  .lh-name {{ font-size: 18px; font-weight: bold; }}
  .lh-text {{ color: #444; font-size: 11px; line-height: 1.4; }}
  .bank {{ margin: 8px 0; padding: 6px 8px; background: #f7f8fa;
           border: 1px solid #e0e3e8; font-size: 11px; }}
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
{header}
<h1>{title}</h1>
<div class="meta">{meta}</div>
<table><thead><tr>{ths}</tr></thead><tbody>{rows}</tbody></table>
{summary}
{bank}
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


def build_muster_roll_html(lines, dates, start, end, site_name='',
                           company_name='Construction OS',
                           reconciliation=None, explanation=''):
    """Render the muster roll in CPWA Form 21 shape.

    Part I is the nominal roll: name and father's name, a day-by-day
    attendance grid, rate, days, gross, advance recovered, net — and a
    signature / thumb-impression column, which is the whole point of the form.
    It is left blank by design: it is signed on paper at the moment of payment,
    and a pre-filled acknowledgement would be worthless as evidence.

    Part II reconciles the wage bill against the value of work measured in the
    same period (``muster.work_reconciliation``), with room for the written
    explanation the statutory excess/saving column calls for.
    """
    lines = list(lines or [])
    dates = list(dates or [])
    day_headers = ''.join('<th class="day">{}</th>'.format(d.strftime('%d'))
                          for d in dates)

    body = []
    for idx, l in enumerate(lines, 1):
        cells = ''.join('<td class="day">{}</td>'.format(_text(c))
                        for c in l['cells'])
        body.append(
            '<tr><td class="num">{}</td><td>{}</td><td>{}</td><td>{}</td>{}'
            '<td class="num">{}</td><td class="num">{}</td>'
            '<td class="num">{}</td><td class="num">{}</td>'
            '<td class="num">{}</td><td class="sign"></td></tr>'.format(
                idx, _text(l['name']), _text(l['father_name'] or '—'),
                _text(l['skill']), cells,
                '{:,.2f}'.format(l['daily_wage']),
                '{:g}'.format(l['days']), _money(l['gross']),
                _money(l['deduction']), _money(l['net'])))
    rows_html = ''.join(body) or (
        '<tr><td colspan="{}" class="muted">No labour on this roll.</td></tr>'
        .format(10 + len(dates)))

    total = muster.summarise_roll(lines)
    rec = reconciliation or {}
    ratio = rec.get('ratio_pct')
    if rec.get('unmeasured'):
        rec_note = ('<div class="warn">Wages were paid but no work was '
                    'measured in this period. Either the measurements are '
                    'outstanding or the work was not executed — this must be '
                    'explained below before the roll is passed.</div>')
    elif rec.get('needs_explanation'):
        rec_note = ('<div class="warn">Labour cost is {:g}% of the value of '
                    'work measured in this period, which is high. Record the '
                    'reason below.</div>'.format(ratio))
    elif ratio is not None:
        rec_note = ('<div class="ok-note">Labour cost is {:g}% of the value of '
                    'work measured in this period.</div>'.format(ratio))
    else:
        rec_note = ''

    return _MUSTER_TEMPLATE.format(
        company=_text(company_name),
        site_name=_text(site_name or '-'),
        start=_text(start), end=_text(end),
        day_headers=day_headers,
        # TOTAL spans the four identity columns plus every day column, so the
        # figures below line up under Days/Gross/Advance/Net.
        label_span=4 + len(dates),
        rows_html=rows_html,
        workers=total['workers'],
        total_days='{:g}'.format(total['days']),
        total_gross=_money(total['gross']),
        total_deduction=_money(total['deduction']),
        total_net=_money(total['net']),
        net_words=_text(numwords.rupees_in_words(total['net'])),
        wage_total=_money(rec.get('wage_total', total['net'])),
        measured_value=_money(rec.get('measured_value', 0)),
        difference=_money(rec.get('difference', 0)),
        ratio=('{:g}%'.format(ratio) if ratio is not None else '&mdash;'),
        rec_note=rec_note,
        explanation=_text(explanation) or '&nbsp;',
        generated=_text(date.today().isoformat()),
    )


def build_unpaid_wages_html(lines, start, end, site_name='',
                            company_name='Construction OS'):
    """Register of Unpaid Wages (CPWA Form 21A).

    Entries struck off the muster roll because the payee was not present at
    payment. Kept as its own document so the liability survives the next roll
    being drawn instead of quietly disappearing.
    """
    lines = list(lines or [])
    rows = ''.join(
        '<tr><td class="num">{}</td><td>{}</td><td>{}</td>'
        '<td class="num">{}</td><td class="num">{}</td>'
        '<td class="sign"></td><td class="sign"></td></tr>'.format(
            idx, _text(l['name']), _text(l['father_name'] or '—'),
            '{:g}'.format(l['days']), _money(l['net']))
        for idx, l in enumerate(lines, 1))
    total = round(sum(l['net'] for l in lines), 2)
    if not rows:
        rows = ('<tr><td colspan="7" class="muted">Every wage on this roll was '
                'paid. Nothing outstanding.</td></tr>')
    return _UNPAID_TEMPLATE.format(
        company=_text(company_name), site_name=_text(site_name or '-'),
        start=_text(start), end=_text(end), rows_html=rows,
        total=_money(total), total_words=_text(numwords.rupees_in_words(total)),
        count=len(lines), generated=_text(date.today().isoformat()))


_MUSTER_TEMPLATE = """<meta charset="utf-8">
<title>Muster Roll {start} to {end}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color: #1a1a1a;
         margin: 18px; font-size: 10px; }}
  h1 {{ margin: 0; font-size: 17px; }}
  h2 {{ font-size: 12px; letter-spacing: .5px; margin: 18px 0 4px; }}
  .doc-title {{ text-align: center; font-size: 13px; letter-spacing: 1px;
                border: 1px solid #333; padding: 4px; margin: 8px 0 4px; }}
  .head {{ display: flex; justify-content: space-between;
           border-bottom: 2px solid #333; padding-bottom: 8px; }}
  table.items {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  table.items th, table.items td {{ border: 1px solid #ccc; padding: 3px 5px;
                                    text-align: left; }}
  table.items th {{ background: #f2f4f7; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.day, th.day {{ text-align: center; width: 20px; padding: 3px 1px; }}
  td.sign {{ width: 90px; }}
  tr.tot td {{ font-weight: bold; background: #fafbfc; }}
  .muted {{ color: #999; text-align: center; font-style: italic;
            padding: 10px; }}
  .muted-note {{ color: #666; font-size: 9px; margin-top: 4px; }}
  .ok-note {{ color: #226622; margin-top: 6px; border-left: 3px solid #226622;
              padding-left: 8px; }}
  .warn {{ color: #8a5a00; margin-top: 6px; border-left: 3px solid #8a5a00;
           padding-left: 8px; background: #fffaf0; padding-top: 4px;
           padding-bottom: 4px; }}
  .rec {{ width: 340px; border-collapse: collapse; margin-top: 6px; }}
  .rec td {{ padding: 4px 8px; border-bottom: 1px solid #eee; }}
  .expl {{ border: 1px solid #ccc; min-height: 44px; padding: 6px;
           margin-top: 8px; }}
  .words {{ margin-top: 6px; font-style: italic; }}
  .sig {{ display: flex; justify-content: space-between; margin-top: 40px; }}
  .sig div {{ border-top: 1px solid #333; padding-top: 4px; width: 30%;
              text-align: center; }}
  .foot {{ margin-top: 20px; color: #999; font-size: 9px;
           border-top: 1px solid #eee; padding-top: 6px; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
<div class="head">
  <div><h1>{company}</h1><div>Site: {site_name}</div></div>
  <div style="text-align:right">
    <div>Period: <strong>{start}</strong> to <strong>{end}</strong></div>
    <div>Workers: <strong>{workers}</strong></div>
  </div>
</div>
<div class="doc-title">MUSTER ROLL &mdash; PART I (NOMINAL ROLL)</div>

<table class="items">
  <thead>
    <tr>
      <th class="num">#</th><th>Name</th><th>Father's name</th><th>Trade</th>
      {day_headers}
      <th class="num">Rate</th><th class="num">Days</th>
      <th class="num">Gross</th><th class="num">Advance</th>
      <th class="num">Net Paid</th><th>Signature / Thumb</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
  <tfoot>
    <tr class="tot"><td colspan="{label_span}">TOTAL</td><td></td>
        <td class="num">{total_days}</td><td class="num">{total_gross}</td>
        <td class="num">{total_deduction}</td><td class="num">{total_net}</td>
        <td></td></tr>
  </tfoot>
</table>
<div class="muted-note">P = present &nbsp; &frac12; = half day &nbsp;
O = overtime &nbsp; A = absent &nbsp; - = not marked. The signature column is
signed by the payee at the time of payment.</div>
<div class="words"><strong>Net wages in words:</strong> {net_words}</div>

<div class="doc-title" style="margin-top:22px">
  PART II &mdash; WAGES AGAINST WORK MEASURED</div>
<table class="rec">
  <tr><td>Wages paid this period</td><td class="num">{wage_total}</td></tr>
  <tr><td>Value of work measured this period</td>
      <td class="num">{measured_value}</td></tr>
  <tr><td>Difference</td><td class="num">{difference}</td></tr>
  <tr><td>Labour cost as % of measured value</td><td class="num">{ratio}</td></tr>
</table>
{rec_note}
<div><strong>Explanation of excess / saving:</strong></div>
<div class="expl">{explanation}</div>

<div class="sig">
  <div>Prepared by</div>
  <div>Paid in my presence</div>
  <div>Engineer-in-charge</div>
</div>
<div class="foot">Generated by {company} on {generated}. Attendance is recorded
per worker per day; wages follow the muster. Part II compares the period wage
bill with the value of work measured in the same period.</div>
"""

_UNPAID_TEMPLATE = """<meta charset="utf-8">
<title>Register of Unpaid Wages {start} to {end}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color: #1a1a1a;
         margin: 24px; font-size: 11px; }}
  h1 {{ margin: 0; font-size: 17px; }}
  .doc-title {{ text-align: center; font-size: 13px; letter-spacing: 1px;
                border: 1px solid #333; padding: 4px; margin: 8px 0 10px; }}
  .head {{ display: flex; justify-content: space-between;
           border-bottom: 2px solid #333; padding-bottom: 8px; }}
  table.items {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  table.items th, table.items td {{ border: 1px solid #ccc; padding: 4px 6px;
                                    text-align: left; }}
  table.items th {{ background: #f2f4f7; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.sign {{ width: 120px; }}
  tr.tot td {{ font-weight: bold; background: #fafbfc; }}
  .muted {{ color: #999; text-align: center; font-style: italic;
            padding: 12px; }}
  .words {{ margin-top: 8px; font-style: italic; }}
  .note {{ margin-top: 12px; color: #8a5a00; border-left: 3px solid #8a5a00;
           padding-left: 8px; }}
  .sig {{ display: flex; justify-content: space-between; margin-top: 44px; }}
  .sig div {{ border-top: 1px solid #333; padding-top: 4px; width: 30%;
              text-align: center; }}
  .foot {{ margin-top: 22px; color: #999; font-size: 10px;
           border-top: 1px solid #eee; padding-top: 6px; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
<div class="head">
  <div><h1>{company}</h1><div>Site: {site_name}</div></div>
  <div style="text-align:right">
    <div>Period: <strong>{start}</strong> to <strong>{end}</strong></div>
    <div>Entries: <strong>{count}</strong></div>
  </div>
</div>
<div class="doc-title">REGISTER OF UNPAID WAGES</div>

<table class="items">
  <thead>
    <tr><th class="num">#</th><th>Name</th><th>Father's name</th>
        <th class="num">Days</th><th class="num">Amount Unpaid</th>
        <th>Date Paid</th><th>Signature / Thumb</th></tr>
  </thead>
  <tbody>{rows_html}</tbody>
  <tfoot>
    <tr class="tot"><td colspan="4">TOTAL UNPAID</td>
        <td class="num">{total}</td><td colspan="2"></td></tr>
  </tfoot>
</table>
<div class="words"><strong>Total unpaid in words:</strong> {total_words}</div>
<div class="note">These wages remain payable. Each entry stays on this register
until the payee is paid and signs against it.</div>

<div class="sig">
  <div>Prepared by</div>
  <div>Checked by</div>
  <div>Engineer-in-charge</div>
</div>
<div class="foot">Generated by {company} on {generated}. Entries are wages
earned on the muster roll for which no payment has been recorded.</div>
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
    # The recovery block is itemised, so its own total has to be shown for the
    # memorandum to be checkable line by line.
    recoveries = sum(float(g(bill, k, 0) or 0) for k in
                     ('retention_amt', 'tds_amt', 'cess_amt',
                      'other_deductions'))
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
        tds_pct='{:g}'.format(float(g(bill, 'tds_pct', 0) or 0)),
        tds_amt=_money(g(bill, 'tds_amt', 0)),
        cess_pct='{:g}'.format(float(g(bill, 'cess_pct', 0) or 0)),
        cess_amt=_money(g(bill, 'cess_amt', 0)),
        other_deductions=_money(g(bill, 'other_deductions', 0)),
        total_recoveries=_money(recoveries),
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
  .memo {{ margin-top: 16px; width: 460px; margin-left: auto; }}
  .memo h2 {{ font-size: 12px; letter-spacing: .5px; margin: 0 0 4px; }}
  .memo table {{ width: 100%; border-collapse: collapse; }}
  .memo td {{ padding: 4px 8px; border-bottom: 1px solid #eee; }}
  .memo td.ind {{ padding-left: 20px; }}
  .memo td.ind2 {{ padding-left: 38px; color: #444; }}
  .memo tr.sub td {{ background: #f7f8fa; font-weight: bold; }}
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
    <tr class="sub"><td colspan="2">4. Deduct &mdash; RECOVERIES</td></tr>
    <tr><td class="ind">(i) Taxes</td><td class="num"></td></tr>
    <tr><td class="ind2">Income tax deducted at source @ {tds_pct}%</td>
        <td class="num">{tds_amt}</td></tr>
    <tr><td class="ind2">Labour cess @ {cess_pct}%</td>
        <td class="num">{cess_amt}</td></tr>
    <tr><td class="ind">(ii) Security deposit @ {retention_pct}%</td>
        <td class="num">{retention_amt}</td></tr>
    <tr><td class="ind">(iii) Other recoveries</td>
        <td class="num">{other_deductions}</td></tr>
    <tr class="sub"><td>Total recoveries</td>
        <td class="num">{total_recoveries}</td></tr>
    <tr class="net"><td>Net amount now payable by cheque</td><td class="num">{net_payable}</td></tr>
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
