"""Accounting: chart of accounts, double-entry journal, and trial balance.

- Chart of Accounts is a flat CrudFrame over ``accounts``.
- The Journal is a bespoke header (``journal_entries``) + lines
  (``journal_lines``) UI. Each line is a debit OR a credit against one account;
  a live indicator shows whether the entry balances (``finance.is_balanced``).
  Header ``total_debit``/``total_credit`` are derived from the lines.
- Trial Balance sums debits and credits per account; the grand totals must be
  equal for the books to balance.

The default chart of accounts is seeded by ``db.seed_default_accounts`` on first
run.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from ui_guard import can_write

import finance
import journal_post
import reports
import bill_export
from crud_frame import CrudFrame, Field
from tab_money import _save_and_open_html


ACCOUNT_TYPES = ['Asset', 'Liability', 'Income', 'Expense', 'Equity']


def account_options(conn):
    return [(r['id'], '{} {}'.format(r['code'] or '', r['name']).strip())
            for r in conn.execute(
                'SELECT id, code, name FROM accounts ORDER BY code, name')]


def build_chart_of_accounts(parent, db_getter):
    fields = [
        Field('code', 'Code'),
        Field('name', 'Name'),
        Field('type', 'Type', kind='combo', options=ACCOUNT_TYPES,
              default='Asset'),
        Field('parent_id', 'Parent', kind='fk', options_func=account_options),
        Field('is_active', 'Active (1/0)', kind='number', default='1'),
    ]
    return CrudFrame(parent, db_getter, 'accounts', fields,
                     'Chart of Accounts', order_by='code')


class JournalFrame(ttk.Frame):
    HEADER_COLUMNS = ('id', 'entry_date', 'narration', 'reference',
                      'total_debit', 'total_credit')
    LINE_COLUMNS = ('id', 'account', 'debit', 'credit', 'notes')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self.selected_line_id = None
        self._acct_map = {}

        self.h = {'entry_date': tk.StringVar(), 'narration': tk.StringVar(),
                  'reference': tk.StringVar()}
        self.l = {'account': tk.StringVar(), 'debit': tk.StringVar(),
                  'credit': tk.StringVar(), 'notes': tk.StringVar()}
        self._build_ui()
        self.refresh_entries()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Journal Entries',
                  font=('TkDefaultFont', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Auto-Post Documents',
                   command=self.auto_post).pack(side='right')

        hdr = ttk.LabelFrame(self, text='Entries')
        hdr.pack(fill='both', expand=True, padx=8, pady=4)
        headings = {'id': 'ID', 'entry_date': 'Date', 'narration': 'Narration',
                    'reference': 'Reference', 'total_debit': 'Debit',
                    'total_credit': 'Credit'}
        self.tree = ttk.Treeview(hdr, columns=self.HEADER_COLUMNS,
                                 show='headings', height=6)
        for col in self.HEADER_COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=50 if col == 'id' else 130, anchor='w')
        self.tree.pack(fill='x', padx=4, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        form = ttk.Frame(hdr)
        form.pack(fill='x', padx=4, pady=4)
        for idx, (key, label) in enumerate(
                [('entry_date', 'Date'), ('narration', 'Narration'),
                 ('reference', 'Reference')]):
            cell = ttk.Frame(form); cell.grid(row=0, column=idx, padx=6, pady=3, sticky='w')
            ttk.Label(cell, text=label, width=10).pack(side='left')
            ttk.Entry(cell, textvariable=self.h[key], width=20).pack(side='left')

        hbtns = ttk.Frame(hdr)
        hbtns.pack(fill='x', padx=4, pady=4)
        ttk.Button(hbtns, text='Add Entry', command=self.add_entry).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Update Entry', command=self.update_entry).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Delete Entry', command=self.delete_entry).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Clear', command=self.clear_entry).pack(side='left', padx=3)

        self.balance_var = tk.StringVar(value='No entry selected.')
        ttk.Label(hdr, textvariable=self.balance_var,
                  font=('TkDefaultFont', 10, 'bold')) \
            .pack(anchor='w', padx=6, pady=(2, 4))

        # ---------------- lines ----------------
        lines = ttk.LabelFrame(self, text='Lines (each line is a debit OR a credit)')
        lines.pack(fill='both', expand=True, padx=8, pady=4)
        self.line_tree = ttk.Treeview(lines, columns=self.LINE_COLUMNS,
                                      show='headings', height=6)
        headings = {'id': 'ID', 'account': 'Account', 'debit': 'Debit',
                    'credit': 'Credit', 'notes': 'Notes'}
        for col in self.LINE_COLUMNS:
            self.line_tree.heading(col, text=headings[col])
            self.line_tree.column(col, width=50 if col == 'id' else 150,
                                  anchor='w')
        self.line_tree.pack(fill='x', padx=4, pady=4)
        self.line_tree.bind('<<TreeviewSelect>>', self._on_line_select)

        lform = ttk.Frame(lines)
        lform.pack(fill='x', padx=4, pady=4)
        cell = ttk.Frame(lform); cell.grid(row=0, column=0, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text='Account', width=8).pack(side='left')
        self.account_combo = ttk.Combobox(cell, textvariable=self.l['account'],
                                          width=24, state='readonly')
        self.account_combo.pack(side='left')
        for idx, (key, label) in enumerate(
                [('debit', 'Debit'), ('credit', 'Credit'), ('notes', 'Notes')],
                start=1):
            cell = ttk.Frame(lform); cell.grid(row=0, column=idx, padx=6, pady=3, sticky='w')
            ttk.Label(cell, text=label, width=6).pack(side='left')
            ttk.Entry(cell, textvariable=self.l[key], width=14).pack(side='left')

        lbtns = ttk.Frame(lines)
        lbtns.pack(fill='x', padx=4, pady=4)
        ttk.Button(lbtns, text='Add Line', command=self.add_line).pack(side='left', padx=3)
        ttk.Button(lbtns, text='Update Line', command=self.update_line).pack(side='left', padx=3)
        ttk.Button(lbtns, text='Delete Line', command=self.delete_line).pack(side='left', padx=3)
        ttk.Button(lbtns, text='Clear', command=self.clear_line).pack(side='left', padx=3)

    # -------------------------------------------------------------- helpers
    def _acct_id(self):
        raw = self.l['account'].get().strip()
        if not raw:
            return None
        return self._acct_map.get(raw, raw.split(' - ')[0])

    def _recalc(self, conn, entry_id):
        row = conn.execute(
            'SELECT COALESCE(SUM(debit), 0) AS d, COALESCE(SUM(credit), 0) AS c '
            'FROM journal_lines WHERE journal_entry_id = ?',
            (entry_id,)).fetchone()
        conn.execute(
            'UPDATE journal_entries SET total_debit = ?, total_credit = ? '
            'WHERE id = ?', (row['d'], row['c'], entry_id))
        conn.commit()
        return row['d'], row['c']

    def _set_balance_label(self, debit, credit):
        if finance.is_balanced(debit, credit):
            self.balance_var.set(
                'Balanced  (Debit {:.2f} = Credit {:.2f})'.format(debit, credit))
        else:
            self.balance_var.set(
                'NOT balanced  (Debit {:.2f}, Credit {:.2f}, diff {:.2f})'.format(
                    debit, credit, abs(debit - credit)))

    # ----------------------------------------------------------- entry ops
    def refresh_entries(self):
        conn = self.db_getter()
        try:
            opts = account_options(conn)
            self._acct_map = {'{} - {}'.format(i, n): i for i, n in opts}
            self.account_combo['values'] = ['{} - {}'.format(i, n) for i, n in opts]
            for item in self.tree.get_children():
                self.tree.delete(item)
            for r in conn.execute(
                    'SELECT id, entry_date, narration, reference, total_debit, '
                    'total_credit FROM journal_entries ORDER BY id DESC'):
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['entry_date'], r['narration'], r['reference'],
                    '{:.2f}'.format(r['total_debit']),
                    '{:.2f}'.format(r['total_credit'])))
        finally:
            conn.close()

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM journal_entries WHERE id = ?',
                             (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        self.h['entry_date'].set(r['entry_date'] or '')
        self.h['narration'].set(r['narration'] or '')
        self.h['reference'].set(r['reference'] or '')
        self._set_balance_label(r['total_debit'], r['total_credit'])
        self.refresh_lines()

    def auto_post(self):
        if not can_write():
            return
        """Generate balanced journal entries from unposted business documents."""
        conn = self.db_getter()
        try:
            count = journal_post.post_all(conn)
        finally:
            conn.close()
        messagebox.showinfo(
            'Auto-post complete',
            'Posted {} new journal entr{} from tax invoices, vendor invoices '
            'and payments.\n\n(Running/RA bills are not auto-posted yet.)'.format(
                count, 'y' if count == 1 else 'ies'))
        self.refresh_entries()

    def add_entry(self):
        if not can_write():
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO journal_entries (entry_date, narration, reference, '
                "source) VALUES (?, ?, ?, 'Manual')",
                (self.h['entry_date'].get().strip(),
                 self.h['narration'].get().strip(),
                 self.h['reference'].get().strip()))
            conn.commit()
        finally:
            conn.close()
        self.refresh_entries()
        self.clear_entry()

    def update_entry(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an entry.')
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'UPDATE journal_entries SET entry_date = ?, narration = ?, '
                'reference = ? WHERE id = ?',
                (self.h['entry_date'].get().strip(),
                 self.h['narration'].get().strip(),
                 self.h['reference'].get().strip(), self.selected_id))
            conn.commit()
        finally:
            conn.close()
        self.refresh_entries()

    def delete_entry(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an entry.')
            return
        if not messagebox.askyesno('Confirm delete',
                                   'Delete this journal entry and its lines?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM journal_entries WHERE id = ?',
                         (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_id = None
        self.refresh_entries()
        self.refresh_lines()
        self.clear_entry()

    def clear_entry(self):
        self.selected_id = None
        for var in self.h.values():
            var.set('')
        self.balance_var.set('No entry selected.')
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self.refresh_lines()

    # ------------------------------------------------------------- line ops
    def refresh_lines(self):
        for item in self.line_tree.get_children():
            self.line_tree.delete(item)
        if self.selected_id is None:
            return
        conn = self.db_getter()
        try:
            for r in conn.execute(
                    'SELECT jl.id, a.code, a.name, jl.debit, jl.credit, '
                    'jl.notes FROM journal_lines jl '
                    'LEFT JOIN accounts a ON a.id = jl.account_id '
                    'WHERE jl.journal_entry_id = ? ORDER BY jl.id',
                    (self.selected_id,)):
                label = '{} {}'.format(r['code'] or '', r['name'] or '').strip()
                self.line_tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], label or '-', '{:.2f}'.format(r['debit']),
                    '{:.2f}'.format(r['credit']), r['notes'] or ''))
        finally:
            conn.close()

    def _on_line_select(self, _event=None):
        sel = self.line_tree.selection()
        if not sel:
            return
        self.selected_line_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM journal_lines WHERE id = ?',
                             (self.selected_line_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        for disp, aid in self._acct_map.items():
            if str(aid) == str(r['account_id']):
                self.l['account'].set(disp)
                break
        self.l['debit'].set(str(r['debit']))
        self.l['credit'].set(str(r['credit']))
        self.l['notes'].set(r['notes'] or '')

    def _collect_line(self):
        acct = self._acct_id()
        if acct is None:
            messagebox.showinfo('No account', 'Select an account for the line.')
            return None
        try:
            debit = float(self.l['debit'].get().strip() or 0)
            credit = float(self.l['credit'].get().strip() or 0)
        except ValueError:
            messagebox.showerror('Invalid number', 'Debit/Credit must be numbers.')
            return None
        if debit and credit:
            messagebox.showerror(
                'Invalid line',
                'A line is either a debit or a credit, not both.')
            return None
        return acct, debit, credit, self.l['notes'].get().strip()

    def _after_line_change(self):
        conn = self.db_getter()
        try:
            d, c = self._recalc(conn, self.selected_id)
        finally:
            conn.close()
        self._set_balance_label(d, c)
        self.refresh_lines()
        self.refresh_entries()
        if self.tree.exists(str(self.selected_id)):
            self.tree.selection_set(str(self.selected_id))

    def add_line(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No entry', 'Select or add a journal entry first.')
            return
        line = self._collect_line()
        if line is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO journal_lines (journal_entry_id, account_id, '
                'debit, credit, notes) VALUES (?, ?, ?, ?, ?)',
                (self.selected_id,) + line)
            conn.commit()
        finally:
            conn.close()
        self._after_line_change()
        self.clear_line()

    def update_line(self):
        if not can_write():
            return
        if self.selected_line_id is None:
            messagebox.showinfo('No selection', 'Select a line.')
            return
        line = self._collect_line()
        if line is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'UPDATE journal_lines SET account_id = ?, debit = ?, '
                'credit = ?, notes = ? WHERE id = ?',
                line + (self.selected_line_id,))
            conn.commit()
        finally:
            conn.close()
        self._after_line_change()

    def delete_line(self):
        if not can_write():
            return
        if self.selected_line_id is None:
            messagebox.showinfo('No selection', 'Select a line.')
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM journal_lines WHERE id = ?',
                         (self.selected_line_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_line_id = None
        self._after_line_change()
        self.clear_line()

    def clear_line(self):
        self.selected_line_id = None
        for var in self.l.values():
            var.set('')
        if self.line_tree.selection():
            self.line_tree.selection_remove(self.line_tree.selection())


class TrialBalance(ttk.Frame):
    COLUMNS = ('code', 'name', 'type', 'debit', 'credit')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter

        ttk.Label(self, text='Trial Balance',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        headings = {'code': 'Code', 'name': 'Account', 'type': 'Type',
                    'debit': 'Debit', 'credit': 'Credit'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=150 if col == 'name' else 110,
                             anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var,
                  font=('TkDefaultFont', 10, 'bold')) \
            .pack(anchor='w', padx=8, pady=(0, 4))
        ttk.Button(self, text='Refresh', command=self.refresh) \
            .pack(anchor='w', padx=8, pady=(0, 8))
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            rows = conn.execute(
                'SELECT a.code, a.name, a.type, '
                'COALESCE(SUM(jl.debit), 0) AS d, '
                'COALESCE(SUM(jl.credit), 0) AS c '
                'FROM accounts a '
                'LEFT JOIN journal_lines jl ON jl.account_id = a.id '
                'GROUP BY a.id ORDER BY a.code').fetchall()
        finally:
            conn.close()

        total_d = total_c = 0.0
        for r in rows:
            d, c = r['d'], r['c']
            total_d += d
            total_c += c
            if not d and not c:
                continue  # hide unused accounts to keep the report readable
            self.tree.insert('', 'end', values=(
                r['code'] or '', r['name'], r['type'],
                '{:.2f}'.format(d), '{:.2f}'.format(c)))
        self.tree.insert('', 'end', values=(
            '', 'TOTAL', '', '{:.2f}'.format(total_d),
            '{:.2f}'.format(total_c)))
        if finance.is_balanced(total_d, total_c):
            self.status_var.set('Books balance: debits = credits = {:.2f}'.format(
                total_d))
        else:
            self.status_var.set(
                'OUT OF BALANCE by {:.2f} — check journal entries.'.format(
                    abs(total_d - total_c)))


def _account_totals(conn):
    """Per-account debit/credit totals — the basis for TB / P&L / balance sheet."""
    return conn.execute(
        'SELECT a.code, a.name, a.type, '
        'COALESCE(SUM(jl.debit), 0) AS debit, '
        'COALESCE(SUM(jl.credit), 0) AS credit '
        'FROM accounts a LEFT JOIN journal_lines jl ON jl.account_id = a.id '
        'GROUP BY a.id ORDER BY a.code').fetchall()


class ProfitAndLoss(ttk.Frame):
    """P&L on the posted ledger: income less expense = net profit."""

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._lines = []

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Profit & Loss',
                  font=('TkDefaultFont', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='right', padx=2)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='right', padx=2)

        self.tree = ttk.Treeview(self, columns=('particulars', 'amount'),
                                 show='headings')
        self.tree.heading('particulars', text='Particulars')
        self.tree.heading('amount', text='Amount')
        self.tree.column('particulars', width=280, anchor='w')
        self.tree.column('amount', width=140, anchor='w')
        self.tree.tag_configure('head', background='#eceff1')
        self.tree.tag_configure('total', background='#e8f5e9')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=4)
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            pl = reports.profit_and_loss(_account_totals(conn))
        finally:
            conn.close()
        self._lines = []

        def add(particulars, amount, tag=''):
            val = '' if amount is None else '{:,.2f}'.format(amount)
            self.tree.insert('', 'end', values=(particulars, val), tags=(tag,))
            self._lines.append((particulars, val))

        add('INCOME', None, 'head')
        for name, amt in pl['income']:
            add('  ' + name, amt)
        add('Total Income', pl['total_income'], 'total')
        add('EXPENSES', None, 'head')
        for name, amt in pl['expense']:
            add('  ' + name, amt)
        add('Total Expenses', pl['total_expense'], 'total')
        label = 'Net Profit' if pl['net_profit'] >= 0 else 'Net Loss'
        add(label, abs(pl['net_profit']), 'total')
        self.summary_var.set('{}: {:,.2f}'.format(label, abs(pl['net_profit'])))

    def export(self):
        html = bill_export.build_statement_html(
            'Profit & Loss', ['As on today (posted ledger)'],
            ['Particulars', 'Amount'], self._lines, summary=self.summary_var.get())
        _save_and_open_html(html, 'profit_and_loss.html')


class BalanceSheet(ttk.Frame):
    """Balance sheet on the posted ledger: assets vs liabilities + equity."""

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._lines = []

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Balance Sheet',
                  font=('TkDefaultFont', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='right', padx=2)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='right', padx=2)

        self.tree = ttk.Treeview(self, columns=('particulars', 'amount'),
                                 show='headings')
        self.tree.heading('particulars', text='Particulars')
        self.tree.heading('amount', text='Amount')
        self.tree.column('particulars', width=280, anchor='w')
        self.tree.column('amount', width=140, anchor='w')
        self.tree.tag_configure('head', background='#eceff1')
        self.tree.tag_configure('total', background='#e8f5e9')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=4)
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            bs = reports.balance_sheet(_account_totals(conn))
        finally:
            conn.close()
        self._lines = []

        def add(particulars, amount, tag=''):
            val = '' if amount is None else '{:,.2f}'.format(amount)
            self.tree.insert('', 'end', values=(particulars, val), tags=(tag,))
            self._lines.append((particulars, val))

        add('ASSETS', None, 'head')
        for name, amt in bs['assets']:
            add('  ' + name, amt)
        add('Total Assets', bs['total_assets'], 'total')
        add('LIABILITIES', None, 'head')
        for name, amt in bs['liabilities']:
            add('  ' + name, amt)
        add('EQUITY', None, 'head')
        for name, amt in bs['equity']:
            add('  ' + name, amt)
        add('Total Liabilities + Equity', bs['total_liabilities_equity'], 'total')
        if bs['balanced']:
            self.summary_var.set('Balanced: assets = liabilities + equity = '
                                 '{:,.2f}'.format(bs['total_assets']))
        else:
            self.summary_var.set(
                'OUT OF BALANCE by {:,.2f} — run Auto-Post and check the journal.'
                .format(abs(bs['total_assets'] - bs['total_liabilities_equity'])))

    def export(self):
        html = bill_export.build_statement_html(
            'Balance Sheet', ['As on today (posted ledger)'],
            ['Particulars', 'Amount'], self._lines, summary=self.summary_var.get())
        _save_and_open_html(html, 'balance_sheet.html')


def build_accounting_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(build_chart_of_accounts(nb, db_getter), text='Chart of Accounts')
    nb.add(JournalFrame(nb, db_getter), text='Journal')
    nb.add(TrialBalance(nb, db_getter), text='Trial Balance')
    nb.add(ProfitAndLoss(nb, db_getter), text='Profit & Loss')
    nb.add(BalanceSheet(nb, db_getter), text='Balance Sheet')
    return nb
