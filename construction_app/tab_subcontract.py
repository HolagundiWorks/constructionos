"""Subcontractor / work-order billing (Phase 7).

Two sub-tabs:

* **Work Orders** — a header + BOQ-items DocumentFrame (like a PO, but awarded
  to a subcontractor). ``total_amount`` is the pre-tax items subtotal. The
  work order carries default retention % and TDS % applied to its bills.
* **Sub Bills** — running bills *payable to* the subcontractor. Enter the value
  of work done this bill; previous value auto-fills from earlier bills on the
  same work order; retention / TDS / other deductions come off to give the net
  payable (``subcontract.sub_bill_totals``). Printable.

Money figures on a sub bill are always derived from the entered work value +
the percentages — never hand-typed.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from ui_guard import can_write

import subcontract
import bill_export
import report_open
from tab_documents import DocumentFrame
from crud_frame import Field
from tab_masters import vendor_options, site_options


def _wo_options(conn):
    return [(r['id'], r['wo_no'] or 'WO {}'.format(r['id']))
            for r in conn.execute(
                'SELECT id, wo_no FROM work_orders ORDER BY id DESC')]


def build_work_orders_frame(parent, db_getter):
    header_fields = [
        Field('wo_no', 'WO No'),
        Field('vendor_id', 'Subcontractor', kind='fk', options_func=vendor_options),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('wo_date', 'WO Date'),
        Field('retention_pct', 'Retention %', kind='number', default='5'),
        Field('tds_pct', 'TDS %', kind='number', default='1'),
        Field('status', 'Status', kind='combo',
              options=['Draft', 'Awarded', 'Running', 'Closed', 'Cancelled'],
              default='Draft'),
        Field('description', 'Description'),
    ]
    return DocumentFrame(parent, db_getter, 'work_orders', header_fields,
                         'work_order_items', 'work_order_id', 'total_amount',
                         'Work Orders')


class SubBillFrame(ttk.Frame):
    HEADER_COLUMNS = ('id', 'bill_no', 'wo', 'bill_date', 'status', 'this_value',
                      'retention', 'tds', 'net')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self._wo_map = {}
        self.h = {}
        self._build_ui()
        self.refresh_bills()

    def _build_ui(self):
        ttk.Label(self, text='Subcontractor Bills',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        box = ttk.LabelFrame(self, text='Bills'); box.pack(fill='both', expand=True, padx=8, pady=4)
        heads = {'id': 'ID', 'bill_no': 'Bill No', 'wo': 'Work Order',
                 'bill_date': 'Date', 'status': 'Status', 'this_value': 'This Value',
                 'retention': 'Retention', 'tds': 'TDS', 'net': 'Net Payable'}
        self.tree = ttk.Treeview(box, columns=self.HEADER_COLUMNS,
                                 show='headings', height=8)
        for col in self.HEADER_COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=50 if col == 'id' else 100, anchor='w')
        self.tree.pack(fill='x', padx=4, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        form = ttk.Frame(box); form.pack(fill='x', padx=4, pady=4)
        for key, default in (('bill_no', ''), ('bill_date', ''),
                             ('this_bill_value', '0'), ('previous_value', '0'),
                             ('retention_pct', '5'), ('tds_pct', '1'),
                             ('other_deductions', '0'), ('remarks', '')):
            self.h[key] = tk.StringVar(value=default)
        self.h['wo'] = tk.StringVar()
        self.h['status'] = tk.StringVar(value='Draft')

        self._combo(form, 0, 0, 'Work Order', 'wo')
        self._entry(form, 0, 1, 'Bill No', 'bill_no')
        self._entry(form, 0, 2, 'Bill Date', 'bill_date')
        self._entry(form, 1, 0, 'This Bill Value', 'this_bill_value')
        self._entry(form, 1, 1, 'Previous Value', 'previous_value')
        self._combo_vals(form, 1, 2, 'Status', 'status',
                         ['Draft', 'Approved', 'Paid'])
        self._entry(form, 2, 0, 'Retention %', 'retention_pct')
        self._entry(form, 2, 1, 'TDS %', 'tds_pct')
        self._entry(form, 2, 2, 'Other Deductions', 'other_deductions')
        self._entry(form, 3, 0, 'Remarks', 'remarks')

        self.totals_var = tk.StringVar(value='Cumulative 0.00  |  Retention 0.00  '
                                             '|  TDS 0.00  |  Net 0.00')
        ttk.Label(box, textvariable=self.totals_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=6, pady=(2, 4))

        btns = ttk.Frame(box); btns.pack(fill='x', padx=4, pady=4)
        ttk.Button(btns, text='Compute', command=self._compute).pack(side='left', padx=3)
        ttk.Button(btns, text='Add Bill', command=self.add_bill).pack(side='left', padx=3)
        ttk.Button(btns, text='Update Selected', command=self.update_bill).pack(side='left', padx=3)
        ttk.Button(btns, text='Delete', command=self.delete_bill).pack(side='left', padx=3)
        ttk.Button(btns, text='Print / Export', command=self.export_bill).pack(side='left', padx=3)
        ttk.Button(btns, text='Clear', command=self.clear).pack(side='left', padx=3)

    def _entry(self, parent, row, col, label, key):
        cell = ttk.Frame(parent); cell.grid(row=row, column=col, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=15).pack(side='left')
        ttk.Entry(cell, textvariable=self.h[key], width=16).pack(side='left')

    def _combo(self, parent, row, col, label, key):
        cell = ttk.Frame(parent); cell.grid(row=row, column=col, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=15).pack(side='left')
        self.wo_combo = ttk.Combobox(cell, textvariable=self.h[key], width=14,
                                     state='readonly')
        self.wo_combo.pack(side='left')
        self.wo_combo.bind('<<ComboboxSelected>>', lambda e: self._on_wo_change())

    def _combo_vals(self, parent, row, col, label, key, values):
        cell = ttk.Frame(parent); cell.grid(row=row, column=col, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=15).pack(side='left')
        ttk.Combobox(cell, textvariable=self.h[key], width=14, state='readonly',
                     values=values).pack(side='left')

    # ------------------------------------------------------------- helpers
    def _num(self, key):
        try:
            return float(self.h[key].get().strip() or 0)
        except ValueError:
            messagebox.showerror('Invalid number', '"{}" must be a number.'.format(key))
            return None

    def _wo_id(self):
        raw = self.h['wo'].get().strip()
        if not raw:
            return None
        return self._wo_map.get(raw, raw.split(' - ')[0])

    def _totals(self):
        vals = [self._num(k) for k in ('this_bill_value', 'previous_value',
                                       'retention_pct', 'tds_pct', 'other_deductions')]
        if None in vals:
            return None
        return subcontract.sub_bill_totals(vals[0], vals[1], vals[2], vals[3], vals[4])

    def _compute(self):
        t = self._totals()
        if t is None:
            return
        self.totals_var.set(
            'Cumulative {cumulative_value:.2f}  |  Retention {retention_amt:.2f}  '
            '|  TDS {tds_amount:.2f}  |  Net {net_payable:.2f}'.format(**t))
        return t

    def _on_wo_change(self):
        """Default retention/TDS from the work order and auto-fill previous value."""
        wo_id = self._wo_id()
        if wo_id is None:
            return
        conn = self.db_getter()
        try:
            wo = conn.execute('SELECT retention_pct, tds_pct FROM work_orders '
                              'WHERE id = ?', (wo_id,)).fetchone()
            prev = conn.execute(
                'SELECT COALESCE(SUM(this_bill_value), 0) AS p FROM sub_bills '
                'WHERE work_order_id = ?', (wo_id,)).fetchone()['p']
        finally:
            conn.close()
        if wo is not None:
            self.h['retention_pct'].set(str(wo['retention_pct'] or 0))
            self.h['tds_pct'].set(str(wo['tds_pct'] or 0))
        self.h['previous_value'].set('{:.2f}'.format(prev or 0))

    # ------------------------------------------------------------- bill ops
    def refresh_bills(self):
        conn = self.db_getter()
        try:
            opts = _wo_options(conn)
            self._wo_map = {'{} - {}'.format(i, n): i for i, n in opts}
            self.wo_combo['values'] = ['{} - {}'.format(i, n) for i, n in opts]
            for item in self.tree.get_children():
                self.tree.delete(item)
            for r in conn.execute(
                    "SELECT sb.id, sb.bill_no, wo.wo_no, sb.bill_date, sb.status, "
                    "sb.this_bill_value, sb.retention_amt, sb.tds_amount, "
                    "sb.net_payable FROM sub_bills sb "
                    "LEFT JOIN work_orders wo ON wo.id = sb.work_order_id "
                    "ORDER BY sb.id DESC"):
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['bill_no'] or '-', r['wo_no'] or '-',
                    r['bill_date'] or '', r['status'],
                    '{:.2f}'.format(r['this_bill_value'] or 0),
                    '{:.2f}'.format(r['retention_amt'] or 0),
                    '{:.2f}'.format(r['tds_amount'] or 0),
                    '{:.2f}'.format(r['net_payable'] or 0)))
        finally:
            conn.close()

    def _values(self):
        wo_id = self._wo_id()
        if wo_id is None:
            messagebox.showinfo('No work order', 'Select a work order.')
            return None
        t = self._totals()
        if t is None:
            return None
        return {
            'work_order_id': wo_id,
            'bill_no': self.h['bill_no'].get().strip(),
            'bill_date': self.h['bill_date'].get().strip(),
            'status': self.h['status'].get().strip() or 'Draft',
            'this_bill_value': t['this_bill_value'],
            'previous_value': t['previous_value'],
            'cumulative_value': t['cumulative_value'],
            'retention_pct': self._num('retention_pct') or 0,
            'retention_amt': t['retention_amt'],
            'tds_pct': self._num('tds_pct') or 0,
            'tds_amount': t['tds_amount'],
            'other_deductions': self._num('other_deductions') or 0,
            'net_payable': t['net_payable'],
            'remarks': self.h['remarks'].get().strip(),
        }

    def add_bill(self):
        if not can_write():
            return
        v = self._values()
        if v is None:
            return
        cols = list(v.keys())
        conn = self.db_getter()
        try:
            conn.execute('INSERT INTO sub_bills ({}) VALUES ({})'.format(
                ', '.join(cols), ', '.join(['?'] * len(cols))),
                [v[c] for c in cols])
            conn.commit()
        finally:
            conn.close()
        self.refresh_bills()
        self.clear()

    def update_bill(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a bill.')
            return
        v = self._values()
        if v is None:
            return
        cols = list(v.keys())
        conn = self.db_getter()
        try:
            conn.execute('UPDATE sub_bills SET {} WHERE id = ?'.format(
                ', '.join('{} = ?'.format(c) for c in cols)),
                [v[c] for c in cols] + [self.selected_id])
            conn.commit()
        finally:
            conn.close()
        self.refresh_bills()

    def delete_bill(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a bill.')
            return
        if not messagebox.askyesno('Confirm delete', 'Delete this sub bill?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM sub_bills WHERE id = ?', (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_id = None
        self.refresh_bills()
        self.clear()

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM sub_bills WHERE id = ?',
                             (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        self.h['bill_no'].set(r['bill_no'] or '')
        self.h['bill_date'].set(r['bill_date'] or '')
        self.h['this_bill_value'].set(str(r['this_bill_value'] or 0))
        self.h['previous_value'].set(str(r['previous_value'] or 0))
        self.h['retention_pct'].set(str(r['retention_pct'] or 0))
        self.h['tds_pct'].set(str(r['tds_pct'] or 0))
        self.h['other_deductions'].set(str(r['other_deductions'] or 0))
        self.h['status'].set(r['status'] or 'Draft')
        self.h['remarks'].set(r['remarks'] or '')
        for disp, rid in self._wo_map.items():
            if str(rid) == str(r['work_order_id']):
                self.h['wo'].set(disp); break
        self._compute()

    def clear(self):
        self.selected_id = None
        for key, default in (('bill_no', ''), ('bill_date', ''),
                             ('this_bill_value', '0'), ('previous_value', '0'),
                             ('other_deductions', '0'), ('remarks', ''), ('wo', '')):
            self.h[key].set(default)
        self.h['status'].set('Draft')
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())

    def export_bill(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a bill to export.')
            return
        conn = self.db_getter()
        try:
            r = conn.execute(
                "SELECT sb.*, wo.wo_no, v.name AS sub_name FROM sub_bills sb "
                "LEFT JOIN work_orders wo ON wo.id = sb.work_order_id "
                "LEFT JOIN vendors v ON v.id = wo.vendor_id "
                "WHERE sb.id = ?", (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        meta = ['Subcontractor: {}'.format(r['sub_name'] or '-'),
                'Work Order: {}'.format(r['wo_no'] or '-'),
                'Bill No: {}'.format(r['bill_no'] or '-'),
                'Date: {}'.format(r['bill_date'] or '-')]
        rows = [
            ('Work done this bill', '{:,.2f}'.format(r['this_bill_value'] or 0)),
            ('Previous value', '{:,.2f}'.format(r['previous_value'] or 0)),
            ('Cumulative value', '{:,.2f}'.format(r['cumulative_value'] or 0)),
            ('Less: Retention @ {:.1f}%'.format(r['retention_pct'] or 0),
             '{:,.2f}'.format(r['retention_amt'] or 0)),
            ('Less: TDS @ {:.1f}%'.format(r['tds_pct'] or 0),
             '{:,.2f}'.format(r['tds_amount'] or 0)),
            ('Less: Other deductions', '{:,.2f}'.format(r['other_deductions'] or 0)),
        ]
        html = bill_export.build_statement_html(
            'Subcontractor Running Bill', meta, ['Particulars', 'Amount'], rows,
            summary='Net payable to subcontractor: {:,.2f}'.format(r['net_payable'] or 0))
        report_open.save_and_open_html(
            html, 'sub_bill_{}.html'.format(r['bill_no'] or self.selected_id))


def build_subcontract_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(build_work_orders_frame(nb, db_getter), text='Work Orders')
    nb.add(SubBillFrame(nb, db_getter), text='Sub Bills')
    return nb
