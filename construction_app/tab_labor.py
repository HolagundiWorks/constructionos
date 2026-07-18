"""Labor tab: Attendance (CrudFrame), Advances (CrudFrame), and Payroll.

Payroll is bespoke (list + Generate + Mark Paid, no per-row edit/delete). The
day-fraction rule is extracted to the module-level ``days_present_for`` so it
can be unit-tested without a GUI or database.
"""

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox

import wages
from crud_frame import CrudFrame, Field
from tab_masters import labor_options


# ---------------------------------------------------------------- pure logic
# The day-fraction rule now lives in wages.py (shared with the muster roll and
# weekly payout); kept re-exported here under its original name for callers/docs.
days_present_for = wages.day_fraction


# ---------------------------------------------------------------- sub-frames
def _build_attendance(parent, db_getter):
    fields = [
        Field('att_date', 'Date'),
        Field('labor_id', 'Labor', kind='fk', options_func=labor_options),
        Field('status', 'Status', kind='combo',
              options=['Present', 'Half Day', 'Overtime', 'Absent'],
              default='Present'),
        Field('hours', 'Hours', kind='number', default='8'),
        Field('remarks', 'Remarks', width=160),
    ]
    return CrudFrame(parent, db_getter, 'attendance', fields, 'Attendance',
                     order_by='att_date DESC, id DESC')


def _build_advances(parent, db_getter):
    fields = [
        Field('adv_date', 'Date'),
        Field('labor_id', 'Labor', kind='fk', options_func=labor_options),
        Field('amount', 'Amount', kind='number', default='0'),
        Field('recovered', 'Recovered', kind='number', default='0'),
        Field('status', 'Status', kind='combo',
              options=['Open', 'Closed'], default='Open'),
        Field('remarks', 'Remarks', width=160),
    ]
    return CrudFrame(parent, db_getter, 'advances', fields, 'Advances',
                     order_by='adv_date DESC, id DESC')


class PayrollFrame(ttk.Frame):
    """Generate/list/mark-paid payroll. No per-row edit or delete (see §7)."""

    MONTHS = [str(m) for m in range(1, 13)]

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter

        ttk.Label(self, text='Payroll', font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        controls = ttk.Frame(self)
        controls.pack(fill='x', padx=8, pady=4)
        today = date.today()
        ttk.Label(controls, text='Month').pack(side='left')
        self.month_var = tk.StringVar(value=str(today.month))
        ttk.Combobox(controls, textvariable=self.month_var, width=5,
                     state='readonly', values=self.MONTHS).pack(side='left', padx=4)
        ttk.Label(controls, text='Year').pack(side='left')
        self.year_var = tk.StringVar(value=str(today.year))
        ttk.Entry(controls, textvariable=self.year_var, width=8) \
            .pack(side='left', padx=4)
        ttk.Button(controls, text='Generate',
                   command=self.generate_payroll).pack(side='left', padx=6)
        ttk.Button(controls, text='Mark Paid',
                   command=self.mark_paid).pack(side='left', padx=6)
        ttk.Button(controls, text='Refresh',
                   command=self.refresh).pack(side='left', padx=6)

        columns = ('id', 'labor', 'month', 'year', 'days', 'gross',
                   'deduction', 'net', 'status')
        headings = {'id': 'ID', 'labor': 'Labor', 'month': 'Month',
                    'year': 'Year', 'days': 'Days', 'gross': 'Gross',
                    'deduction': 'Deduction', 'net': 'Net', 'status': 'Status'}
        self.tree = ttk.Treeview(self, columns=columns, show='headings')
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=90 if col != 'labor' else 140,
                             anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            sql = ("SELECT p.id, l.name AS labor, p.month, p.year, "
                   "p.days_present, p.gross_amount, p.deduction, "
                   "p.net_amount, p.status "
                   "FROM payroll p LEFT JOIN labor l ON l.id = p.labor_id "
                   "ORDER BY p.year DESC, p.month DESC, l.name")
            for r in conn.execute(sql):
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['labor'] or '-', r['month'], r['year'],
                    '{:.2f}'.format(r['days_present']),
                    '{:.2f}'.format(r['gross_amount']),
                    '{:.2f}'.format(r['deduction']),
                    '{:.2f}'.format(r['net_amount']), r['status']))
        finally:
            conn.close()

    def generate_payroll(self):
        try:
            month = int(self.month_var.get())
            year = int(self.year_var.get())
        except ValueError:
            messagebox.showerror('Invalid period', 'Month/Year must be numbers.')
            return

        month_str = '{:02d}'.format(month)
        year_str = str(year)
        created = 0
        skipped = 0
        conn = self.db_getter()
        try:
            active = conn.execute(
                "SELECT id, daily_wage FROM labor WHERE status = 'Active'"
            ).fetchall()
            for lab in active:
                labor_id = lab['id']
                # Idempotency guard: skip an existing (labor, month, year).
                exists = conn.execute(
                    "SELECT 1 FROM payroll "
                    "WHERE labor_id = ? AND month = ? AND year = ?",
                    (labor_id, month, year)).fetchone()
                if exists:
                    skipped += 1
                    continue

                days = 0.0
                for att in conn.execute(
                        "SELECT status, hours FROM attendance "
                        "WHERE labor_id = ? "
                        "AND strftime('%m', att_date) = ? "
                        "AND strftime('%Y', att_date) = ?",
                        (labor_id, month_str, year_str)):
                    days += days_present_for(att['status'], att['hours'])

                gross = days * (lab['daily_wage'] or 0)
                open_balance = conn.execute(
                    "SELECT COALESCE(SUM(amount - recovered), 0) AS bal "
                    "FROM advances WHERE labor_id = ? AND status = 'Open'",
                    (labor_id,)).fetchone()['bal']
                deduction = min(max(open_balance, 0), gross)
                net = gross - deduction

                conn.execute(
                    "INSERT INTO payroll (labor_id, month, year, days_present, "
                    "gross_amount, deduction, net_amount, status, "
                    "generated_date) VALUES (?, ?, ?, ?, ?, ?, ?, 'Unpaid', ?)",
                    (labor_id, month, year, days, gross, deduction, net,
                     date.today().isoformat()))
                created += 1
            conn.commit()
        finally:
            conn.close()

        messagebox.showinfo(
            'Payroll generated',
            'Created {} payroll row(s); skipped {} existing.'.format(
                created, skipped))
        self.refresh()

    def mark_paid(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('No selection', 'Select a payroll row.')
            return
        conn = self.db_getter()
        try:
            for iid in sel:
                conn.execute("UPDATE payroll SET status = 'Paid' WHERE id = ?",
                             (int(iid),))
            conn.commit()
        finally:
            conn.close()
        self.refresh()


def build_labor_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(_build_attendance(nb, db_getter), text='Attendance')
    nb.add(_build_advances(nb, db_getter), text='Advances')
    nb.add(PayrollFrame(nb, db_getter), text='Payroll')
    return nb
