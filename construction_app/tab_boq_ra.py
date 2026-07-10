"""BOQ, Measurement Book, and RA (Running Account) bills — the civil billing spine.

This is how civil contractors actually bill: a **BOQ** of priced items per
contract, quantities measured on site in a **Measurement Book** (Nos x L x B x
D), and **RA bills** that abstract the cumulative measured quantity against each
BOQ item, subtract what previous RA bills already billed, and pay the balance
(less retention and deductions).

All arithmetic is delegated to ``civil.py`` (``measurement_quantity``,
``ra_current``, ``ra_bill_totals``) so it is testable without a GUI.

RA generation mirrors the running-bill convention in ``tab_billing`` (§6): only
RA bills in status Approved/Paid count as "previously billed" when computing the
previous quantity/value of a later bill.
"""

import os
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import civil
import bill_export


def contract_options(conn):
    return [(r['id'], r['contract_no'] or 'Contract {}'.format(r['id']))
            for r in conn.execute(
                'SELECT id, contract_no FROM contracts ORDER BY id DESC')]


def _fill_contract_combo(combo, mapping, options, include_blank=False):
    display = ['{} - {}'.format(i, n) for i, n in options]
    mapping.clear()
    mapping.update({'{} - {}'.format(i, n): i for i, n in options})
    combo['values'] = ([''] + display) if include_blank else display


def _combo_id(var, mapping):
    raw = var.get().strip()
    if not raw:
        return None
    return mapping.get(raw, raw.split(' - ')[0])


def _num(value, default=None):
    s = str(value).strip()
    if s == '':
        return default
    try:
        return float(s)
    except ValueError:
        return default


