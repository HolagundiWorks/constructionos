"""Compliance calendar — the statutory filings the firm owes, and their state.

Generates a financial year's obligations from ``compliance.OBLIGATIONS`` for
whichever regimes the firm has ticked, then lets each one be marked filed with
its acknowledgement number.

Regeneration is **idempotent and non-destructive**: rows are inserted with
``INSERT OR IGNORE`` against a unique (obligation, period) index, so rebuilding
the calendar never disturbs a filing already recorded. That matters because the
natural instinct on seeing a wrong date is to press the rebuild button, and
losing a year of filing history to that would be unforgivable.

Due dates are stored on the row rather than recomputed on read, so a date the
department has extended by notification can be edited in place and stays
edited.
"""

import tkinter as tk
import theme
from datetime import date
from tkinter import ttk, messagebox

from ui_guard import can_write

import bill_export
import compliance
import report_open

# app_settings keys, colon-namespaced per house convention.
_FLAG_KEYS = [
    (compliance.GST, 'compliance:gst', 'GST registered (monthly returns)'),
    (compliance.GST_QRMP, 'compliance:gst_qrmp', 'QRMP scheme (quarterly GSTR-1)'),
    (compliance.GST_COMPOSITION, 'compliance:gst_composition', 'Composition scheme'),
    (compliance.TDS, 'compliance:tds', 'Deducts TDS'),
    (compliance.PF, 'compliance:pf', 'PF registered'),
    (compliance.ESI, 'compliance:esi', 'ESI registered'),
    (compliance.CESS, 'compliance:cess', 'Labour cess (BOCW)'),
    (compliance.INCOME_TAX, 'compliance:income_tax', 'Income tax / advance tax'),
]


def firm_flags(conn):
    """Which regimes the firm has ticked. Absent means not applicable."""
    keys = [k for _f, k, _l in _FLAG_KEYS]
    saved = {r['key']: r['value'] for r in conn.execute(
        'SELECT key, value FROM app_settings WHERE key IN ({})'.format(
            ', '.join(['?'] * len(keys))), keys)}
    return {flag for flag, key, _l in _FLAG_KEYS if saved.get(key) == '1'}


def filing_rows(conn, fy_start=None):
    """Stored filings, newest financial year first, as plain dicts."""
    sql = ('SELECT id, obligation, period, due_date, filed_date, ref_no, '
           'amount, notes FROM compliance_filings')
    rows = [dict(r) for r in conn.execute(sql + ' ORDER BY due_date')]
    for r in rows:
        ob = compliance.BY_KEY.get(r['obligation'], {})
        r['name'] = ob.get('name', r['obligation'])
        r['authority'] = ob.get('authority', '')
    if fy_start is not None:
        lo = '{}-04-01'.format(fy_start)
        hi = '{}-12-31'.format(fy_start + 1)   # annual returns fall after March
        rows = [r for r in rows if lo <= (r['due_date'] or '') <= hi]
    return rows


def open_obligations(conn, as_on=None):
    """Overdue + due-soon counts, for the KPI dashboard."""
    return compliance.summarise(filing_rows(conn), as_on=as_on)


