"""Postable money documents for the browser — **payments, tax invoices, vendor
invoices and running bills**. Tkinter-free.

The pattern is deliberately conservative and reuses the desktop's engine rather
than re-implementing double entry:

1. The web writes the document row with the *same* derived amounts the desktop
   computes (GST, TDS, net payable, retention, the incremental bill value).
2. It then calls ``journal_post.post_all`` — the one **idempotent** posting
   engine — which produces the balanced journal lines by the exact rules in
   ``posting.py``. Because posting is idempotent and state-gated (an invoice
   needs a subtotal, a bill must be Approved/Paid), a *Draft* saves without
   posting, and nothing is ever posted twice.

These are records of fact, so the web offers **create + view** only; editing or
reversing a posted document stays a careful desktop operation.

A field mirrors ``web_masters``' shape (so ``web_masters.coerce`` validates it),
plus ``store``: ``False`` marks a form-only input (e.g. a retention %) that
feeds ``compute`` but is not itself a column. ``compute(values)`` returns the
dict of real columns to INSERT.
"""

from datetime import date

import civil


def _f(key, label, kind='text', options=None, fk_sql=None, default='',
       required=False, store=True):
    return {'key': key, 'label': label, 'kind': kind, 'options': options or [],
            'fk_sql': fk_sql, 'default': default, 'required': required,
            'store': store}


_CLIENTS = 'SELECT id, name FROM clients ORDER BY name'
_VENDORS = 'SELECT id, name FROM vendors ORDER BY name'
_CONTRACTS = 'SELECT id, contract_no FROM contracts ORDER BY id DESC'


def _r(x):
    try:
        return round(float(x or 0), 2)
    except (TypeError, ValueError):
        return 0.0


# ── compute functions (form values -> the real columns to store) ──────────────
def _payment(v):
    return {'pay_date': v['pay_date'], 'direction': v['direction'],
            'party_type': v['party_type'], 'party_name': v['party_name'],
            'mode': v['mode'], 'amount': _r(v['amount']),
            'ref_no': v['ref_no'], 'narration': v['narration']}


def _tax_invoice(v):
    sub = _r(v['subtotal'])
    tax = _r(sub * _r(v['gst_pct']) / 100.0)
    return {'invoice_no': v['invoice_no'], 'client_id': v['client_id'],
            'invoice_date': v['invoice_date'], 'gst_pct': _r(v['gst_pct']),
            'status': v['status'], 'subtotal': sub, 'tax_amount': tax,
            'total_amount': _r(sub + tax)}


def _vendor_invoice(v):
    sub = _r(v['subtotal'])
    tax = _r(sub * _r(v['gst_pct']) / 100.0)
    tds = _r(sub * _r(v['tds_pct']) / 100.0)
    return {'invoice_no': v['invoice_no'], 'vendor_id': v['vendor_id'],
            'invoice_date': v['invoice_date'], 'gst_pct': _r(v['gst_pct']),
            'tds_pct': _r(v['tds_pct']), 'subtotal': sub, 'tax_amount': tax,
            'tds_amount': tds, 'total_amount': _r(sub + tax),
            'net_payable': _r(sub + tax - tds), 'status': v['status']}


def _bill(v):
    this = _r(_r(v['work_done_value']) - _r(v['previous_billed']))
    ret = _r(this * _r(v['retention_pct']) / 100.0)
    other = _r(v['other_deductions'])
    return {'bill_no': v['bill_no'], 'contract_id': v['contract_id'],
            'bill_date': v['bill_date'], 'status': v['status'],
            'work_done_value': _r(v['work_done_value']),
            'previous_billed': _r(v['previous_billed']),
            'retention_amt': ret, 'other_deductions': other,
            'net_payable': _r(this - ret - other), 'remarks': v['remarks']}


def _ra_bill(v):
    # Reuse the desktop's pure roll-up (CPWA Form 26 recovery block) so the
    # browser and the RA Bill tab compute identical retention / TDS / cess / net.
    t = civil.ra_bill_totals(v['this_bill_value'], v['previous_value'],
                             v['retention_pct'], v['other_deductions'],
                             v['tds_pct'], v['cess_pct'])
    return {'bill_no': v['bill_no'], 'contract_id': v['contract_id'],
            'bill_date': v['bill_date'], 'status': v['status'],
            'this_bill_value': t['this_bill_value'],
            'previous_value': t['previous_value'],
            'cumulative_value': t['cumulative_value'],
            'retention_pct': _r(v['retention_pct']),
            'retention_amt': t['retention_amt'],
            'tds_pct': _r(v['tds_pct']), 'tds_amt': t['tds_amt'],
            'cess_pct': _r(v['cess_pct']), 'cess_amt': t['cess_amt'],
            'other_deductions': t['other_deductions'],
            'net_payable': t['net_payable'], 'remarks': v['remarks']}


