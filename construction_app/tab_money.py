"""Money — the cash-first heart for a small contractor (Phase 1).

Three plain-language views (see docs/PRODUCT.md and docs/ROADMAP.md):
- **Payments & Receipts**: record money in (from clients) and out (to vendors /
  labour), by mode, optionally against a site.
- **Party Balances**: per client / vendor / labour — billed vs settled and the
  running balance ("baaki").
- **Cash Book**: the digital bahi-khata — dated cash in/out with a running
  balance and an optional opening balance.

Cash/balance arithmetic lives in ``money.py`` so it is testable without a GUI.
"""

import os
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ui_guard import can_write

import money as m
import bill_export


def _save_and_open_html(html, default_name):
    """Write an HTML report and open it in the browser (print / Save-as-PDF)."""
    path = filedialog.asksaveasfilename(
        title='Save report', defaultextension='.html',
        initialfile=default_name,
        filetypes=[('HTML document', '*.html'), ('All files', '*.*')])
    if not path:
        return
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    webbrowser.open('file://' + os.path.abspath(path))


PARTY_TYPES = ['Client', 'Vendor', 'Labour', 'Other']
MODES = ['Cash', 'Bank', 'UPI', 'Cheque']
CASH_OPENING_KEY = 'cash_opening'


def _party_options(conn, party_type):
    if party_type == 'Client':
        rows = conn.execute('SELECT id, name FROM clients ORDER BY name')
    elif party_type == 'Vendor':
        rows = conn.execute('SELECT id, name FROM vendors ORDER BY name')
    elif party_type == 'Labour':
        rows = conn.execute('SELECT id, name FROM labor ORDER BY name')
    else:
        return []
    return [(r['id'], r['name']) for r in rows]


def _site_options(conn):
    return [(s['id'], s['name'])
            for s in conn.execute('SELECT id, name FROM sites ORDER BY name')]


def _parse_combo(raw, mapping):
    """Return (id, name) from a 'id - name' combo value, or (None, raw)."""
    raw = (raw or '').strip()
    if not raw:
        return None, ''
    if raw in mapping:
        rid = mapping[raw]
        name = raw.split(' - ', 1)[1] if ' - ' in raw else raw
        return rid, name
    return None, raw


