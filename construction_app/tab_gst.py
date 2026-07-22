"""GST & TDS summaries (Phase 5 — compliance made simple).

Computed reports over data the app already captures — outward GST from
``tax_invoices``, input GST and TDS from ``vendor_invoices`` — enough for a
contractor and their CA at return time, without turning the app into
accounting software. Each view filters by month (``YYYY-MM``; blank = all) and
prints to HTML. GST breakups are recomputed from the stored subtotal + rate +
inter-state flag via ``finance.split_gst`` so they always reconcile.
"""

from datetime import date
import tkinter as tk
from tkinter import ttk

import finance
import bill_export
from gst import (  # pure compute — keep GUI thin
    _fmt, outward, inward, hsn_summary, tds_register,
)
from tab_money import _save_and_open_html   # reuse the save+open helper


class ReportView(ttk.Frame):
    """A month-filtered, printable tabular report."""

    def __init__(self, parent, db_getter, title, headers, builder):
        super().__init__(parent)
        self.db_getter = db_getter
        self.title = title
        self.headers = headers
        self.builder = builder          # builder(conn, month) -> (rows, summary_str)
        self._rows = []
        self.month_var = tk.StringVar(value=date.today().strftime('%Y-%m'))

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Month (YYYY-MM, blank = all)').pack(side='left')
        ttk.Entry(top, textvariable=self.month_var, width=10).pack(side='left', padx=4)
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='left', padx=4)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='left', padx=4)

        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=4)

        self.tree = ttk.Treeview(self, columns=headers, show='headings')
        for h in headers:
            self.tree.heading(h, text=h)
            self.tree.column(h, width=140 if h in ('Party', 'Item') else 95, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        month = self.month_var.get().strip()
        conn = self.db_getter()
        try:
            rows, summary = self.builder(conn, month)
        finally:
            conn.close()
        self._rows = rows
        for row in rows:
            self.tree.insert('', 'end', values=row)
        self.summary_var.set(summary)

    def export(self):
        month = self.month_var.get().strip() or 'All'
        html = bill_export.build_statement_html(
            self.title, ['Period: {}'.format(month)], list(self.headers),
            self._rows, summary=self.summary_var.get())
        _save_and_open_html(html, self.title.lower().replace(' ', '_') + '.html')


def _outward_builder(conn, month):
    rows, t = outward(conn, month)
    return rows, ('Taxable {taxable}   CGST {cgst}   SGST {sgst}   '
                  'IGST {igst}   Total {total}'.format(
                      **{k: _fmt(v) for k, v in t.items()}))


def _inward_builder(conn, month):
    rows, t = inward(conn, month)
    return rows, ('Taxable {taxable}   CGST {cgst}   SGST {sgst}   '
                  'IGST {igst}   Total {total}'.format(
                      **{k: _fmt(v) for k, v in t.items()}))


def _tds_builder(conn, month):
    rows, total = tds_register(conn, month)
    return rows, 'Total TDS deducted: {}'.format(_fmt(total))


def _hsn_builder(conn, month):
    rows, t = hsn_summary(conn, month)
    return rows, ('Taxable {taxable}   CGST {cgst}   SGST {sgst}   '
                  'IGST {igst}'.format(**{k: _fmt(v) for k, v in t.items()}))


def _summary_builder(conn, month):
    _, out = outward(conn, month)
    _, inp = inward(conn, month)
    s = finance.gst_summary(out['cgst'] + out['sgst'] + out['igst'],
                            inp['cgst'] + inp['sgst'] + inp['igst'])
    rows = [
        ('Output GST on sales', _fmt(s['output_tax'])),
        ('  of which CGST / SGST / IGST',
         '{} / {} / {}'.format(_fmt(out['cgst']), _fmt(out['sgst']), _fmt(out['igst']))),
        ('Input GST credit on purchases', _fmt(s['input_tax'])),
        ('  of which CGST / SGST / IGST',
         '{} / {} / {}'.format(_fmt(inp['cgst']), _fmt(inp['sgst']), _fmt(inp['igst']))),
        ('Net GST payable', _fmt(s['net_payable'])),
        ('Credit carried forward', _fmt(s['credit_carried'])),
    ]
    if s['net_payable'] > 0:
        summary = 'Net GST payable this period: {}'.format(_fmt(s['net_payable']))
    else:
        summary = 'Input credit carried forward: {}'.format(_fmt(s['credit_carried']))
    return rows, summary


def build_gst_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    inv_headers = ('Invoice No', 'Date', 'Party', 'Taxable', 'CGST', 'SGST',
                   'IGST', 'Total')
    out_headers = ('Source', 'Doc No', 'Date', 'Party', 'Taxable', 'CGST',
                   'SGST', 'IGST', 'Total')
    nb.add(ReportView(nb, db_getter, 'Output GST (Sales)', out_headers,
                      _outward_builder), text='Output GST (Sales)')
    nb.add(ReportView(nb, db_getter, 'Input GST (Purchases)', inv_headers,
                      _inward_builder), text='Input GST (Purchases)')
    nb.add(ReportView(nb, db_getter, 'HSN Summary',
                      ('HSN/SAC', 'Taxable', 'CGST', 'SGST', 'IGST', 'Tax'),
                      _hsn_builder), text='HSN Summary')
    nb.add(ReportView(nb, db_getter, 'GST Summary', ('Particulars', 'Amount'),
                      _summary_builder), text='GST Summary')
    nb.add(ReportView(nb, db_getter, 'TDS Register',
                      ('Invoice No', 'Date', 'Party', 'Taxable', 'TDS %', 'TDS Amount'),
                      _tds_builder), text='TDS Register')
    return nb
