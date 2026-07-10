"""Generic "list + form" widget used by every simple single-table tab.

``Field`` describes one column/form input. ``CrudFrame`` renders a Treeview
list on top, an auto-generated form below it (3 fields per row), and
Add/Update/Delete/Clear/Refresh buttons. It runs raw INSERT/UPDATE/DELETE
against a single ``table`` using the ``fields`` list.

It knows nothing about foreign-key cascades or business rules: any derived
column or side effect must be handled by the optional ``on_save`` callback,
invoked with a live connection after each insert/update.
"""

import tkinter as tk
from tkinter import ttk, messagebox


class Field:
    """Descriptor for one form field / table column.

    kind:
        'text'   -> ttk.Entry, stored as a string.
        'number' -> ttk.Entry, parsed with float() on save (error dialog if not
                    numeric).
        'combo'  -> read-only Combobox from a static ``options=[...]`` list.
        'fk'     -> read-only Combobox populated by ``options_func(conn)`` which
                    returns [(id, label), ...]. Displayed as "{id} - {label}";
                    the leading id is parsed back out on save.
    """

    def __init__(self, key, label, kind='text', width=110,
                 options=None, options_func=None, default=''):
        self.key = key
        self.label = label
        self.kind = kind
        self.width = width
        self.options = options or []
        self.options_func = options_func
        self.default = default


