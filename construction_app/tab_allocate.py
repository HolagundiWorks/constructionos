"""Allocate a payment across the bills it settles (Phase 8, Wave 1).

A dialog opened from Payments & Receipts. It lists the party's billed
documents with what is still open on each, lets the user type an amount against
any of them (or press "Auto" to fill oldest-first), and refuses to save a set
that over-allocates.

The document queries live here rather than in ``allocation.py`` because they
touch the database; all arithmetic stays pure in that module.

Which documents count as "billed to this party":

* **Client** — Approved/Paid running bills and RA bills on that client's
  contracts, plus issued tax invoices. Draft bills are excluded: nothing has
  been asked for yet, so there is nothing to settle.
* **Vendor** — vendor invoices, at their net payable (after TDS), because that
  is what we actually owe.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import allocation
from ui_guard import can_write


def party_documents(conn, party_type, party_id):
    """Billed documents for a party, newest first."""
    docs = []
    if party_type == 'Client' and party_id:
        for r in conn.execute(
                "SELECT b.id, b.bill_no, b.bill_date, b.net_payable "
                "FROM bills b JOIN contracts c ON c.id = b.contract_id "
                "WHERE c.client_id = ? AND b.status IN ('Approved','Paid')",
                (party_id,)):
            docs.append({'doc_type': 'Bill', 'doc_id': r['id'],
                         'number': r['bill_no'] or 'Bill {}'.format(r['id']),
                         'date': r['bill_date'], 'amount': r['net_payable']})
        for r in conn.execute(
                "SELECT rb.id, rb.bill_no, rb.bill_date, rb.net_payable "
                "FROM ra_bills rb JOIN contracts c ON c.id = rb.contract_id "
                "WHERE c.client_id = ? AND rb.status IN ('Approved','Paid')",
                (party_id,)):
            docs.append({'doc_type': 'RABill', 'doc_id': r['id'],
                         'number': r['bill_no'] or 'RA {}'.format(r['id']),
                         'date': r['bill_date'], 'amount': r['net_payable']})
        for r in conn.execute(
                "SELECT id, invoice_no, invoice_date, total_amount FROM tax_invoices "
                "WHERE client_id = ? AND status != 'Cancelled'", (party_id,)):
            docs.append({'doc_type': 'TaxInvoice', 'doc_id': r['id'],
                         'number': r['invoice_no'] or 'INV {}'.format(r['id']),
                         'date': r['invoice_date'], 'amount': r['total_amount']})
    elif party_type == 'Vendor' and party_id:
        for r in conn.execute(
                'SELECT id, invoice_no, invoice_date, net_payable '
                'FROM vendor_invoices WHERE vendor_id = ?', (party_id,)):
            docs.append({'doc_type': 'VendorInvoice', 'doc_id': r['id'],
                         'number': r['invoice_no'] or 'VI {}'.format(r['id']),
                         'date': r['invoice_date'], 'amount': r['net_payable']})
    return sorted(docs, key=lambda d: str(d['date'] or ''), reverse=True)


def allocations_for_party(conn, party_type, party_id, exclude_payment=None):
    """Every allocation already made against this party's documents.

    Needed so a second payment cannot be allocated to a bill the first one
    already settled. The payment being edited is excluded so its own existing
    allocation shows as available rather than as someone else's claim.
    """
    docs = party_documents(conn, party_type, party_id)
    if not docs:
        return []
    keys = {(d['doc_type'], d['doc_id']) for d in docs}
    out = []
    sql = ('SELECT pa.doc_type, pa.doc_id, pa.amount FROM payment_allocations pa '
           'WHERE pa.payment_id != ?' if exclude_payment else
           'SELECT doc_type, doc_id, amount FROM payment_allocations pa')
    args = (exclude_payment,) if exclude_payment else ()
    for r in conn.execute(sql, args):
        if (r['doc_type'], r['doc_id']) in keys:
            out.append({'doc_type': r['doc_type'], 'doc_id': r['doc_id'],
                        'amount': r['amount']})
    return out


def load_allocations(conn, payment_id):
    return [{'doc_type': r['doc_type'], 'doc_id': r['doc_id'],
             'amount': r['amount']}
            for r in conn.execute(
                'SELECT doc_type, doc_id, amount FROM payment_allocations '
                'WHERE payment_id = ?', (payment_id,))]


def save_allocations(conn, payment_id, rows):
    """Replace this payment's allocations, and keep ``against_*`` in step.

    The legacy single-document columns are still filled when the payment
    settles exactly one document, so anything reading them keeps working;
    a split payment records 'Multiple' rather than a misleading single id.
    """
    conn.execute('DELETE FROM payment_allocations WHERE payment_id = ?',
                 (payment_id,))
    kept = [r for r in rows if allocation.money(r['amount']) > 0]
    for r in kept:
        conn.execute(
            'INSERT INTO payment_allocations (payment_id, doc_type, doc_id, '
            'amount) VALUES (?, ?, ?, ?)',
            (payment_id, r['doc_type'], r['doc_id'],
             allocation.money(r['amount'])))
    if len(kept) == 1:
        conn.execute('UPDATE payments SET against_type = ?, against_id = ? '
                     'WHERE id = ?',
                     (kept[0]['doc_type'], kept[0]['doc_id'], payment_id))
    elif kept:
        conn.execute("UPDATE payments SET against_type = 'Multiple', "
                     'against_id = NULL WHERE id = ?', (payment_id,))
    else:
        conn.execute("UPDATE payments SET against_type = 'OnAccount', "
                     'against_id = NULL WHERE id = ?', (payment_id,))
    conn.commit()
    return len(kept)


class AllocateDialog(tk.Toplevel):
    """Modal: split one payment across the documents it settles."""

    COLUMNS = ('number', 'date', 'amount', 'settled', 'open', 'allocate')

    def __init__(self, parent, db_getter, payment):
        super().__init__(parent)
        self.db_getter = db_getter
        self.payment = payment
        self.entries = {}
        self._docs = []

        self.title('Allocate payment to bills')
        self.transient(parent)
        self.grab_set()
        self.geometry('760x520')
        self.summary_var = tk.StringVar()
        self._build_ui()
        self.reload()

    def _build_ui(self):
        p = self.payment
        ttk.Label(self, text='{}  {:,.2f}   ·   {}   ·   {}'.format(
            p['direction'], float(p['amount'] or 0),
            p['party_name'] or '(no party)', p['pay_date'] or ''),
            font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=12, pady=(12, 2))
        ttk.Label(self, text='Tick off the bills this money settles. Anything '
                             'you leave unallocated still counts as received — '
                             'it just is not tied to a bill.',
                  wraplength=700, justify='left', foreground='#555') \
            .pack(anchor='w', padx=12, pady=(0, 8))

        wrap = ttk.Frame(self); wrap.pack(fill='both', expand=True, padx=12)
        heads = {'number': 'Document', 'date': 'Date', 'amount': 'Amount',
                 'settled': 'Already settled', 'open': 'Open', 'allocate': 'Allocate'}
        self.tree = ttk.Treeview(wrap, columns=self.COLUMNS, show='headings',
                                 height=12)
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=150 if c == 'number' else 105,
                             anchor='w' if c in ('number', 'date') else 'e')
        self.tree.pack(fill='both', expand=True, side='left')
        sb = ttk.Scrollbar(wrap, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind('<Double-1>', self._edit_cell)

        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=12, pady=6)

        btns = ttk.Frame(self); btns.pack(fill='x', padx=12, pady=(0, 12))
        ttk.Button(btns, text='Auto (oldest first)', command=self.auto).pack(side='left')
        ttk.Button(btns, text='Clear', command=self.clear).pack(side='left', padx=6)
        ttk.Button(btns, text='Save', command=self.save).pack(side='right')
        ttk.Button(btns, text='Cancel', command=self.destroy).pack(side='right', padx=6)
        ttk.Label(self, text='Double-click a row to type an amount.',
                  foreground='#777').pack(anchor='w', padx=12, pady=(0, 8))

    def reload(self):
        p = self.payment
        conn = self.db_getter()
        try:
            docs = party_documents(conn, p['party_type'], p['party_id'])
            others = allocations_for_party(conn, p['party_type'], p['party_id'],
                                           exclude_payment=p['id'])
            mine = {allocation.doc_key(a['doc_type'], a['doc_id']):
                    allocation.money(a['amount'])
                    for a in load_allocations(conn, p['id'])}
        finally:
            conn.close()
        self._docs = allocation.open_documents(docs, others)
        self.entries = dict(mine)
        self._render()

    def _render(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for d in self._docs:
            key = allocation.doc_key(d['doc_type'], d['doc_id'])
            mine = self.entries.get(key, 0.0)
            self.tree.insert('', 'end', iid=key, values=(
                d['number'], d['date'] or '-',
                '{:,.2f}'.format(d['amount']),
                '{:,.2f}'.format(d['allocated']),
                '{:,.2f}'.format(d['open']),
                '{:,.2f}'.format(mine) if mine else ''))
        if not self._docs:
            self.tree.insert('', 'end', values=(
                '(no billed documents for this party)', '', '', '', '', ''))
        self._update_summary()

    def _update_summary(self):
        total = allocation.money(sum(self.entries.values()))
        amount = allocation.money(self.payment['amount'])
        left = allocation.money(amount - total)
        self.summary_var.set(
            'Payment {:,.2f}   ·   allocated {:,.2f}   ·   unallocated {:,.2f}'
            .format(amount, total, left))

    def _edit_cell(self, event):
        key = self.tree.identify_row(event.y)
        if not key or key not in {allocation.doc_key(d['doc_type'], d['doc_id'])
                                  for d in self._docs}:
            return
        doc = next(d for d in self._docs
                   if allocation.doc_key(d['doc_type'], d['doc_id']) == key)
        current = self.entries.get(key, 0.0)
        win = tk.Toplevel(self); win.title('Allocate'); win.transient(self)
        win.grab_set()
        ttk.Label(win, text='{}\nOpen: {:,.2f}'.format(doc['number'], doc['open']),
                  justify='left').pack(padx=14, pady=(12, 6))
        var = tk.StringVar(value='{:.2f}'.format(current) if current else '')
        entry = ttk.Entry(win, textvariable=var, width=16)
        entry.pack(padx=14); entry.focus_set(); entry.select_range(0, 'end')

        def apply(_e=None):
            raw = var.get().strip()
            try:
                value = allocation.money(raw) if raw else 0.0
            except ValueError:
                messagebox.showerror('Not a number',
                                     'Type an amount, or leave it blank.',
                                     parent=win)
                return
            if value > doc['open'] + 0.005:
                messagebox.showerror(
                    'Too much',
                    'Only {:,.2f} is open on {}.'.format(doc['open'], doc['number']),
                    parent=win)
                return
            if value > 0:
                self.entries[key] = value
            else:
                self.entries.pop(key, None)
            win.destroy()
            self._render()

        entry.bind('<Return>', apply)
        row = ttk.Frame(win); row.pack(pady=10)
        ttk.Button(row, text='OK', command=apply).pack(side='left', padx=4)
        ttk.Button(row, text='Cancel', command=win.destroy).pack(side='left')

    def auto(self):
        self.entries = allocation.suggest_fifo(self._docs, self.payment['amount'])
        self._render()

    def clear(self):
        self.entries = {}
        self._render()

    def save(self):
        if not can_write():
            return
        rows = []
        for d in self._docs:
            key = allocation.doc_key(d['doc_type'], d['doc_id'])
            amount = self.entries.get(key, 0.0)
            if amount:
                rows.append({'doc_type': d['doc_type'], 'doc_id': d['doc_id'],
                             'amount': amount, 'open': d['open'],
                             'number': d['number']})
        ok, msg = allocation.validate(self.payment['amount'], rows)
        if not ok:
            messagebox.showerror('Cannot save', msg, parent=self)
            return
        conn = self.db_getter()
        try:
            n = save_allocations(conn, self.payment['id'], rows)
        finally:
            conn.close()
        messagebox.showinfo(
            'Allocated',
            'Payment split across {} document(s).'.format(n) if n else
            'Allocation cleared — the payment is now on account.', parent=self)
        self.destroy()