# ============================================================ Payments
class PaymentsFrame(ttk.Frame):
    COLUMNS = ('id', 'pay_date', 'direction', 'party_type', 'party_name',
               'mode', 'amount', 'ref_no', 'site', 'narration')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self._party_map = {}
        self._site_map = {}
        self.v = {
            'pay_date': tk.StringVar(),
            'direction': tk.StringVar(value='Receipt'),
            'party_type': tk.StringVar(value='Client'),
            'party': tk.StringVar(),
            'mode': tk.StringVar(value='Cash'),
            'amount': tk.StringVar(value='0'),
            'ref_no': tk.StringVar(),
            'site': tk.StringVar(),
            'narration': tk.StringVar(),
        }
        self._build_ui()
        self.reload()

    def _build_ui(self):
        ttk.Label(self, text='Payments & Receipts',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings',
                                 height=10)
        heads = {'id': 'ID', 'pay_date': 'Date', 'direction': 'In/Out',
                 'party_type': 'Type', 'party_name': 'Party', 'mode': 'Mode',
                 'amount': 'Amount', 'ref_no': 'Ref', 'site': 'Site',
                 'narration': 'Narration'}
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=50 if col == 'id' else 95, anchor='w')
        self.tree.tag_configure('in', background='#e8f5e9')
        self.tree.tag_configure('out', background='#ffebee')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        form = ttk.LabelFrame(self, text='Entry'); form.pack(fill='x', padx=8, pady=4)
        self._entry(form, 0, 0, 'Date', 'pay_date')
        self._combo(form, 0, 1, 'Money', 'direction', ['Receipt', 'Payment'])
        self._combo(form, 0, 2, 'Party Type', 'party_type', PARTY_TYPES,
                    on_change=self._reload_parties)
        cell = ttk.Frame(form); cell.grid(row=1, column=0, padx=6, pady=4, sticky='w')
        ttk.Label(cell, text='Party', width=12).pack(side='left')
        self.party_combo = ttk.Combobox(cell, textvariable=self.v['party'], width=20)
        self.party_combo.pack(side='left')
        self._combo(form, 1, 1, 'Mode', 'mode', MODES)
        self._entry(form, 1, 2, 'Amount', 'amount')
        self._entry(form, 2, 0, 'Ref No', 'ref_no')
        cell = ttk.Frame(form); cell.grid(row=2, column=1, padx=6, pady=4, sticky='w')
        ttk.Label(cell, text='Site', width=12).pack(side='left')
        self.site_combo = ttk.Combobox(cell, textvariable=self.v['site'], width=20,
                                       state='readonly')
        self.site_combo.pack(side='left')
        self._entry(form, 2, 2, 'Narration', 'narration')

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btns, text='Add', command=self.add).pack(side='left', padx=3)
        ttk.Button(btns, text='Update', command=self.update).pack(side='left', padx=3)
        ttk.Button(btns, text='Delete', command=self.delete).pack(side='left', padx=3)
        ttk.Button(btns, text='Allocate to Bills…',
                   command=self.allocate).pack(side='left', padx=3)
        ttk.Button(btns, text='Clear', command=self.clear).pack(side='left', padx=3)
        ttk.Button(btns, text='Refresh', command=self.reload).pack(side='left', padx=3)

    def _entry(self, parent, r, c, label, key):
        cell = ttk.Frame(parent); cell.grid(row=r, column=c, padx=6, pady=4, sticky='w')
        ttk.Label(cell, text=label, width=12).pack(side='left')
        ttk.Entry(cell, textvariable=self.v[key], width=22).pack(side='left')

    def _combo(self, parent, r, c, label, key, values, on_change=None):
        cell = ttk.Frame(parent); cell.grid(row=r, column=c, padx=6, pady=4, sticky='w')
        ttk.Label(cell, text=label, width=12).pack(side='left')
        w = ttk.Combobox(cell, textvariable=self.v[key], width=20,
                         state='readonly', values=values)
        w.pack(side='left')
        if on_change:
            w.bind('<<ComboboxSelected>>', lambda e: on_change())

    def reload(self):
        conn = self.db_getter()
        try:
            self._site_map = {'{} - {}'.format(i, n): i for i, n in _site_options(conn)}
            self.site_combo['values'] = [''] + list(self._site_map.keys())
            self._reload_parties(conn=conn)
            self._refresh_list(conn)
        finally:
            conn.close()

    def _reload_parties(self, conn=None):
        close = False
        if conn is None:
            conn = self.db_getter(); close = True
        try:
            opts = _party_options(conn, self.v['party_type'].get())
        finally:
            if close:
                conn.close()
        self._party_map = {'{} - {}'.format(i, n): i for i, n in opts}
        self.party_combo['values'] = list(self._party_map.keys())

    def _refresh_list(self, conn):
        for item in self.tree.get_children():
            self.tree.delete(item)
        sql = ("SELECT p.id, p.pay_date, p.direction, p.party_type, "
               "p.party_name, p.mode, p.amount, p.ref_no, s.name AS site, "
               "p.narration FROM payments p "
               "LEFT JOIN sites s ON s.id = p.site_id ORDER BY p.pay_date DESC, p.id DESC")
        for r in conn.execute(sql):
            tag = 'in' if r['direction'] == 'Receipt' else 'out'
            self.tree.insert('', 'end', iid=str(r['id']), values=(
                r['id'], r['pay_date'], r['direction'], r['party_type'],
                r['party_name'] or '-', r['mode'], '{:.2f}'.format(r['amount']),
                r['ref_no'] or '', r['site'] or '', r['narration'] or ''),
                tags=(tag,))

    def allocate(self):
        """Split the selected payment across the bills it settles."""
        if self.selected_id is None:
            messagebox.showinfo('No selection',
                                'Select a payment or receipt first.')
            return
        conn = self.db_getter()
        try:
            row = conn.execute('SELECT * FROM payments WHERE id = ?',
                               (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return
        if row['party_type'] not in ('Client', 'Vendor') or not row['party_id']:
            messagebox.showinfo(
                'Nothing to allocate against',
                'Allocation applies to a named Client or Vendor — those are '
                'the parties that have bills. This entry is "{}".'.format(
                    row['party_type'] or 'Other'))
            return
        from tab_allocate import AllocateDialog
        dlg = AllocateDialog(self.winfo_toplevel(), self.db_getter, row)
        self.wait_window(dlg)
        self.reload()

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM payments WHERE id = ?',
                             (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        self.v['pay_date'].set(r['pay_date'] or '')
        self.v['direction'].set(r['direction'] or 'Receipt')
        self.v['party_type'].set(r['party_type'] or 'Client')
        self._reload_parties()
        if r['party_id'] is not None:
            self.v['party'].set('{} - {}'.format(r['party_id'], r['party_name'] or ''))
        else:
            self.v['party'].set(r['party_name'] or '')
        self.v['mode'].set(r['mode'] or 'Cash')
        self.v['amount'].set(str(r['amount']))
        self.v['ref_no'].set(r['ref_no'] or '')
        self.v['narration'].set(r['narration'] or '')
        self.v['site'].set(self._display_for(self._site_map, r['site_id']))

    def _display_for(self, mapping, target_id):
        if target_id is None:
            return ''
        for disp, rid in mapping.items():
            if str(rid) == str(target_id):
                return disp
        return ''

    def _collect(self):
        try:
            amount = float(self.v['amount'].get().strip() or 0)
        except ValueError:
            messagebox.showerror('Invalid amount', 'Amount must be a number.')
            return None
        if amount <= 0:
            messagebox.showerror('Invalid amount', 'Amount must be greater than 0.')
            return None
        party_id, party_name = _parse_combo(self.v['party'].get(), self._party_map)
        site_id, _ = _parse_combo(self.v['site'].get(), self._site_map)
        return {
            'pay_date': self.v['pay_date'].get().strip(),
            'direction': self.v['direction'].get(),
            'party_type': self.v['party_type'].get(),
            'party_id': party_id, 'party_name': party_name,
            'mode': self.v['mode'].get(), 'amount': round(amount, 2),
            'ref_no': self.v['ref_no'].get().strip(),
            'site_id': site_id, 'narration': self.v['narration'].get().strip(),
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
            conn.execute('INSERT INTO payments ({}) VALUES ({})'.format(
                ', '.join(cols), ', '.join(['?'] * len(cols))),
                [d[c] for c in cols])
            conn.commit()
            self._refresh_list(conn)
        finally:
            conn.close()
        self.clear()

    def update(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an entry.')
            return
        d = self._collect()
        if d is None:
            return
        cols = list(d.keys())
        conn = self.db_getter()
        try:
            conn.execute('UPDATE payments SET {} WHERE id = ?'.format(
                ', '.join('{} = ?'.format(c) for c in cols)),
                [d[c] for c in cols] + [self.selected_id])
            conn.commit()
            self._refresh_list(conn)
        finally:
            conn.close()

    def delete(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an entry.')
            return
        if not messagebox.askyesno('Confirm delete', 'Delete this entry?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM payments WHERE id = ?', (self.selected_id,))
            conn.commit()
            self._refresh_list(conn)
        finally:
            conn.close()
        self.clear()

    def clear(self):
        self.selected_id = None
        self.v['pay_date'].set(''); self.v['amount'].set('0')
        self.v['party'].set(''); self.v['ref_no'].set('')
        self.v['narration'].set(''); self.v['site'].set('')
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())


# ============================================================ Party balances
class PartyLedgerView(ttk.Frame):
    COLUMNS = ('date', 'particulars', 'in', 'out', 'balance')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._party_map = {}
        self.type_var = tk.StringVar(value='Client')
        self.party_var = tk.StringVar()

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Party Type').pack(side='left')
        tc = ttk.Combobox(top, textvariable=self.type_var, width=10,
                          state='readonly', values=PARTY_TYPES)
        tc.pack(side='left', padx=4)
        tc.bind('<<ComboboxSelected>>', lambda e: self._reload_parties())
        ttk.Label(top, text='Party').pack(side='left')
        self.party_combo = ttk.Combobox(top, textvariable=self.party_var,
                                        width=24, state='readonly')
        self.party_combo.pack(side='left', padx=4)
        self.party_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Button(top, text='Refresh', command=self._reload_parties).pack(side='left', padx=4)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='left', padx=4)

        self._export_rows = []
        self._export_title = ''
        self.summary_var = tk.StringVar(value='Select a party.')
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')) \
            .pack(anchor='w', padx=8, pady=4)

        heads = {'date': 'Date', 'particulars': 'Particulars', 'in': 'Received',
                 'out': 'Paid', 'balance': 'Balance'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=200 if col == 'particulars' else 110, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self._reload_parties()

    def _reload_parties(self):
        conn = self.db_getter()
        try:
            opts = _party_options(conn, self.type_var.get())
        finally:
            conn.close()
        self._party_map = {'{} - {}'.format(i, n): i for i, n in opts}
        self.party_combo['values'] = list(self._party_map.keys())
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        raw = self.party_var.get().strip()
        if not raw:
            self.summary_var.set('Select a party.')
            return
        party_id, party_name = _parse_combo(raw, self._party_map)
        ptype = self.type_var.get()

        conn = self.db_getter()
        try:
            # Payment/receipt transactions for this party.
            txns = conn.execute(
                "SELECT pay_date, direction, mode, amount, narration "
                "FROM payments WHERE party_type = ? AND "
                "(party_id = ? OR (party_id IS NULL AND party_name = ?)) "
                "ORDER BY pay_date, id", (ptype, party_id, party_name)).fetchall()

            billed = 0.0
            received = 0.0
            if ptype == 'Client' and party_id is not None:
                billed = conn.execute(
                    "SELECT COALESCE(SUM(net_payable), 0) AS v FROM bills "
                    "WHERE status IN ('Approved', 'Paid') AND contract_id IN "
                    "(SELECT id FROM contracts WHERE client_id = ?)",
                    (party_id,)).fetchone()['v']
                billed += conn.execute(
                    "SELECT COALESCE(SUM(net_payable), 0) AS v FROM ra_bills "
                    "WHERE status IN ('Approved', 'Paid') AND contract_id IN "
                    "(SELECT id FROM contracts WHERE client_id = ?)",
                    (party_id,)).fetchone()['v']
                received = sum(t['amount'] for t in txns if t['direction'] == 'Receipt')
            elif ptype == 'Vendor' and party_id is not None:
                billed = conn.execute(
                    "SELECT COALESCE(SUM(net_payable), 0) AS v FROM vendor_invoices "
                    "WHERE vendor_id = ?", (party_id,)).fetchone()['v']
                received = sum(t['amount'] for t in txns if t['direction'] == 'Payment')
        finally:
            conn.close()

        # Running balance of just the cash movements (for the statement rows).
        signed = [m.signed_cash(t['direction'], t['amount']) for t in txns]
        balances = m.running_balance(signed)
        self._export_rows = []
        self._export_title = '{} Statement — {}'.format(ptype, party_name)
        for t, bal in zip(txns, balances):
            recv = t['amount'] if t['direction'] == 'Receipt' else 0
            paid = t['amount'] if t['direction'] == 'Payment' else 0
            row = (t['pay_date'], (t['narration'] or t['mode']),
                   '{:.2f}'.format(recv) if recv else '',
                   '{:.2f}'.format(paid) if paid else '',
                   '{:.2f}'.format(bal))
            self.tree.insert('', 'end', values=row)
            self._export_rows.append(row)

        if ptype in ('Client', 'Vendor') and party_id is not None:
            outstanding = m.party_outstanding(billed, received)
            noun = 'billed' if ptype == 'Client' else 'invoiced'
            settle = 'received' if ptype == 'Client' else 'paid'
            owe = 'owes us' if ptype == 'Client' else 'we owe'
            self.summary_var.set(
                '{name}:  {noun} {b:.2f}   {settle} {s:.2f}   ->   {owe} {o:.2f}'.format(
                    name=party_name, noun=noun, b=billed, settle=settle,
                    s=received, owe=owe, o=outstanding))
        else:
            net = balances[-1] if balances else 0.0
            self.summary_var.set('{}:  net cash movement {:.2f}'.format(
                party_name, net))

    def export(self):
        if not self._export_rows:
            messagebox.showinfo('Nothing to export', 'Select a party first.')
            return
        html = bill_export.build_statement_html(
            self._export_title, ['As on today'],
            ['Date', 'Particulars', 'Received', 'Paid', 'Balance'],
            self._export_rows, summary=self.summary_var.get())
        _save_and_open_html(html, 'party_statement.html')


# ============================================================ Cash book
class CashBookView(ttk.Frame):
    COLUMNS = ('date', 'particulars', 'in', 'out', 'balance')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._site_map = {}
        self.site_var = tk.StringVar(value='All')
        self.opening_var = tk.StringVar(value='0')

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Site').pack(side='left')
        self.site_combo = ttk.Combobox(top, textvariable=self.site_var, width=22,
                                       state='readonly')
        self.site_combo.pack(side='left', padx=4)
        self.site_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Label(top, text='Opening Cash').pack(side='left', padx=(10, 0))
        ttk.Entry(top, textvariable=self.opening_var, width=10).pack(side='left', padx=4)
        ttk.Button(top, text='Save Opening', command=self.save_opening).pack(side='left', padx=2)
        ttk.Button(top, text='Refresh', command=self.reload).pack(side='left', padx=4)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='left', padx=4)

        self._export_rows = []
        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=4)

        heads = {'date': 'Date', 'particulars': 'Particulars', 'in': 'Cash In',
                 'out': 'Cash Out', 'balance': 'Balance'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=220 if col == 'particulars' else 110, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.reload()

    def reload(self):
        conn = self.db_getter()
        try:
            self._site_map = {'{} - {}'.format(i, n): i for i, n in _site_options(conn)}
            self.site_combo['values'] = ['All'] + list(self._site_map.keys())
            row = conn.execute('SELECT value FROM app_settings WHERE key = ?',
                               (CASH_OPENING_KEY,)).fetchone()
            if row:
                self.opening_var.set(row['value'])
        finally:
            conn.close()
        self.refresh()

    def save_opening(self):
        try:
            val = float(self.opening_var.get().strip() or 0)
        except ValueError:
            messagebox.showerror('Invalid', 'Opening cash must be a number.')
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                (CASH_OPENING_KEY, str(val)))
            conn.commit()
        finally:
            conn.close()
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            opening = float(self.opening_var.get().strip() or 0)
        except ValueError:
            opening = 0.0
        sel = self.site_var.get()
        where = "mode = 'Cash'"
        params = []
        if sel != 'All' and sel in self._site_map:
            where += ' AND site_id = ?'
            params.append(self._site_map[sel])

        conn = self.db_getter()
        try:
            rows = conn.execute(
                'SELECT pay_date, direction, party_name, amount, narration '
                'FROM payments WHERE {} ORDER BY pay_date, id'.format(where),
                params).fetchall()
        finally:
            conn.close()

        signed = [m.signed_cash(r['direction'], r['amount']) for r in rows]
        balances = m.running_balance(signed, opening)
        total_in = total_out = 0.0
        self._export_rows = [('', 'Opening Balance', '', '', '{:.2f}'.format(opening))]
        for r, bal in zip(rows, balances):
            cin = r['amount'] if r['direction'] == 'Receipt' else 0
            cout = r['amount'] if r['direction'] == 'Payment' else 0
            total_in += cin; total_out += cout
            particulars = r['narration'] or r['party_name'] or '-'
            row = (r['pay_date'], particulars,
                   '{:.2f}'.format(cin) if cin else '',
                   '{:.2f}'.format(cout) if cout else '',
                   '{:.2f}'.format(bal))
            self.tree.insert('', 'end', values=row)
            self._export_rows.append(row)
        closing = m.closing_balance(signed, opening)
        self.summary_var.set(
            'Opening {:.2f}   +In {:.2f}   -Out {:.2f}   =  Closing (cash in hand) {:.2f}'.format(
                opening, total_in, total_out, closing))

    def export(self):
        if not self._export_rows:
            self.refresh()
        html = bill_export.build_statement_html(
            'Cash Book', ['Site: {}'.format(self.site_var.get())],
            ['Date', 'Particulars', 'Cash In', 'Cash Out', 'Balance'],
            self._export_rows, summary=self.summary_var.get())
        _save_and_open_html(html, 'cash_book.html')


def build_money_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(PaymentsFrame(nb, db_getter), text='Payments & Receipts')
    nb.add(PartyLedgerView(nb, db_getter), text='Party Balances')
    nb.add(CashBookView(nb, db_getter), text='Cash Book')
    return nb
