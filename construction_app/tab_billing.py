"""Bills / Running Bills — bespoke header+items UI with running-total math.

Running bills need a computed ``previous_billed`` (sum of prior Approved/Paid
bills on the same contract) that ``DocumentFrame`` has no concept of, so this
tab implements its own header+items UI by hand.

    previous_billed = SUM(net_payable) FROM bills
                       WHERE contract_id = <this contract>
                       AND status IN ('Approved', 'Paid')
                       [AND id != <this bill, when updating>]

    net_payable = work_done_value - previous_billed
                  - retention_amt - other_deductions

Draft/Submitted bills are excluded from ``previous_billed``. Line items are a
separate BOQ breakdown that do NOT auto-drive ``work_done_value``: the user
clicks "Sum Items -> Work Done Value", then "Update Selected" to persist.
"""

import os
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ui_guard import can_write

import bill_export
from tab_masters import site_options  # noqa: F401  (kept for parity/imports)


APPROVED_STATUSES = ('Approved', 'Paid')


# ---------------------------------------------------------------- pure logic
def compute_net_payable(work_done_value, previous_billed, retention_amt,
                        other_deductions):
    """The core running-bill formula (extracted for testability)."""
    return (work_done_value - previous_billed
            - retention_amt - other_deductions)


def _contract_options(conn):
    return [(r['id'], r['contract_no'] or 'Contract {}'.format(r['id']))
            for r in conn.execute(
                'SELECT id, contract_no FROM contracts ORDER BY id')]


