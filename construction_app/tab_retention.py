"""Retention register — money withheld, and when it comes back (Wave 2).

Retention never appears on an invoice, so nobody chases it. A contractor with
twenty bills behind them can be owed a substantial sum and have no single
figure for it. This register produces that figure, splits it by side, and says
which of it is **due for release now**.

* **Receivable** — retention our clients hold on our bills and RA bills.
* **Payable** — retention we hold on subcontractor bills, which we must
  eventually release.

The release date is the contract completion date plus the defect-liability
period, not the bill date: a bill raised early in a job is released on the same
day as the last one. Where no completion date is recorded, the line is shown as
held with the reason stated rather than given an invented date.
"""

import tkinter as tk
from datetime import date
from tkinter import ttk, messagebox

import bill_export
import report_open
import retention
from ui_guard import can_write


def _released_map(conn):
    """{(doc_type, doc_id): released so far}."""
    out = {}
    for r in conn.execute(
            'SELECT doc_type, doc_id, SUM(amount) AS a '
            'FROM retention_releases GROUP BY doc_type, doc_id'):
        out[(r['doc_type'], r['doc_id'])] = r['a'] or 0
    return out


def retention_lines(conn, dlp_months=12):
    """Every document that withheld retention, with its release position."""
    released = _released_map(conn)
    lines = []

    def add(doc_type, doc_id, number, party, side, withheld, completion):
        w = retention.money(withheld)
        if w <= 0:
            return
        rel = retention.money(released.get((doc_type, doc_id), 0))
        due = retention.release_due_date(completion, dlp_months)
        lines.append({
            'doc_type': doc_type, 'doc_id': doc_id, 'number': number or '-',
            'party': party or '-', 'side': side, 'withheld': w,
            'released': rel,
            'outstanding': retention.outstanding(w, rel),
            'due_date': due.isoformat() if due else None,
            'completion': completion or '',
        })

    for r in conn.execute(
            'SELECT b.id, b.bill_no, b.retention_amt, cl.name AS party, '
            'c.end_date FROM bills b '
            'JOIN contracts c ON c.id = b.contract_id '
            'LEFT JOIN clients cl ON cl.id = c.client_id '
            "WHERE b.status IN ('Approved','Paid')"):
        add('Bill', r['id'], r['bill_no'], r['party'], retention.CLIENT,
            r['retention_amt'], r['end_date'])

    for r in conn.execute(
            'SELECT rb.id, rb.bill_no, rb.retention_amt, cl.name AS party, '
            'c.end_date FROM ra_bills rb '
            'JOIN contracts c ON c.id = rb.contract_id '
            'LEFT JOIN clients cl ON cl.id = c.client_id '
            "WHERE rb.status IN ('Approved','Paid')"):
        add('RABill', r['id'], r['bill_no'], r['party'], retention.CLIENT,
            r['retention_amt'], r['end_date'])

    try:
        for r in conn.execute(
                'SELECT sb.id, sb.bill_no, sb.retention_amt, sb.bill_date, '
                'v.name AS party FROM sub_bills sb '
                'LEFT JOIN work_orders wo ON wo.id = sb.work_order_id '
                'LEFT JOIN vendors v ON v.id = wo.vendor_id '
                "WHERE sb.status IN ('Approved','Paid')"):
            add('SubBill', r['id'], r['bill_no'], r['party'], retention.SUB,
                r['retention_amt'], r['bill_date'])
    except Exception:                                        # noqa: BLE001
        pass          # older file without work orders — skip that side
    return lines


