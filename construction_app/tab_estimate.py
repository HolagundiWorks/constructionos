"""Estimates — ported from Construction-Billing-System's estimate flow.

A priced BOQ estimate: header (number, title, site, date, status, contingency%,
GST%) + line items (code, description, unit, qty, rate, amount). The roll-up
(subtotal -> contingency -> taxable -> GST -> grand total) is the pure
``estimate.estimate_totals``; the grand total is stored in ``total_estimate``.
"Print / Export" renders a branded estimate document with the grand total in
words via ``bill_export.build_estimate_html``.

This replaces the earlier DocumentFrame-based estimates (which only summed
items) — the estimate is the one CBS feature ported into Construction OS.
"""

import os
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import estimate as estimate_calc
import bill_export
from tab_masters import site_options
from tab_tax_invoice import _seller_from_settings


class EstimateTab(ttk.Frame):
    HEADER_COLUMNS = ('id', 'est_number', 'title', 'site', 'estimate_date',
                      'status', 'total_estimate')
    ITEM_COLUMNS = ('id', 'item_code', 'description', 'unit', 'qty', 'rate',
                    'amount')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self.selected_item_id = None
        self._site_map = {}
        self.h = {}
        self.i = {}
        self._build_ui()
        self.refresh_estimates()

    def _build_ui(self):
        ttk.Label(self, text='Estimates',
                  font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        hdr = ttk.LabelFrame(self, text='Estimates')
        hdr.pack(fill='both', expand=True, padx=8, pady=4)
        heads = {'id': 'ID', 'est_number': 'Est No', 'title': 'Title',
                 'site': 'Site', 'estimate_date': 'Date', 'status': 'Status',
                 'total_estimate': 'Grand Total'}
        self.tree = ttk.Treeview(hdr, columns=self.HEADER_COLUMNS,
                                 show='headings', height=6)
        for col in self.HEADER_COLUMNS:
            self.tree.heading(col, text=heads[col])
            self.tree.column(col, width=50 if col == 'id' else 115, anchor='w')
        self.tree.pack(fill='x', padx=4, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        form = ttk.Frame(hdr); form.pack(fill='x', padx=4, pady=4)
        for key, default in (('est_number', ''), ('title', ''),
                             ('estimate_date', ''), ('contingency_pct', '0'),
                             ('gst_pct', '18'), ('notes', '')):
            self.h[key] = tk.StringVar(value=default)
        self.h['site'] = tk.StringVar()
        self.h['status'] = tk.StringVar(value='Draft')

        self._entry(form, 0, 0, 'Est No', 'est_number')
        self._entry(form, 0, 1, 'Title', 'title')
        cell = ttk.Frame(form); cell.grid(row=0, column=2, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text='Site', width=13).pack(side='left')
        self.site_combo = ttk.Combobox(cell, textvariable=self.h['site'],
                                       width=18, state='readonly')
        self.site_combo.pack(side='left')
        self._entry(form, 1, 0, 'Date', 'estimate_date')
        self._combo(form, 1, 1, 'Status', 'status',
                    ['Draft', 'Approved', 'Revised'])
        self._entry(form, 1, 2, 'Contingency %', 'contingency_pct')
        self._entry(form, 2, 0, 'GST %', 'gst_pct')
        self._entry(form, 2, 1, 'Notes', 'notes')

        self.totals_var = tk.StringVar(
            value='Subtotal 0.00  |  Contingency 0.00  |  GST 0.00  |  Grand Total 0.00')
        ttk.Label(hdr, textvariable=self.totals_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=6, pady=(2, 4))

        hbtns = ttk.Frame(hdr); hbtns.pack(fill='x', padx=4, pady=4)
        ttk.Button(hbtns, text='Add Estimate', command=self.add_estimate).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Update Selected', command=self.update_estimate).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Delete', command=self.delete_estimate).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Print / Export', command=self.export_estimate).pack(side='left', padx=3)
        ttk.Button(hbtns, text='Clear', command=self.clear_estimate).pack(side='left', padx=3)

        items = ttk.LabelFrame(self, text='Items'); items.pack(fill='both', expand=True, padx=8, pady=4)
        self.item_tree = ttk.Treeview(items, columns=self.ITEM_COLUMNS,
                                      show='headings', height=6)
        for col in self.ITEM_COLUMNS:
            self.item_tree.heading(col, text=col.replace('_', ' ').title())
            self.item_tree.column(col, width=50 if col == 'id' else 110, anchor='w')
        self.item_tree.pack(fill='x', padx=4, pady=4)
        self.item_tree.bind('<<TreeviewSelect>>', self._on_item_select)

        iform = ttk.Frame(items); iform.pack(fill='x', padx=4, pady=4)
        for idx, (key, label) in enumerate(
                [('item_code', 'Code'), ('description', 'Description'),
                 ('unit', 'Unit'), ('qty', 'Qty'), ('rate', 'Rate')]):
            self.i[key] = tk.StringVar()
            cell = ttk.Frame(iform); cell.grid(row=0, column=idx, padx=6, pady=3, sticky='w')
            ttk.Label(cell, text=label, width=9).pack(side='left')
            ttk.Entry(cell, textvariable=self.i[key], width=14).pack(side='left')

        ibtns = ttk.Frame(items); ibtns.pack(fill='x', padx=4, pady=4)
        ttk.Button(ibtns, text='Add Item', command=self.add_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Update Item', command=self.update_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Delete Item', command=self.delete_item).pack(side='left', padx=3)
        ttk.Button(ibtns, text='Clear', command=self.clear_item).pack(side='left', padx=3)

    def _entry(self, parent, r, c, label, key):
        cell = ttk.Frame(parent); cell.grid(row=r, column=c, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=13).pack(side='left')
        ttk.Entry(cell, textvariable=self.h[key], width=18).pack(side='left')

    def _combo(self, parent, r, c, label, key, values):
        cell = ttk.Frame(parent); cell.grid(row=r, column=c, padx=6, pady=3, sticky='w')
        ttk.Label(cell, text=label, width=13).pack(side='left')
        ttk.Combobox(cell, textvariable=self.h[key], width=16, state='readonly',
                     values=values).pack(side='left')

    # -------------------------------------------------------------- helpers
    def _num(self, key, label):
        raw = self.h[key].get().strip()
        try:
            return float(raw) if raw else 0.0
        except ValueError:
            messagebox.showerror('Invalid number', '"{}" must be a number.'.format(label))
            return None

    def _site_id(self):
        raw = self.h['site'].get().strip()
        if not raw:
            return None
        return self._site_map.get(raw, raw.split(' - ')[0])

    def _recalc(self, conn, est_id):
        row = conn.execute('SELECT contingency_pct, gst_pct FROM estimates WHERE id = ?',
                           (est_id,)).fetchone()
        items = conn.execute(
            'SELECT rate, qty, amount FROM estimate_items WHERE estimate_id = ?',
            (est_id,)).fetchall()
        t = estimate_calc.estimate_totals(items, row['contingency_pct'], row['gst_pct'])
        conn.execute('UPDATE estimates SET total_estimate = ? WHERE id = ?',
                     (t['grand_total'], est_id))
        conn.commit()
        return t

    def _set_totals_label(self, t):
        self.totals_var.set(
            'Subtotal {subtotal:.2f}  |  Contingency {contingency:.2f}  |  '
            'GST {gst:.2f}  |  Grand Total {grand_total:.2f}'.format(**t))

    # ----------------------------------------------------------- estimate ops
    def refresh_estimates(self):
        conn = self.db_getter()
        try:
            opts = site_options(conn)
            self._site_map = {'{} - {}'.format(i, n): i for i, n in opts}
            self.site_combo['values'] = ['{} - {}'.format(i, n) for i, n in opts]
            for item in self.tree.get_children():
                self.tree.delete(item)
            for r in conn.execute(
                    "SELECT e.id, e.est_number, e.title, s.name AS site, "
                    "e.estimate_date, e.status, e.total_estimate FROM estimates e "
                    "LEFT JOIN sites s ON s.id = e.site_id ORDER BY e.id DESC"):
                self.tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['est_number'] or '-', r['title'] or '',
                    r['site'] or '-', r['estimate_date'], r['status'],
                    '{:.2f}'.format(r['total_estimate'] or 0)))
        finally:
            conn.close()

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = conn.execute('SELECT * FROM estimates WHERE id = ?',
                             (self.selected_id,)).fetchone()
            t = self._recalc(conn, self.selected_id)
        finally:
            conn.close()
        if r is None:
            return
        self.h['est_number'].set(r['est_number'] or '')
        self.h['title'].set(r['title'] or '')
        self.h['estimate_date'].set(r['estimate_date'] or '')
        self.h['status'].set(r['status'] or 'Draft')
        self.h['contingency_pct'].set(str(r['contingency_pct'] or 0))
        self.h['gst_pct'].set(str(r['gst_pct'] or 0))
        self.h['notes'].set(r['notes'] or '')
        for disp, sid in self._site_map.items():
            if str(sid) == str(r['site_id']):
                self.h['site'].set(disp); break
        else:
            self.h['site'].set('')
        self._set_totals_label(t)
        self.refresh_items()

    def _header_values(self):
        cont = self._num('contingency_pct', 'Contingency %')
        gst = self._num('gst_pct', 'GST %')
        if None in (cont, gst):
            return None
        return {
            'est_number': self.h['est_number'].get().strip(),
            'title': self.h['title'].get().strip(),
            'site_id': self._site_id(),
            'estimate_date': self.h['estimate_date'].get().strip(),
            'status': self.h['status'].get().strip() or 'Draft',
            'contingency_pct': cont, 'gst_pct': gst,
            'notes': self.h['notes'].get().strip(),
        }

    def add_estimate(self):
        v = self._header_values()
        if v is None:
            return
        conn = self.db_getter()
        try:
            if not v['est_number']:
                n = conn.execute('SELECT COUNT(*) AS c FROM estimates').fetchone()['c']
                v['est_number'] = 'EST-{}'.format(n + 1)
            cols = list(v.keys())
            cur = conn.execute('INSERT INTO estimates ({}) VALUES ({})'.format(
                ', '.join(cols), ', '.join(['?'] * len(cols))),
                [v[c] for c in cols])
            conn.commit()
            self._recalc(conn, cur.lastrowid)
        finally:
            conn.close()
        self.refresh_estimates()
        self.clear_estimate()

    def update_estimate(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an estimate.')
            return
        v = self._header_values()
        if v is None:
            return
        cols = list(v.keys())
        conn = self.db_getter()
        try:
            conn.execute('UPDATE estimates SET {} WHERE id = ?'.format(
                ', '.join('{} = ?'.format(c) for c in cols)),
                [v[c] for c in cols] + [self.selected_id])
            conn.commit()
            t = self._recalc(conn, self.selected_id)
        finally:
            conn.close()
        self.refresh_estimates()
        self._set_totals_label(t)

    def delete_estimate(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an estimate.')
            return
        if not messagebox.askyesno('Confirm delete', 'Delete this estimate and its items?'):
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM estimates WHERE id = ?', (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_id = None
        self.refresh_estimates()
        self.refresh_items()
        self.clear_estimate()

    def clear_estimate(self):
        self.selected_id = None
        for key, default in (('est_number', ''), ('title', ''),
                             ('estimate_date', ''), ('contingency_pct', '0'),
                             ('gst_pct', '18'), ('notes', ''), ('site', '')):
            self.h[key].set(default)
        self.h['status'].set('Draft')
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
        self.refresh_items()

    def export_estimate(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select an estimate to export.')
            return
        conn = self.db_getter()
        try:
            est = conn.execute('SELECT * FROM estimates WHERE id = ?',
                               (self.selected_id,)).fetchone()
            items = conn.execute(
                'SELECT item_code, description, unit, qty, rate, amount '
                'FROM estimate_items WHERE estimate_id = ? ORDER BY id',
                (self.selected_id,)).fetchall()
            seller = _seller_from_settings(conn)
        finally:
            conn.close()
        if est is None:
            return
        html = bill_export.build_estimate_html(
            est, items, seller, company_name=seller.get('name') or 'Construction OS')
        safe = (est['est_number'] or 'estimate').replace('/', '-').replace(' ', '_')
        path = filedialog.asksaveasfilename(
            title='Save estimate', defaultextension='.html',
            initialfile='estimate_{}.html'.format(safe),
            filetypes=[('HTML document', '*.html'), ('All files', '*.*')])
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(html)
        webbrowser.open('file://' + os.path.abspath(path))

    # ------------------------------------------------------------- item ops
    def refresh_items(self):
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)
        if self.selected_id is None:
            return
        conn = self.db_getter()
        try:
            for r in conn.execute(
                    'SELECT id, item_code, description, unit, qty, rate, amount '
                    'FROM estimate_items WHERE estimate_id = ? ORDER BY id',
                    (self.selected_id,)):
                self.item_tree.insert('', 'end', iid=str(r['id']), values=(
                    r['id'], r['item_code'], r['description'], r['unit'],
                    r['qty'], r['rate'], r['amount']))
        finally:
            conn.close()

    def _on_item_select(self, _e=None):
        sel = self.item_tree.selection()
        if not sel:
            return
        self.selected_item_id = int(sel[0])
        vals = self.item_tree.item(sel[0], 'values')
        self.i['item_code'].set(vals[1]); self.i['description'].set(vals[2])
        self.i['unit'].set(vals[3]); self.i['qty'].set(vals[4])
        self.i['rate'].set(vals[5])

    def _collect_item(self):
        try:
            qty = float(self.i['qty'].get().strip() or 0)
            rate = float(self.i['rate'].get().strip() or 0)
        except ValueError:
            messagebox.showerror('Invalid number', 'Qty/Rate must be numbers.')
            return None
        return (self.i['item_code'].get().strip(), self.i['description'].get().strip(),
                self.i['unit'].get().strip(), qty, rate,
                estimate_calc.item_amount(rate, qty))

    def _after_item_change(self):
        conn = self.db_getter()
        try:
            t = self._recalc(conn, self.selected_id)
        finally:
            conn.close()
        self.refresh_items()
        self.refresh_estimates()
        if self.tree.exists(str(self.selected_id)):
            self.tree.selection_set(str(self.selected_id))
        self._set_totals_label(t)

    def add_item(self):
        if self.selected_id is None:
            messagebox.showinfo('No estimate', 'Select an estimate first.')
            return
        item = self._collect_item()
        if item is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'INSERT INTO estimate_items (estimate_id, item_code, description, '
                'unit, qty, rate, amount) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (self.selected_id,) + item)
            conn.commit()
        finally:
            conn.close()
        self._after_item_change()
        self.clear_item()

    def update_item(self):
        if self.selected_item_id is None:
            messagebox.showinfo('No selection', 'Select a line item.')
            return
        item = self._collect_item()
        if item is None:
            return
        conn = self.db_getter()
        try:
            conn.execute(
                'UPDATE estimate_items SET item_code = ?, description = ?, '
                'unit = ?, qty = ?, rate = ?, amount = ? WHERE id = ?',
                item + (self.selected_item_id,))
            conn.commit()
        finally:
            conn.close()
        self._after_item_change()

    def delete_item(self):
        if self.selected_item_id is None:
            messagebox.showinfo('No selection', 'Select a line item.')
            return
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM estimate_items WHERE id = ?',
                         (self.selected_item_id,))
            conn.commit()
        finally:
            conn.close()
        self.selected_item_id = None
        self._after_item_change()
        self.clear_item()

    def clear_item(self):
        self.selected_item_id = None
        for var in self.i.values():
            var.set('')
        if self.item_tree.selection():
            self.item_tree.selection_remove(self.item_tree.selection())


def build_estimate_tab(parent, db_getter):
    return EstimateTab(parent, db_getter)