class BillingTab(ttk.Frame):
    HEADER_COLUMNS = ('id', 'contract', 'bill_no', 'bill_date', 'status',
                      'work_done', 'prev_billed', 'retention', 'other_ded',
                      'net_payable')
    ITEM_COLUMNS = ('id', 'description', 'unit', 'qty', 'rate', 'amount')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_bill_id = None
        self.selected_item_id = None
        self._contract_map = {}   # display -> id

        self.h = {}   # header var key -> StringVar
        self.i = {}   # item var key -> StringVar

        self._build_ui()
        self.refresh_bills()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        ttk.Label(self, text='Bills / Running Bills',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        hdr = ttk.LabelFrame(self, text='Bills')
        hdr.pack(fill='both', expand=True, padx=8, pady=4)

        headings = {'id': 'ID', 'contract': 'Contract', 'bill_no': 'Bill No',
                    'bill_date': 'Date', 'status': 'Status',
                    'work_done': 'Work Done', 'prev_billed': 'Prev Billed',
                    'retention': 'Retention', 'other_ded': 'Other Ded',
                    'net_payable': 'Net Payable'}
        self.bill_tree = ttk.Treeview(hdr, columns=self.HEADER_COLUMNS,
                                      show='headings', height=7)
        for col in self.HEADER_COLUMNS:
            self.bill_tree.heading(col, text=headings[col])
            self.bill_tree.column(col, width=50 if col == 'id' else 100,
                                  anchor='w')
        self.bill_tree.pack(fill='x', padx=4, pady=4)
        self.bill_tree.bind('<<TreeviewSelect>>', self._on_bill_select)

        form = ttk.Frame(hdr)
        form.pack(fill='x', padx=4, pady=4)

        # Editable header inputs.
        self.h['contract'] = tk.StringVar()
        self.h['bill_no'] = tk.StringVar()
        self.h['bill_date'] = tk.StringVar()
        self.h['status'] = tk.StringVar(value='Draft')
        self.h['work_done_value'] = tk.StringVar(value='0')
        self.h['retention_amt'] = tk.StringVar(value='0')
        self.h['other_deductions'] = tk.StringVar(value='0')
        self.h['remarks'] = tk.StringVar()

        cell = ttk.Frame(form); cell.grid(row=0, column=0, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text='Contract', width=12).pack(side='left')
        self.contract_combo = ttk.Combobox(cell, textvariable=self.h['contract'],
                                            width=18, state='readonly')
        self.contract_combo.pack(side='left')

        self._entry(form, 0, 1, 'Bill No', 'bill_no')
        self._entry(form, 0, 2, 'Bill Date', 'bill_date')

        cell = ttk.Frame(form); cell.grid(row=1, column=0, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text='Status', width=12).pack(side='left')
        ttk.Combobox(cell, textvariable=self.h['status'], width=18,
                     state='readonly',
                     values=['Draft', 'Submitted', 'Approved', 'Paid']) \
            .pack(side='left')

        self._entry(form, 1, 1, 'Work Done', 'work_done_value')
        self._entry(form, 1, 2, 'Retention', 'retention_amt')
        self._entry(form, 2, 0, 'Other Ded', 'other_deductions')
        self._entry(form, 2, 1, 'Remarks', 'remarks')

        hbtns = ttk.Frame(hdr)
        hbtns.pack(fill='x', padx=4, pady=4)
        ttk.Button(hbtns, text='Add Bill', command=self.add_bill).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Update Selected', command=self.update_bill).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Delete Bill', command=self.delete_bill).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Sum Items -> Work Done Value',
                   command=self.sum_items_to_work_done).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Make Bill (Export)',
                   command=self.make_bill).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Clear', command=self.clear_bill).pack(side='left', padx=3)

        # ---------------- items ----------------
        items = ttk.LabelFrame(self, text='Bill Items (BOQ breakdown)')
        items.pack(fill='both', expand=True, padx=8, pady=4)

        self.item_tree = ttk.Treeview(items, columns=self.ITEM_COLUMNS,
                                      show='headings', height=6)
        for col in self.ITEM_COLUMNS:
            self.item_tree.heading(col, text=col.title())
            self.item_tree.column(col, width=50 if col == 'id' else 120,
                                  anchor='w')
        self.item_tree.pack(fill='x', padx=4, pady=4)
        self.item_tree.bind('<<TreeviewSelect>>', self._on_item_select)

        iform = ttk.Frame(items)
        iform.pack(fill='x', padx=4, pady=4)
        for idx, (key, label) in enumerate(
                [('description', 'Description'), ('unit', 'Unit'),
                 ('qty', 'Qty'), ('rate', 'Rate')]):
            self.i[key] = tk.StringVar()
            cell = ttk.Frame(iform); cell.grid(row=0, column=idx, padx=6, pady=3, sticky='w')
            ttk.Label(cell, text=label, width=10).pack(side='left')
            ttk.Entry(cell, textvariable=self.i[key], width=16).pack(side='left')

        ibtns = ttk.Frame(items)
        ibtns.pack(fill='x', padx=4, pady=4)
        ttk.Button(ibtns, text='Add Item', command=self.add_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Update Item', command=self.update_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Delete Item', command=self.delete_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Clear', command=self.clear_item).pack(side='left', padx=3)

    def _entry(self, parent, row, col, label, key):
        cell = ttk.Frame(parent)
        cell.grid(row=row, column=col, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=12).pack(side='left')
        ttk.Entry(cell, textvariable=self.h[key], width=20).pack(side='left')

    # -------------------------------------------------------------- helpers
    def _num(self, var_key, label):
        raw = self.h[var_key].get().strip()
        try:
            return float(raw) if raw else 0.0
        except ValueError:
            messagebox.showerror('Invalid number',
                                 '"{}" must be a number.'.format(label))
            return None

    def _contract_id(self):
        raw = self.h['contract'].get().strip()
        if not raw:
            return None
        return self._contract_map.get(raw, raw.split(' - ')[0])

    def _previous_billed(self, conn, contract_id, exclude_bill_id=None):
        """SUM(net_payable) of prior Approved/Paid bills on this contract."""
        sql = ("SELECT COALESCE(SUM(net_payable), 0) AS t FROM bills "
               "WHERE contract_id = ? AND status IN ('Approved', 'Paid')")
        params = [contract_id]
        if exclude_bill_id is not None:
            sql += ' AND id != ?'
            params.append(exclude_bill_id)
        return conn.execute(sql, params).fetchone()['t']

    # ----------------------------------------------------------- bill ops
    def refresh_bills(self):
        conn = self.db_getter()
        try:
            options = _contract_options(conn)
            display = ['{} - {}'.format(cid, label) for cid, label in options]
            self._contract_map = {
                '{} - {}'.format(cid, label): cid for cid, label in options}
            self.contract_combo['values'] = display

            for item in self.bill_tree.get_children():
                self.bill_tree.delete(item)
            sql = ("SELECT b.id, c.contract_no, b.contract_id, b.bill_no, "
                   "b.bill_date, b.status, b.work_done_value, b.previous_billed, "
                   "b.retention_amt, b.other_deductions, b.net_payable "
                   "FROM bills b LEFT JOIN contracts c ON c.id = b.contract_id "
                   "ORDER BY b.contract_id, b.id")
            for r in conn.execute(sql):
                contract_label = r['contract_no'] or (
                    'Contract {}'.format(r['contract_id'])
                    if r['contract_id'] is not None else '-')
                self.bill_tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], contract_label, r['bill_no'], r['bill_date'],
                    r['status'], '{:.2f}'.format(r['work_done_value']),
                    '{:.2f}'.format(r['previous_billed']),
                    '{:.2f}'.format(r['retention_amt']),
                    '{:.2f}'.format(r['other_deductions']),
                    '{:.2f}'.format(r['net_payable'])))
        finally:
            conn.close()

    def _on_bill_select(self, _event=None):
        sel = self.bill_tree.selection()
        if not sel:
            return
        self.selected_bill_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM bills WHERE id = ?',
                             (self.selected_bill_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        if r['contract_id'] is not None:
            for disp, cid in self._contract_map.items():
                if str(cid) == str(r['contract_id']):
                    self.h['contract'].set(disp)
                    break
        self.h['bill_no'].set(r['bill_no'] or '')
        self.h['bill_date'].set(r['bill_date'] or '')
        self.h['status'].set(r['status'] or 'Draft')
        self.h['work_done_value'].set(str(r['work_done_value']))
        self.h['retention_amt'].set(str(r['retention_amt']))
        self.h['other_deductions'].set(str(r['other_deductions']))
        self.h['remarks'].set(r['remarks'] or '')
        self.refresh_items()

    def add_bill(self):
        if not can_write():
            return
        contract_id = self._contract_id()
        if contract_id is None:
            messagebox.showinfo('No contract', 'Select a contract.')
            return
        work_done = self._num('work_done_value', 'Work Done')
        retention = self._num('retention_amt', 'Retention')
        other = self._num('other_deductions', 'Other Ded')
        if None in (work_done, retention, other):
            return
        status = self.h['status'].get().strip() or 'Draft'
        conn = self.db_getter()
        try:
            prev = self._previous_billed(conn, contract_id)
            net = compute_net_payable(work_done, prev, retention, other)
            conn.execute(
                "INSERT INTO bills (contract_id, bill_no, bill_date, status, "
                "work_done_value, previous_billed, retention_amt, "
                "other_deductions, net_payable, remarks) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (contract_id, self.h['bill_no'].get().strip(),
                 self.h['bill_date'].get().strip(), status, work_done, prev,
                 retention, other, net, self.h['remarks'].get().strip()))
            conn.commit()
        finally:
            conn.close()
        self.refresh_bills()
        self.clear_bill()

    def update_bill(self):
        if not can_write():
            return
        if self.selected_bill_id is None:
            messagebox.showinfo('No selection', 'Select a bill to update.')
            return
        contract_id = self._contract_id()
        if contract_id is None:
            messagebox.showinfo('No contract', 'Select a contract.')
            return
        work_done = self._num('work_done_value', 'Work Done')
        retention = self._num('retention_amt', 'Retention')
        other = self._num('other_deductions', 'Other Ded')
        if None in (work_done, retention, other):
            return
        status = self.h['status'].get().strip() or 'Draft'
        conn = self.db_getter()
        try:
            prev = self._previous_billed(conn, contract_id,
                                         exclude_bill_id=self.selected_bill_id)
            net = compute_net_payable(work_done, prev, retention, other)
            conn.execute(
                "UPDATE bills SET contract_id = ?, bill_no = ?, bill_date = ?, "
                "status = ?, work_done_value = ?, previous_billed = ?, "
                "retention_amt = ?, other_deductions = ?, net_payable = ?, "
                "remarks = ? WHERE id = ?",
                (contract_id, self.h['bill_no'].get().strip(),
                 self.h['bill_date'].get().strip(), status, work_done, prev,
                 retention, other, net, self.h['remarks'].get().strip(),
                 self.selected_bill_id))
            conn.commit()
        finally:
            conn.close()
        self.refresh_bills()

    def delete_bill(self):
        if not can_write():
            return
        if self.selected_bill_id is None:
            messagebox.showinfo('No selection', 'Select a bill to delete.')
            return
        if not messagebox.askyesno('Confirm delete',
                                   'Delete this bill and its items?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM bills WHERE id = ?',
                         (self.selected_bill_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_bill_id = None
        self.refresh_bills()
        self.refresh_items()
        self.clear_bill()

    def sum_items_to_work_done(self):
        """Pull the item total into the Work Done Value field (manual step)."""
        if self.selected_bill_id is None:
            messagebox.showinfo('No bill', 'Select a bill first.')
            return
        conn = self.db_getter()
        try:
            total = conn.execute(
                'SELECT COALESCE(SUM(amount), 0) AS t FROM bill_items '
                'WHERE bill_id = ?', (self.selected_bill_id,)).fetchone()['t']
        finally:
            conn.close()
        self.h['work_done_value'].set('{:.2f}'.format(total))
        messagebox.showinfo(
            'Work Done Value',
            'Pulled item total {:.2f}. Click "Update Selected" to save.'.format(
                total))

    def make_bill(self):
        """Render the selected bill to a printable HTML file and open it."""
        if self.selected_bill_id is None:
            messagebox.showinfo('No bill', 'Select a bill to export.')
            return
        conn = self.db_getter()
        try:
            bill = conn.execute('SELECT * FROM bills WHERE id = ?',
                                (self.selected_bill_id,)).fetchone()
            if bill is None:
                messagebox.showerror('Not found', 'That bill no longer exists.')
                return
            contract = client = site = None
            if bill['contract_id'] is not None:
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
                'SELECT description, unit, qty, rate, amount FROM bill_items '
                'WHERE bill_id = ? ORDER BY id',
                (self.selected_bill_id,)).fetchall()
        finally:
            conn.close()

        html = bill_export.build_bill_html(bill, contract, client, site, items)

        safe_no = (bill['bill_no'] or 'bill').replace('/', '-').replace(' ', '_')
        path = filedialog.asksaveasfilename(
            title='Save bill as', defaultextension='.html',
            initialfile='bill_{}.html'.format(safe_no),
            filetypes=[('HTML document', '*.html'), ('All files', '*.*')])
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(html)
        except OSError as exc:
            messagebox.showerror('Save failed', str(exc))
            return
        webbrowser.open('file://' + os.path.abspath(path))

    def clear_bill(self):
        self.selected_bill_id = None
        self.h['contract'].set('')
        self.h['bill_no'].set('')
        self.h['bill_date'].set('')
        self.h['status'].set('Draft')
        self.h['work_done_value'].set('0')
        self.h['retention_amt'].set('0')
        self.h['other_deductions'].set('0')
        self.h['remarks'].set('')
        if self.bill_tree.selection():
            self.bill_tree.selection_remove(self.bill_tree.selection())
        self.refresh_items()

    # ------------------------------------------------------------- item ops
    def refresh_items(self):
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        if self.selected_bill_id is None:
            return
        conn = self.db_getter()
        try:
            for r in conn.execute(
                    'SELECT id, description, unit, qty, rate, amount '
                    'FROM bill_items WHERE bill_id = ? ORDER BY id',
                    (self.selected_bill_id,)):
                self.item_tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['description'], r['unit'], r['qty'], r['rate'],
                    r['amount']))
        finally:
            conn.close()

    def _on_item_select(self, _event=None):
        sel = self.item_tree.selection()
        if not sel:
            return
        self.selected_item_id = int(sel[0])
        values = self.item_tree.item(sel[0], 'values')
        self.i['description'].set(values[1])
        self.i['unit'].set(values[2])
        self.i['qty'].set(values[3])
        self.i['rate'].set(values[4])

    def _collect_item(self):
        try:
            qty = float(self.i['qty'].get().strip() or 0)
            rate = float(self.i['rate'].get().strip() or 0)
        except ValueError:
            messagebox.showerror('Invalid number', 'Qty/Rate must be numbers.')
            return None
        return (self.i['description'].get().strip(),
                self.i['unit'].get().strip(), qty, rate, qty * rate)

    def add_item(self):
        if not can_write():
            return
        if self.selected_bill_id is None:
            messagebox.showinfo('No bill', 'Select a bill first.')
            return
        item = self._collect_item()
        if item is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO bill_items (bill_id, description, unit, qty, rate, '
                'amount) VALUES (?, ?, ?, ?, ?, ?)',
                (self.selected_bill_id,) + item)
            conn.commit()
        finally:
            conn.close()
        self.refresh_items()
        self.clear_item()

    def update_item(self):
        if not can_write():
            return
        if self.selected_item_id is None:
            messagebox.showinfo('No selection', 'Select a line item.')
            return
        item = self._collect_item()
        if item is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'UPDATE bill_items SET description = ?, unit = ?, qty = ?, '
                'rate = ?, amount = ? WHERE id = ?',
                item + (self.selected_item_id,))
            conn.commit()
        finally:
            conn.close()
        self.refresh_items()

    def delete_item(self):
        if not can_write():
            return
        if self.selected_item_id is None:
            messagebox.showinfo('No selection', 'Select a line item.')
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM bill_items WHERE id = ?',
                         (self.selected_item_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_item_id = None
        self.refresh_items()
        self.clear_item()

    def clear_item(self):
        self.selected_item_id = None
        for var in self.i.values():
            var.set('')
        if self.item_tree.selection():
            self.item_tree.selection_remove(self.item_tree.selection())