class ComplianceCalendar(ttk.Frame):
    COLUMNS = ('id', 'due_date', 'name', 'period', 'status', 'filed_date',
               'ref_no')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self._rows = []
        self.fy_var = tk.StringVar()
        self.headline_var = tk.StringVar()
        self.note_var = tk.StringVar()
        self.flag_vars = {}
        self._build_ui()
        self.reload()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Financial year starting April').pack(side='left')
        self.fy_combo = ttk.Combobox(top, textvariable=self.fy_var, width=8,
                                     state='readonly')
        this_fy = compliance.current_fy()
        self.fy_combo['values'] = [str(y) for y in
                                   range(this_fy - 2, this_fy + 3)]
        self.fy_var.set(str(this_fy))
        self.fy_combo.pack(side='left', padx=6)
        self.fy_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Button(top, text='Build / Update Calendar',
                   command=self.generate).pack(side='left', padx=6)
        ttk.Button(top, text='Mark Filed',
                   command=self.mark_filed).pack(side='left', padx=3)
        ttk.Button(top, text='Print / Export',
                   command=self.export).pack(side='left', padx=3)

        flags = ttk.LabelFrame(self, text='What applies to this firm')
        flags.pack(fill='x', padx=8, pady=4)
        for idx, (flag, key, label) in enumerate(_FLAG_KEYS):
            var = tk.BooleanVar()
            self.flag_vars[key] = var
            ttk.Checkbutton(flags, text=label, variable=var,
                            command=self.save_flags).grid(
                row=idx // 4, column=idx % 4, padx=8, pady=3, sticky='w')

        ttk.Label(self, textvariable=self.headline_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10)

        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        headings = {'id': 'ID', 'due_date': 'Due', 'name': 'Filing',
                    'period': 'Period', 'status': 'Status',
                    'filed_date': 'Filed On', 'ref_no': 'ARN / Challan'}
        for col in self.COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=50 if col == 'id' else
                             (240 if col == 'name' else 110), anchor='w')
        self.tree.tag_configure('overdue', background=theme.wash('bad'))
        self.tree.tag_configure('due', background=theme.wash('warn'))
        self.tree.tag_configure('filed', background=theme.wash('good'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        ttk.Label(self, textvariable=self.note_var, foreground='#555',
                  wraplength=900, justify='left').pack(anchor='w', padx=10)
        ttk.Label(self, text=(
            'Dates shown are the standard statutory dates. The government '
            'extends them by notification and state rules differ — check the '
            'portal before relying on a date, and edit the row if it has '
            'moved. No late fee or interest is calculated here; those rates '
            'change too often to quote a figure you could act on.'),
            foreground='#8a5a00', wraplength=900, justify='left') \
            .pack(anchor='w', padx=10, pady=(2, 8))

    # ------------------------------------------------------------- flags
    def reload(self):
        conn = self.db_getter()
        try:
            saved = {r['key']: r['value'] for r in conn.execute(
                "SELECT key, value FROM app_settings "
                "WHERE key LIKE 'compliance:%'")}
        finally:
            conn.close()
        for key, var in self.flag_vars.items():
            var.set(saved.get(key) == '1')
        self.refresh()

    def save_flags(self):
        if not can_write():
            return
        conn = self.db_getter()
        try:
            for key, var in self.flag_vars.items():
                conn.execute(
                    'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                    'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                    (key, '1' if var.get() else '0'))
            conn.commit()
        finally:
            conn.close()

    def _flags(self):
        return {flag for flag, key, _l in _FLAG_KEYS
                if self.flag_vars[key].get()}

    def _fy(self):
        try:
            return int(self.fy_var.get())
        except ValueError:
            return compliance.current_fy()

    # -------------------------------------------------------- generation
    def generate(self):
        """Add any missing rows for the year. Never touches existing ones."""
        if not can_write():
            return
        flags = self._flags()
        if not flags:
            messagebox.showinfo(
                'Nothing ticked',
                'Tick what applies to this firm first — a calendar full of '
                'obligations you do not have is one nobody reads.')
            return
        rows = compliance.calendar_for_fy(self._fy(), flags)
        conn = self.db_getter()
        try:
            before = conn.execute(
                'SELECT COUNT(*) FROM compliance_filings').fetchone()[0]
            conn.executemany(
                'INSERT OR IGNORE INTO compliance_filings '
                '(obligation, period, due_date, notes) VALUES (?, ?, ?, ?)',
                [(r['obligation'], r['period'], r['due_date'], r['note'])
                 for r in rows])
            conn.commit()
            after = conn.execute(
                'SELECT COUNT(*) FROM compliance_filings').fetchone()[0]
        finally:
            conn.close()
        self.refresh()
        messagebox.showinfo(
            'Calendar updated',
            '{} filing(s) added for {}. Existing rows and anything already '
            'marked filed were left untouched.'.format(
                after - before, compliance.fy_label(self._fy())))

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = self.db_getter()
        try:
            self._rows = filing_rows(conn, self._fy())
        finally:
            conn.close()

        today = date.today().isoformat()
        for r in self._rows:
            state = compliance.status(r['due_date'], r['filed_date'],
                                      as_on=today)
            tag = ('filed' if state == compliance.FILED else
                   'overdue' if state == compliance.OVERDUE else
                   'due' if state == compliance.DUE else '')
            label = state
            if state == compliance.OVERDUE:
                late = compliance.days_late(r['due_date'], as_on=today)
                label = '{} by {} day{}'.format(state, late,
                                                '' if late == 1 else 's')
            r['status'] = label
            self.tree.insert('', 'end', iid=str(r['id']), tags=(tag,), values=(
                r['id'], r['due_date'] or '-', r['name'], r['period'],
                label, r['filed_date'] or '-', r['ref_no'] or '-'))

        s = compliance.summarise(self._rows)
        if not self._rows:
            self.headline_var.set(
                'No calendar yet for {} — tick what applies and press Build.'
                .format(compliance.fy_label(self._fy())))
        elif s['overdue']:
            self.headline_var.set(
                '{} filing(s) OVERDUE, worst by {} days.   {} due in the next '
                '30 days.   {} of {} filed.'.format(
                    s['overdue'], s['max_days_late'], s['due_soon'],
                    s['filed'], s['total']))
        else:
            nxt = s['next']
            self.headline_var.set(
                'Nothing overdue.   {} due in the next 30 days.{}   {} of {} '
                'filed.'.format(
                    s['due_soon'],
                    '   Next: {} on {}.'.format(nxt['name'], nxt['due_date'])
                    if nxt else '',
                    s['filed'], s['total']))
        self.note_var.set('')

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        row = next((r for r in self._rows if r['id'] == self.selected_id), None)
        self.note_var.set((row or {}).get('notes') or '')

    # ------------------------------------------------------------ filing
    def mark_filed(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a filing.')
            return
        row = next((r for r in self._rows if r['id'] == self.selected_id), None)
        if row is None:
            return

        win = tk.Toplevel(self)
        win.title('Mark filed — {}'.format(row['name']))
        win.transient(self.winfo_toplevel())
        win.grab_set()
        filed = tk.StringVar(value=row['filed_date'] or date.today().isoformat())
        ref = tk.StringVar(value=row['ref_no'] or '')
        amount = tk.StringVar(value='{:g}'.format(row['amount'] or 0))
        due = tk.StringVar(value=row['due_date'] or '')

        ttk.Label(win, text='{}   ({})'.format(row['name'], row['period']),
                  font=('TkDefaultFont', 10, 'bold')).grid(
            row=0, column=0, columnspan=2, padx=10, pady=(10, 4), sticky='w')
        for idx, (label, var) in enumerate(
                [('Due date', due), ('Filed on', filed),
                 ('ARN / Challan no', ref), ('Amount paid', amount)], start=1):
            ttk.Label(win, text=label, width=16).grid(
                row=idx, column=0, padx=10, pady=3, sticky='w')
            ttk.Entry(win, textvariable=var, width=24).grid(
                row=idx, column=1, padx=10, pady=3, sticky='w')
        ttk.Label(win, text=('Due date is editable — if the department '
                             'extended it by notification, correct it here.'),
                  foreground='#555', wraplength=320, justify='left').grid(
            row=5, column=0, columnspan=2, padx=10, pady=(2, 6), sticky='w')

        def save():
            # Guarded here as well as at mark_filed: the dialog outlives the
            # call that opened it, so the check belongs where the write is.
            if not can_write():
                return
            try:
                amt = float(amount.get().strip() or 0)
            except ValueError:
                messagebox.showerror('Invalid amount', 'Amount must be a number.')
                return
            conn = self.db_getter()
            try:
                conn.execute(
                    'UPDATE compliance_filings SET filed_date = ?, ref_no = ?, '
                    'amount = ?, due_date = ? WHERE id = ?',
                    (filed.get().strip() or None, ref.get().strip(), amt,
                     due.get().strip() or None, self.selected_id))
                conn.commit()
            finally:
                conn.close()
            win.destroy()
            self.refresh()

        def clear():
            """Undo a filing recorded by mistake."""
            if not can_write():
                return
            conn = self.db_getter()
            try:
                conn.execute('UPDATE compliance_filings SET filed_date = NULL '
                             'WHERE id = ?', (self.selected_id,))
                conn.commit()
            finally:
                conn.close()
            win.destroy()
            self.refresh()

        btns = ttk.Frame(win)
        btns.grid(row=6, column=0, columnspan=2, padx=10, pady=(4, 10),
                  sticky='w')
        ttk.Button(btns, text='Save', command=save).pack(side='left', padx=3)
        ttk.Button(btns, text='Not filed', command=clear).pack(side='left', padx=3)
        ttk.Button(btns, text='Cancel',
                   command=win.destroy).pack(side='left', padx=3)

    def export(self):
        if not self._rows:
            messagebox.showinfo('Nothing to export', 'Build the calendar first.')
            return
        s = compliance.summarise(self._rows)
        rows = [(r['due_date'] or '-', r['name'], r['authority'], r['period'],
                 r['status'], r['filed_date'] or '-', r['ref_no'] or '-')
                for r in self._rows]
        html = bill_export.build_statement_html(
            'Compliance calendar — {}'.format(
                compliance.fy_label(self._fy())),
            [self.headline_var.get(),
             'Standard statutory dates. Extensions notified by the department '
             'override these; no late fee or interest is computed.'],
            ['Due', 'Filing', 'Authority', 'Period', 'Status', 'Filed On',
             'ARN / Challan'],
            rows, summary='{} of {} filed, {} overdue.'.format(
                s['filed'], s['total'], s['overdue']))
        report_open.save_and_open_html(html, 'compliance_calendar.html')


def build_compliance_tab(parent, db_getter):
    return ComplianceCalendar(parent, db_getter)
