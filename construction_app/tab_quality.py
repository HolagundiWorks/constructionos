"""Quality gates: ITP checklists, inspections and non-conformances (Wave 3).

Three views:

* **ITP Checklist** — the template. Per activity and stage, the checks to be
  made, each marked Hold, Witness or Record.
* **Inspections** — an actual inspection of an element. Pull the checklist in
  for the activity, mark each line, and the screen answers the only question
  that matters on site: **may the work proceed?** An outstanding Hold point
  blocks even though nothing has failed, because unrecorded is exactly how an
  inspection gets skipped.
* **NCR Log** — non-conformances with root cause, corrective and preventive
  action. The headline is how long the oldest open one has been sitting.

The inspection's own result is derived from its lines, never typed, so it
cannot disagree with the evidence beneath it.
"""

import tkinter as tk
from datetime import date
from tkinter import ttk, messagebox

import bill_export
import quality
import report_open
from crud_frame import CrudFrame, Field
from tab_masters import site_options
from ui_guard import can_write


def build_itp_template(parent, db_getter):
    fields = [
        Field('activity', 'Activity'),
        Field('stage', 'Stage'),
        Field('description', 'Check'),
        Field('check_type', 'Type', kind='combo', options=quality.CHECK_TYPES,
              default=quality.HOLD),
        Field('reference', 'IS code / spec'),
        Field('sort_order', 'Order', kind='number', default='0'),
    ]
    return CrudFrame(parent, db_getter, 'itp_items', fields,
                     'ITP checklist — Hold stops work, Witness invites, '
                     'Record files evidence', order_by='activity, sort_order, id')