DOCS = {
    'payments': {
        'label': 'Payment',
        'note': 'Records a cash/bank movement and posts it to the ledger.',
        'compute': _payment,
        'fields': [
            _f('pay_date', 'Date', default='@today'),
            _f('direction', 'Direction', 'combo',
               options=['Receipt', 'Payment'], default='Receipt', required=True),
            _f('party_type', 'Party type', 'combo',
               options=['Client', 'Vendor', 'Labour', 'Other'], default='Client'),
            _f('party_name', 'Party name'),
            _f('mode', 'Mode', 'combo',
               options=['Cash', 'Bank', 'UPI', 'Cheque'], default='Cash'),
            _f('amount', 'Amount', 'number', required=True),
            _f('ref_no', 'Reference'),
            _f('narration', 'Narration', 'textarea'),
        ],
    },
    'tax_invoices': {
        'label': 'Tax Invoice',
        'note': 'Outward sale. GST is added; the invoice posts to the ledger.',
        'compute': _tax_invoice,
        'fields': [
            _f('invoice_no', 'Invoice no', required=True),
            _f('client_id', 'Client', 'fk', fk_sql=_CLIENTS),
            _f('invoice_date', 'Date', default='@today'),
            _f('subtotal', 'Taxable value', 'number', required=True),
            _f('gst_pct', 'GST %', 'number', default='18'),
            _f('status', 'Status', 'combo',
               options=['Draft', 'Issued', 'Paid'], default='Issued'),
        ],
    },
    'vendor_invoices': {
        'label': 'Vendor Invoice',
        'note': 'Inward purchase. GST/TDS applied; posts to the ledger.',
        'compute': _vendor_invoice,
        'fields': [
            _f('invoice_no', 'Invoice no', required=True),
            _f('vendor_id', 'Vendor', 'fk', fk_sql=_VENDORS),
            _f('invoice_date', 'Date', default='@today'),
            _f('subtotal', 'Taxable value', 'number', required=True),
            _f('gst_pct', 'GST %', 'number', default='18'),
            _f('tds_pct', 'TDS %', 'number', default='0'),
            _f('status', 'Status', 'combo',
               options=['Received', 'Approved', 'Paid'], default='Received'),
        ],
    },
    'bills': {
        'label': 'Running Bill',
        'note': ('Cumulative work value less what was billed before. Posts to '
                 'the ledger only when Approved or Paid.'),
        'compute': _bill,
        'fields': [
            _f('bill_no', 'Bill no', required=True),
            _f('contract_id', 'Contract', 'fk', fk_sql=_CONTRACTS),
            _f('bill_date', 'Date', default='@today'),
            _f('work_done_value', 'Work done to date', 'number', required=True),
            _f('previous_billed', 'Previously billed', 'number', default='0'),
            _f('retention_pct', 'Retention %', 'number', default='5',
               store=False),
            _f('other_deductions', 'Other deductions', 'number', default='0'),
            _f('status', 'Status', 'combo',
               options=['Draft', 'Approved', 'Paid'], default='Draft'),
            _f('remarks', 'Remarks', 'textarea'),
        ],
    },
    'ra_bills': {
        'label': 'RA Bill',
        'note': ('Running-account bill. Enter the value of work done in THIS '
                 'bill (detailed measurement entry stays in the desktop '
                 'Measurement Book; the saved bill’s items, its Form-23 '
                 'Measurement Book and Form-26 abstract are viewable and '
                 'printable from its record here). The CPWA Form-26 recoveries — '
                 'security deposit, income-tax TDS, labour cess — are charged on '
                 'this bill’s value. Posts to the ledger when Approved or Paid.'),
        'compute': _ra_bill,
        'fields': [
            _f('bill_no', 'Bill no', required=True),
            _f('contract_id', 'Contract', 'fk', fk_sql=_CONTRACTS),
            _f('bill_date', 'Date', default='@today'),
            _f('this_bill_value', 'Value of work this bill', 'number',
               required=True),
            _f('previous_value', 'Value billed previously', 'number',
               default='0'),
            _f('retention_pct', 'Security deposit %', 'number', default='2.5'),
            _f('tds_pct', 'Income-tax TDS %', 'number', default='0'),
            _f('cess_pct', 'Labour cess %', 'number', default='0'),
            _f('other_deductions', 'Other deductions', 'number', default='0'),
            _f('status', 'Status', 'combo',
               options=['Draft', 'Approved', 'Paid'], default='Draft'),
            _f('remarks', 'Remarks', 'textarea'),
        ],
    },
}


def is_doc(table):
    return table in DOCS


def fields(table):
    return DOCS[table]['fields']


def label(table):
    return DOCS[table]['label']


def note(table):
    return DOCS[table].get('note', '')


def compute(table, values):
    return DOCS[table]['compute'](values)


def resolve_default(default):
    return date.today().isoformat() if default == '@today' else default
