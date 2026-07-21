"""Goods receipt + three-way match — the procurement gate (Phase 8, Wave 2).

Three views:

* **Requisitions** — the site's written request for material, so a purchase
  begins with a record rather than a phone call.
* **Goods Receipt** — receive against a purchase order. A GRN is a *Draft*
  until it is **Posted**, and posting is the gate: it writes the accepted
  quantities into the material ledger as IN rows. Before this, stock was
  hand-typed and disconnected from the PO it was bought on.
* **3-Way Match** — per PO: ordered vs received vs invoiced. The figure that
  matters is **over-invoiced** — value billed with no receipt behind it, which
  is a payment about to leave for goods that never arrived.

Posting is deliberately one-way and guarded. Re-posting would duplicate stock,
so a posted GRN refuses to post again; ledger rows carry the GRN number in
their remarks so a stock entry can always be traced back to the delivery that
created it.
"""

import tkinter as tk
import theme
from datetime import date
from tkinter import ttk, messagebox

import bill_export
import procurement
import report_open
from crud_frame import CrudFrame, Field
from tab_masters import site_options, material_options, vendor_options
from ui_guard import can_write


def _po_options(conn):
    return [(r['id'], '{}  ({})'.format(r['po_no'] or 'PO {}'.format(r['id']),
                                        r['status'] or ''))
            for r in conn.execute(
                'SELECT id, po_no, status FROM purchase_orders ORDER BY id DESC')]


