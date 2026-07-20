"""Muster roll, weekly wage payout, and thekedar (labour-contractor) ledger.

How a real T2/T3 site runs its labour:

- **Muster Roll** — mark the whole gang Present/Absent/Half/OT for one date in
  one screen; writes to the existing ``attendance`` table (one row per
  labourer per day, replacing any existing mark for that day).
- **Weekly Payout** — from the muster, compute each labourer's days, gross,
  advance deduction, and net for a 7-day week (``wages`` maths), print a payout
  sheet, and optionally **record the nets as cash Payments** so they flow into
  the cash book automatically.
- **Thekedars** — labour contractors as parties: a master plus a running-balance
  ledger (Work owed vs Paid).
"""

import os
import webbrowser
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ui_guard import can_write

import wages
import muster
import money as m
import bill_export
from crud_frame import CrudFrame, Field
from tab_masters import site_options


STATUS_OPTIONS = ['Present', 'Half Day', 'Overtime', 'Absent']


def _save_and_open_html(html, default_name):
    path = filedialog.asksaveasfilename(
        title='Save', defaultextension='.html', initialfile=default_name,
        filetypes=[('HTML document', '*.html'), ('All files', '*.*')])
    if not path:
        return
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    webbrowser.open('file://' + os.path.abspath(path))


def _company_name(conn):
    """Firm name from app_settings (Tools > Firm Details), for printouts."""
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'company_name'").fetchone()
    return (row['value'] if row and row['value'] else '') or 'Construction OS'


def _recover_advances(conn, labor_id, amount):
    """Mark ``amount`` of a labourer's open advances as recovered (FIFO).

    Closes an advance once fully recovered. Because the open-balance query uses
    ``amount - recovered`` for ``status='Open'`` advances, recovering here stops
    the same advance being deducted again in a later payout. DB-only, testable.
    """
    remaining = round(float(amount or 0), 2)
    if remaining <= 0:
        return
    advances = conn.execute(
        "SELECT id, amount, recovered FROM advances "
        "WHERE labor_id = ? AND status = 'Open' ORDER BY adv_date, id",
        (labor_id,)).fetchall()
    for adv in advances:
        if remaining <= 0:
            break
        outstanding = round((adv['amount'] or 0) - (adv['recovered'] or 0), 2)
        if outstanding <= 0:
            continue
        take = min(outstanding, remaining)
        new_recovered = round((adv['recovered'] or 0) + take, 2)
        status = 'Closed' if new_recovered >= (adv['amount'] or 0) - 1e-6 else 'Open'
        conn.execute('UPDATE advances SET recovered = ?, status = ? WHERE id = ?',
                     (new_recovered, status, adv['id']))
        remaining = round(remaining - take, 2)


def _fill_sites(combo, mapping, conn, include_all=False):
    opts = site_options(conn)
    mapping.clear()
    mapping.update({'{} - {}'.format(i, n): i for i, n in opts})
    vals = ['{} - {}'.format(i, n) for i, n in opts]
    combo['values'] = (['All'] + vals) if include_all else vals


