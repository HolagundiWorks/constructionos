"""GST Tax Invoices (outward, to clients) — Phase 2 "get paid & submit".

The printed tax invoice is the document a contractor hands to the client/
department. Header + line items (with HSN/SAC); the taxable subtotal is rolled
up with GST (CGST/SGST intra-state, or IGST inter-state) via ``finance`` — no
TDS on the outward side (the client may deduct it). ``subtotal``/``tax_amount``/
``total_amount`` are always derived. "Print / Export" renders the invoice via
``bill_export.build_tax_invoice_html`` (with amount-in-words) and opens it in the
browser to print or Save-as-PDF.

Seller details on the printout (name/GSTIN/address) come from ``app_settings``
keys ``company_name`` / ``seller_gstin`` / ``seller_address`` when set.
"""

import os
import webbrowser
from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import finance
import bill_export
import docnum
from tab_masters import client_options


def _seller_from_settings(conn):
    rows = {r['key']: r['value'] for r in conn.execute(
        "SELECT key, value FROM app_settings WHERE key IN "
        "('company_name', 'seller_gstin', 'seller_address')")}
    return {
        'name': rows.get('company_name', 'Contractor-OS'),
        'gstin': rows.get('seller_gstin', ''),
        'address': rows.get('seller_address', ''),
    }


