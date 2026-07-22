"""Rate analysis — build a per-unit rate from its inputs (CPWD DAR skeleton).

Header (the item being analysed) over line items (material, labour, machinery,
sundries), with the DAR build-up computed live: inputs → +1% water on wet items
→ +15% CPOH → divided by the analysis quantity.

All arithmetic lives in ``rateanalysis.py`` so it is testable without a GUI.
The derived rate can be pushed into the Rate Book, which is the point of doing
the analysis — otherwise the number dies in this screen.
"""

import branding
import tkinter as tk
import theme
from tkinter import ttk, messagebox

from ui_guard import can_write

import bill_export
import rateanalysis
import report_open


def _num(value, default=None):
    s = str(value).strip()
    if s == '':
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _company_name(conn):
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = 'company_name'").fetchone()
    return (row['value'] if row and row['value'] else '') or branding.APP_NAME


class RateAnalysisFrame(ttk.Frame):
    HEADER_COLUMNS = ('id', 'code', 'description', 'unit', 'analysis_qty',
                      'rate_per_unit')
    ITEM_COLUMNS = ('id', 'kind', 'description', 'unit', 'qty', 'rate',
                    'amount')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self.selected_item = None
        self.h = {k: tk.StringVar() for k in
                  ('code', 'description', 'unit', 'analysis_qty', 'water_pct',
                   'cpoh_pct', 'scaffolding', 'notes')}
        self.h['analysis_qty'].set('1')
        self.h['water_pct'].set('{:g}'.format(rateanalysis.WATER_PCT))
        self.h['cpoh_pct'].set('{:g}'.format(rateanalysis.CPOH_PCT))
        self.h['scaffolding'].set('0')
        self.water_var = tk.BooleanVar(value=False)
        self.i = {k: tk.StringVar() for k in
                  ('description', 'unit', 'qty', 'rate')}
        self.kind_var = tk.StringVar(value=rateanalysis.MATERIAL)
        self.buildup_var = tk.StringVar()
        self.rate_var = tk.StringVar(value='—')
        self.warn_var = tk.StringVar()
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        hdr = ttk.LabelFrame(self, text='Item being analysed')
        hdr.pack(fill='x', padx=8, pady=(8, 4))
        entries = [('code', 'Code', 10), ('description', 'Description', 34),
                   ('unit', 'Unit', 8), ('analysis_qty', 'Analysis Qty', 8),
                   ('cpoh_pct', 'CPOH %', 6), ('water_pct', 'Water %', 6),
                   ('scaffolding', 'Scaffolding', 10), ('notes', 'Notes', 34)]
        for idx, (key, label, w) in enumerate(entries):
            cell = ttk.Frame(hdr)
            cell.grid(row=idx // 4, column=idx % 4, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=12).pack(side='left')
            ttk.Entry(cell, textvariable=self.h[key], width=w).pack(side='left')
        wc = ttk.Frame(hdr); wc.grid(row=2, column=0, padx=6, pady=4, sticky='w')
        ttk.Checkbutton(wc, text='Water charges (wet items only)',
                        variable=self.water_var,
                        command=self._recalc).pack(side='left')
        btns = ttk.Frame(hdr); btns.grid(row=2, column=2, columnspan=2,
                                         padx=6, pady=4, sticky='e')
        ttk.Button(btns, text='New', command=self.new).pack(side='left', padx=3)
        ttk.Button(btns, text='Save', command=self.save).pack(side='left', padx=3)
        ttk.Button(btns, text='Delete', command=self.delete).pack(side='left', padx=3)

        panes = ttk.Frame(self); panes.pack(fill='both', expand=True, padx=8)
        left = ttk.LabelFrame(panes, text='Analyses')
        left.pack(side='left', fill='both', expand=True, padx=(0, 4))
        self.tree = ttk.Treeview(left, columns=self.HEADER_COLUMNS,
                                 show='headings', height=8)
        for col in self.HEADER_COLUMNS:
            self.tree.heading(col, text=col.replace('_', ' ').title())
            self.tree.column(col, width=60 if col in ('id', 'unit') else 110)
        self.tree.pack(fill='both', expand=True, padx=4, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        right = ttk.LabelFrame(panes, text='Inputs')
        right.pack(side='left', fill='both', expand=True, padx=(4, 0))
        self.item_tree = ttk.Treeview(right, columns=self.ITEM_COLUMNS,
                                      show='headings', height=8)
        for col in self.ITEM_COLUMNS:
            self.item_tree.heading(col, text=col.title())
            self.item_tree.column(col, width=50 if col == 'id' else 95)
        self.item_tree.pack(fill='both', expand=True, padx=4, pady=4)
        self.item_tree.bind('<<TreeviewSelect>>', self._on_item_select)

        form = ttk.Frame(right); form.pack(fill='x', padx=4, pady=(0, 4))
        ttk.Label(form, text='Kind', width=6).pack(side='left')
        ttk.Combobox(form, textvariable=self.kind_var, width=11,
                     state='readonly',
                     values=list(rateanalysis.KINDS)).pack(side='left', padx=2)
        for key, label, w in (('description', 'Description', 18),
                              ('unit', 'Unit', 6), ('qty', 'Qty', 7),
                              ('rate', 'Rate', 9)):
            ttk.Label(form, text=label).pack(side='left', padx=(6, 2))
            ttk.Entry(form, textvariable=self.i[key], width=w).pack(side='left')
        ib = ttk.Frame(right); ib.pack(fill='x', padx=4, pady=(0, 6))
        ttk.Button(ib, text='Add', command=self.add_item).pack(side='left', padx=3)
        ttk.Button(ib, text='Update', command=self.update_item).pack(side='left', padx=3)
        ttk.Button(ib, text='Remove', command=self.remove_item).pack(side='left', padx=3)

        foot = ttk.Frame(self); foot.pack(fill='x', padx=8, pady=(4, 8))
        ttk.Label(foot, textvariable=self.buildup_var).pack(anchor='w')
        ttk.Label(foot, textvariable=self.rate_var,
                  font=('TkDefaultFont', 12, 'bold')).pack(anchor='w')
        ttk.Label(foot, textvariable=self.warn_var, foreground=theme.palette()['warning'],
                  wraplength=900, justify='left').pack(anchor='w')
        act = ttk.Frame(foot); act.pack(anchor='w', pady=(4, 0))
        ttk.Button(act, text='Send Rate to Rate Book',
                   command=self.push_to_rate_book).pack(side='left', padx=3)
        ttk.Button(act, text='Print / Export',
                   command=self.export).pack(side='left', padx=3)

    # ---------------------------------------------------------- loading
    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        conn = self.db_getter()
        try:
            for r in conn.execute(
                    'SELECT id, code, description, unit, analysis_qty, '
                    'rate_per_unit FROM rate_analysis ORDER BY id DESC'):
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['code'] or '', r['description'] or '',
                    r['unit'] or '', '{:g}'.format(r['analysis_qty'] or 0),
                    '{:,.2f}'.format(r['rate_per_unit'] or 0)))
        finally:
            conn.close()
        self._refresh_items()

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM rate_analysis WHERE id = ?',
                             (self.selected_id,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        for key in ('code', 'description', 'unit', 'notes'):
            self.h[key].set(r[key] or '')
        for key in ('analysis_qty', 'water_pct', 'cpoh_pct', 'scaffolding'):
            self.h[key].set('{:g}'.format(r[key] or 0))
        self.water_var.set(bool(r['apply_water']))
        self._refresh_items()

    def _refresh_items(self):
        for row in self.item_tree.get_children():
            self.item_tree.delete(row)
        if self.selected_id is None:
            self._recalc()
            return
        conn = self.db_getter()
        try:
            for r in conn.execute(
                    'SELECT * FROM rate_analysis_items WHERE analysis_id = ? '
                    'ORDER BY id', (self.selected_id,)):
                self.item_tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['kind'] or '', r['description'] or '',
                    r['unit'] or '', '{:g}'.format(r['qty'] or 0),
                    '{:,.2f}'.format(r['rate'] or 0),
                    '{:,.2f}'.format(r['amount'] or 0)))
        finally:
            conn.close()
        self._recalc()

    def _on_item_select(self, _e=None):
        sel = self.item_tree.selection()
        if not sel:
            return
        self.selected_item = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM rate_analysis_items WHERE id = ?',
                             (self.selected_item,)).fetchone()
        finally:
            conn.close()
        if r is None:
            return
        self.kind_var.set(r['kind'] or rateanalysis.MATERIAL)
        self.i['description'].set(r['description'] or '')
        self.i['unit'].set(r['unit'] or '')
        self.i['qty'].set('{:g}'.format(r['qty'] or 0))
        self.i['rate'].set('{:g}'.format(r['rate'] or 0))

    # ------------------------------------------------------- computation
    def _current_lines(self):
        if self.selected_id is None:
            return []
        conn = self.db_getter()
        try:
            return [dict(r) for r in conn.execute(
                'SELECT kind, qty, rate, amount FROM rate_analysis_items '
                'WHERE analysis_id = ?', (self.selected_id,))]
        finally:
            conn.close()

    def _result(self):
        return rateanalysis.analyse(
            self._current_lines(),
            analysis_qty=_num(self.h['analysis_qty'].get(), 0) or 0,
            apply_water=self.water_var.get(),
            water_pct=_num(self.h['water_pct'].get(), rateanalysis.WATER_PCT),
            cpoh_pct=_num(self.h['cpoh_pct'].get(), rateanalysis.CPOH_PCT),
            scaffolding=_num(self.h['scaffolding'].get(), 0) or 0)

    def _recalc(self):
        res = self._result()
        by = res['by_kind']
        self.buildup_var.set(
            'Material {:,.2f}  +  Labour {:,.2f}  +  Machinery {:,.2f}  +  '
            'Sundries {:,.2f}  =  {:,.2f}      water {:,.2f}      '
            'CPOH {:,.2f} (profit {:,.2f} + overhead {:,.2f})      '
            'total {:,.2f}'.format(
                by['Material'], by['Labour'], by['Machinery'], by['Sundries'],
                res['inputs'], res['water'], res['cpoh'], res['profit'],
                res['overhead'], res['total']))
        rate = res['rate_per_unit']
        self.rate_var.set(
            'Rate per {}: {:,.2f}'.format(self.h['unit'].get() or 'unit', rate)
            if rate is not None else 'Rate per unit: — (set the analysis qty)')
        self.warn_var.set('  •  '.join(rateanalysis.warnings(res)))
        return res

    # ------------------------------------------------------------ writes
    def new(self):
        self.selected_id = None
        self.selected_item = None
        for key in ('code', 'description', 'unit', 'notes'):
            self.h[key].set('')
        self.h['analysis_qty'].set('1')
        self.h['scaffolding'].set('0')
        self.water_var.set(False)
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self._refresh_items()

    def _header_values(self, res):
        return (self.h['code'].get().strip(),
                self.h['description'].get().strip(),
                self.h['unit'].get().strip(),
                _num(self.h['analysis_qty'].get(), 0) or 0,
                1 if self.water_var.get() else 0,
                _num(self.h['water_pct'].get(), rateanalysis.WATER_PCT),
                _num(self.h['cpoh_pct'].get(), rateanalysis.CPOH_PCT),
                _num(self.h['scaffolding'].get(), 0) or 0,
                res['rate_per_unit'] or 0,
                self.h['notes'].get().strip())

    def save(self):
        if not can_write():
            return
        if not self.h['description'].get().strip():
            messagebox.showinfo('Missing', 'Enter a description.')
            return
        res = self._result()
        vals = self._header_values(res)
        conn = self.db_getter()
        try:
            if self.selected_id is None:
                cur = conn.execute(
                    'INSERT INTO rate_analysis (code, description, unit, '
                    'analysis_qty, apply_water, water_pct, cpoh_pct, '
                    'scaffolding, rate_per_unit, notes) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', vals)
                self.selected_id = cur.lastrowid
            else:
                conn.execute(
                    'UPDATE rate_analysis SET code = ?, description = ?, '
                    'unit = ?, analysis_qty = ?, apply_water = ?, '
                    'water_pct = ?, cpoh_pct = ?, scaffolding = ?, '
                    'rate_per_unit = ?, notes = ? WHERE id = ?',
                    vals + (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.refresh()
        if self.tree.exists(str(self.selected_id)):
            self.tree.selection_set(str(self.selected_id))

    def delete(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an analysis.')
            return
        if not messagebox.askyesno('Delete', 'Delete this analysis and its '
                                             'input lines?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM rate_analysis_items WHERE analysis_id = ?',
                         (self.selected_id,))
            conn.execute('DELETE FROM rate_analysis WHERE id = ?',
                         (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.new()
        self.refresh()

    def _item_values(self):
        qty = _num(self.i['qty'].get(), 0) or 0
        rate = _num(self.i['rate'].get(), 0) or 0
        return (self.kind_var.get(), self.i['description'].get().strip(),
                self.i['unit'].get().strip(), qty, rate,
                rateanalysis.line_amount(qty, rate))

    def add_item(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('Save first',
                                'Save the analysis before adding inputs.')
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO rate_analysis_items (analysis_id, kind, '
                'description, unit, qty, rate, amount) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (self.selected_id,) + self._item_values())
            conn.commit()
        finally:
            conn.close()
        self._clear_item()
        self._refresh_items()
        self.save()          # keep the stored rate in step with its inputs

    def update_item(self):
        if not can_write():
            return
        if self.selected_item is None:
            messagebox.showinfo('No selection', 'Select an input line.')
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'UPDATE rate_analysis_items SET kind = ?, description = ?, '
                'unit = ?, qty = ?, rate = ?, amount = ? WHERE id = ?',
                self._item_values() + (self.selected_item,))
            conn.commit()
        finally:
            conn.close()
        self._refresh_items()
        self.save()

    def remove_item(self):
        if not can_write():
            return
        if self.selected_item is None:
            messagebox.showinfo('No selection', 'Select an input line.')
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM rate_analysis_items WHERE id = ?',
                         (self.selected_item,))
            conn.commit()
        finally:
            conn.close()
        self.selected_item = None
        self._clear_item()
        self._refresh_items()
        self.save()

    def _clear_item(self):
        for var in self.i.values():
            var.set('')

    def push_to_rate_book(self):
        """Copy the derived rate into the Rate Book for reuse."""
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an analysis.')
            return
        res = self._result()
        if not rateanalysis.is_complete(res):
            messagebox.showinfo(
                'Incomplete',
                'This analysis has no usable rate yet. Add input lines and '
                'set the analysis quantity first.')
            return
        code = self.h['code'].get().strip()
        desc = self.h['description'].get().strip()
        conn = self.db_getter()
        try:
            existing = conn.execute(
                'SELECT id FROM rate_book WHERE (code = ? AND code <> \'\') '
                'OR description = ?', (code, desc)).fetchone()
            spec = 'Derived by rate analysis #{}{}'.format(
                self.selected_id,
                ' — ' + self.h['notes'].get().strip()
                if self.h['notes'].get().strip() else '')
            if existing:
                if not messagebox.askyesno(
                        'Already in the rate book',
                        'Update the existing rate book entry to '
                        '{:,.2f}?'.format(res['rate_per_unit'])):
                    return
                conn.execute(
                    'UPDATE rate_book SET rate = ?, unit = ?, '
                    'specification = ? WHERE id = ?',
                    (res['rate_per_unit'], self.h['unit'].get().strip(),
                     spec, existing['id']))
            else:
                conn.execute(
                    'INSERT INTO rate_book (code, category, description, '
                    "unit, rate, specification) VALUES (?, 'Analysed', "
                    '?, ?, ?, ?)',
                    (code, desc, self.h['unit'].get().strip(),
                     res['rate_per_unit'], spec))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(
            'Sent to Rate Book',
            '{} at {:,.2f} per {} is now in the Rate Book.'.format(
                desc or code, res['rate_per_unit'],
                self.h['unit'].get().strip() or 'unit'))

    def export(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an analysis.')
            return
        res = self._result()
        conn = self.db_getter()
        try:
            items = conn.execute(
                'SELECT kind, description, unit, qty, rate, amount '
                'FROM rate_analysis_items WHERE analysis_id = ? ORDER BY id',
                (self.selected_id,)).fetchall()
            company = _company_name(conn)
        finally:
            conn.close()
        rows = [(r['kind'] or '', r['description'] or '', r['unit'] or '',
                 '{:g}'.format(r['qty'] or 0),
                 '{:,.2f}'.format(r['rate'] or 0),
                 '{:,.2f}'.format(r['amount'] or 0)) for r in items]
        rows.append(('', 'Total inputs', '', '', '',
                     '{:,.2f}'.format(res['inputs'])))
        if res['water']:
            rows.append(('', 'Add: water charges @ {:g}%'.format(
                _num(self.h['water_pct'].get(), 0) or 0), '', '', '',
                '{:,.2f}'.format(res['water'])))
        rows.append(('', 'Add: CPOH @ {:g}% (profit {:,.2f} + overhead {:,.2f})'
                     .format(_num(self.h['cpoh_pct'].get(), 0) or 0,
                             res['profit'], res['overhead']),
                     '', '', '', '{:,.2f}'.format(res['cpoh'])))
        rows.append(('', 'Total for {:g} {}'.format(
            res['analysis_qty'], self.h['unit'].get() or 'unit'),
            '', '', '', '{:,.2f}'.format(res['total'])))
        rate = res['rate_per_unit']
        summary = ('Rate per {}: {:,.2f}'.format(
            self.h['unit'].get() or 'unit', rate) if rate is not None
            else 'Rate per unit not yet derived.')
        html = bill_export.build_statement_html(
            'Analysis of Rates — {}'.format(
                self.h['description'].get() or self.h['code'].get() or ''),
            ['Code: {}'.format(self.h['code'].get() or '-'),
             'Analysed for: {:g} {}'.format(
                 res['analysis_qty'], self.h['unit'].get() or 'unit'),
             'Notes: {}'.format(self.h['notes'].get() or '-')],
            ['Kind', 'Description', 'Unit', 'Qty', 'Rate', 'Amount'],
            rows, summary=summary, company_name=company)
        report_open.save_and_open_html(html, 'rate_analysis.html')


def build_rate_analysis_tab(parent, db_getter):
    return RateAnalysisFrame(parent, db_getter)