# ============================================================ Muster Roll
class MusterRollFrame(ttk.Frame):
    COLUMNS = ('labor_id', 'name', 'skill', 'wage', 'status', 'hours')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._site_map = {}
        self.site_var = tk.StringVar()
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.status_var = tk.StringVar(value='Present')
        self.hours_var = tk.StringVar(value='8')
        self._build_ui()
        self.reload_sites()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Site').pack(side='left')
        self.site_combo = ttk.Combobox(top, textvariable=self.site_var, width=22,
                                       state='readonly')
        self.site_combo.pack(side='left', padx=4)
        ttk.Label(top, text='Date').pack(side='left')
        ttk.Entry(top, textvariable=self.date_var, width=12).pack(side='left', padx=4)
        ttk.Button(top, text='Load', command=self.load).pack(side='left', padx=6)

        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings', height=12)
        heads = {'labor_id': 'ID', 'name': 'Name', 'skill': 'Skill',
                 'wage': 'Daily Wage', 'status': 'Status', 'hours': 'Hours'}
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=60 if col in ('labor_id', 'hours') else 130,
                             anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        form = ttk.LabelFrame(self, text='Mark'); form.pack(fill='x', padx=8, pady=4)
        ttk.Label(form, text='Status').pack(side='left', padx=(6, 2))
        ttk.Combobox(form, textvariable=self.status_var, width=12, state='readonly',
                     values=STATUS_OPTIONS).pack(side='left', padx=2)
        ttk.Label(form, text='Hours').pack(side='left', padx=(6, 2))
        ttk.Entry(form, textvariable=self.hours_var, width=6).pack(side='left', padx=2)
        ttk.Button(form, text='Apply to Selected', command=self.apply_selected).pack(side='left', padx=6)
        ttk.Button(form, text='All Present', command=lambda: self.mark_all('Present')).pack(side='left', padx=3)
        ttk.Button(form, text='All Absent', command=lambda: self.mark_all('Absent')).pack(side='left', padx=3)

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btns, text='Save Muster', command=self.save).pack(side='left', padx=3)

    def reload_sites(self):
        conn = self.db_getter()
        try:
            _fill_sites(self.site_combo, self._site_map, conn)
        finally:
            conn.close()

    def _site_id(self):
        raw = self.site_var.get().strip()
        if not raw:
            return None
        return self._site_map.get(raw, raw.split(' - ')[0])

    def load(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        site_id = self._site_id()
        if site_id is None:
            messagebox.showinfo('No site', 'Select a site.')
            return
        day = self.date_var.get().strip()
        conn = self.db_getter()
        try:
            labour = conn.execute(
                "SELECT id, name, skill, daily_wage FROM labor "
                "WHERE status = 'Active' AND site_id = ? ORDER BY name",
                (site_id,)).fetchall()
            existing = {r['labor_id']: (r['status'], r['hours']) for r in conn.execute(
                'SELECT labor_id, status, hours FROM attendance WHERE att_date = ?',
                (day,))}
        finally:
            conn.close()
        if not labour:
            messagebox.showinfo('No labour',
                                'No active labour is assigned to this site.')
            return
        for lab in labour:
            status, hours = existing.get(lab['id'], ('Present', 8))
            self.tree.insert('', 'end', iid=str(lab['id']), values=(
                lab['id'], lab['name'], lab['skill'] or '',
                '{:.2f}'.format(lab['daily_wage'] or 0), status, hours))

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], 'values')
        self.status_var.set(vals[4]); self.hours_var.set(vals[5])

    def apply_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('No selection', 'Select a labour row.')
            return
        for iid in sel:
            vals = list(self.tree.item(iid, 'values'))
            vals[4] = self.status_var.get()
            vals[5] = self.hours_var.get()
            self.tree.item(iid, values=vals)

    def mark_all(self, status):
        for iid in self.tree.get_children():
            vals = list(self.tree.item(iid, 'values'))
            vals[4] = status
            self.tree.item(iid, values=vals)

    def save(self):
        if not can_write():
            return
        rows = self.tree.get_children()
        if not rows:
            messagebox.showinfo('Nothing to save', 'Load a site first.')
            return
        day = self.date_var.get().strip()
        conn = self.db_getter()
        try:
            for iid in rows:
                vals = self.tree.item(iid, 'values')
                labor_id = int(vals[0])
                status = vals[4]
                try:
                    hours = float(vals[5] or 0)
                except ValueError:
                    hours = 8.0
                # One mark per labourer per day: replace any existing row.
                conn.execute('DELETE FROM attendance WHERE labor_id = ? AND att_date = ?',
                             (labor_id, day))
                conn.execute(
                    'INSERT INTO attendance (labor_id, att_date, status, hours) '
                    'VALUES (?, ?, ?, ?)', (labor_id, day, status, hours))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo('Saved', 'Muster saved for {}.'.format(day))