def build_ncr_log(parent, db_getter):
    fields = [
        Field('ncr_no', 'NCR No'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('raised_date', 'Raised', default='TODAY'),
        Field('raised_by', 'Raised By'),
        Field('description', 'Non-conformance'),
        Field('severity', 'Severity', kind='combo',
              options=['Minor', 'Major', 'Critical'], default='Minor'),
        Field('root_cause', 'Root cause'),
        Field('corrective_action', 'Corrective action'),
        Field('preventive_action', 'Preventive action'),
        Field('status', 'Status', kind='combo',
              options=[quality.OPEN, quality.CLOSED], default=quality.OPEN),
        Field('closed_date', 'Closed on'),
        Field('closed_by', 'Closed by'),
    ]
    return CrudFrame(parent, db_getter, 'ncrs', fields,
                     'Non-conformance log')


class InspectionFrame(ttk.Frame):
    HEAD = ('id', 'date', 'site', 'activity', 'element', 'stage', 'result')
    ITEMS = ('id', 'description', 'type', 'result', 'checked_by', 'remarks')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self.selected_item = None
        self._site_map = {}
        self.h = {}
        self.gate_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ttk.Label(self, text='Inspections',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 2))
        ttk.Label(self, text='Record the checks before work is covered up. A '
                             'Hold point that is not signed off stops the work '
                             '— that is the point of the plan.',
                  wraplength=700, justify='left', foreground='#555') \
            .pack(anchor='w', padx=8, pady=(0, 6))

        hdr = ttk.LabelFrame(self, text='Inspections')
        hdr.pack(fill='both', expand=True, padx=8, pady=4)
        heads = {'id': 'ID', 'date': 'Date', 'site': 'Site',
                 'activity': 'Activity', 'element': 'Element',
                 'stage': 'Stage', 'result': 'Result'}
        self.tree = ttk.Treeview(hdr, columns=self.HEAD, show='headings', height=6)
        for c in self.HEAD:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=50 if c == 'id' else 115, anchor='w')
        self.tree.tag_configure('fail', background='#ffe3e3')
        self.tree.tag_configure('pass', background='#e4f1e8')
        self.tree.tag_configure('pending', background='#fff4e5')
        self.tree.pack(fill='x', padx=4, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        form = ttk.Frame(hdr); form.pack(fill='x', padx=4, pady=4)
        for key, default in (('activity', ''), ('element', ''), ('stage', ''),
                             ('inspection_date', date.today().isoformat()),
                             ('inspected_by', ''), ('remarks', '')):
            self.h[key] = tk.StringVar(value=default)
        self.h['site'] = tk.StringVar()
        self.h['reinspection'] = tk.StringVar(value='No')
        cell = ttk.Frame(form); cell.grid(row=0, column=0, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text='Site', width=12).pack(side='left')
        self.site_combo = ttk.Combobox(cell, textvariable=self.h['site'],
                                       width=20, state='readonly')
        self.site_combo.pack(side='left')
        self._entry(form, 0, 1, 'Activity', 'activity')
        self._entry(form, 0, 2, 'Element', 'element')
        self._entry(form, 1, 0, 'Stage', 'stage')
        self._entry(form, 1, 1, 'Date', 'inspection_date')
        self._entry(form, 1, 2, 'Inspected By', 'inspected_by')
        cell = ttk.Frame(form); cell.grid(row=2, column=0, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text='Re-inspection', width=12).pack(side='left')
        ttk.Combobox(cell, textvariable=self.h['reinspection'], width=6,
                     state='readonly', values=['No', 'Yes']).pack(side='left')
        self._entry(form, 2, 1, 'Remarks', 'remarks')

        b = ttk.Frame(hdr); b.pack(fill='x', padx=4, pady=4)
        ttk.Button(b, text='New Inspection', command=self.add).pack(side='left', padx=3)
        ttk.Button(b, text='Update', command=self.update).pack(side='left', padx=3)
        ttk.Button(b, text='Load Checklist', command=self.load_checklist).pack(side='left', padx=3)
        ttk.Button(b, text='Delete', command=self.delete).pack(side='left', padx=3)
        ttk.Button(b, text='Export', command=self.export).pack(side='left', padx=3)

        gate = ttk.Frame(self); gate.pack(fill='x', padx=8, pady=(2, 0))
        self.gate_label = ttk.Label(gate, textvariable=self.gate_var,
                                    font=('TkDefaultFont', 12, 'bold'),
                                    wraplength=700, justify='left')
        self.gate_label.pack(anchor='w')

        items = ttk.LabelFrame(self, text='Checks')
        items.pack(fill='both', expand=True, padx=8, pady=4)
        heads2 = {'id': 'ID', 'description': 'Check', 'type': 'Type',
                  'result': 'Result', 'checked_by': 'By', 'remarks': 'Remarks'}
        self.item_tree = ttk.Treeview(items, columns=self.ITEMS,
                                      show='headings', height=8)
        for c in self.ITEMS:
            self.item_tree.heading(c, text=heads2[c])
            self.item_tree.column(c, width=50 if c == 'id' else
                                  (230 if c == 'description' else 100), anchor='w')
        self.item_tree.tag_configure('fail', background='#ffe3e3')
        self.item_tree.tag_configure('hold', background='#fff4e5')
        self.item_tree.pack(fill='both', expand=True, padx=4, pady=4)
        self.item_tree.bind('<<TreeviewSelect>>', self._on_item)

        ib = ttk.Frame(items); ib.pack(fill='x', padx=4, pady=4)
        for label, value in (('Mark Pass', quality.PASS),
                             ('Mark Fail', quality.FAIL),
                             ('Mark N/A', quality.NA)):
            ttk.Button(ib, text=label,
                       command=lambda v=value: self.mark(v)).pack(side='left', padx=3)
        ttk.Button(ib, text='Raise NCR from Fail',
                   command=self.raise_ncr).pack(side='left', padx=12)

    def _entry(self, parent, r, c, label, key):
        cell = ttk.Frame(parent); cell.grid(row=r, column=c, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=12).pack(side='left')
        ttk.Entry(cell, textvariable=self.h[key], width=20).pack(side='left')

    # ------------------------------------------------------------- headers
    def refresh(self):
        conn = self.db_getter()
        try:
            opts = site_options(conn)
            self._site_map = {'{} - {}'.format(i, n): i for i, n in opts}
            self.site_combo['values'] = ['{} - {}'.format(i, n) for i, n in opts]
            for item in self.tree.get_children():
                self.tree.delete(item)
            for r in conn.execute(
                    'SELECT i.id, i.inspection_date, s.name AS site, i.activity, '
                    'i.element, i.stage, i.result FROM inspections i '
                    'LEFT JOIN sites s ON s.id = i.site_id ORDER BY i.id DESC'):
                tag = ('fail' if r['result'] == quality.FAIL else
                       'pass' if r['result'] == quality.PASS else 'pending')
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['inspection_date'] or '-', r['site'] or '-',
                    r['activity'] or '-', r['element'] or '-',
                    r['stage'] or '-', r['result'] or quality.PENDING),
                    tags=(tag,))
        finally:
            conn.close()
        self.refresh_items()

    def _values(self):
        raw = self.h['site'].get().strip()
        return {
            'site_id': self._site_map.get(raw) if raw else None,
            'activity': self.h['activity'].get().strip(),
            'element': self.h['element'].get().strip(),
            'stage': self.h['stage'].get().strip(),
            'inspection_date': self.h['inspection_date'].get().strip(),
            'inspected_by': self.h['inspected_by'].get().strip(),
            'reinspection': 1 if self.h['reinspection'].get() == 'Yes' else 0,
            'remarks': self.h['remarks'].get().strip(),
        }

    def add(self):
        if not can_write():
            return
        v = self._values()
        cols = list(v.keys())
        conn = self.db_getter()
        try:
            conn.execute('INSERT INTO inspections ({}) VALUES ({})'.format(
                ', '.join(cols), ', '.join(['?'] * len(cols))),
                [v[c] for c in cols])
            conn.commit()
        finally:
            conn.close()
        self.refresh()

    def update(self):
        if not can_write() or self.selected_id is None:
            return
        v = self._values()
        cols = list(v.keys())
        conn = self.db_getter()
        try:
            conn.execute('UPDATE inspections SET {} WHERE id = ?'.format(
                ', '.join('{} = ?'.format(c) for c in cols)),
                [v[c] for c in cols] + [self.selected_id])
            conn.commit()
        finally:
            conn.close()
        self.refresh()

    def delete(self):
        if not can_write() or self.selected_id is None:
            return
        if not messagebox.askyesno('Delete', 'Delete this inspection?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM inspections WHERE id = ?', (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_id = None
        self.refresh()

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM inspections WHERE id = ?',
                             (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        for k in ('activity', 'element', 'stage', 'inspection_date',
                  'inspected_by', 'remarks'):
            self.h[k].set(r[k] or '')
        self.h['reinspection'].set('Yes' if r['reinspection'] else 'No')
        for disp, sid in self._site_map.items():
            if str(sid) == str(r['site_id']):
                self.h['site'].set(disp); break
        else:
            self.h['site'].set('')
        self.refresh_items()

    def load_checklist(self):
        """Pull the ITP lines for this activity into the inspection."""
        if not can_write() or self.selected_id is None:
            messagebox.showinfo('No inspection', 'Create the inspection first.')
            return
        activity = self.h['activity'].get().strip()
        stage = self.h['stage'].get().strip()
        conn = self.db_getter()
        try:
            sql = 'SELECT * FROM itp_items WHERE activity = ?'
            args = [activity]
            if stage:
                sql += ' AND (stage = ? OR stage IS NULL OR stage = "")'
                args.append(stage)
            rows = conn.execute(sql + ' ORDER BY sort_order, id', args).fetchall()
            for r in rows:
                conn.execute(
                    'INSERT INTO inspection_items (inspection_id, itp_item_id, '
                    'description, check_type, result) VALUES (?, ?, ?, ?, ?)',
                    (self.selected_id, r['id'], r['description'],
                     r['check_type'], quality.PENDING))
            conn.commit()
        finally:
            conn.close()
        if not rows:
            messagebox.showinfo(
                'No checklist',
                'No ITP lines found for activity "{}". Add them in the ITP '
                'Checklist tab first.'.format(activity))
        self.refresh_items()

    # --------------------------------------------------------------- items
    def refresh_items(self):
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        self.gate_var.set('')
        if self.selected_id is None:
            return
        conn = self.db_getter()
        try:
            rows = conn.execute(
                'SELECT * FROM inspection_items WHERE inspection_id = ? '
                'ORDER BY id', (self.selected_id,)).fetchall()
        finally:
            conn.close()
        for r in rows:
            tag = ('fail' if r['result'] == quality.FAIL else
                   'hold' if (r['check_type'] == quality.HOLD and
                              r['result'] == quality.PENDING) else '')
            self.item_tree.insert('', 'end', iid=str(r['id']), values=(
                r['id'], r['description'] or '-', r['check_type'],
                r['result'] or quality.PENDING, r['checked_by'] or '',
                r['remarks'] or ''), tags=(tag,) if tag else ())
        self._update_gate(rows)

    def _update_gate(self, rows):
        """Derive the inspection result and say whether work may proceed."""
        result = quality.inspection_result(rows)
        allowed, reason = quality.may_proceed(rows)
        conn = self.db_getter()
        try:
            conn.execute('UPDATE inspections SET result = ? WHERE id = ?',
                         (result, self.selected_id))
            conn.commit()
        finally:
            conn.close()
        if not rows:
            self.gate_var.set('No checks loaded — use "Load Checklist".')
            self.gate_label.configure(foreground='#777')
        elif allowed:
            self.gate_var.set('✓ WORK MAY PROCEED — all hold points cleared.')
            self.gate_label.configure(foreground='#2e7d46')
        else:
            self.gate_var.set('✗ DO NOT PROCEED — ' + reason)
            self.gate_label.configure(foreground='#a4343a')

    def _on_item(self, _e=None):
        sel = self.item_tree.selection()
        self.selected_item = int(sel[0]) if sel else None

    def mark(self, result):
        if not can_write():
            return
        if self.selected_item is None:
            messagebox.showinfo('No check', 'Select a check line first.')
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'UPDATE inspection_items SET result = ?, checked_by = ? '
                'WHERE id = ?',
                (result, self.h['inspected_by'].get().strip(), self.selected_item))
            conn.commit()
        finally:
            conn.close()
        self.refresh_items()
        self.refresh()

    def raise_ncr(self):
        """Turn a failed check into a non-conformance, pre-filled."""
        if not can_write() or self.selected_item is None:
            messagebox.showinfo('No check', 'Select the failed check first.')
            return
        conn = self.db_getter()
        try:
            item = conn.execute('SELECT * FROM inspection_items WHERE id = ?',
                                (self.selected_item,)).fetchone()
            insp = conn.execute('SELECT * FROM inspections WHERE id = ?',
                                (self.selected_id,)).fetchone()
            if item is None or item['result'] != quality.FAIL:
                messagebox.showinfo(
                    'Not a failure',
                    'Raise an NCR from a check marked Fail — that is what a '
                    'non-conformance records.')
                return
            existing = [r['ncr_no'] for r in conn.execute('SELECT ncr_no FROM ncrs')]
            import procurement
            ncr_no = procurement.next_doc_no(existing, 'NCR')
            conn.execute(
                'INSERT INTO ncrs (ncr_no, site_id, inspection_id, raised_date, '
                'raised_by, description, severity, status) '
                "VALUES (?, ?, ?, ?, ?, ?, 'Major', 'Open')",
                (ncr_no, insp['site_id'], self.selected_id,
                 insp['inspection_date'] or date.today().isoformat(),
                 insp['inspected_by'],
                 '{} — {} ({})'.format(insp['activity'] or '', item['description'] or '',
                                       insp['element'] or '')))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo('NCR raised',
                            '{} created. Complete the root cause and corrective '
                            'action in the NCR Log.'.format(ncr_no))

    def export(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an inspection.')
            return
        conn = self.db_getter()
        try:
            insp = conn.execute(
                'SELECT i.*, s.name AS site FROM inspections i '
                'LEFT JOIN sites s ON s.id = i.site_id WHERE i.id = ?',
                (self.selected_id,)).fetchone()
            rows = conn.execute(
                'SELECT * FROM inspection_items WHERE inspection_id = ? ORDER BY id',
                (self.selected_id,)).fetchall()
        finally:
            conn.close()
        allowed, reason = quality.may_proceed(rows)
        html = bill_export.build_statement_html(
            'Inspection — {} {}'.format(insp['activity'] or '', insp['element'] or ''),
            ['Site: {}'.format(insp['site'] or '-'),
             'Stage: {}   Date: {}'.format(insp['stage'] or '-',
                                           insp['inspection_date'] or '-'),
             'Inspected by: {}'.format(insp['inspected_by'] or '-'),
             'WORK MAY PROCEED' if allowed else 'DO NOT PROCEED — ' + reason],
            ['Check', 'Type', 'Result', 'By', 'Remarks'],
            [(r['description'] or '', r['check_type'], r['result'],
              r['checked_by'] or '', r['remarks'] or '') for r in rows],
            summary='Result: {}'.format(quality.inspection_result(rows)))
        report_open.save_and_open_html(html, 'inspection_{}.html'.format(self.selected_id))


def build_quality_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(InspectionFrame(nb, db_getter), text='Inspections')
    nb.add(build_itp_template(nb, db_getter), text='ITP Checklist')
    nb.add(build_ncr_log(nb, db_getter), text='NCR Log')
    return nb