class TaxInvoiceTab(ttk.Frame):
    HEADER_COLUMNS = ('id', 'invoice_no', 'client', 'invoice_date', 'status',
                      'subtotal', 'tax', 'total')
    ITEM_COLUMNS = ('id', 'description', 'hsn_code', 'unit', 'qty', 'rate',
                    'amount')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self.selected_item_id = None
        self._client_map = {}
        self.h = {}
        self.i = {}
        self._build_ui()
        self.refresh_invoices()

    def _build_ui(self):
        ttk.Label(self, text='GST Tax Invoices',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        hdr = ttk.LabelFrame(self, text='Invoices')
        hdr.pack(fill='both', expand=True, padx=8, pady=4)
        heads = {'id': 'ID', 'invoice_no': 'Invoice No', 'client': 'Client',
                 'invoice_date': 'Date', 'status': 'Status',
                 'subtotal': 'Taxable', 'tax': 'GST', 'total': 'Total'}
        self.tree = ttk.Treeview(hdr, columns=self.HEADER_COLUMNS,
                                 show='headings', height=6)
        for col in self.HEADER_COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=50 if col == 'id' else 105, anchor='w')
        self.tree.pack(fill='x', padx=4, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        form = ttk.Frame(hdr); form.pack(fill='x', padx=4, pady=4)
        for key, default in (('invoice_no', ''), ('invoice_date', ''),
                             ('place_of_supply', ''), ('gst_pct', '18'),
                             ('notes', '')):
            self.h[key] = tk.StringVar(value=default)
        self.h['client'] = tk.StringVar()
        self.h['interstate'] = tk.StringVar(value='No')
        self.h['status'] = tk.StringVar(value='Draft')

        cell = ttk.Frame(form); cell.grid(row=0, column=0, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text='Client', width=13).pack(side='left')
        self.client_combo = ttk.Combobox(cell, textvariable=self.h['client'],
                                         width=20, state='readonly')
        self.client_combo.pack(side='left')
        self._entry(form, 0, 1, 'Invoice No', 'invoice_no')
        self._entry(form, 0, 2, 'Invoice Date', 'invoice_date')
        self._entry(form, 1, 0, 'Place of Supply', 'place_of_supply')
        self._combo(form, 1, 1, 'Inter-state', 'interstate', ['No', 'Yes'])
        self._entry(form, 1, 2, 'GST %', 'gst_pct')
        self._combo(form, 2, 0, 'Status', 'status',
                    ['Draft', 'Issued', 'Paid', 'Cancelled'])
        self._entry(form, 2, 1, 'Notes', 'notes')

        self.totals_var = tk.StringVar(value='Taxable 0.00  |  GST 0.00  |  Total 0.00')
        ttk.Label(hdr, textvariable=self.totals_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=6, pady=(2, 4))

        hbtns = ttk.Frame(hdr); hbtns.pack(fill='x', padx=4, pady=4)
        ttk.Button(hbtns, text='Add Invoice', command=self.add_invoice).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Update Selected', command=self.update_invoice).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Delete', command=self.delete_invoice).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Print / Export', command=self.export_invoice).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Clear', command=self.clear_invoice).pack(side='left', padx=3)

        items = ttk.LabelFrame(self, text='Items'); items.pack(fill='both', expand=True, padx=8, pady=4)
        self.item_tree = ttk.Treeview(items, columns=self.ITEM_COLUMNS,
                                      show='headings', height=6)
        for col in self.ITEM_COLUMNS:
            self.item_tree.heading(col, text=col.replace('_', ' ').title())
            self.item_tree.column(col, width=50 if col == 'id' else 110, anchor='w')
        self.item_tree.pack(fill='x', padx=4, pady=4)
        self.item_tree.bind('<<TreeviewSelect>>', self._on_item_select)

        iform = ttk.Frame(items); iform.pack(fill='x', padx=4, pady=4)
        for idx, (key, label) in enumerate(
                [('description', 'Description'), ('hsn_code', 'HSN/SAC'),
                 ('unit', 'Unit'), ('qty', 'Qty'), ('rate', 'Rate')]):
            self.i[key] = tk.StringVar()
            cell = ttk.Frame(iform); cell.grid(row=0, column=idx, padx=6, pady=3, sticky='w')
            ttk.Label(cell, text=label, width=10).pack(side='left')
            ttk.Entry(cell, textvariable=self.i[key], width=14).pack(side='left')

        ibtns = ttk.Frame(items); ibtns.pack(fill='x', padx=4, pady=4)
        ttk.Button(ibtns, text='Add Item', command=self.add_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Update Item', command=self.update_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Delete Item', command=self.delete_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Clear', command=self.clear_item).pack(side='left', padx=3)

    def _entry(self, parent, r, c, label, key):
        cell = ttk.Frame(parent); cell.grid(row=r, column=c, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=13).pack(side='left')
        ttk.Entry(cell, textvariable=self.h[key], width=18).pack(side='left')

    def _combo(self, parent, r, c, label, key, values):
        cell = ttk.Frame(parent); cell.grid(row=r, column=c, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=13).pack(side='left')
        ttk.Combobox(cell, textvariable=self.h[key], width=16, state='readonly',
                     values=values).pack(side='left')

    # -------------------------------------------------------------- helpers
    def _num(self, key, label):
        raw = self.h[key].get().strip()
        try:
            return float(raw) if raw else 0.0
        except ValueError:
            messagebox.showerror('Invalid number', '"{}" must be a number.'.format(label))
            return None

    def _client_id(self):
        raw = self.h['client'].get().strip()
        if not raw:
            return None
        return self._client_map.get(raw, raw.split(' - ')[0])

    def _recalc(self, conn, invoice_id):
        row = conn.execute('SELECT gst_pct, interstate FROM tax_invoices WHERE id = ?',
                           (invoice_id,)).fetchone()
        subtotal = conn.execute(
            'SELECT COALESCE(SUM(amount), 0) AS t FROM tax_invoice_items '
            'WHERE tax_invoice_id = ?', (invoice_id,)).fetchone()['t']
        tot = finance.invoice_totals(subtotal, row['gst_pct'], 0,
                                     bool(row['interstate']))
        conn.execute(
            'UPDATE tax_invoices SET subtotal = ?, tax_amount = ?, '
            'total_amount = ? WHERE id = ?',
            (tot['subtotal'], tot['tax_amount'], tot['total_amount'], invoice_id))
        conn.commit()
        return tot

    # ----------------------------------------------------------- invoice ops
    def refresh_invoices(self):
        conn = self.db_getter()
        try:
            opts = client_options(conn)
            self._client_map = {'{} - {}'.format(i, n): i for i, n in opts}
            self.client_combo['values'] = ['{} - {}'.format(i, n) for i, n in opts]
            for item in self.tree.get_children():
                self.tree.delete(item)
            for r in conn.execute(
                    "SELECT ti.id, ti.invoice_no, c.name AS client, "
                    "ti.invoice_date, ti.status, ti.subtotal, ti.tax_amount, "
                    "ti.total_amount FROM tax_invoices ti "
                    "LEFT JOIN clients c ON c.id = ti.client_id "
                    "ORDER BY ti.id DESC"):
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['invoice_no'], r['client'] or '-',
                    r['invoice_date'], r['status'],
                    '{:.2f}'.format(r['subtotal']),
                    '{:.2f}'.format(r['tax_amount']),
                    '{:.2f}'.format(r['total_amount'])))
        finally:
            conn.close()

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM tax_invoices WHERE id = ?',
                             (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        self.h['invoice_no'].set(r['invoice_no'] or '')
        self.h['invoice_date'].set(r['invoice_date'] or '')
        self.h['place_of_supply'].set(r['place_of_supply'] or '')
        self.h['gst_pct'].set(str(r['gst_pct']))
        self.h['interstate'].set('Yes' if r['interstate'] else 'No')
        self.h['status'].set(r['status'] or 'Draft')
        self.h['notes'].set(r['notes'] or '')
        for disp, cid in self._client_map.items():
            if str(cid) == str(r['client_id']):
                self.h['client'].set(disp); break
        else:
            self.h['client'].set('')
        self.totals_var.set('Taxable {:.2f}  |  GST {:.2f}  |  Total {:.2f}'.format(
            r['subtotal'], r['tax_amount'], r['total_amount']))
        self.refresh_items()

    def _header_values(self):
        client_id = self._client_id()
        if client_id is None:
            messagebox.showinfo('No client', 'Select a client.')
            return None
        gst = self._num('gst_pct', 'GST %')
        if gst is None:
            return None
        return {
            'invoice_no': self.h['invoice_no'].get().strip(),
            'client_id': client_id,
            'invoice_date': self.h['invoice_date'].get().strip(),
            'place_of_supply': self.h['place_of_supply'].get().strip(),
            'interstate': 1 if self.h['interstate'].get() == 'Yes' else 0,
            'gst_pct': gst,
            'status': self.h['status'].get().strip() or 'Draft',
            'notes': self.h['notes'].get().strip(),
        }

    def add_invoice(self):
        v = self._header_values()
        if v is None:
            return
        conn = self.db_getter()
        try:
            if not v['invoice_no']:
                # Auto-number when left blank, from the configurable series
                # (Tools > Firm Details): prefix + optional financial-year
                # reset, max-serial-based so deletions never cause duplicates.
                settings = {r['key']: r['value'] for r in conn.execute(
                    "SELECT key, value FROM app_settings WHERE key IN "
                    "('invoice_prefix', 'invoice_fy_reset')")}
                prefix = (settings.get('invoice_prefix') or '').strip() or 'INV'
                fy = ''
                if settings.get('invoice_fy_reset') == 'Yes':
                    # Fall back to today when the typed date is blank/invalid.
                    fy = docnum.fy_label(v['invoice_date']) or \
                        docnum.fy_label(date.today().isoformat())
                existing = [r['invoice_no'] for r in conn.execute(
                    'SELECT invoice_no FROM tax_invoices')]
                v['invoice_no'] = docnum.next_doc_no(existing, prefix, fy)
            cols = list(v.keys())
            cur = conn.execute('INSERT INTO tax_invoices ({}) VALUES ({})'.format(
                ', '.join(cols), ', '.join(['?'] * len(cols))),
                [v[c] for c in cols])
            conn.commit()
            self._recalc(conn, cur.lastrowid)
        finally:
            conn.close()
        self.refresh_invoices()
        self.clear_invoice()

    def update_invoice(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an invoice.')
            return
        v = self._header_values()
        if v is None:
            return
        cols = list(v.keys())
        conn = self.db_getter()
        try:
            conn.execute('UPDATE tax_invoices SET {} WHERE id = ?'.format(
                ', '.join('{} = ?'.format(c) for c in cols)),
                [v[c] for c in cols] + [self.selected_id])
            conn.commit()
            tot = self._recalc(conn, self.selected_id)
        finally:
            conn.close()
        self.refresh_invoices()
        self.totals_var.set(
            'Taxable {subtotal:.2f}  |  GST {tax_amount:.2f}  |  '
            'Total {total_amount:.2f}'.format(**tot))

    def delete_invoice(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an invoice.')
            return
        if not messagebox.askyesno('Confirm delete', 'Delete this invoice and its items?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM tax_invoices WHERE id = ?', (self.selected_id,))
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
                             ('place_of_supply', ''), ('gst_pct', '18'),
                             ('notes', ''), ('client', '')):
            self.h[key].set(default)
        self.h['interstate'].set('No')
        self.h['status'].set('Draft')
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self.refresh_items()

    def export_invoice(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an invoice to export.')
            return
        conn = self.db_getter()
        try:
            inv = conn.execute('SELECT * FROM tax_invoices WHERE id = ?',
                               (self.selected_id,)).fetchone()
            client = None
            if inv and inv['client_id'] is not None:
                client = conn.execute('SELECT * FROM clients WHERE id = ?',
                                      (inv['client_id'],)).fetchone()
            items = conn.execute(
                'SELECT description, hsn_code, unit, qty, rate, amount '
                'FROM tax_invoice_items WHERE tax_invoice_id = ? ORDER BY id',
                (self.selected_id,)).fetchall()
            seller = _seller_from_settings(conn)
        finally:
            conn.close()
        if inv is None:
            return
        html = bill_export.build_tax_invoice_html(
            inv, client, items, seller, company_name=seller.get('name') or 'Contractor-OS')
        safe = (inv['invoice_no'] or 'invoice').replace('/', '-').replace(' ', '_')
        path = filedialog.asksaveasfilename(
            title='Save tax invoice', defaultextension='.html',
            initialfile='tax_invoice_{}.html'.format(safe),
            filetypes=[('HTML document', '*.html'), ('All files', '*.*')])
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(html)
        webbrowser.open('file://' + os.path.abspath(path))

    # ------------------------------------------------------------- item ops
    def refresh_items(self):
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        if self.selected_id is None:
            return
        conn = self.db_getter()
        try:
            for r in conn.execute(
                    'SELECT id, description, hsn_code, unit, qty, rate, amount '
                    'FROM tax_invoice_items WHERE tax_invoice_id = ? ORDER BY id',
                    (self.selected_id,)):
                self.item_tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['description'], r['hsn_code'], r['unit'],
                    r['qty'], r['rate'], r['amount']))
        finally:
            conn.close()

    def _on_item_select(self, _e=None):
        sel = self.item_tree.selection()
        if not sel:
            return
        self.selected_item_id = int(sel[0])
        vals = self.item_tree.item(sel[0], 'values')
        self.i['description'].set(vals[1]); self.i['hsn_code'].set(vals[2])
        self.i['unit'].set(vals[3]); self.i['qty'].set(vals[4])
        self.i['rate'].set(vals[5])

    def _collect_item(self):
        try:
            qty = float(self.i['qty'].get().strip() or 0)
            rate = float(self.i['rate'].get().strip() or 0)
        except ValueError:
            messagebox.showerror('Invalid number', 'Qty/Rate must be numbers.')
            return None
        return (self.i['description'].get().strip(), self.i['hsn_code'].get().strip(),
                self.i['unit'].get().strip(), qty, rate, qty * rate)

    def _after_item_change(self):
        conn = self.db_getter()
        try:
            tot = self._recalc(conn, self.selected_id)
        finally:
            conn.close()
        self.refresh_items()
        self.refresh_invoices()
        if self.tree.exists(str(self.selected_id)):
            self.tree.selection_set(str(self.selected_id))
        self.totals_var.set(
            'Taxable {subtotal:.2f}  |  GST {tax_amount:.2f}  |  '
            'Total {total_amount:.2f}'.format(**tot))

    def add_item(self):
        if self.selected_id is None:
            messagebox.showinfo('No invoice', 'Select an invoice first.')
            return
        item = self._collect_item()
        if item is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO tax_invoice_items (tax_invoice_id, description, '
                'hsn_code, unit, qty, rate, amount) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (self.selected_id,) + item)
            conn.commit()
        finally:
            conn.close()
        self._after_item_change()
        self.clear_item()

    def update_item(self):
        if self.selected_item_id is None:
            messagebox.showinfo('No selection', 'Select a line item.')
            return
        item = self._collect_item()
        if item is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'UPDATE tax_invoice_items SET description = ?, hsn_code = ?, '
                'unit = ?, qty = ?, rate = ?, amount = ? WHERE id = ?',
                item + (self.selected_item_id,))
            conn.commit()
        finally:
            conn.close()
        self._after_item_change()

    def delete_item(self):
        if self.selected_item_id is None:
            messagebox.showinfo('No selection', 'Select a line item.')
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM tax_invoice_items WHERE id = ?',
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


def build_tax_invoice_tab(parent, db_getter):
    return TaxInvoiceTab(parent, db_getter)
