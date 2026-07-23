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

import branding
import os
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import theme

from ui_guard import can_write

import civil
import mb
import mb_report
import bill_export
import event_hooks
import followups
import ratebook_picker
import report_open


def contract_options(conn):
    return [(r['id'], r['contract_no'] or 'Contract {}'.format(r['id']))
            for r in conn.execute(
                'SELECT id, contract_no FROM contracts ORDER BY id DESC')]


def _company_name(conn):
    """Firm name from app_settings (Tools > Firm Details), for printouts."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'company_name'").fetchone()
    return (row['value'] if row and row['value'] else '') or branding.APP_NAME


def _fill_contract_combo(combo, mapping, options, include_blank=False):
    display = ['{} - {}'.format(i, n) for i, n in options]
    mapping.clear()
    mapping.update({'{} - {}'.format(i, n): i for i, n in options})
    combo['values'] = ([''] + display) if include_blank else display


def _col(row, key, default=''):
    """Read a column that may predate a migration on an old data file."""
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


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
        ttk.Button(btns, text='From Rate Book…',
                   command=self.pick_from_rate_book).pack(side='left', padx=(3, 12))
        ttk.Button(btns, text='Add', command=self.add).pack(side='left', padx=3)
        ttk.Button(btns, text='Update', command=self.update).pack(side='left', padx=3)
        ttk.Button(btns, text='Delete', command=self.delete).pack(side='left', padx=3)
        ttk.Button(btns, text='Clear', command=self.clear).pack(side='left', padx=3)

    def pick_from_rate_book(self):
        """Fill the BOQ item fields from a chosen rate-book line (editable)."""
        row = ratebook_picker.pick(self, self.db_getter)
        if not row:
            return
        self.v['item_no'].set(row['code'])
        self.v['description'].set(row['description'])
        self.v['unit'].set(row['unit'])
        self.v['rate'].set('{:g}'.format(float(row['rate'] or 0)))

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
        if not can_write():
            return
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
        if not can_write():
            return
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
        if not can_write():
            return
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
                   'breadth', 'depth', 'remarks', 'measured_by', 'checked_by')}
        self.qty_var = tk.StringVar(value='0.000')
        self.check_var = tk.StringVar()
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
                   ('depth', 'Depth'), ('remarks', 'Remarks'),
                   ('measured_by', 'Measured By'),
                   ('checked_by', 'Checked By')]
        for idx, (key, label) in enumerate(entries):
            pos = idx + 1
            cell = ttk.Frame(form); cell.grid(row=pos // 3, column=pos % 3, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=11).pack(side='left')
            e = ttk.Entry(cell, textvariable=self.v[key], width=16)
            e.pack(side='left')
            if key in ('nos', 'length', 'breadth', 'depth'):
                self.v[key].trace_add('write', lambda *a: self._live_qty())

        # Row 4: the ten entry cells above fill rows 0-3 (pos // 3), so the
        # quantity readout has to sit clear of them.
        qcell = ttk.Frame(form)
        qcell.grid(row=4, column=0, padx=6, pady=4, sticky='w')
        ttk.Label(qcell, text='Quantity', width=11).pack(side='left')
        ttk.Label(qcell, textvariable=self.qty_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(side='left')

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btns, text='Add', command=self.add).pack(side='left', padx=3)
        ttk.Button(btns, text='Update', command=self.update).pack(side='left', padx=3)
        ttk.Button(btns, text='Delete', command=self.delete).pack(side='left', padx=3)
        ttk.Button(btns, text='Clear', command=self.clear).pack(side='left', padx=3)
        ttk.Button(btns, text='Export Measurement Book (Form 23)',
                   command=self.export_mb).pack(side='right', padx=3)
        ttk.Label(btns, textvariable=self.check_var,
                  foreground=theme.palette()['warning']).pack(side='right', padx=8)

    def export_mb(self):
        """Print the book in Form 23 layout (a CMB for works >= Rs 15 lakh)."""
        cid = self._contract_id()
        if cid is None:
            messagebox.showinfo('No contract', 'Select a contract first.')
            return
        conn = self.db_getter()
        try:
            if not mb_report.has_measurements(conn, cid):
                messagebox.showinfo(
                    'Nothing to print',
                    'No measurements recorded for this contract.')
                return
            contract, _client, _site = mb_report.contract_context(conn, cid)
            # Same assembly as the browser's /t/ra_bills/<id>/mb, one source.
            html = mb_report.measurement_book_html(conn, cid)
        finally:
            conn.close()
        safe = (_col(contract, 'contract_no', '') or 'contract').replace(
            '/', '-').replace(' ', '_')
        self._save_html(html, '{}_measurement_book.html'.format(safe),
                        'Save measurement book')

    def _contract_context(self, conn, cid):
        """Contract row plus its client and site (any may be None)."""
        contract = conn.execute('SELECT * FROM contracts WHERE id = ?',
                                (cid,)).fetchone()
        client = site = None
        if contract is not None:
            if contract['client_id'] is not None:
                client = conn.execute('SELECT * FROM clients WHERE id = ?',
                                      (contract['client_id'],)).fetchone()
            if contract['site_id'] is not None:
                site = conn.execute('SELECT * FROM sites WHERE id = ?',
                                    (contract['site_id'],)).fetchone()
        return contract, client, site

    def _save_html(self, html, default_name, title):
        path = filedialog.asksaveasfilename(
            title=title, defaultextension='.html', initialfile=default_name,
            filetypes=[('HTML document', '*.html'), ('All files', '*.*')])
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(html)
        webbrowser.open('file://' + os.path.abspath(path))

    def _refresh_check(self, rows):
        """Surface record-integrity errors in the tab, not only on the print.

        A duplicated or zero measurement is a billing error, so it should be
        visible while entering rather than discovered at certification.
        """
        errors = len(mb.blocking_issues(rows))
        warnings = len(mb.integrity_issues(rows)) - errors
        if errors:
            self.check_var.set('{} record error{} — see Form 23 export'.format(
                errors, '' if errors == 1 else 's'))
        elif warnings:
            self.check_var.set('{} record warning{}'.format(
                warnings, '' if warnings == 1 else 's'))
        else:
            self.check_var.set('')

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
            self.check_var.set('')
            return
        conn = self.db_getter()
        try:
            # boq_item_id comes along for the record check, which keys the
            # duplicate test on it.
            sql = ("SELECT m.id, m.mb_date, m.mb_ref, m.boq_item_id, "
                   "TRIM(COALESCE(b.item_no,'')||' '||COALESCE(b.description,'')) AS item, "
                   "m.description, m.nos, m.length, m.breadth, m.depth, m.quantity "
                   "FROM measurements m "
                   "LEFT JOIN boq_items b ON b.id = m.boq_item_id "
                   "WHERE m.contract_id = ? ORDER BY m.id")
            rows = conn.execute(sql, (cid,)).fetchall()
            for r in rows:
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['mb_date'], r['mb_ref'], r['item'] or '-',
                    r['description'], _blank(r['nos']), _blank(r['length']),
                    _blank(r['breadth']), _blank(r['depth']),
                    '{:.3f}'.format(r['quantity'] or 0)))
            self._refresh_check(rows)
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
        self.v['measured_by'].set(_col(r, 'measured_by'))
        self.v['checked_by'].set(_col(r, 'checked_by'))
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
            'measured_by': self.v['measured_by'].get().strip(),
            'checked_by': self.v['checked_by'].get().strip(),
        }

    def add(self):
        if not can_write():
            return
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
        try:
            result = event_hooks.react(followups.MEASUREMENT_ENTERED, {
                'contract_id': d.get('contract_id'),
                'boq_item_id': d.get('boq_item_id'),
                'quantity': d.get('quantity'),
            })
            steps = result.get('followups') or []
            if steps:
                lines = ['• {} — {}'.format(f.get('action', ''), f.get('where', ''))
                         for f in steps]
                messagebox.showinfo(
                    'Suggested next steps',
                    'Measurement saved. Draft follow-ups '
                    '(nothing was auto-posted):\n\n' + '\n'.join(lines))
        except Exception:                                    # noqa: BLE001
            pass
        self.refresh_items(); self.clear()

    def update(self):
        if not can_write():
            return
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
        if not can_write():
            return
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
        # CPWD deducts 2.5% security deposit per running bill (Works Manual
        # Para 21.2) on top of the 5% performance guarantee taken up front.
        # State PWDs vary, so it is an editable default, not a constant.
        self.retention_var = tk.StringVar(value='2.5')
        self.tds_var = tk.StringVar(value='0')
        self.cess_var = tk.StringVar(value='0')
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
                ('Bill Date', self.date_var, 14),
                ('Security Deposit %', self.retention_var, 8),
                ('Income Tax TDS %', self.tds_var, 8),
                ('Labour Cess %', self.cess_var, 8),
                ('Other Deductions', self.deduction_var, 10)]):
            cell = ttk.Frame(gen)
            cell.grid(row=idx // 3, column=idx % 3, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=17).pack(side='left')
            ttk.Entry(cell, textvariable=var, width=w).pack(side='left')
        ttk.Button(gen, text='Generate RA Bill', command=self.generate) \
            .grid(row=1, column=2, padx=8, sticky='e')

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
        ttk.Button(actions, text='Export PWD Abstract', command=self.export_pwd).pack(side='left', padx=3)
        ttk.Button(actions, text='Export Deviation Stmt', command=self.export_deviation).pack(side='left', padx=3)

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

        # Part rate: pay an incomplete item below its BOQ rate (Draft bills
        # only). Edits the selected abstract line's rate and recomputes the
        # bill's payable figures.
        pr = ttk.Frame(abstract); pr.pack(fill='x', padx=4, pady=(0, 4))
        ttk.Label(pr, text='Part Rate').pack(side='left')
        self.part_rate_var = tk.StringVar()
        ttk.Entry(pr, textvariable=self.part_rate_var, width=10).pack(side='left', padx=4)
        ttk.Button(pr, text='Apply to Selected Item',
                   command=self.apply_part_rate).pack(side='left', padx=4)
        ttk.Label(pr, text='(Draft bills only; enter the reduced rate — the '
                           'BOQ rate applies again on the next bill)').pack(side='left')

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
                    "SELECT ri.id, TRIM(COALESCE(b.item_no,'')||' '||COALESCE(b.description,'')) AS item, "
                    "b.unit, ri.upto_qty, ri.previous_qty, ri.current_qty, "
                    "ri.rate, ri.current_amount FROM ra_bill_items ri "
                    "LEFT JOIN boq_items b ON b.id = ri.boq_item_id "
                    "WHERE ri.ra_bill_id = ? ORDER BY ri.id", (self.selected_id,)):
                self.item_tree.insert('', 'end', iid=str(r['id']), values=(
                    r['item'] or '-', r['unit'] or '', '{:.3f}'.format(r['upto_qty']),
                    '{:.3f}'.format(r['previous_qty']), '{:.3f}'.format(r['current_qty']),
                    '{:.2f}'.format(r['rate']), '{:.2f}'.format(r['current_amount'])))
        finally:
            conn.close()

    def generate(self):
        if not can_write():
            return
        cid = self._contract_id()
        if cid is None:
            messagebox.showinfo('No contract', 'Select a contract.')
            return
        bill_date = self.date_var.get().strip()
        retention_pct = _num(self.retention_var.get(), 0.0)
        tds_pct = _num(self.tds_var.get(), 0.0)
        cess_pct = _num(self.cess_var.get(), 0.0)
        other = _num(self.deduction_var.get(), 0.0)
        if None in (retention_pct, tds_pct, cess_pct, other):
            messagebox.showerror(
                'Invalid number',
                'Security deposit, TDS, cess and deductions must be numbers.')
            return

        import ra_generate
        conn = self.db_getter()
        try:
            try:
                result = ra_generate.generate(
                    conn, cid, bill_date=bill_date,
                    retention_pct=retention_pct, tds_pct=tds_pct,
                    cess_pct=cess_pct, other_deductions=other)
            except ValueError as exc:
                messagebox.showinfo('Cannot generate', str(exc))
                return
        finally:
            conn.close()
        messagebox.showinfo('RA Bill generated',
                            '{} generated: net payable {:.2f}.'.format(
                                result['bill_no'],
                                result['totals']['net_payable']))
        self.refresh_bills()

    def apply_part_rate(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an RA bill.')
            return
        sel = self.item_tree.selection()
        if not sel:
            messagebox.showinfo('No item', 'Select an abstract line first.')
            return
        rate = _num(self.part_rate_var.get())
        if rate is None or rate < 0:
            messagebox.showerror('Invalid rate', 'Part rate must be a number.')
            return
        item_id = int(sel[0])
        conn = self.db_getter()
        try:
            bill = conn.execute(
                'SELECT status, previous_value, retention_pct, tds_pct, '
                'cess_pct, other_deductions '
                'FROM ra_bills WHERE id = ?', (self.selected_id,)).fetchone()
            if bill is None:
                return
            if bill['status'] != 'Draft':
                messagebox.showinfo(
                    'Not a draft',
                    'Part rate can only be applied while the bill is a Draft.')
                return
            item = conn.execute(
                'SELECT current_qty FROM ra_bill_items WHERE id = ?',
                (item_id,)).fetchone()
            if item is None:
                return
            conn.execute(
                'UPDATE ra_bill_items SET rate = ?, current_amount = ? '
                'WHERE id = ?',
                (rate, round(item['current_qty'] * rate, 2), item_id))
            # Re-roll the bill's payable figures from the re-priced items.
            this_bill_value = conn.execute(
                'SELECT COALESCE(SUM(current_amount), 0) AS t '
                'FROM ra_bill_items WHERE ra_bill_id = ?',
                (self.selected_id,)).fetchone()['t']
            # Every percentage recovery is charged on this bill's value, so
            # re-pricing an item has to re-roll the tax lines as well. Leaving
            # them at their old amounts would unbalance the posting and leave
            # a memorandum whose recoveries do not sum to the deduction.
            totals = civil.ra_bill_totals(
                this_bill_value, bill['previous_value'],
                bill['retention_pct'], bill['other_deductions'],
                tds_pct=_col(bill, 'tds_pct', 0),
                cess_pct=_col(bill, 'cess_pct', 0))
            conn.execute(
                'UPDATE ra_bills SET this_bill_value = ?, cumulative_value = ?, '
                'retention_amt = ?, tds_amt = ?, cess_amt = ?, '
                'net_payable = ? WHERE id = ?',
                (totals['this_bill_value'], totals['cumulative_value'],
                 totals['retention_amt'], totals['tds_amt'],
                 totals['cess_amt'], totals['net_payable'],
                 self.selected_id))
            conn.commit()
        finally:
            conn.close()
        bid = self.selected_id
        self.refresh_bills()
        if self.tree.exists(str(bid)):
            self.tree.selection_set(str(bid))

    def _save_html(self, html, default_name, title):
        path = filedialog.asksaveasfilename(
            title=title, defaultextension='.html', initialfile=default_name,
            filetypes=[('HTML document', '*.html'), ('All files', '*.*')])
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(html)
        webbrowser.open('file://' + os.path.abspath(path))

    def _bill_context(self, conn):
        """Selected bill + its contract/client/site rows (any may be None)."""
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
        return bill, contract, client, site

    def export_pwd(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an RA bill to export.')
            return
        conn = self.db_getter()
        try:
            bill = conn.execute('SELECT * FROM ra_bills WHERE id = ?',
                                (self.selected_id,)).fetchone()
            # Same assembly as the browser's /t/ra_bills/<id>/ra, one source.
            html = mb_report.ra_abstract_html(conn, self.selected_id)
        finally:
            conn.close()
        if bill is None or html is None:
            return
        safe = (bill['bill_no'] or 'ra_bill').replace('/', '-').replace(' ', '_')
        self._save_html(html, '{}_pwd_abstract.html'.format(safe),
                        'Save PWD-style abstract')

    def export_deviation(self):
        """Deviation statement: tendered BOQ qty vs executed qty upto this bill."""
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an RA bill first.')
            return
        conn = self.db_getter()
        try:
            bill, contract, client, site = self._bill_context(conn)
            items = conn.execute(
                "SELECT b.item_no, b.description, b.unit, b.qty AS boq_qty, "
                "b.rate AS boq_rate, ri.upto_qty "
                "FROM ra_bill_items ri LEFT JOIN boq_items b ON b.id = ri.boq_item_id "
                "WHERE ri.ra_bill_id = ? ORDER BY ri.id", (self.selected_id,)).fetchall()
            company = _company_name(conn)
        finally:
            conn.close()
        if bill is None:
            return
        rows = []
        net_effect = 0.0
        for it in items:
            d = civil.deviation_row(it['boq_qty'], it['upto_qty'], it['boq_rate'])
            net_effect += d['amount_effect']
            rows.append((
                it['item_no'] or '-', it['description'] or '', it['unit'] or '',
                '{:.2f}'.format(it['boq_rate'] or 0),
                '{:.3f}'.format(d['boq_qty']), '{:.3f}'.format(d['executed_qty']),
                '{:+.3f}'.format(d['deviation_qty']),
                '-' if d['deviation_pct'] is None
                else '{:+.1f}%'.format(d['deviation_pct']),
                '{:+.2f}'.format(d['amount_effect'])))
        html = bill_export.build_statement_html(
            'Deviation Statement — {}'.format(bill['bill_no'] or ''),
            ['Contract: {}'.format((contract['contract_no'] if contract else None) or '-'),
             'Client: {}'.format((client['name'] if client else None) or '-'),
             'Site: {}'.format((site['name'] if site else None) or '-'),
             'Quantities executed upto {}'.format(bill['bill_date'] or '-')],
            ['Item', 'Description', 'Unit', 'Rate', 'Tender Qty',
             'Executed Qty', 'Deviation Qty', 'Deviation', 'Amount Effect'],
            rows,
            summary='Net effect of deviations at BOQ rates: {:+.2f} '
                    '({})'.format(round(net_effect, 2),
                                  'excess' if net_effect >= 0 else 'saving'),
            company_name=company)
        safe = (bill['bill_no'] or 'ra_bill').replace('/', '-').replace(' ', '_')
        self._save_html(html, '{}_deviation.html'.format(safe),
                        'Save deviation statement')

    def update_status(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an RA bill.')
            return
        new_status = self.status_var.get()
        conn = self.db_getter()
        try:
            conn.execute('UPDATE ra_bills SET status = ? WHERE id = ?',
                         (new_status, self.selected_id))
            conn.commit()
        finally:
            conn.close()
        self.refresh_bills()
        if new_status in ('Approved', 'Paid'):
            result = event_hooks.react(followups.RA_BILL_APPROVED, {
                'ra_bill_id': self.selected_id, 'status': new_status})
            steps = result.get('followups') or []
            if steps:
                lines = []
                for f in steps:
                    tag = '  [needs your approval]' if f.get('gated') else ''
                    lines.append('• {} — {}{}'.format(
                        f.get('action', ''), f.get('where', ''), tag))
                messagebox.showinfo(
                    'Suggested next steps',
                    'Status updated. Draft follow-ups (nothing was auto-posted):\n\n'
                    + '\n'.join(lines))

    def delete_bill(self):
        if not can_write():
            return
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


class DeviationStatement(ttk.Frame):
    """PWD-style deviation statement: tendered BOQ vs executed (measured).

    For each BOQ item of a contract, tendered qty (BOQ) is compared with the
    executed qty (sum of measurements) at the BOQ rate, showing the deviation
    quantity/amount and whether it is an Excess or a Saving. Printable.
    """

    COLUMNS = ('item', 'desc', 'unit', 'rate', 'tender_qty', 'exec_qty',
               'dev_qty', 'dev_amt', 'status')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._map = {}
        self._rows = []
        self.contract_var = tk.StringVar()

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Deviation Statement',
                  font=('TkDefaultFont', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='right', padx=2)

        sel = ttk.Frame(self); sel.pack(fill='x', padx=8, pady=(0, 4))
        ttk.Label(sel, text='Contract').pack(side='left')
        self.combo = ttk.Combobox(sel, textvariable=self.contract_var, width=26,
                                  state='readonly')
        self.combo.pack(side='left', padx=6)
        self.combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Button(sel, text='Reload', command=self.reload).pack(side='left')

        heads = {'item': 'Item', 'desc': 'Description', 'unit': 'Unit',
                 'rate': 'Rate', 'tender_qty': 'BOQ Qty', 'exec_qty': 'Exec Qty',
                 'dev_qty': 'Dev Qty', 'dev_amt': 'Dev Amount', 'status': 'Status'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=160 if col == 'desc' else 85, anchor='w')
        self.tree.tag_configure('excess', background=theme.wash('bad'))
        self.tree.tag_configure('saving', background=theme.wash('good'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=4)
        self.reload()

    def reload(self):
        conn = self.db_getter()
        try:
            opts = contract_options(conn)
        finally:
            conn.close()
        self._map = {'{} - {}'.format(i, n): i for i, n in opts}
        self.combo['values'] = ['{} - {}'.format(i, n) for i, n in opts]
        if opts and not self.contract_var.get():
            self.contract_var.set('{} - {}'.format(opts[0][0], opts[0][1]))
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        raw = self.contract_var.get().strip()
        if not raw:
            return
        cid = self._map.get(raw, raw.split(' - ')[0])
        conn = self.db_getter()
        try:
            rows = conn.execute(
                "SELECT b.item_no, b.description, b.unit, b.qty AS tender, b.rate, "
                "COALESCE((SELECT SUM(m.quantity) FROM measurements m "
                "WHERE m.boq_item_id = b.id), 0) AS executed "
                "FROM boq_items b WHERE b.contract_id = ? ORDER BY b.id",
                (cid,)).fetchall()
        finally:
            conn.close()
        tot_dev = 0.0
        for r in rows:
            d = civil.deviation(r['tender'], r['executed'], r['rate'])
            tot_dev += d['deviation_amount']
            tag = {'Excess': 'excess', 'Saving': 'saving'}.get(d['status'], '')
            row = (r['item_no'] or '-', r['description'] or '', r['unit'] or '',
                   '{:.2f}'.format(r['rate'] or 0),
                   '{:.3f}'.format(d['tender_qty']),
                   '{:.3f}'.format(d['executed_qty']),
                   '{:.3f}'.format(d['deviation_qty']),
                   '{:.2f}'.format(d['deviation_amount']), d['status'])
            self.tree.insert('', 'end', values=row, tags=(tag,))
            self._rows.append(row)
        self.summary_var.set('Net deviation amount: {:,.2f}'.format(round(tot_dev, 2)))

    def export(self):
        html = bill_export.build_statement_html(
            'Deviation Statement', ['Contract: {}'.format(self.contract_var.get())],
            ['Item', 'Description', 'Unit', 'Rate', 'BOQ Qty', 'Exec Qty',
             'Dev Qty', 'Dev Amount', 'Status'], self._rows,
            summary=self.summary_var.get())
        report_open.save_and_open_html(html, 'deviation_statement.html')


def build_boq_ra_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(BOQFrame(nb, db_getter), text='BOQ')
    nb.add(MeasurementFrame(nb, db_getter), text='Measurement Book')
    nb.add(RABillFrame(nb, db_getter), text='RA Bills')
    nb.add(DeviationStatement(nb, db_getter), text='Deviation')
    return nb
