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