# ============================================================ BOQ
class BOQFrame(ttk.Frame):
    COLUMNS = ('id', 'item_no', 'description', 'unit', 'qty', 'rate', 'amount')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self._cmap = {}
        self.contract_var = tk.StringVar()
        self.v = {k: tk.StringVar() for k in
                  ('item_no', 'description', 'unit', 'qty', 'rate')}
        self._build_ui()
        self.refresh_contracts()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Contract', font=('TkDefaultFont', 11, 'bold')) \
            .pack(side='left')
        self.contract_combo = ttk.Combobox(top, textvariable=self.contract_var,
                                            width=28, state='readonly')
        self.contract_combo.pack(side='left', padx=6)
        self.contract_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_items())
        ttk.Button(top, text='Refresh', command=self.refresh_contracts).pack(side='left')

        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=11)
        for col in self.COLUMNS:
            self.tree.heading(col, text=col.replace('_', ' ').title())
            self.tree.column(col, width=50 if col == 'id' else 130, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        form = ttk.LabelFrame(self, text='BOQ Item'); form.pack(fill='x', padx=8, pady=4)
        labels = [('item_no', 'Item No'), ('description', 'Description'),
                  ('unit', 'Unit'), ('qty', 'BOQ Qty'), ('rate', 'Rate')]
        for idx, (key, label) in enumerate(labels):
            cell = ttk.Frame(form); cell.grid(row=idx // 3, column=idx % 3, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=11).pack(side='left')
            ttk.Entry(cell, textvariable=self.v[key], width=22).pack(side='left')

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btns, text='Add', command=self.add).pack(side='left', padx=3)
        ttk.Button(btns, text='Update', command=self.update).pack(side='left', padx=3)
        ttk.Button(btns, text='Delete', command=self.delete).pack(side='left', padx=3)
        ttk.Button(btns, text='Clear', command=self.clear).pack(side='left', padx=3)

    def refresh_contracts(self):
        conn = self.db_getter()
        try:
            _fill_contract_combo(self.contract_combo, self._cmap,
                                 contract_options(conn))
        finally:
            conn.close()
        self.refresh_items()

    def _contract_id(self):
        return _combo_id(self.contract_var, self._cmap)

    def refresh_items(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        cid = self._contract_id()
        if cid is None:
            return
        conn = self.db_getter()
        try:
            for r in conn.execute(
                    'SELECT id, item_no, description, unit, qty, rate, amount '
                    'FROM boq_items WHERE contract_id = ? ORDER BY id', (cid,)):
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['item_no'], r['description'], r['unit'],
                    r['qty'], r['rate'], r['amount']))
        finally:
            conn.close()

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        vals = self.tree.item(sel[0], 'values')
        self.v['item_no'].set(vals[1]); self.v['description'].set(vals[2])
        self.v['unit'].set(vals[3]); self.v['qty'].set(vals[4])
        self.v['rate'].set(vals[5])

    def _collect(self):
        cid = self._contract_id()
        if cid is None:
            messagebox.showinfo('No contract', 'Select a contract first.')
            return None
        qty = _num(self.v['qty'].get(), 0.0)
        rate = _num(self.v['rate'].get(), 0.0)
        if qty is None or rate is None:
            messagebox.showerror('Invalid number', 'Qty/Rate must be numbers.')
            return None
        return cid, {
            'item_no': self.v['item_no'].get().strip(),
            'description': self.v['description'].get().strip(),
            'unit': self.v['unit'].get().strip(),
            'qty': qty, 'rate': rate, 'amount': round(qty * rate, 2),
        }

    def add(self):
        collected = self._collect()
        if collected is None:
            return
        cid, d = collected
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO boq_items (contract_id, item_no, description, '
                'unit, qty, rate, amount) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (cid, d['item_no'], d['description'], d['unit'], d['qty'],
                 d['rate'], d['amount']))
            conn.commit()
        finally:
            conn.close()
        self.refresh_items(); self.clear()

    def update(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a BOQ item.')
            return
        collected = self._collect()
        if collected is None:
            return
        _cid, d = collected
        conn = self.db_getter()
        try:
            conn.execute(
                'UPDATE boq_items SET item_no = ?, description = ?, unit = ?, '
                'qty = ?, rate = ?, amount = ? WHERE id = ?',
                (d['item_no'], d['description'], d['unit'], d['qty'], d['rate'],
                 d['amount'], self.selected_id))
            conn.commit()
        finally:
            conn.close()
        self.refresh_items()

    def delete(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a BOQ item.')
            return
        if not messagebox.askyesno(
                'Confirm delete',
                'Delete this BOQ item and its measurements?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM boq_items WHERE id = ?', (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_id = None
        self.refresh_items(); self.clear()

    def clear(self):
        self.selected_id = None
        for var in self.v.values():
            var.set('')
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())


# ============================================================ Measurement Book
class MeasurementFrame(ttk.Frame):
    COLUMNS = ('id', 'mb_date', 'mb_ref', 'item', 'description', 'nos',
               'length', 'breadth', 'depth', 'quantity')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self._cmap = {}
        self._imap = {}
        self.contract_var = tk.StringVar()
        self.item_var = tk.StringVar()
        self.v = {k: tk.StringVar() for k in
                  ('mb_date', 'mb_ref', 'description', 'nos', 'length',
                   'breadth', 'depth', 'remarks')}
        self.qty_var = tk.StringVar(value='0.000')
        self._build_ui()
        self.refresh_contracts()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Contract', font=('TkDefaultFont', 11, 'bold')).pack(side='left')
        self.contract_combo = ttk.Combobox(top, textvariable=self.contract_var,
                                            width=24, state='readonly')
        self.contract_combo.pack(side='left', padx=6)
        self.contract_combo.bind('<<ComboboxSelected>>', lambda e: self._on_contract())
        ttk.Button(top, text='Refresh', command=self.refresh_contracts).pack(side='left')

        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=10)
        for col in self.COLUMNS:
            self.tree.heading(col, text=col.replace('_', ' ').title())
            self.tree.column(col, width=50 if col == 'id' else 95, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        form = ttk.LabelFrame(self, text='Measurement (Nos x L x B x D; blanks count as 1)')
        form.pack(fill='x', padx=8, pady=4)
        cell = ttk.Frame(form); cell.grid(row=0, column=0, padx=6, pady=4, sticky='w')
        ttk.Label(cell, text='BOQ Item', width=11).pack(side='left')
        self.item_combo = ttk.Combobox(cell, textvariable=self.item_var,
                                       width=26, state='readonly')
        self.item_combo.pack(side='left')
        entries = [('mb_date', 'MB Date'), ('mb_ref', 'MB Ref'),
                   ('description', 'Location'), ('nos', 'Nos'),
                   ('length', 'Length'), ('breadth', 'Breadth'),
                   ('depth', 'Depth'), ('remarks', 'Remarks')]
        for idx, (key, label) in enumerate(entries):
            pos = idx + 1
            cell = ttk.Frame(form); cell.grid(row=pos // 3, column=pos % 3, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=11).pack(side='left')
            e = ttk.Entry(cell, textvariable=self.v[key], width=16)
            e.pack(side='left')
            if key in ('nos', 'length', 'breadth', 'depth'):
                self.v[key].trace_add('write', lambda *a: self._live_qty())

        qcell = ttk.Frame(form)
        qcell.grid(row=3, column=1, padx=6, pady=4, sticky='w')
        ttk.Label(qcell, text='Quantity', width=11).pack(side='left')
        ttk.Label(qcell, textvariable=self.qty_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(side='left')

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btns, text='Add', command=self.add).pack(side='left', padx=3)
        ttk.Button(btns, text='Update', command=self.update).pack(side='left', padx=3)
        ttk.Button(btns, text='Delete', command=self.delete).pack(side='left', padx=3)
        ttk.Button(btns, text='Clear', command=self.clear).pack(side='left', padx=3)

    def _live_qty(self):
        self.qty_var.set('{:.3f}'.format(civil.measurement_quantity(
            self.v['nos'].get(), self.v['length'].get(),
            self.v['breadth'].get(), self.v['depth'].get())))

    def refresh_contracts(self):
        conn = self.db_getter()
        try:
            _fill_contract_combo(self.contract_combo, self._cmap,
                                 contract_options(conn))
        finally:
            conn.close()
        self._on_contract()

    def _contract_id(self):
        return _combo_id(self.contract_var, self._cmap)

    def _on_contract(self):
        self._refresh_item_combo()
        self.refresh_items()

    def _refresh_item_combo(self):
        cid = self._contract_id()
        self._imap = {}
        if cid is None:
            self.item_combo['values'] = []
            return
        conn = self.db_getter()
        try:
            opts = [(r['id'], '{} {}'.format(r['item_no'] or '', r['description'] or '').strip())
                    for r in conn.execute(
                        'SELECT id, item_no, description FROM boq_items '
                        'WHERE contract_id = ? ORDER BY id', (cid,))]
        finally:
            conn.close()
        self._imap = {'{} - {}'.format(i, n): i for i, n in opts}
        self.item_combo['values'] = ['{} - {}'.format(i, n) for i, n in opts]

    def refresh_items(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        cid = self._contract_id()
        if cid is None:
            return
        conn = self.db_getter()
        try:
            sql = ("SELECT m.id, m.mb_date, m.mb_ref, "
                   "TRIM(COALESCE(b.item_no,'')||' '||COALESCE(b.description,'')) AS item, "
                   "m.description, m.nos, m.length, m.breadth, m.depth, m.quantity "
                   "FROM measurements m "
                   "LEFT JOIN boq_items b ON b.id = m.boq_item_id "
                   "WHERE m.contract_id = ? ORDER BY m.id")
            for r in conn.execute(sql, (cid,)):
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['mb_date'], r['mb_ref'], r['item'] or '-',
                    r['description'], _blank(r['nos']), _blank(r['length']),
                    _blank(r['breadth']), _blank(r['depth']),
                    '{:.3f}'.format(r['quantity'] or 0)))
        finally:
            conn.close()

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM measurements WHERE id = ?',
                             (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        for disp, iid in self._imap.items():
            if str(iid) == str(r['boq_item_id']):
                self.item_var.set(disp); break
        self.v['mb_date'].set(r['mb_date'] or '')
        self.v['mb_ref'].set(r['mb_ref'] or '')
        self.v['description'].set(r['description'] or '')
        self.v['nos'].set(_blank(r['nos'])); self.v['length'].set(_blank(r['length']))
        self.v['breadth'].set(_blank(r['breadth'])); self.v['depth'].set(_blank(r['depth']))
        self.v['remarks'].set(r['remarks'] or '')
        self._live_qty()

    def _collect(self):
        cid = self._contract_id()
        boq_id = _combo_id(self.item_var, self._imap)
        if cid is None or boq_id is None:
            messagebox.showinfo('Missing', 'Select a contract and BOQ item.')
            return None
        qty = civil.measurement_quantity(
            self.v['nos'].get(), self.v['length'].get(),
            self.v['breadth'].get(), self.v['depth'].get())
        return {
            'boq_item_id': boq_id, 'contract_id': cid,
            'mb_date': self.v['mb_date'].get().strip(),
            'mb_ref': self.v['mb_ref'].get().strip(),
            'description': self.v['description'].get().strip(),
            'nos': _num(self.v['nos'].get()), 'length': _num(self.v['length'].get()),
            'breadth': _num(self.v['breadth'].get()), 'depth': _num(self.v['depth'].get()),
            'quantity': qty, 'remarks': self.v['remarks'].get().strip(),
        }

    def add(self):
        d = self._collect()
        if d is None:
            return
        cols = list(d.keys())
        conn = self.db_getter()
        try:
            conn.execute('INSERT INTO measurements ({}) VALUES ({})'.format(
                ', '.join(cols), ', '.join(['?'] * len(cols))),
                [d[c] for c in cols])
            conn.commit()
        finally:
            conn.close()
        self.refresh_items(); self.clear()

    def update(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a measurement.')
            return
        d = self._collect()
        if d is None:
            return
        cols = list(d.keys())
        conn = self.db_getter()
        try:
            conn.execute('UPDATE measurements SET {} WHERE id = ?'.format(
                ', '.join('{} = ?'.format(c) for c in cols)),
                [d[c] for c in cols] + [self.selected_id])
            conn.commit()
        finally:
            conn.close()
        self.refresh_items()

    def delete(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a measurement.')
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM measurements WHERE id = ?', (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_id = None
        self.refresh_items(); self.clear()

    def clear(self):
        self.selected_id = None
        self.item_var.set('')
        for var in self.v.values():
            var.set('')
        self.qty_var.set('0.000')
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())


# ============================================================ RA Bills
class RABillFrame(ttk.Frame):
    HEADER_COLUMNS = ('id', 'bill_no', 'bill_date', 'status', 'this_bill_value',
                      'cumulative_value', 'retention_amt', 'net_payable')
    ITEM_COLUMNS = ('item', 'unit', 'upto_qty', 'previous_qty', 'current_qty',
                    'rate', 'current_amount')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self._cmap = {}
        self.contract_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.retention_var = tk.StringVar(value='5')
        self.deduction_var = tk.StringVar(value='0')
        self.status_var = tk.StringVar(value='Draft')
        self._build_ui()
        self.refresh_contracts()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Contract', font=('TkDefaultFont', 11, 'bold')).pack(side='left')
        self.contract_combo = ttk.Combobox(top, textvariable=self.contract_var,
                                            width=22, state='readonly')
        self.contract_combo.pack(side='left', padx=6)
        self.contract_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_bills())

        gen = ttk.LabelFrame(self, text='Generate RA Bill'); gen.pack(fill='x', padx=8, pady=4)
        for idx, (label, var, w) in enumerate([
                ('Bill Date', self.date_var, 14), ('Retention %', self.retention_var, 8),
                ('Other Deductions', self.deduction_var, 10)]):
            cell = ttk.Frame(gen); cell.grid(row=0, column=idx, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=14).pack(side='left')
            ttk.Entry(cell, textvariable=var, width=w).pack(side='left')
        ttk.Button(gen, text='Generate RA Bill', command=self.generate) \
            .grid(row=0, column=3, padx=8)

        hdr = ttk.LabelFrame(self, text='RA Bills'); hdr.pack(fill='both', expand=True, padx=8, pady=4)
        headings = {'id': 'ID', 'bill_no': 'Bill No', 'bill_date': 'Date',
                    'status': 'Status', 'this_bill_value': 'This Bill',
                    'cumulative_value': 'Cumulative', 'retention_amt': 'Retention',
                    'net_payable': 'Net Payable'}
        self.tree = ttk.Treeview(hdr, columns=self.HEADER_COLUMNS,
                                 show='headings', height=6)
        for col in self.HEADER_COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=50 if col == 'id' else 105, anchor='w')
        self.tree.pack(fill='x', padx=4, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        actions = ttk.Frame(hdr); actions.pack(fill='x', padx=4, pady=4)
        ttk.Label(actions, text='Status').pack(side='left')
        ttk.Combobox(actions, textvariable=self.status_var, width=12,
                     state='readonly',
                     values=['Draft', 'Submitted', 'Approved', 'Paid']).pack(side='left', padx=4)
        ttk.Button(actions, text='Update Status', command=self.update_status).pack(side='left', padx=3)
        ttk.Button(actions, text='Delete Bill', command=self.delete_bill).pack(side='left', padx=3)
        ttk.Button(actions, text='Export Abstract (HTML)', command=self.export_bill).pack(side='left', padx=3)

        abstract = ttk.LabelFrame(self, text='Abstract'); abstract.pack(fill='both', expand=True, padx=8, pady=4)
        headings2 = {'item': 'Item', 'unit': 'Unit', 'upto_qty': 'Qty Upto',
                     'previous_qty': 'Prev Qty', 'current_qty': 'This Bill Qty',
                     'rate': 'Rate', 'current_amount': 'Amount'}
        self.item_tree = ttk.Treeview(abstract, columns=self.ITEM_COLUMNS,
                                      show='headings', height=6)
        for col in self.ITEM_COLUMNS:
            self.item_tree.heading(col, text=headings2[col])
            self.item_tree.column(col, width=140 if col == 'item' else 95, anchor='w')
        self.item_tree.pack(fill='both', expand=True, padx=4, pady=4)

    def refresh_contracts(self):
        conn = self.db_getter()
        try:
            _fill_contract_combo(self.contract_combo, self._cmap,
                                 contract_options(conn))
        finally:
            conn.close()
        self.refresh_bills()

    def _contract_id(self):
        return _combo_id(self.contract_var, self._cmap)

    def refresh_bills(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        cid = self._contract_id()
        if cid is None:
            return
        conn = self.db_getter()
        try:
            for r in conn.execute(
                    'SELECT id, bill_no, bill_date, status, this_bill_value, '
                    'cumulative_value, retention_amt, net_payable FROM ra_bills '
                    'WHERE contract_id = ? ORDER BY id', (cid,)):
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['bill_no'], r['bill_date'], r['status'],
                    '{:.2f}'.format(r['this_bill_value']),
                    '{:.2f}'.format(r['cumulative_value']),
                    '{:.2f}'.format(r['retention_amt']),
                    '{:.2f}'.format(r['net_payable'])))
        finally:
            conn.close()

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        conn = self.db_getter()
        try:
            bill = conn.execute('SELECT status FROM ra_bills WHERE id = ?',
                                (self.selected_id,)).fetchone()
            if bill:
                self.status_var.set(bill['status'])
            for r in conn.execute(
                    "SELECT TRIM(COALESCE(b.item_no,'')||' '||COALESCE(b.description,'')) AS item, "
                    "b.unit, ri.upto_qty, ri.previous_qty, ri.current_qty, "
                    "ri.rate, ri.current_amount FROM ra_bill_items ri "
                    "LEFT JOIN boq_items b ON b.id = ri.boq_item_id "
                    "WHERE ri.ra_bill_id = ? ORDER BY ri.id", (self.selected_id,)):
                self.item_tree.insert('', 'end', values=(
                    r['item'] or '-', r['unit'] or '', '{:.3f}'.format(r['upto_qty']),
                    '{:.3f}'.format(r['previous_qty']), '{:.3f}'.format(r['current_qty']),
                    '{:.2f}'.format(r['rate']), '{:.2f}'.format(r['current_amount'])))
        finally:
            conn.close()

    def generate(self):
        cid = self._contract_id()
        if cid is None:
            messagebox.showinfo('No contract', 'Select a contract.')
            return
        bill_date = self.date_var.get().strip()
        retention_pct = _num(self.retention_var.get(), 0.0)
        other = _num(self.deduction_var.get(), 0.0)
        if retention_pct is None or other is None:
            messagebox.showerror('Invalid number', 'Retention/Deductions must be numbers.')
            return

        conn = self.db_getter()
        try:
            boq = conn.execute('SELECT id, rate FROM boq_items WHERE contract_id = ?',
                               (cid,)).fetchall()
            if not boq:
                messagebox.showinfo('No BOQ', 'This contract has no BOQ items.')
                return
            lines = []
            for b in boq:
                upto = conn.execute(
                    "SELECT COALESCE(SUM(quantity), 0) AS q FROM measurements "
                    "WHERE boq_item_id = ? AND (mb_date <= ? OR mb_date IS NULL "
                    "OR mb_date = '')",
                    (b['id'], bill_date or '9999-12-31')).fetchone()['q']
                previous = conn.execute(
                    "SELECT COALESCE(SUM(ri.current_qty), 0) AS q "
                    "FROM ra_bill_items ri JOIN ra_bills rb ON rb.id = ri.ra_bill_id "
                    "WHERE ri.boq_item_id = ? AND rb.status IN ('Approved', 'Paid')",
                    (b['id'],)).fetchone()['q']
                current, amount = civil.ra_current(upto, previous, b['rate'])
                lines.append((b['id'], upto, previous, current, b['rate'], amount))

            this_bill_value = round(sum(ln[5] for ln in lines), 2)
            previous_value = conn.execute(
                "SELECT COALESCE(SUM(this_bill_value), 0) AS v FROM ra_bills "
                "WHERE contract_id = ? AND status IN ('Approved', 'Paid')",
                (cid,)).fetchone()['v']
            totals = civil.ra_bill_totals(this_bill_value, previous_value,
                                          retention_pct, other)
            count = conn.execute('SELECT COUNT(*) AS c FROM ra_bills WHERE contract_id = ?',
                                 (cid,)).fetchone()['c']
            bill_no = 'RA-{}'.format(count + 1)

            cur = conn.execute(
                'INSERT INTO ra_bills (contract_id, bill_no, bill_date, status, '
                'this_bill_value, previous_value, cumulative_value, retention_pct, '
                'retention_amt, other_deductions, net_payable) '
                "VALUES (?, ?, ?, 'Draft', ?, ?, ?, ?, ?, ?, ?)",
                (cid, bill_no, bill_date, totals['this_bill_value'],
                 totals['previous_value'], totals['cumulative_value'],
                 retention_pct, totals['retention_amt'], other,
                 totals['net_payable']))
            ra_id = cur.lastrowid
            conn.executemany(
                'INSERT INTO ra_bill_items (ra_bill_id, boq_item_id, upto_qty, '
                'previous_qty, current_qty, rate, current_amount) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                [(ra_id,) + ln for ln in lines])
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo('RA Bill generated',
                            '{} generated: net payable {:.2f}.'.format(
                                bill_no, totals['net_payable']))
        self.refresh_bills()

    def update_status(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an RA bill.')
            return
        conn = self.db_getter()
        try:
            conn.execute('UPDATE ra_bills SET status = ? WHERE id = ?',
                         (self.status_var.get(), self.selected_id))
            conn.commit()
        finally:
            conn.close()
        self.refresh_bills()

    def delete_bill(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an RA bill.')
            return
        if not messagebox.askyesno('Confirm delete', 'Delete this RA bill?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM ra_bills WHERE id = ?', (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_id = None
        self.refresh_bills()

    def export_bill(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an RA bill to export.')
            return
        conn = self.db_getter()
        try:
            bill = conn.execute('SELECT * FROM ra_bills WHERE id = ?',
                                (self.selected_id,)).fetchone()
            contract = client = site = None
            if bill and bill['contract_id'] is not None:
                contract = conn.execute('SELECT * FROM contracts WHERE id = ?',
                                        (bill['contract_id'],)).fetchone()
            if contract is not None:
                if contract['client_id'] is not None:
                    client = conn.execute('SELECT * FROM clients WHERE id = ?',
                                          (contract['client_id'],)).fetchone()
                if contract['site_id'] is not None:
                    site = conn.execute('SELECT * FROM sites WHERE id = ?',
                                        (contract['site_id'],)).fetchone()
            items = conn.execute(
                "SELECT b.item_no, b.description, b.unit, ri.upto_qty, "
                "ri.previous_qty, ri.current_qty, ri.rate, ri.current_amount "
                "FROM ra_bill_items ri LEFT JOIN boq_items b ON b.id = ri.boq_item_id "
                "WHERE ri.ra_bill_id = ? ORDER BY ri.id", (self.selected_id,)).fetchall()
        finally:
            conn.close()
        if bill is None:
            return
        html = bill_export.build_ra_bill_html(bill, contract, client, site, items)
        safe = (bill['bill_no'] or 'ra_bill').replace('/', '-').replace(' ', '_')
        path = filedialog.asksaveasfilename(
            title='Save RA bill abstract', defaultextension='.html',
            initialfile='{}.html'.format(safe),
            filetypes=[('HTML document', '*.html'), ('All files', '*.*')])
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(html)
        webbrowser.open('file://' + os.path.abspath(path))


def _blank(value):
    """Render NULL dimensions as an empty string in the grid/form."""
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def build_boq_ra_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(BOQFrame(nb, db_getter), text='BOQ')
    nb.add(MeasurementFrame(nb, db_getter), text='Measurement Book')
    nb.add(RABillFrame(nb, db_getter), text='RA Bills')
    return nb