class CrudFrame(ttk.Frame):
    def __init__(self, parent, db_getter, table, fields, title,
                 extra_where='', order_by='id DESC', on_save=None):
        super().__init__(parent)
        self.db_getter = db_getter
        self.table = table
        self.fields = fields
        self.title = title
        self.extra_where = extra_where
        self.order_by = order_by
        self.on_save = on_save

        self.vars = {}          # key -> tk.StringVar
        self.widgets = {}       # key -> widget (needed to refresh fk options)
        self._fk_maps = {}      # key -> {display_string: id}
        self.selected_id = None

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        ttk.Label(self, text=self.title, font=('TkDefaultFont', 12, 'bold')) \
            .pack(anchor='w', padx=8, pady=(8, 4))

        # --- list ---
        list_frame = ttk.Frame(self)
        list_frame.pack(fill='both', expand=True, padx=8, pady=4)

        columns = ['id'] + [f.key for f in self.fields]
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings',
                                 height=10)
        for col in columns:
            label = 'ID' if col == 'id' else \
                next((f.label for f in self.fields if f.key == col), col)
            self.tree.heading(col, text=label)
            width = 50 if col == 'id' else \
                next((f.width for f in self.fields if f.key == col), 110)
            self.tree.column(col, width=width, anchor='w')
        vsb = ttk.Scrollbar(list_frame, orient='vertical',
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        # --- form (3 fields per row) ---
        form = ttk.LabelFrame(self, text='Details')
        form.pack(fill='x', padx=8, pady=4)
        for idx, field in enumerate(self.fields):
            row, col = divmod(idx, 3)
            cell = ttk.Frame(form)
            cell.grid(row=row, column=col, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=field.label, width=14).pack(side='left')
            var = tk.StringVar(value=field.default)
            self.vars[field.key] = var
            if field.kind in ('combo', 'fk'):
                widget = ttk.Combobox(cell, textvariable=var, width=20,
                                      state='readonly')
                if field.kind == 'combo':
                    widget['values'] = field.options
                self.widgets[field.key] = widget
                widget.pack(side='left')
            else:
                widget = ttk.Entry(cell, textvariable=var, width=22)
                self.widgets[field.key] = widget
                widget.pack(side='left')

        # --- buttons ---
        btns = ttk.Frame(self)
        btns.pack(fill='x', padx=8, pady=(4, 8))
        ttk.Button(btns, text='Add', command=self.add).pack(side='left', padx=3)
        ttk.Button(btns, text='Update', command=self.update).pack(side='left', padx=3)
        ttk.Button(btns, text='Delete', command=self.delete_selected).pack(side='left', padx=3)
        ttk.Button(btns, text='Clear', command=self.clear).pack(side='left', padx=3)
        ttk.Button(btns, text='Refresh', command=self.refresh).pack(side='left', padx=3)

    # -------------------------------------------------------------- helpers
    def _refresh_fk_options(self, conn):
        """(Re)populate every fk combobox from its options_func."""
        for field in self.fields:
            if field.kind != 'fk' or not field.options_func:
                continue
            rows = field.options_func(conn)
            display = ['{} - {}'.format(rid, label) for rid, label in rows]
            self._fk_maps[field.key] = {
                '{} - {}'.format(rid, label): rid for rid, label in rows}
            self.widgets[field.key]['values'] = display

    def _collect_values(self):
        """Read the form into a {column: value} dict, validating as we go.

        Returns None (after showing a dialog) if a number/fk field is invalid.
        """
        values = {}
        for field in self.fields:
            raw = self.vars[field.key].get().strip()
            if field.kind == 'number':
                if raw == '':
                    values[field.key] = 0.0
                else:
                    try:
                        values[field.key] = float(raw)
                    except ValueError:
                        messagebox.showerror(
                            'Invalid number',
                            '"{}" must be a number.'.format(field.label))
                        return None
            elif field.kind == 'fk':
                if raw == '':
                    values[field.key] = None
                else:
                    # Display is "{id} - {label}"; split on the first ' - '.
                    values[field.key] = self._fk_maps.get(
                        raw, raw.split(' - ')[0])
            else:
                values[field.key] = raw
        return values

    # -------------------------------------------------------------- actions
    def refresh(self):
        conn = self.db_getter()
        try:
            self._refresh_fk_options(conn)
            for item in self.tree.get_children():
                self.tree.delete(item)
            where = 'WHERE {}'.format(self.extra_where) if self.extra_where else ''
            cols = ', '.join(['id'] + [f.key for f in self.fields])
            sql = 'SELECT {} FROM {} {} ORDER BY {}'.format(
                cols, self.table, where, self.order_by)
            for row in conn.execute(sql):
                values = [row['id']] + [row[f.key] for f in self.fields]
                self.tree.insert('', 'end', iid=str(row['id']), values=values)
        finally:
            conn.close()

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        values = self.tree.item(sel[0], 'values')
        # values[0] is id; fields follow in order.
        for idx, field in enumerate(self.fields):
            val = values[idx + 1]
            self.vars[field.key].set('' if val is None else str(val))

    def add(self):
        values = self._collect_values()
        if values is None:
            return
        cols = list(values.keys())
        placeholders = ', '.join(['?'] * len(cols))
        sql = 'INSERT INTO {} ({}) VALUES ({})'.format(
            self.table, ', '.join(cols), placeholders)
        conn = self.db_getter()
        try:
            cur = conn.execute(sql, [values[c] for c in cols])
            conn.commit()
            row_id = cur.lastrowid
            if self.on_save:
                self.on_save(conn, row_id, values)
        finally:
            conn.close()
        self.refresh()
        self.clear()

    def update(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a row to update.')
            return
        values = self._collect_values()
        if values is None:
            return
        cols = list(values.keys())
        assignments = ', '.join('{} = ?'.format(c) for c in cols)
        sql = 'UPDATE {} SET {} WHERE id = ?'.format(self.table, assignments)
        conn = self.db_getter()
        try:
            conn.execute(sql, [values[c] for c in cols] + [self.selected_id])
            conn.commit()
            if self.on_save:
                self.on_save(conn, self.selected_id, values)
        finally:
            conn.close()
        self.refresh()

    def delete_selected(self):
        if self.selected_id is None:
            messagebox.showinfo('No selection', 'Select a row to delete.')
            return
        if not messagebox.askyesno('Confirm delete',
                                   'Delete the selected row?'):
            return
        # No cascade logic here by design (see AGENTS.md §4/§10): a bare DELETE.
        # Deleting a parent still referenced by a child table raises an
        # IntegrityError that surfaces as an uncaught exception.
        conn = self.db_getter()
        try:
            conn.execute('DELETE FROM {} WHERE id = ?'.format(self.table),
                         (self.selected_id,))
            conn.commit()
        finally:
            conn.close()
        self.refresh()
        self.clear()

    def clear(self):
        self.selected_id = None
        for field in self.fields:
            self.vars[field.key].set(field.default)
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
