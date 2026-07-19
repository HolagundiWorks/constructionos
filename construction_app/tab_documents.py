"""Header + line-items documents: Quotations and Estimates.

``DocumentFrame`` is a header grid+form on top and a line-items grid+form on
the bottom, joined by ``fk_col``. Selecting a header loads only that document's
items. Every item add/update/delete calls ``_recalc_total`` which re-sums the
items and writes the total into the header's ``total_col`` — the header total
is always derived, never hand-entered (there is deliberately no field for it in
``header_fields``).

Contracts is a plain ``CrudFrame`` (no line items) and lives at the bottom of
this file.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import bill_export
import report_open
from crud_frame import CrudFrame, Field
from ui_guard import can_write
from tab_masters import site_options, client_options, vendor_options


class DocumentFrame(ttk.Frame):
    ITEM_COLUMNS = ('id', 'description', 'unit', 'qty', 'rate', 'amount')

    def __init__(self, parent, db_getter, header_table, header_fields,
                 item_table, fk_col, total_col, title,
                 header_order_by='id DESC'):
        super().__init__(parent)
        self.db_getter = db_getter
        self.header_table = header_table
        self.header_fields = header_fields
        self.item_table = item_table
        self.fk_col = fk_col
        self.total_col = total_col
        self.title = title
        self.header_order_by = header_order_by

        self.header_vars = {}
        self.header_widgets = {}
        self._fk_maps = {}
        self.selected_header_id = None

        self.item_vars = {}
        self.selected_item_id = None

        self._build_ui()
        self.refresh_headers()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        ttk.Label(self, text=self.title,
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        # ---------------- header ----------------
        hdr = ttk.LabelFrame(self, text='Documents')
        hdr.pack(fill='both', expand=True, padx=8, pady=4)

        columns = ['id'] + [f.key for f in self.header_fields] + [self.total_col]
        self.header_tree = ttk.Treeview(hdr, columns=columns, show='headings',
                                        height=7)
        for col in columns:
            if col == 'id':
                label = 'ID'
            elif col == self.total_col:
                label = 'Total'
            else:
                label = next(f.label for f in self.header_fields if f.key == col)
            self.header_tree.heading(col, text=label)
            self.header_tree.column(col, width=50 if col == 'id' else 120,
                                    anchor='w')
        self.header_tree.pack(fill='x', padx=4, pady=4)
        self.header_tree.bind('<<TreeviewSelect>>', self._on_header_select)

        form = ttk.Frame(hdr)
        form.pack(fill='x', padx=4, pady=4)
        for idx, field in enumerate(self.header_fields):
            row, col = divmod(idx, 3)
            cell = ttk.Frame(form)
            cell.grid(row=row, column=col, padx=6, pady=3, sticky='w')
            ttk.Label(cell, text=field.label, width=12).pack(side='left')
            var = tk.StringVar(value=field.default)
            self.header_vars[field.key] = var
            if field.kind in ('combo', 'fk'):
                w = ttk.Combobox(cell, textvariable=var, width=18,
                                 state='readonly')
                if field.kind == 'combo':
                    w['values'] = field.options
            else:
                w = ttk.Entry(cell, textvariable=var, width=20)
            w.pack(side='left')
            self.header_widgets[field.key] = w

        hbtns = ttk.Frame(hdr)
        hbtns.pack(fill='x', padx=4, pady=4)
        ttk.Button(hbtns, text='Add Doc', command=self.add_header).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Update Doc', command=self.update_header).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Delete Doc', command=self.delete_header).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Print / Export', command=self.export_document).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Clear', command=self.clear_header).pack(side='left', padx=3)

        # ---------------- items ----------------
        items = ttk.LabelFrame(self, text='Line Items')
        items.pack(fill='both', expand=True, padx=8, pady=4)

        self.item_tree = ttk.Treeview(items, columns=self.ITEM_COLUMNS,
                                      show='headings', height=7)
        for col in self.ITEM_COLUMNS:
            self.item_tree.heading(col, text=col.title())
            self.item_tree.column(col, width=50 if col == 'id' else 120,
                                  anchor='w')
        self.item_tree.pack(fill='x', padx=4, pady=4)
        self.item_tree.bind('<<TreeviewSelect>>', self._on_item_select)

        iform = ttk.Frame(items)
        iform.pack(fill='x', padx=4, pady=4)
        item_fields = [('description', 'Description'), ('unit', 'Unit'),
                       ('qty', 'Qty'), ('rate', 'Rate')]
        for idx, (key, label) in enumerate(item_fields):
            cell = ttk.Frame(iform)
            cell.grid(row=0, column=idx, padx=6, pady=3, sticky='w')
            ttk.Label(cell, text=label, width=10).pack(side='left')
            var = tk.StringVar()
            self.item_vars[key] = var
            ttk.Entry(cell, textvariable=var, width=16).pack(side='left')

        ibtns = ttk.Frame(items)
        ibtns.pack(fill='x', padx=4, pady=4)
        ttk.Button(ibtns, text='Add Item', command=self.add_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Update Item', command=self.update_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Delete Item', command=self.delete_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Clear', command=self.clear_item).pack(side='left', padx=3)

    # -------------------------------------------------------------- helpers
    def _refresh_fk_options(self, conn):
        for field in self.header_fields:
            if field.kind != 'fk' or not field.options_func:
                continue
            rows = field.options_func(conn)
            display = ['{} - {}'.format(rid, label) for rid, label in rows]
            self._fk_maps[field.key] = {
                '{} - {}'.format(rid, label): rid for rid, label in rows}
            self.header_widgets[field.key]['values'] = display

    def _collect_header(self):
        values = {}
        for field in self.header_fields:
            raw = self.header_vars[field.key].get().strip()
            if field.kind == 'number':
                try:
                    values[field.key] = float(raw) if raw else 0.0
                except ValueError:
                    messagebox.showerror('Invalid number',
                                         '"{}" must be a number.'.format(field.label))
                    return None
            elif field.kind == 'fk':
                values[field.key] = None if raw == '' else \
                    self._fk_maps.get(raw, raw.split(' - ')[0])
            else:
                values[field.key] = raw
        return values

    def _parse_number(self, raw, label):
        try:
            return float(raw) if raw else 0.0
        except ValueError:
            messagebox.showerror('Invalid number',
                                 '"{}" must be a number.'.format(label))
            return None

    # ----------------------------------------------------------- header ops
    def refresh_headers(self):
        conn = self.db_getter()
        try:
            self._refresh_fk_options(conn)
            for item in self.header_tree.get_children():
                self.header_tree.delete(item)
            cols = ['id'] + [f.key for f in self.header_fields] + [self.total_col]
            sql = 'SELECT {} FROM {} ORDER BY {}'.format(
                ', '.join(cols), self.header_table, self.header_order_by)
            for row in conn.execute(sql):
                self.header_tree.insert('', 'end', iid=str(row['id']),
                                        values=[row[c] for c in cols])
        finally:
            conn.close()

    def _on_header_select(self, _event=None):
        sel = self.header_tree.selection()
        if not sel:
            return
        self.selected_header_id = int(sel[0])
        values = self.header_tree.item(sel[0], 'values')
        for idx, field in enumerate(self.header_fields):
            val = values[idx + 1]
            self.header_vars[field.key].set('' if val is None else str(val))
        self.refresh_items()

    def add_header(self):
        if not can_write():
            return
        values = self._collect_header()
        if values is None:
            return
        cols = list(values.keys())
        sql = 'INSERT INTO {} ({}) VALUES ({})'.format(
            self.header_table, ', '.join(cols), ', '.join(['?'] * len(cols)))
        conn = self.db_getter()
        try:
            conn.execute(sql, [values[c] for c in cols])
            conn.commit()
        finally:
            conn.close()
        self.refresh_headers()
        self.clear_header()

    def update_header(self):
        if not can_write():
            return
        if self.selected_header_id is None:
            messagebox.showinfo('No selection', 'Select a document to update.')
            return
        values = self._collect_header()
        if values is None:
            return
        cols = list(values.keys())
        assignments = ', '.join('{} = ?'.format(c) for c in cols)
        sql = 'UPDATE {} SET {} WHERE id = ?'.format(self.header_table, assignments)
        conn = self.db_getter()
        try:
            conn.execute(sql, [values[c] for c in cols] + [self.selected_header_id])
            conn.commit()
        finally:
            conn.close()
        self.refresh_headers()

    def delete_header(self):
        if not can_write():
            return
        if self.selected_header_id is None:
            messagebox.showinfo('No selection', 'Select a document to delete.')
            return
        if not messagebox.askyesno('Confirm delete',
                                   'Delete this document and all its items?'):
            return
        conn = self.db_getter()
        try:
            # Delete children first (explicit, even though the FK also cascades).
            conn.execute('DELETE FROM {} WHERE {} = ?'.format(
                self.item_table, self.fk_col), (self.selected_header_id,))
            conn.execute('DELETE FROM {} WHERE id = ?'.format(
                self.header_table), (self.selected_header_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_header_id = None
        self.refresh_headers()
        self.refresh_items()
        self.clear_header()

    def clear_header(self):
        self.selected_header_id = None
        for field in self.header_fields:
            self.header_vars[field.key].set(field.default)
        if self.header_tree.selection():
            self.header_tree.selection_remove(self.header_tree.selection())
        self.refresh_items()

    def export_document(self):
        """Render the selected document (header fields + items + total) to HTML."""
        if self.selected_header_id is None:
            messagebox.showinfo('No selection', 'Select a document to export.')
            return
        conn = self.db_getter()
        try:
            cols = ['id'] + [f.key for f in self.header_fields] + [self.total_col]
            row = conn.execute('SELECT {} FROM {} WHERE id = ?'.format(
                ', '.join(cols), self.header_table),
                (self.selected_header_id,)).fetchone()
            items = conn.execute(
                'SELECT description, unit, qty, rate, amount FROM {} '
                'WHERE {} = ? ORDER BY id'.format(self.item_table, self.fk_col),
                (self.selected_header_id,)).fetchall()
        finally:
            conn.close()
        if row is None:
            return
        # Header field label:value pairs, resolving fk ids back to their labels.
        meta = []
        for f in self.header_fields:
            val = row[f.key]
            if val in (None, ''):
                continue
            if f.kind == 'fk':
                val = next((d for d, i in self._fk_maps.get(f.key, {}).items()
                            if str(i) == str(val)), val)
            meta.append('{}: {}'.format(f.label, val))
        item_rows = [(str(idx), it['description'] or '', it['unit'] or '',
                      '{:.2f}'.format(it['qty'] or 0), '{:.2f}'.format(it['rate'] or 0),
                      '{:.2f}'.format(it['amount'] or 0))
                     for idx, it in enumerate(items, start=1)]
        html = bill_export.build_statement_html(
            self.title, meta,
            ['#', 'Description', 'Unit', 'Qty', 'Rate', 'Amount'], item_rows,
            summary='Total: {:,.2f}'.format(row[self.total_col] or 0))
        report_open.save_and_open_html(
            html, self.title.lower().replace(' ', '_') + '.html')

    # ------------------------------------------------------------- item ops
    def refresh_items(self):
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        if self.selected_header_id is None:
            return
        conn = self.db_getter()
        try:
            sql = ('SELECT id, description, unit, qty, rate, amount '
                   'FROM {} WHERE {} = ? ORDER BY id'.format(
                       self.item_table, self.fk_col))
            for r in conn.execute(sql, (self.selected_header_id,)):
                self.item_tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['description'], r['unit'],
                    r['qty'], r['rate'], r['amount']))
        finally:
            conn.close()

    def _on_item_select(self, _event=None):
        sel = self.item_tree.selection()
        if not sel:
            return
        self.selected_item_id = int(sel[0])
        values = self.item_tree.item(sel[0], 'values')
        self.item_vars['description'].set(values[1])
        self.item_vars['unit'].set(values[2])
        self.item_vars['qty'].set(values[3])
        self.item_vars['rate'].set(values[4])

    def _collect_item(self):
        qty = self._parse_number(self.item_vars['qty'].get().strip(), 'Qty')
        if qty is None:
            return None
        rate = self._parse_number(self.item_vars['rate'].get().strip(), 'Rate')
        if rate is None:
            return None
        return {
            'description': self.item_vars['description'].get().strip(),
            'unit': self.item_vars['unit'].get().strip(),
            'qty': qty,
            'rate': rate,
            'amount': qty * rate,
        }

    def add_item(self):
        if not can_write():
            return
        if self.selected_header_id is None:
            messagebox.showinfo('No document', 'Select a document first.')
            return
        item = self._collect_item()
        if item is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO {} ({}, description, unit, qty, rate, amount) '
                'VALUES (?, ?, ?, ?, ?, ?)'.format(self.item_table, self.fk_col),
                (self.selected_header_id, item['description'], item['unit'],
                 item['qty'], item['rate'], item['amount']))
            conn.commit()
            self._recalc_total(conn, self.selected_header_id)
        finally:
            conn.close()
        self.refresh_items()
        self.refresh_headers()
        self._reselect_header()
        self.clear_item()

    def update_item(self):
        if not can_write():
            return
        if self.selected_item_id is None:
            messagebox.showinfo('No selection', 'Select a line item to update.')
            return
        item = self._collect_item()
        if item is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'UPDATE {} SET description = ?, unit = ?, qty = ?, rate = ?, '
                'amount = ? WHERE id = ?'.format(self.item_table),
                (item['description'], item['unit'], item['qty'], item['rate'],
                 item['amount'], self.selected_item_id))
            conn.commit()
            self._recalc_total(conn, self.selected_header_id)
        finally:
            conn.close()
        self.refresh_items()
        self.refresh_headers()
        self._reselect_header()

    def delete_item(self):
        if not can_write():
            return
        if self.selected_item_id is None:
            messagebox.showinfo('No selection', 'Select a line item to delete.')
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM {} WHERE id = ?'.format(self.item_table),
                         (self.selected_item_id,))
            conn.commit()
            self._recalc_total(conn, self.selected_header_id)
        finally:
            conn.close()
        self.selected_item_id = None
        self.refresh_items()
        self.refresh_headers()
        self._reselect_header()
        self.clear_item()

    def clear_item(self):
        self.selected_item_id = None
        for var in self.item_vars.values():
            var.set('')
        if self.item_tree.selection():
            self.item_tree.selection_remove(self.item_tree.selection())

    def _recalc_total(self, conn, header_id):
        """Re-sum this document's items and write the total into the header."""
        total = conn.execute(
            'SELECT COALESCE(SUM(amount), 0) AS t FROM {} WHERE {} = ?'.format(
                self.item_table, self.fk_col), (header_id,)).fetchone()['t']
        conn.execute('UPDATE {} SET {} = ? WHERE id = ?'.format(
            self.header_table, self.total_col), (total, header_id))
        conn.commit()

    def _reselect_header(self):
        """Keep the header selected after a headers refresh so items stay visible."""
        if self.selected_header_id is not None:
            iid = str(self.selected_header_id)
            if self.header_tree.exists(iid):
                self.header_tree.selection_set(iid)