class RetentionRegister(ttk.Frame):
    COLUMNS = ('side', 'number', 'party', 'withheld', 'released',
               'outstanding', 'due', 'status')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._lines = []
        self._rows = []
        self.dlp_var = tk.StringVar(value='12')
        self.summary_var = tk.StringVar()
        self.due_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Retention register',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='Retention is money you have already earned and '
                             'someone else is holding. It never appears on an '
                             'invoice, so it is the easiest money to forget.',
                  wraplength=700, justify='left', foreground='#555') \
            .pack(anchor='w', padx=8, pady=(0, 6))

        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=4)
        ttk.Label(top, text='Defect liability (months)').pack(side='left')
        ttk.Entry(top, textvariable=self.dlp_var, width=6).pack(side='left', padx=4)
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='left', padx=6)
        ttk.Button(top, text='Record Release', command=self.record_release).pack(side='left')
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='left', padx=6)

        ttk.Label(self, textvariable=self.due_var, foreground='#a4343a',
                  font=('TkDefaultFont', 11, 'bold'), wraplength=700,
                  justify='left').pack(anchor='w', padx=8, pady=(4, 0))

        heads = {'side': 'Side', 'number': 'Document', 'party': 'Party',
                 'withheld': 'Withheld', 'released': 'Released',
                 'outstanding': 'Outstanding', 'due': 'Release due',
                 'status': 'Status'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for c in self.COLUMNS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=130 if c in ('party', 'status') else 105,
                             anchor='e' if c in ('withheld', 'released',
                                                 'outstanding') else 'w')
        self.tree.tag_configure('due', background='#ffe3e3')
        self.tree.tag_configure('done', background='#e4f1e8')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=6)

    def _dlp(self):
        try:
            return int(str(self.dlp_var.get()).strip() or 12)
        except ValueError:
            return 12

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            self._lines = retention_lines(conn, self._dlp())
        finally:
            conn.close()

        self._rows = []
        for ln in self._lines:
            status = retention.line_status(ln['withheld'], ln['released'],
                                           ln['due_date'])
            values = (ln['side'], ln['number'], ln['party'],
                      '{:,.2f}'.format(ln['withheld']),
                      '{:,.2f}'.format(ln['released']),
                      '{:,.2f}'.format(ln['outstanding']),
                      ln['due_date'] or '(no completion date)', status)
            self._rows.append(values)
            tag = ('due' if status.startswith('DUE') else
                   'done' if status == 'Released' else '')
            self.tree.insert('', 'end', iid='{}:{}'.format(ln['doc_type'],
                                                           ln['doc_id']),
                             values=values, tags=(tag,) if tag else ())

        recv = [l for l in self._lines if l['side'] == retention.CLIENT]
        pay = [l for l in self._lines if l['side'] == retention.SUB]
        sr, sp = retention.summarise(recv), retention.summarise(pay)
        s = retention.summarise(self._lines)
        self.summary_var.set(
            'Owed to us {:,.2f}   ·   we hold {:,.2f}   ·   released to date '
            '{:,.2f}'.format(sr['outstanding'], sp['outstanding'], s['released']))
        if s['due_now'] > 0:
            self.due_var.set(
                '{:,.2f} is past its defect-liability date and still not '
                'released{}. Claim it.'.format(
                    s['due_now'],
                    ' (oldest by {} days)'.format(s['max_overdue_days'])
                    if s['max_overdue_days'] else ''))
        else:
            upcoming = retention.upcoming(self._lines, 60)
            self.due_var.set(
                '{} release(s) fall due in the next 60 days — raise the claim '
                'before the date.'.format(len(upcoming)) if upcoming else '')

    def record_release(self):
        if not can_write():
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('No selection', 'Select a retention line first.')
            return
        doc_type, doc_id = sel[0].split(':')
        line = next((l for l in self._lines
                     if l['doc_type'] == doc_type and str(l['doc_id']) == doc_id),
                    None)
        if line is None:
            return
        if line['outstanding'] <= 0:
            messagebox.showinfo('Already released',
                                'Nothing is outstanding on this line.')
            return

        win = tk.Toplevel(self); win.title('Record retention release')
        win.transient(self.winfo_toplevel()); win.grab_set()
        ttk.Label(win, text='{}  {}\nOutstanding: {:,.2f}'.format(
            line['side'], line['number'], line['outstanding']),
            justify='left').pack(padx=14, pady=(12, 6))
        amount_var = tk.StringVar(value='{:.2f}'.format(line['outstanding']))
        date_var = tk.StringVar(value=date.today().isoformat())
        ref_var = tk.StringVar()
        for label, var in (('Amount', amount_var), ('Date', date_var),
                           ('Reference', ref_var)):
            row = ttk.Frame(win); row.pack(fill='x', padx=14, pady=3)
            ttk.Label(row, text=label, width=10).pack(side='left')
            ttk.Entry(row, textvariable=var, width=22).pack(side='left')

        def save():
            try:
                amount = retention.money(amount_var.get().strip())
            except ValueError:
                messagebox.showerror('Not a number', 'Enter an amount.', parent=win)
                return
            if amount <= 0:
                messagebox.showerror('Nothing to record',
                                     'Enter an amount above zero.', parent=win)
                return
            if amount > line['outstanding'] + 0.005:
                messagebox.showerror(
                    'Too much',
                    'Only {:,.2f} is outstanding on this line.'.format(
                        line['outstanding']), parent=win)
                return
            conn = self.db_getter()
            try:
                conn.execute(
                    'INSERT INTO retention_releases (doc_type, doc_id, '
                    'release_date, amount, reference) VALUES (?, ?, ?, ?, ?)',
                    (doc_type, int(doc_id), date_var.get().strip(), amount,
                     ref_var.get().strip()))
                conn.commit()
            finally:
                conn.close()
            win.destroy()
            self.refresh()

        row = ttk.Frame(win); row.pack(pady=12)
        ttk.Button(row, text='Save', command=save).pack(side='left', padx=4)
        ttk.Button(row, text='Cancel', command=win.destroy).pack(side='left')

    def export(self):
        html = bill_export.build_statement_html(
            'Retention register',
            [self.due_var.get() or 'Nothing overdue for release.',
             self.summary_var.get()],
            ['Side', 'Document', 'Party', 'Withheld', 'Released',
             'Outstanding', 'Release due', 'Status'],
            self._rows, summary=self.summary_var.get())
        report_open.save_and_open_html(html, 'retention_register.html')


def build_retention_tab(parent, db_getter):
    return RetentionRegister(parent, db_getter)