# ------------------------------------------------------------- requisitions
def build_requisitions(parent, db_getter):
    fields = [
        Field('req_no', 'Requisition No'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('req_date', 'Date', default='TODAY'),
        Field('required_by', 'Required By'),
        Field('requested_by', 'Requested By'),
        Field('status', 'Status', kind='combo',
              options=['Open', 'Ordered', 'Closed', 'Cancelled'], default='Open'),
        Field('remarks', 'Remarks'),
    ]
    return CrudFrame(parent, db_getter, 'material_requisitions', fields,
                     'Material Requisitions (site asks)')


# --------------------------------------------------------------------- GRN
class GRNFrame(ttk.Frame):
    HEAD = ('id', 'grn_no', 'po', 'vendor', 'grn_date', 'challan', 'status')
    ITEMS = ('id', 'description', 'unit', 'received', 'rejected', 'accepted',
             'rate', 'amount')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self.selected_item = None
        self._po_map = {}
        self._mat_map = {}
        self.h = {}
        self.i = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Goods Receipt Notes',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='Record what actually arrived, against its purchase '
                             'order. Posting a GRN puts the accepted quantity '
                             'into stock — that is the only way material should '
                             'enter the ledger.',
                  wraplength=700, justify='left', foreground=theme.palette()['muted']) \
            .pack(anchor='w', padx=8, pady=(0, 6))

        hdr = ttk.LabelFrame(self, text='Receipts')
        hdr.pack(fill='both', expand=True, padx=8, pady=4)
        heads = {'id': 'ID', 'grn_no': 'GRN No', 'po': 'Against PO',
                 'vendor': 'Vendor', 'grn_date': 'Date', 'challan': 'Challan',
                 'status': 'Status'}
        self.tree = ttk.Treeview(hdr, columns=self.HEAD, show='headings', height=6)
        for c in self.HEAD:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=50 if c == 'id' else 120, anchor='w')
        self.tree.tag_configure('posted', background=theme.wash('good'))
        self.tree.pack(fill='x', padx=4, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        form = ttk.Frame(hdr); form.pack(fill='x', padx=4, pady=4)
        for key, default in (('grn_no', ''), ('grn_date', date.today().isoformat()),
                             ('challan_no', ''), ('vehicle_no', ''),
                             ('received_by', ''), ('remarks', '')):
            self.h[key] = tk.StringVar(value=default)
        self.h['po'] = tk.StringVar()
        cell = ttk.Frame(form); cell.grid(row=0, column=0, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text='Purchase Order', width=14).pack(side='left')
        self.po_combo = ttk.Combobox(cell, textvariable=self.h['po'], width=24,
                                     state='readonly')
        self.po_combo.pack(side='left')
        self._entry(form, 0, 1, 'GRN No', 'grn_no')
        self._entry(form, 0, 2, 'Date', 'grn_date')
        self._entry(form, 1, 0, 'Challan No', 'challan_no')
        self._entry(form, 1, 1, 'Vehicle No', 'vehicle_no')
        self._entry(form, 1, 2, 'Received By', 'received_by')
        self._entry(form, 2, 0, 'Remarks', 'remarks')

        b = ttk.Frame(hdr); b.pack(fill='x', padx=4, pady=4)
        ttk.Button(b, text='New GRN', command=self.add).pack(side='left', padx=3)
        ttk.Button(b, text='Update', command=self.update).pack(side='left', padx=3)
        ttk.Button(b, text='Copy Items From PO', command=self.copy_from_po).pack(side='left', padx=3)
        ttk.Button(b, text='Post to Stock', command=self.post).pack(side='left', padx=3)
        ttk.Button(b, text='Delete', command=self.delete).pack(side='left', padx=3)

        items = ttk.LabelFrame(self, text='Received items')
        items.pack(fill='both', expand=True, padx=8, pady=4)
        heads2 = {'id': 'ID', 'description': 'Material', 'unit': 'Unit',
                  'received': 'Received', 'rejected': 'Rejected',
                  'accepted': 'Accepted', 'rate': 'Rate', 'amount': 'Amount'}
        self.item_tree = ttk.Treeview(items, columns=self.ITEMS, show='headings',
                                      height=7)
        for c in self.ITEMS:
            self.item_tree.heading(c, text=heads2[c])
            self.item_tree.column(c, width=50 if c == 'id' else 110, anchor='w')
        self.item_tree.pack(fill='x', padx=4, pady=4)
        self.item_tree.bind('<<TreeviewSelect>>', self._on_item)

        iform = ttk.Frame(items); iform.pack(fill='x', padx=4, pady=4)
        cell = ttk.Frame(iform); cell.grid(row=0, column=0, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text='Material', width=9).pack(side='left')
        self.i['material'] = tk.StringVar()
        self.mat_combo = ttk.Combobox(cell, textvariable=self.i['material'],
                                      width=22, state='readonly')
        self.mat_combo.pack(side='left')
        for idx, (key, label) in enumerate(
                [('description', 'Description'), ('unit', 'Unit'),
                 ('qty_received', 'Received'), ('qty_rejected', 'Rejected'),
                 ('rate', 'Rate')], start=1):
            self.i[key] = tk.StringVar()
            cell = ttk.Frame(iform); cell.grid(row=0, column=idx, padx=6, pady=3, sticky='w')
            ttk.Label(cell, text=label, width=10).pack(side='left')
            ttk.Entry(cell, textvariable=self.i[key], width=13).pack(side='left')

        ib = ttk.Frame(items); ib.pack(fill='x', padx=4, pady=4)
        ttk.Button(ib, text='Add Item', command=self.add_item).pack(side='left', padx=3)
        ttk.Button(ib, text='Update Item', command=self.update_item).pack(side='left', padx=3)
        ttk.Button(ib, text='Delete Item', command=self.delete_item).pack(side='left', padx=3)

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, foreground=theme.palette()['success'],
                  wraplength=700, justify='left').pack(anchor='w', padx=8, pady=(0, 8))

    def _entry(self, parent, r, c, label, key):
        cell = ttk.Frame(parent); cell.grid(row=r, column=c, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=14).pack(side='left')
        ttk.Entry(cell, textvariable=self.h[key], width=20).pack(side='left')

    def _num(self, var):
        try:
            return float(str(var.get()).strip() or 0)
        except ValueError:
            return None

    # ------------------------------------------------------------ headers
    def refresh(self):
        conn = self.db_getter()
        try:
            pos = _po_options(conn)
            self._po_map = {'{} - {}'.format(i, n): i for i, n in pos}
            self.po_combo['values'] = ['{} - {}'.format(i, n) for i, n in pos]
            mats = material_options(conn)
            self._mat_map = {'{} - {}'.format(i, n): i for i, n in mats}
            self.mat_combo['values'] = ['{} - {}'.format(i, n) for i, n in mats]
            for item in self.tree.get_children():
                self.tree.delete(item)
            for r in conn.execute(
                    'SELECT g.id, g.grn_no, po.po_no, v.name AS vendor, '
                    'g.grn_date, g.challan_no, g.status FROM goods_receipts g '
                    'LEFT JOIN purchase_orders po ON po.id = g.purchase_order_id '
                    'LEFT JOIN vendors v ON v.id = g.vendor_id ORDER BY g.id DESC'):
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['grn_no'] or '-', r['po_no'] or '-',
                    r['vendor'] or '-', r['grn_date'] or '-',
                    r['challan_no'] or '-', r['status']),
                    tags=('posted',) if r['status'] == 'Posted' else ())
        finally:
            conn.close()
        self.refresh_items()

    def _po_id(self):
        raw = self.h['po'].get().strip()
        if not raw:
            return None
        return self._po_map.get(raw, raw.split(' - ')[0])

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM goods_receipts WHERE id = ?',
                             (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        for k in ('grn_no', 'grn_date', 'challan_no', 'vehicle_no',
                  'received_by', 'remarks'):
            self.h[k].set(r[k] or '')
        for disp, pid in self._po_map.items():
            if str(pid) == str(r['purchase_order_id']):
                self.h['po'].set(disp); break
        else:
            self.h['po'].set('')
        self.refresh_items()

    def _header_values(self):
        po_id = self._po_id()
        if po_id is None:
            messagebox.showinfo('No purchase order',
                                'A goods receipt must be against a purchase '
                                'order — that link is what makes the match work.')
            return None
        conn = self.db_getter()
        try:
            po = conn.execute('SELECT vendor_id, site_id FROM purchase_orders '
                              'WHERE id = ?', (po_id,)).fetchone()
        finally:
            conn.close()
        return {
            'grn_no': self.h['grn_no'].get().strip(),
            'purchase_order_id': po_id,
            'vendor_id': po['vendor_id'] if po else None,
            'site_id': po['site_id'] if po else None,
            'grn_date': self.h['grn_date'].get().strip(),
            'challan_no': self.h['challan_no'].get().strip(),
            'vehicle_no': self.h['vehicle_no'].get().strip(),
            'received_by': self.h['received_by'].get().strip(),
            'remarks': self.h['remarks'].get().strip(),
        }

    def add(self):
        if not can_write():
            return
        v = self._header_values()
        if v is None:
            return
        conn = self.db_getter()
        try:
            if not v['grn_no']:
                existing = [r['grn_no'] for r in conn.execute(
                    'SELECT grn_no FROM goods_receipts')]
                v['grn_no'] = procurement.next_doc_no(existing, 'GRN')
            cols = list(v.keys())
            conn.execute('INSERT INTO goods_receipts ({}) VALUES ({})'.format(
                ', '.join(cols), ', '.join(['?'] * len(cols))),
                [v[c] for c in cols])
            conn.commit()
        finally:
            conn.close()
        self.refresh()

    def _guard_posted(self):
        """A posted GRN is history — editing it would desync the stock ledger."""
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a GRN first.')
            return True
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT status FROM goods_receipts WHERE id = ?',
                             (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r and r['status'] == 'Posted':
            messagebox.showinfo(
                'Already posted',
                'This GRN has been posted to stock. Create a new one for a '
                'further delivery, or a stock adjustment to correct an error — '
                'editing it now would leave the ledger out of step.')
            return True
        return False

    def update(self):
        if not can_write() or self._guard_posted():
            return
        v = self._header_values()
        if v is None:
            return
        cols = list(v.keys())
        conn = self.db_getter()
        try:
            conn.execute('UPDATE goods_receipts SET {} WHERE id = ?'.format(
                ', '.join('{} = ?'.format(c) for c in cols)),
                [v[c] for c in cols] + [self.selected_id])
            conn.commit()
        finally:
            conn.close()
        self.refresh()

    def delete(self):
        if not can_write() or self._guard_posted():
            return
        if not messagebox.askyesno('Delete GRN', 'Delete this goods receipt?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM goods_receipts WHERE id = ?',
                         (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_id = None
        self.refresh()

    def copy_from_po(self):
        """Pull the PO's lines in, less whatever earlier GRNs already received."""
        if not can_write() or self._guard_posted():
            return
        conn = self.db_getter()
        try:
            po_id = conn.execute(
                'SELECT purchase_order_id FROM goods_receipts WHERE id = ?',
                (self.selected_id,)).fetchone()['purchase_order_id']
            lines = conn.execute(
                'SELECT * FROM purchase_order_items WHERE purchase_order_id = ?',
                (po_id,)).fetchall()
            already = {}
            for r in conn.execute(
                    'SELECT gi.purchase_order_item_id AS pid, '
                    'SUM(gi.qty_accepted) AS q FROM grn_items gi '
                    'JOIN goods_receipts g ON g.id = gi.grn_id '
                    "WHERE g.purchase_order_id = ? AND g.id != ? "
                    'GROUP BY gi.purchase_order_item_id', (po_id, self.selected_id)):
                already[r['pid']] = r['q'] or 0
            added = 0
            for ln in lines:
                outstanding = round(float(ln['qty'] or 0) -
                                    float(already.get(ln['id'], 0)), 3)
                if outstanding <= 0:
                    continue
                conn.execute(
                    'INSERT INTO grn_items (grn_id, purchase_order_item_id, '
                    'material_id, description, unit, qty_received, qty_rejected, '
                    'qty_accepted, rate, amount) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)',
                    (self.selected_id, ln['id'],
                     ln['material_id'] if 'material_id' in ln.keys() else None,
                     ln['description'], ln['unit'], outstanding, outstanding,
                     ln['rate'], procurement.line_amount(outstanding, ln['rate'])))
                added += 1
            conn.commit()
        finally:
            conn.close()
        self.status_var.set(
            'Copied {} outstanding line(s) from the PO — edit the received '
            'quantities to match the challan.'.format(added) if added else
            'Nothing outstanding on that PO.')
        self.refresh_items()

    # -------------------------------------------------------------- items
    def refresh_items(self):
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        if self.selected_id is None:
            return
        conn = self.db_getter()
        try:
            for r in conn.execute(
                    'SELECT * FROM grn_items WHERE grn_id = ? ORDER BY id',
                    (self.selected_id,)):
                self.item_tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['description'] or '-', r['unit'] or '',
                    '{:.3f}'.format(r['qty_received'] or 0),
                    '{:.3f}'.format(r['qty_rejected'] or 0),
                    '{:.3f}'.format(r['qty_accepted'] or 0),
                    '{:.2f}'.format(r['rate'] or 0),
                    '{:.2f}'.format(r['amount'] or 0)))
        finally:
            conn.close()

    def _on_item(self, _e=None):
        sel = self.item_tree.selection()
        if not sel:
            return
        self.selected_item = int(sel[0])
        v = self.item_tree.item(sel[0], 'values')
        self.i['description'].set(v[1]); self.i['unit'].set(v[2])
        self.i['qty_received'].set(v[3]); self.i['qty_rejected'].set(v[4])
        self.i['rate'].set(v[6])

    def _item_values(self):
        received = self._num(self.i['qty_received'])
        rejected = self._num(self.i['qty_rejected']) or 0
        rate = self._num(self.i['rate']) or 0
        if received is None:
            messagebox.showerror('Invalid number', 'Received quantity must be a number.')
            return None
        if rejected > received:
            messagebox.showerror(
                'More rejected than received',
                'You cannot reject more than arrived.')
            return None
        accepted = procurement.accepted_qty(received, rejected)
        raw = self.i['material'].get().strip()
        material_id = self._mat_map.get(raw) if raw else None
        return (material_id, self.i['description'].get().strip(),
                self.i['unit'].get().strip(), received, rejected, accepted,
                rate, procurement.line_amount(accepted, rate))

    def add_item(self):
        if not can_write() or self._guard_posted():
            return
        vals = self._item_values()
        if vals is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO grn_items (grn_id, material_id, description, unit, '
                'qty_received, qty_rejected, qty_accepted, rate, amount) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (self.selected_id,) + vals)
            conn.commit()
        finally:
            conn.close()
        self.refresh_items()

    def update_item(self):
        if not can_write() or self._guard_posted():
            return
        if self.selected_item is None:
            messagebox.showinfo('No selection', 'Select a line first.')
            return
        vals = self._item_values()
        if vals is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'UPDATE grn_items SET material_id = ?, description = ?, unit = ?, '
                'qty_received = ?, qty_rejected = ?, qty_accepted = ?, rate = ?, '
                'amount = ? WHERE id = ?', vals + (self.selected_item,))
            conn.commit()
        finally:
            conn.close()
        self.refresh_items()

    def delete_item(self):
        if not can_write() or self._guard_posted():
            return
        if self.selected_item is None:
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM grn_items WHERE id = ?', (self.selected_item,))
            conn.commit()
        finally:
            conn.close()
        self.selected_item = None
        self.refresh_items()

    # --------------------------------------------------------------- post
    def post(self):
        """The gate: move accepted quantities into stock, once."""
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a GRN to post.')
            return
        conn = self.db_getter()
        try:
            g = conn.execute('SELECT * FROM goods_receipts WHERE id = ?',
                             (self.selected_id,)).fetchone()
            items = conn.execute('SELECT * FROM grn_items WHERE grn_id = ?',
                                 (self.selected_id,)).fetchall()
        finally:
            conn.close()
        if g is None:
            return
        if g['status'] == 'Posted':
            messagebox.showinfo('Already posted',
                                'This GRN is already in stock. Posting again '
                                'would double the quantities.')
            return
        if not items:
            messagebox.showinfo('Nothing to post', 'Add the received items first.')
            return
        with_material = [i for i in items if i['material_id']]
        skipped = len(items) - len(with_material)
        if not with_material:
            messagebox.showinfo(
                'No material chosen',
                'None of these lines names a material from the Materials '
                'master, so nothing can be added to stock. Pick a material on '
                'each line first.')
            return
        if not messagebox.askyesno(
                'Post to stock',
                'Add {} line(s) to the stock ledger as received on {}?\n\n'
                'This cannot be undone from here.{}'.format(
                    len(with_material), g['grn_date'] or 'today',
                    '\n\n{} line(s) have no material and will be skipped.'.format(skipped)
                    if skipped else '')):
            return
        conn = self.db_getter()
        try:
            for it in with_material:
                if (it['qty_accepted'] or 0) <= 0:
                    continue
                conn.execute(
                    "INSERT INTO material_ledger (txn_date, site_id, material_id, "
                    "txn_type, qty, rate, vendor_id, remarks) "
                    "VALUES (?, ?, ?, 'IN', ?, ?, ?, ?)",
                    (g['grn_date'], g['site_id'], it['material_id'],
                     it['qty_accepted'], it['rate'], g['vendor_id'],
                     'GRN {}'.format(g['grn_no'] or self.selected_id)))
            conn.execute("UPDATE goods_receipts SET status = 'Posted' WHERE id = ?",
                         (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.status_var.set(
            'Posted GRN {} — {} line(s) added to stock.'.format(
                g['grn_no'] or self.selected_id, len(with_material)))
        self.refresh()


# ------------------------------------------------------------- 3-way match
class ThreeWayMatch(ttk.Frame):
    COLUMNS = ('po', 'vendor', 'ordered', 'received', 'invoiced',
               'over_invoiced', 'status')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._rows = []
        self.tol_var = tk.StringVar(value='100')
        self.summary_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Three-way match  (ordered → received → invoiced)',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='"Over-invoiced" is value billed with no goods '
                             'receipt behind it — a payment about to leave for '
                             'material that never arrived. Check this before '
                             'paying a vendor.',
                  wraplength=700, justify='left', foreground=theme.palette()['muted']) \
            .pack(anchor='w', padx=8, pady=(0, 6))

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=4)
        ttk.Label(top, text='Tolerance (amount)').pack(side='left')
        ttk.Entry(top, textvariable=self.tol_var, width=10).pack(side='left', padx=4)
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='left', padx=6)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='left')

        heads = {'po': 'PO', 'vendor': 'Vendor', 'ordered': 'Ordered',
                 'received': 'Received', 'invoiced': 'Invoiced',
                 'over_invoiced': 'Over-invoiced', 'status': 'Result'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=140 if c in ('po', 'vendor', 'status') else 115,
                             anchor='w' if c in ('po', 'vendor', 'status') else 'e')
        self.tree.tag_configure('bad', background=theme.wash('bad'))
        self.tree.tag_configure('warn', background=theme.wash('warn'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=6)

    def refresh(self):
        try:
            tol = float(self.tol_var.get().strip() or 0)
        except ValueError:
            tol = 0.0
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        conn = self.db_getter()
        try:
            pos = conn.execute(
                'SELECT po.id, po.po_no, po.total_amount, v.name AS vendor '
                'FROM purchase_orders po LEFT JOIN vendors v ON v.id = po.vendor_id '
                'ORDER BY po.id DESC').fetchall()
            received = {}
            for r in conn.execute(
                    'SELECT g.purchase_order_id AS pid, SUM(gi.amount) AS a '
                    'FROM grn_items gi JOIN goods_receipts g ON g.id = gi.grn_id '
                    "WHERE g.status = 'Posted' GROUP BY g.purchase_order_id"):
                received[r['pid']] = r['a'] or 0
            invoiced = {}
            for r in conn.execute(
                    'SELECT purchase_order_id AS pid, SUM(subtotal) AS a '
                    'FROM vendor_invoices WHERE purchase_order_id IS NOT NULL '
                    'GROUP BY purchase_order_id'):
                invoiced[r['pid']] = r['a'] or 0
        finally:
            conn.close()

        matches = []
        for po in pos:
            m = procurement.three_way(po['total_amount'],
                                      received.get(po['id'], 0),
                                      invoiced.get(po['id'], 0), tol)
            matches.append(m)
            values = (po['po_no'] or 'PO {}'.format(po['id']), po['vendor'] or '-',
                      '{:,.2f}'.format(m['ordered']), '{:,.2f}'.format(m['received']),
                      '{:,.2f}'.format(m['invoiced']),
                      '{:,.2f}'.format(m['over_invoiced']), m['status'])
            self._rows.append(values)
            tag = ('bad' if m['status'] == procurement.OVER_INVOICED else
                   'warn' if not m['ok'] else '')
            self.tree.insert('', 'end', values=values, tags=(tag,) if tag else ())

        s = procurement.summarise(matches)
        self.summary_var.set(
            'At risk (invoiced without a receipt): {:,.2f}   ·   awaiting '
            'delivery {:,.2f}   ·   received not yet invoiced {:,.2f}   ·   '
            '{} of {} POs need attention'.format(
                s['at_risk'], s['awaiting_delivery'], s['received_not_invoiced'],
                s['problem_count'], s['total_count']))

    def export(self):
        html = bill_export.build_statement_html(
            'Three-way match (PO / GRN / Invoice)', [self.summary_var.get()],
            ['PO', 'Vendor', 'Ordered', 'Received', 'Invoiced',
             'Over-invoiced', 'Result'],
            self._rows, summary=self.summary_var.get())
        report_open.save_and_open_html(html, 'three_way_match.html')


def build_grn_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(build_requisitions(nb, db_getter), text='Requisitions')
    nb.add(GRNFrame(nb, db_getter), text='Goods Receipt')
    nb.add(ThreeWayMatch(nb, db_getter), text='3-Way Match')
    return nb
