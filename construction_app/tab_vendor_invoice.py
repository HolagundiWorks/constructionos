"""Vendor invoices and PO reconciliation.

A vendor invoice is a header + BOQ line items (like a bill), but its money
figures are tax-driven: line items give a pre-tax ``subtotal``, and
``finance.invoice_totals`` rolls that up with GST (CGST/SGST or IGST) and TDS
into ``tax_amount``/``tds_amount``/``total_amount``/``net_payable``. Those five
columns are always derived — every item change (and every header edit) calls
``_recalc`` — never hand-entered.

The Reconciliation sub-tab compares each invoice's pre-tax subtotal against the
pre-tax subtotal of its linked purchase order via ``finance.reconcile`` and
flags Over/Under-billed variances beyond a tolerance.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from ui_guard import can_write

import bill_export
import finance
import report_open
from tab_masters import vendor_options


def _po_options(conn):
    return [(r['id'], r['po_no'] or 'PO {}'.format(r['id']))
            for r in conn.execute(
                'SELECT id, po_no FROM purchase_orders ORDER BY id DESC')]


class VendorInvoiceEntry(ttk.Frame):
    HEADER_COLUMNS = ('id', 'invoice_no', 'vendor', 'po', 'invoice_date',
                      'status', 'subtotal', 'tax', 'tds', 'total', 'net')
    ITEM_COLUMNS = ('id', 'description', 'unit', 'qty', 'rate', 'amount')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self.selected_item_id = None
        self._vendor_map = {}
        self._po_map = {}

        self.h = {}
        self.i = {}
        self._build_ui()
        self.refresh_invoices()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        ttk.Label(self, text='Vendor Invoices',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        hdr = ttk.LabelFrame(self, text='Invoices')
        hdr.pack(fill='both', expand=True, padx=8, pady=4)

        headings = {'id': 'ID', 'invoice_no': 'Invoice No', 'vendor': 'Vendor',
                    'po': 'PO', 'invoice_date': 'Date', 'status': 'Status',
                    'subtotal': 'Subtotal', 'tax': 'GST', 'tds': 'TDS',
                    'total': 'Total', 'net': 'Net Payable'}
        self.tree = ttk.Treeview(hdr, columns=self.HEADER_COLUMNS,
                                 show='headings', height=7)
        for col in self.HEADER_COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=50 if col == 'id' else 95, anchor='w')
        self.tree.pack(fill='x', padx=4, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        form = ttk.Frame(hdr)
        form.pack(fill='x', padx=4, pady=4)
        for key, default in (('invoice_no', ''), ('invoice_date', ''),
                             ('received_date', ''), ('gst_pct', '18'),
                             ('tds_pct', '0'), ('notes', '')):
            self.h[key] = tk.StringVar(value=default)
        self.h['vendor'] = tk.StringVar()
        self.h['po'] = tk.StringVar()
        self.h['interstate'] = tk.StringVar(value='No')
        self.h['status'] = tk.StringVar(value='Received')

        # row 0
        self._combo(form, 0, 0, 'Vendor', 'vendor')
        self._combo(form, 0, 1, 'Purchase Order', 'po')
        self._entry(form, 0, 2, 'Invoice No', 'invoice_no')
        # row 1
        self._entry(form, 1, 0, 'Invoice Date', 'invoice_date')
        self._entry(form, 1, 1, 'Received Date', 'received_date')
        self._combo_vals(form, 1, 2, 'Inter-state', 'interstate',
                         ['No', 'Yes'])
        # row 2
        self._entry(form, 2, 0, 'GST %', 'gst_pct')
        self._entry(form, 2, 1, 'TDS %', 'tds_pct')
        self._combo_vals(form, 2, 2, 'Status', 'status',
                         ['Received', 'Matched', 'Disputed', 'Paid'])
        # row 3
        self._entry(form, 3, 0, 'Notes', 'notes')

        # derived totals (read-only labels)
        self.totals_var = tk.StringVar(value='Subtotal 0.00  |  GST 0.00  |  '
                                             'TDS 0.00  |  Total 0.00  |  '
                                             'Net 0.00')
        ttk.Label(hdr, textvariable=self.totals_var,
                  font=('TkDefaultFont', 10, 'bold')) \
            .pack(anchor='w', padx=6, pady=(2, 4))

        hbtns = ttk.Frame(hdr)
        hbtns.pack(fill='x', padx=4, pady=4)
        ttk.Button(hbtns, text='Add Invoice', command=self.add_invoice).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Update Selected', command=self.update_invoice).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Delete Invoice', command=self.delete_invoice).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Print / Export', command=self.export_invoice).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Clear', command=self.clear_invoice).pack(side='left', padx=3)

        # ---------------- items ----------------
        items = ttk.LabelFrame(self, text='Invoice Items')
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
        cell = ttk.Frame(parent); cell.grid(row=row, column=col, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=13).pack(side='left')
        ttk.Entry(cell, textvariable=self.h[key], width=18).pack(side='left')

    def _combo(self, parent, row, col, label, key):
        cell = ttk.Frame(parent); cell.grid(row=row, column=col, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=13).pack(side='left')
        w = ttk.Combobox(cell, textvariable=self.h[key], width=16, state='readonly')
        w.pack(side='left')
        if key == 'vendor':
            self.vendor_combo = w
        elif key == 'po':
            self.po_combo = w

    def _combo_vals(self, parent, row, col, label, key, values):
        cell = ttk.Frame(parent); cell.grid(row=row, column=col, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=13).pack(side='left')
        ttk.Combobox(cell, textvariable=self.h[key], width=16,
                     state='readonly', values=values).pack(side='left')

    # -------------------------------------------------------------- helpers
    def _num(self, key, label):
        raw = self.h[key].get().strip()
        try:
            return float(raw) if raw else 0.0
        except ValueError:
            messagebox.showerror('Invalid number',
                                 '"{}" must be a number.'.format(label))
            return None

    def _fk_id(self, key, mapping):
        raw = self.h[key].get().strip()
        if not raw:
            return None
        return mapping.get(raw, raw.split(' - ')[0])

    def _recalc(self, conn, invoice_id):
        """Recompute subtotal + GST/TDS totals from items and header rates."""
        row = conn.execute(
            'SELECT gst_pct, tds_pct, interstate FROM vendor_invoices '
            'WHERE id = ?', (invoice_id,)).fetchone()
        subtotal = conn.execute(
            'SELECT COALESCE(SUM(amount), 0) AS t FROM vendor_invoice_items '
            'WHERE vendor_invoice_id = ?', (invoice_id,)).fetchone()['t']
        tot = finance.invoice_totals(subtotal, row['gst_pct'], row['tds_pct'],
                                     bool(row['interstate']))
        conn.execute(
            'UPDATE vendor_invoices SET subtotal = ?, tax_amount = ?, '
            'tds_amount = ?, total_amount = ?, net_payable = ? WHERE id = ?',
            (tot['subtotal'], tot['tax_amount'], tot['tds_amount'],
             tot['total_amount'], tot['net_payable'], invoice_id))
        conn.commit()
        return tot

    # ----------------------------------------------------------- invoice ops
    def refresh_invoices(self):
        conn = self.db_getter()
        try:
            vopts = vendor_options(conn)
            self._vendor_map = {'{} - {}'.format(i, n): i for i, n in vopts}
            self.vendor_combo['values'] = ['{} - {}'.format(i, n) for i, n in vopts]
            popts = _po_options(conn)
            self._po_map = {'{} - {}'.format(i, n): i for i, n in popts}
            self.po_combo['values'] = [''] + ['{} - {}'.format(i, n) for i, n in popts]

            for item in self.tree.get_children():
                self.tree.delete(item)
            sql = ("SELECT vi.id, vi.invoice_no, v.name AS vendor, po.po_no, "
                   "vi.invoice_date, vi.status, vi.subtotal, vi.tax_amount, "
                   "vi.tds_amount, vi.total_amount, vi.net_payable "
                   "FROM vendor_invoices vi "
                   "LEFT JOIN vendors v ON v.id = vi.vendor_id "
                   "LEFT JOIN purchase_orders po ON po.id = vi.purchase_order_id "
                   "ORDER BY vi.id DESC")
            for r in conn.execute(sql):
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['invoice_no'], r['vendor'] or '-',
                    r['po_no'] or '-', r['invoice_date'], r['status'],
                    '{:.2f}'.format(r['subtotal']),
                    '{:.2f}'.format(r['tax_amount']),
                    '{:.2f}'.format(r['tds_amount']),
                    '{:.2f}'.format(r['total_amount']),
                    '{:.2f}'.format(r['net_payable'])))
        finally:
            conn.close()

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM vendor_invoices WHERE id = ?',
                             (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        self.h['invoice_no'].set(r['invoice_no'] or '')
        self.h['invoice_date'].set(r['invoice_date'] or '')
        self.h['received_date'].set(r['received_date'] or '')
        self.h['gst_pct'].set(str(r['gst_pct']))
        self.h['tds_pct'].set(str(r['tds_pct']))
        self.h['interstate'].set('Yes' if r['interstate'] else 'No')
        self.h['status'].set(r['status'] or 'Received')
        self.h['notes'].set(r['notes'] or '')
        self.h['vendor'].set(self._display_for(self._vendor_map, r['vendor_id']))
        self.h['po'].set(self._display_for(self._po_map, r['purchase_order_id']))
        self._set_totals_label(r)
        self.refresh_items()

    def _display_for(self, mapping, target_id):
        if target_id is None:
            return ''
        for disp, rid in mapping.items():
            if str(rid) == str(target_id):
                return disp
        return ''

    def _set_totals_label(self, r):
        self.totals_var.set(
            'Subtotal {:.2f}  |  GST {:.2f}  |  TDS {:.2f}  |  '
            'Total {:.2f}  |  Net {:.2f}'.format(
                r['subtotal'], r['tax_amount'], r['tds_amount'],
                r['total_amount'], r['net_payable']))

    def _header_values(self):
        vendor_id = self._fk_id('vendor', self._vendor_map)
        if vendor_id is None:
            messagebox.showinfo('No vendor', 'Select a vendor.')
            return None
        gst = self._num('gst_pct', 'GST %')
        tds = self._num('tds_pct', 'TDS %')
        if None in (gst, tds):
            return None
        return {
            'invoice_no': self.h['invoice_no'].get().strip(),
            'vendor_id': vendor_id,
            'purchase_order_id': self._fk_id('po', self._po_map),
            'invoice_date': self.h['invoice_date'].get().strip(),
            'received_date': self.h['received_date'].get().strip(),
            'interstate': 1 if self.h['interstate'].get() == 'Yes' else 0,
            'gst_pct': gst,
            'tds_pct': tds,
            'status': self.h['status'].get().strip() or 'Received',
            'notes': self.h['notes'].get().strip(),
        }

    def add_invoice(self):
        if not can_write():
            return
        v = self._header_values()
        if v is None:
            return
        cols = list(v.keys())
        conn = self.db_getter()
        try:
            cur = conn.execute(
                'INSERT INTO vendor_invoices ({}) VALUES ({})'.format(
                    ', '.join(cols), ', '.join(['?'] * len(cols))),
                [v[c] for c in cols])
            conn.commit()
            self._recalc(conn, cur.lastrowid)
        finally:
            conn.close()
        self.refresh_invoices()
        self.clear_invoice()

    def update_invoice(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an invoice.')
            return
        v = self._header_values()
        if v is None:
            return
        cols = list(v.keys())
        conn = self.db_getter()
        try:
            conn.execute(
                'UPDATE vendor_invoices SET {} WHERE id = ?'.format(
                    ', '.join('{} = ?'.format(c) for c in cols)),
                [v[c] for c in cols] + [self.selected_id])
            conn.commit()
            tot = self._recalc(conn, self.selected_id)
        finally:
            conn.close()
        self.refresh_invoices()
        self.totals_var.set(
            'Subtotal {subtotal:.2f}  |  GST {tax_amount:.2f}  |  '
            'TDS {tds_amount:.2f}  |  Total {total_amount:.2f}  |  '
            'Net {net_payable:.2f}'.format(**tot))

    def delete_invoice(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an invoice.')
            return
        if not messagebox.askyesno('Confirm delete',
                                   'Delete this invoice and its items?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM vendor_invoices WHERE id = ?',
                         (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_id = None
        self.refresh_invoices()
        self.refresh_items()
        self.clear_invoice()

    def clear_invoice(self):
        self.selected_id = None
        for key, default in (('invoice_no', ''), ('invoice_date', ''),
                             ('received_date', ''), ('gst_pct', '18'),
                             ('tds_pct', '0'), ('notes', ''), ('vendor', ''),
                             ('po', '')):
            self.h[key].set(default)
        self.h['interstate'].set('No')
        self.h['status'].set('Received')
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self.refresh_items()

    # -------------------------------------------------------------- export
    def export_invoice(self):
        """Render the selected vendor invoice (header + items + GST/TDS
        breakup) to a printable HTML document and open it in the browser."""
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an invoice to export.')
            return
        conn = self.db_getter()
        try:
            r = conn.execute(
                "SELECT vi.*, v.name AS vendor_name, v.gst_no AS vendor_gstin, "
                "po.po_no AS po_no FROM vendor_invoices vi "
                "LEFT JOIN vendors v ON v.id = vi.vendor_id "
                "LEFT JOIN purchase_orders po ON po.id = vi.purchase_order_id "
                "WHERE vi.id = ?", (self.selected_id,)).fetchone()
            items = conn.execute(
                'SELECT description, unit, qty, rate, amount '
                'FROM vendor_invoice_items WHERE vendor_invoice_id = ? '
                'ORDER BY id', (self.selected_id,)).fetchall()
        finally:
            conn.close()
        if r is None:
            return

        meta = ['Vendor: {}'.format(r['vendor_name'] or '-')]
        if r['vendor_gstin']:
            meta.append('Vendor GSTIN: {}'.format(r['vendor_gstin']))
        if r['invoice_no']:
            meta.append('Invoice No: {}'.format(r['invoice_no']))
        if r['invoice_date']:
            meta.append('Invoice Date: {}'.format(r['invoice_date']))
        if r['po_no']:
            meta.append('Against PO: {}'.format(r['po_no']))
        meta.append('Supply: {}'.format(
            'Inter-state (IGST)' if r['interstate'] else 'Intra-state (CGST+SGST)'))

        item_rows = [(str(idx), it['description'] or '', it['unit'] or '',
                      '{:.2f}'.format(it['qty'] or 0),
                      '{:.2f}'.format(it['rate'] or 0),
                      '{:.2f}'.format(it['amount'] or 0))
                     for idx, it in enumerate(items, start=1)]

        summary = ('Subtotal {:,.2f}  |  GST {:,.2f}  |  TDS {:,.2f}  |  '
                   'Total {:,.2f}  |  Net Payable {:,.2f}'.format(
                       r['subtotal'] or 0, r['tax_amount'] or 0,
                       r['tds_amount'] or 0, r['total_amount'] or 0,
                       r['net_payable'] or 0))

        html = bill_export.build_statement_html(
            'Vendor Invoice', meta,
            ['#', 'Description', 'Unit', 'Qty', 'Rate', 'Amount'], item_rows,
            summary=summary)
        default = 'vendor_invoice_{}.html'.format(
            (r['invoice_no'] or self.selected_id))
        report_open.save_and_open_html(html, default)

    # ------------------------------------------------------------- item ops
    def refresh_items(self):
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        if self.selected_id is None:
            return
        conn = self.db_getter()
        try:
            for r in conn.execute(
                    'SELECT id, description, unit, qty, rate, amount '
                    'FROM vendor_invoice_items WHERE vendor_invoice_id = ? '
                    'ORDER BY id', (self.selected_id,)):
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
        vals = self.item_tree.item(sel[0], 'values')
        self.i['description'].set(vals[1])
        self.i['unit'].set(vals[2])
        self.i['qty'].set(vals[3])
        self.i['rate'].set(vals[4])

    def _collect_item(self):
        try:
            qty = float(self.i['qty'].get().strip() or 0)
            rate = float(self.i['rate'].get().strip() or 0)
        except ValueError:
            messagebox.showerror('Invalid number', 'Qty/Rate must be numbers.')
            return None
        return (self.i['description'].get().strip(),
                self.i['unit'].get().strip(), qty, rate, qty * rate)

    def _after_item_change(self):
        conn = self.db_getter()
        try:
            self._recalc(conn, self.selected_id)
        finally:
            conn.close()
        self.refresh_items()
        self.refresh_invoices()
        if self.tree.exists(str(self.selected_id)):
            self.tree.selection_set(str(self.selected_id))

    def add_item(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No invoice', 'Select an invoice first.')
            return
        item = self._collect_item()
        if item is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO vendor_invoice_items (vendor_invoice_id, '
                'description, unit, qty, rate, amount) VALUES (?, ?, ?, ?, ?, ?)',
                (self.selected_id,) + item)
            conn.commit()
        finally:
            conn.close()
        self._after_item_change()
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
                'UPDATE vendor_invoice_items SET description = ?, unit = ?, '
                'qty = ?, rate = ?, amount = ? WHERE id = ?',
                item + (self.selected_item_id,))
            conn.commit()
        finally:
            conn.close()
        self._after_item_change()

    def delete_item(self):
        if not can_write():
            return
        if self.selected_item_id is None:
            messagebox.showinfo('No selection', 'Select a line item.')
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM vendor_invoice_items WHERE id = ?',
                         (self.selected_item_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_item_id = None
        self._after_item_change()
        self.clear_item()

    def clear_item(self):
        self.selected_item_id = None
        for var in self.i.values():
            var.set('')
        if self.item_tree.selection():
            self.item_tree.selection_remove(self.item_tree.selection())


class ReconciliationView(ttk.Frame):
    """Compare each invoice's pre-tax subtotal against its linked PO subtotal."""

    COLUMNS = ('invoice', 'vendor', 'po', 'po_subtotal', 'inv_subtotal',
               'variance', 'variance_pct', 'result')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter

        ttk.Label(self, text='PO / Invoice Reconciliation',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        controls = ttk.Frame(self)
        controls.pack(fill='x', padx=8, pady=4)
        ttk.Label(controls, text='Tolerance (amount)').pack(side='left')
        self.tol_var = tk.StringVar(value='0')
        ttk.Entry(controls, textvariable=self.tol_var, width=10) \
            .pack(side='left', padx=4)
        ttk.Button(controls, text='Refresh', command=self.refresh) \
            .pack(side='left', padx=6)

        headings = {'invoice': 'Invoice', 'vendor': 'Vendor', 'po': 'PO',
                    'po_subtotal': 'PO Subtotal', 'inv_subtotal': 'Inv Subtotal',
                    'variance': 'Variance', 'variance_pct': 'Var %',
                    'result': 'Result'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=110, anchor='w')
        self.tree.tag_configure('matched', background='#e8f5e9')
        self.tree.tag_configure('over', background='#ffebee')
        self.tree.tag_configure('under', background='#fff8e1')
        self.tree.tag_configure('nopo', background='#eceff1')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.refresh()

    def refresh(self):
        try:
            tolerance = float(self.tol_var.get().strip() or 0)
        except ValueError:
            tolerance = 0.0
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            sql = ("SELECT vi.invoice_no, v.name AS vendor, po.po_no, "
                   "po.total_amount AS po_subtotal, vi.subtotal AS inv_subtotal, "
                   "vi.purchase_order_id "
                   "FROM vendor_invoices vi "
                   "LEFT JOIN vendors v ON v.id = vi.vendor_id "
                   "LEFT JOIN purchase_orders po ON po.id = vi.purchase_order_id "
                   "ORDER BY vi.id DESC")
            rows = conn.execute(sql).fetchall()
        finally:
            conn.close()

        tag_by_status = {'Matched': 'matched', 'Over-billed': 'over',
                         'Under-billed': 'under', 'No PO': 'nopo'}
        for r in rows:
            po_subtotal = r['po_subtotal'] if r['purchase_order_id'] else None
            rec = finance.reconcile(po_subtotal, r['inv_subtotal'], tolerance)
            vpct = '-' if rec['variance_pct'] is None else \
                '{:.1f}%'.format(rec['variance_pct'])
            self.tree.insert('', 'end', values=(
                r['invoice_no'] or '-', r['vendor'] or '-', r['po_no'] or '-',
                '-' if po_subtotal is None else '{:.2f}'.format(po_subtotal),
                '{:.2f}'.format(r['inv_subtotal']),
                '{:.2f}'.format(rec['variance']), vpct, rec['status']),
                tags=(tag_by_status.get(rec['status'], ''),))


def build_vendor_invoices_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(VendorInvoiceEntry(nb, db_getter), text='Vendor Invoices')
    nb.add(ReconciliationView(nb, db_getter), text='Reconciliation')
    return nb