# ============================================================ Weekly Payout
class WeeklyPayoutFrame(ttk.Frame):
    COLUMNS = ('labor_id', 'name', 'days', 'gross', 'deduction', 'net')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._site_map = {}
        self.site_var = tk.StringVar()
        self.start_var = tk.StringVar(value=date.today().isoformat())
        self._rows = []
        self._period = ('', '')
        self._build_ui()
        self.reload_sites()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Site').pack(side='left')
        self.site_combo = ttk.Combobox(top, textvariable=self.site_var, width=22,
                                       state='readonly')
        self.site_combo.pack(side='left', padx=4)
        ttk.Label(top, text='Week Start').pack(side='left')
        ttk.Entry(top, textvariable=self.start_var, width=12).pack(side='left', padx=4)
        ttk.Button(top, text='Compute (7 days)', command=self.compute).pack(side='left', padx=6)

        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings', height=11)
        heads = {'labor_id': 'ID', 'name': 'Name', 'days': 'Days',
                 'gross': 'Gross', 'deduction': 'Adv. Deduct', 'net': 'Net Pay'}
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=60 if col in ('labor_id', 'days') else 130,
                             anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=4)

        btns = ttk.Frame(self); btns.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(btns, text='Export Payout Sheet', command=self.export).pack(side='left', padx=3)
        ttk.Button(btns, text='Muster Roll (Form 21)',
                   command=self.export_muster_roll).pack(side='left', padx=3)
        ttk.Button(btns, text='Unpaid Wages (Form 21A)',
                   command=self.export_unpaid).pack(side='left', padx=3)
        ttk.Button(btns, text='Record as Payments', command=self.record_payments).pack(side='left', padx=3)

    def reload_sites(self):
        conn = self.db_getter()
        try:
            _fill_sites(self.site_combo, self._site_map, conn)
        finally:
            conn.close()

    def _site_id(self):
        raw = self.site_var.get().strip()
        if not raw:
            return None
        return self._site_map.get(raw, raw.split(' - ')[0])

    def compute(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        site_id = self._site_id()
        if site_id is None:
            messagebox.showinfo('No site', 'Select a site.')
            return
        try:
            start = datetime.strptime(self.start_var.get().strip(), '%Y-%m-%d')
        except ValueError:
            messagebox.showerror('Invalid date', 'Week start must be YYYY-MM-DD.')
            return
        end = start + timedelta(days=6)
        s, e = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
        self._period = (s, e)

        conn = self.db_getter()
        try:
            labour = conn.execute(
                "SELECT id, name, daily_wage FROM labor "
                "WHERE status = 'Active' AND site_id = ? ORDER BY name",
                (site_id,)).fetchall()
            for lab in labour:
                atts = conn.execute(
                    'SELECT status, hours FROM attendance WHERE labor_id = ? '
                    'AND att_date BETWEEN ? AND ?', (lab['id'], s, e)).fetchall()
                days = round(sum(wages.day_fraction(a['status'], a['hours'])
                                 for a in atts), 2)
                adv = conn.execute(
                    "SELECT COALESCE(SUM(amount - recovered), 0) AS b FROM advances "
                    "WHERE labor_id = ? AND status = 'Open'", (lab['id'],)).fetchone()['b']
                w = wages.wage_net(days, lab['daily_wage'], adv)
                if days == 0 and w['net'] == 0:
                    continue
                self._rows.append({'labor_id': lab['id'], 'name': lab['name'],
                                   'days': days, **w})
        finally:
            conn.close()

        total = 0.0
        for r in self._rows:
            total += r['net']
            self.tree.insert('', 'end', values=(
                r['labor_id'], r['name'], '{:.2f}'.format(r['days']),
                '{:.2f}'.format(r['gross']), '{:.2f}'.format(r['deduction']),
                '{:.2f}'.format(r['net'])))
        self.summary_var.set('Week {} to {}   —   total net payout {:.2f}'.format(
            s, e, round(total, 2)))

    def export(self):
        if not self._rows:
            messagebox.showinfo('Nothing to export', 'Compute a week first.')
            return
        rows = [(r['name'], '{:.2f}'.format(r['days']), '{:.2f}'.format(r['gross']),
                 '{:.2f}'.format(r['deduction']), '{:.2f}'.format(r['net']))
                for r in self._rows]
        html = bill_export.build_statement_html(
            'Weekly Wage Payout',
            ['Site: {}'.format(self.site_var.get()),
             'Week: {} to {}'.format(*self._period)],
            ['Name', 'Days', 'Gross', 'Adv. Deduct', 'Net Pay'],
            rows, summary=self.summary_var.get())
        _save_and_open_html(html, 'weekly_payout.html')

    # ---------------------------------------------------- Form 21 / 21A
    def _roll_context(self, conn, site_id, start, end):
        """Everything the Form 21 documents need for one wage period.

        Unlike ``compute``, this keeps workers with no attendance: the muster
        roll is the record of who was *on the books* for the period, and
        dropping a zero-day worker would hide someone who should have been
        marked. ``compute`` is about who to pay, which is a different question.
        """
        labour = conn.execute(
            "SELECT id, name, father_name, skill, daily_wage FROM labor "
            "WHERE status = 'Active' AND site_id = ? ORDER BY name",
            (site_id,)).fetchall()
        atts = conn.execute(
            'SELECT a.labor_id, a.att_date, a.status, a.hours FROM attendance a '
            'JOIN labor l ON l.id = a.labor_id '
            'WHERE l.site_id = ? AND a.att_date BETWEEN ? AND ?',
            (site_id, start, end)).fetchall()
        advances = {r['labor_id']: r['b'] for r in conn.execute(
            "SELECT labor_id, COALESCE(SUM(amount - recovered), 0) AS b "
            "FROM advances WHERE status = 'Open' GROUP BY labor_id")}
        lines = muster.roll_lines(labour, atts, start, end, advances)

        # Value of work measured on this site in the same period — Part II.
        measured = conn.execute(
            'SELECT COALESCE(SUM(m.quantity * b.rate), 0) AS v '
            'FROM measurements m '
            'JOIN boq_items b ON b.id = m.boq_item_id '
            'JOIN contracts c ON c.id = m.contract_id '
            'WHERE c.site_id = ? AND m.mb_date BETWEEN ? AND ?',
            (site_id, start, end)).fetchone()['v']

        narration = 'Wages {} to {}'.format(start, end)
        paid_ids = [r['party_id'] for r in conn.execute(
            "SELECT party_id FROM payments WHERE party_type = 'Labour' "
            "AND narration = ?", (narration,))]
        return lines, measured, paid_ids

    def _period_or_warn(self):
        if not self._rows and not self._period:
            messagebox.showinfo('No period', 'Compute a week first.')
            return None
        return self._period

    def export_muster_roll(self):
        """Print the muster roll in CPWA Form 21 shape."""
        period = self._period_or_warn()
        site_id = self._site_id()
        if period is None or site_id is None:
            if site_id is None:
                messagebox.showinfo('No site', 'Select a site.')
            return
        s, e = period
        conn = self.db_getter()
        try:
            lines, measured, _paid = self._roll_context(conn, site_id, s, e)
            company = _company_name(conn)
        finally:
            conn.close()
        total = muster.summarise_roll(lines)
        html = bill_export.build_muster_roll_html(
            lines, muster.period_dates(s, e), s, e,
            site_name=self.site_var.get(), company_name=company,
            reconciliation=muster.work_reconciliation(total['gross'], measured))
        _save_and_open_html(html, 'muster_roll_{}.html'.format(s))

    def export_unpaid(self):
        """Register of Unpaid Wages (Form 21A) for the computed period."""
        period = self._period_or_warn()
        site_id = self._site_id()
        if period is None or site_id is None:
            if site_id is None:
                messagebox.showinfo('No site', 'Select a site.')
            return
        s, e = period
        conn = self.db_getter()
        try:
            lines, _measured, paid_ids = self._roll_context(conn, site_id, s, e)
            company = _company_name(conn)
        finally:
            conn.close()
        unpaid = muster.unpaid_lines(lines, paid_ids)
        html = bill_export.build_unpaid_wages_html(
            unpaid, s, e, site_name=self.site_var.get(), company_name=company)
        _save_and_open_html(html, 'unpaid_wages_{}.html'.format(s))

    def record_payments(self):
        if not can_write():
            return
        if not self._rows:
            messagebox.showinfo('Nothing to record', 'Compute a week first.')
            return
        payable = [r for r in self._rows if r['net'] > 0]
        if not payable:
            messagebox.showinfo('Nothing to pay', 'No positive net pay to record.')
            return
        if not messagebox.askyesno(
                'Record payments',
                'Record {} cash wage payment(s) totalling {:.2f} into the cash '
                'book?'.format(len(payable), round(sum(r['net'] for r in payable), 2))):
            return
        site_id = self._site_id()
        s, e = self._period
        narration = 'Wages {} to {}'.format(s, e)
        recorded = skipped = 0
        conn = self.db_getter()
        try:
            for r in payable:
                # Idempotent: don't double-record the same labourer's week.
                exists = conn.execute(
                    "SELECT 1 FROM payments WHERE party_type='Labour' "
                    "AND party_id=? AND narration=? LIMIT 1",
                    (r['labor_id'], narration)).fetchone()
                if exists:
                    skipped += 1
                    continue
                conn.execute(
                    "INSERT INTO payments (pay_date, direction, party_type, "
                    "party_id, party_name, mode, amount, site_id, narration) "
                    "VALUES (?, 'Payment', 'Labour', ?, ?, 'Cash', ?, ?, ?)",
                    (e, r['labor_id'], r['name'], r['net'], site_id, narration))
                # Mark the deducted advance as recovered so it isn't taken again.
                _recover_advances(conn, r['labor_id'], r['deduction'])
                recorded += 1
            conn.commit()
        finally:
            conn.close()
        self.compute()   # reflect the now-recovered advances
        messagebox.showinfo(
            'Recorded',
            'Recorded {} wage payment(s) in Money > Cash Book; skipped {} '
            'already recorded. Advance deductions marked recovered.'.format(
                recorded, skipped))


# ============================================================ Thekedar ledger
def _build_thekedars(parent, db_getter):
    fields = [
        Field('name', 'Name'),
        Field('phone', 'Phone'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('skill_type', 'Skill/Trade'),
        Field('status', 'Status', kind='combo',
              options=['Active', 'Inactive'], default='Active'),
    ]
    return CrudFrame(parent, db_getter, 'thekedars', fields,
                     'Thekedars (Labour Contractors)')


class ThekedarLedgerFrame(ttk.Frame):
    COLUMNS = ('date', 'type', 'particulars', 'work', 'paid', 'balance')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._map = {}
        self.thekedar_var = tk.StringVar()
        self.v = {'entry_date': tk.StringVar(value=date.today().isoformat()),
                  'entry_type': tk.StringVar(value='Work'),
                  'description': tk.StringVar(), 'amount': tk.StringVar(value='0'),
                  'remarks': tk.StringVar()}
        self._export_rows = []
        self._build_ui()
        self.reload()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Thekedar').pack(side='left')
        self.combo = ttk.Combobox(top, textvariable=self.thekedar_var, width=24,
                                  state='readonly')
        self.combo.pack(side='left', padx=4)
        self.combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Button(top, text='Refresh', command=self.reload).pack(side='left', padx=4)
        ttk.Button(top, text='Print / Export', command=self.export).pack(side='left', padx=4)

        self.summary_var = tk.StringVar(value='Select a thekedar.')
        ttk.Label(self, textvariable=self.summary_var,
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', padx=8, pady=4)

        heads = {'date': 'Date', 'type': 'Type', 'particulars': 'Particulars',
                 'work': 'Work (owed)', 'paid': 'Paid', 'balance': 'Balance'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=180 if col == 'particulars' else 100, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        form = ttk.LabelFrame(self, text='Add Entry'); form.pack(fill='x', padx=8, pady=4)
        ttk.Label(form, text='Date').pack(side='left', padx=(6, 2))
        ttk.Entry(form, textvariable=self.v['entry_date'], width=11).pack(side='left', padx=2)
        ttk.Label(form, text='Type').pack(side='left', padx=(6, 2))
        ttk.Combobox(form, textvariable=self.v['entry_type'], width=8, state='readonly',
                     values=['Work', 'Paid']).pack(side='left', padx=2)
        ttk.Label(form, text='Particulars').pack(side='left', padx=(6, 2))
        ttk.Entry(form, textvariable=self.v['description'], width=18).pack(side='left', padx=2)
        ttk.Label(form, text='Amount').pack(side='left', padx=(6, 2))
        ttk.Entry(form, textvariable=self.v['amount'], width=10).pack(side='left', padx=2)
        ttk.Button(form, text='Add', command=self.add_entry).pack(side='left', padx=6)
        ttk.Button(form, text='Delete Selected', command=self.delete_entry).pack(side='left', padx=3)

    def reload(self):
        conn = self.db_getter()
        try:
            opts = [(r['id'], r['name']) for r in conn.execute(
                'SELECT id, name FROM thekedars ORDER BY name')]
        finally:
            conn.close()
        self._map = {'{} - {}'.format(i, n): i for i, n in opts}
        self.combo['values'] = list(self._map.keys())
        self.refresh()

    def _thekedar_id(self):
        raw = self.thekedar_var.get().strip()
        if not raw:
            return None
        return self._map.get(raw, raw.split(' - ')[0])

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._export_rows = []
        tid = self._thekedar_id()
        if tid is None:
            self.summary_var.set('Select a thekedar.')
            return
        conn = self.db_getter()
        try:
            entries = conn.execute(
                'SELECT id, entry_date, entry_type, description, amount '
                'FROM thekedar_entries WHERE thekedar_id = ? ORDER BY entry_date, id',
                (tid,)).fetchall()
        finally:
            conn.close()
        signed = [(e['amount'] if e['entry_type'] == 'Work' else -e['amount'])
                  for e in entries]
        balances = m.running_balance(signed)
        for e, bal in zip(entries, balances):
            work = e['amount'] if e['entry_type'] == 'Work' else 0
            paid = e['amount'] if e['entry_type'] == 'Paid' else 0
            row = (e['entry_date'], e['entry_type'], e['description'] or '',
                   '{:.2f}'.format(work) if work else '',
                   '{:.2f}'.format(paid) if paid else '', '{:.2f}'.format(bal))
            self.tree.insert('', 'end', iid=str(e['id']), values=row)
            self._export_rows.append(row)
        bal = balances[-1] if balances else 0.0
        self.summary_var.set('{}:  we owe thekedar {:.2f}'.format(
            self.thekedar_var.get().split(' - ', 1)[-1], bal))

    def add_entry(self):
        if not can_write():
            return
        tid = self._thekedar_id()
        if tid is None:
            messagebox.showinfo('No thekedar', 'Select a thekedar.')
            return
        try:
            amount = float(self.v['amount'].get().strip() or 0)
        except ValueError:
            messagebox.showerror('Invalid amount', 'Amount must be a number.')
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO thekedar_entries (thekedar_id, entry_date, '
                'entry_type, description, amount) VALUES (?, ?, ?, ?, ?)',
                (tid, self.v['entry_date'].get().strip(), self.v['entry_type'].get(),
                 self.v['description'].get().strip(), amount))
            conn.commit()
        finally:
            conn.close()
        self.v['description'].set(''); self.v['amount'].set('0')
        self.refresh()

    def delete_entry(self):
        if not can_write():
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('No selection', 'Select an entry to delete.')
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM thekedar_entries WHERE id = ?', (int(sel[0]),))
            conn.commit()
        finally:
            conn.close()
        self.refresh()

    def export(self):
        if not self._export_rows:
            messagebox.showinfo('Nothing to export', 'Select a thekedar first.')
            return
        html = bill_export.build_statement_html(
            'Thekedar Ledger — {}'.format(self.thekedar_var.get().split(' - ', 1)[-1]),
            ['As on today'],
            ['Date', 'Type', 'Particulars', 'Work (owed)', 'Paid', 'Balance'],
            self._export_rows, summary=self.summary_var.get())
        _save_and_open_html(html, 'thekedar_ledger.html')


def build_muster_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(MusterRollFrame(nb, db_getter), text='Muster Roll')
    nb.add(WeeklyPayoutFrame(nb, db_getter), text='Weekly Payout')
    nb.add(_build_thekedars(nb, db_getter), text='Thekedars')
    nb.add(ThekedarLedgerFrame(nb, db_getter), text='Thekedar Ledger')
    from tab_statutory import StatutoryCalculator
    nb.add(StatutoryCalculator(nb, db_getter), text='Statutory')
    return nb