# ---------------------------------------------------------------- builders
def build_quotations_tab(parent, db_getter):
    header_fields = [
        Field('client_id', 'Client', kind='fk', options_func=client_options),
        Field('quote_date', 'Quote Date'),
        Field('valid_until', 'Valid Until'),
        Field('status', 'Status', kind='combo',
              options=['Draft', 'Sent', 'Accepted', 'Rejected'],
              default='Draft'),
        Field('notes', 'Notes'),
    ]
    return DocumentFrame(parent, db_getter, 'quotations', header_fields,
                         'quotation_items', 'quotation_id', 'total_amount',
                         'Quotations')


# Estimates moved to tab_estimate.py (CBS-style flow with contingency/GST/grand
# total + printable document). DocumentFrame is still used for Quotations and
# Purchase Orders below.


def build_purchase_orders_tab(parent, db_getter):
    """Purchase Orders — a header+items DocumentFrame (per AGENTS.md §5).

    ``total_amount`` is the pre-tax items subtotal (derived like any other
    DocumentFrame total). ``gst_pct`` is header metadata; GST is realised
    downstream when a vendor invoice is booked against the PO.
    """
    header_fields = [
        Field('po_no', 'PO No'),
        Field('vendor_id', 'Vendor', kind='fk', options_func=vendor_options),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('po_date', 'PO Date'),
        Field('expected_date', 'Expected'),
        Field('gst_pct', 'GST %', kind='number', default='18'),
        Field('status', 'Status', kind='combo',
              options=['Draft', 'Sent', 'Partially Received', 'Received',
                       'Closed', 'Cancelled'], default='Draft'),
        Field('notes', 'Notes'),
    ]
    return DocumentFrame(parent, db_getter, 'purchase_orders', header_fields,
                         'purchase_order_items', 'purchase_order_id',
                         'total_amount', 'Purchase Orders')


def build_contracts_tab(parent, db_getter):
    """Contracts is a flat single-table form — a plain CrudFrame."""
    fields = [
        Field('contract_no', 'Contract No'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('client_id', 'Client', kind='fk', options_func=client_options),
        Field('contract_value', 'Value', kind='number', default='0'),
        Field('retention_pct', 'Retention %', kind='number', default='0'),
        Field('start_date', 'Start Date'),
        Field('end_date', 'End Date'),
        Field('status', 'Status', kind='combo',
              options=['Active', 'Completed', 'Terminated'], default='Active'),
    ]
    return CrudFrame(parent, db_getter, 'contracts', fields, 'Contracts')
