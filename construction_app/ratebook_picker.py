"""A modal picker over the Rate Book, so a priced item can be pulled from the
reference library instead of retyped.

``pick(parent, db_getter)`` opens a searchable list of rate-book items and
returns the chosen row as ``{'code', 'description', 'unit', 'rate'}``, or
``None`` if cancelled. When the rate book is empty it says so and points at the
loader in Tools, rather than opening a blank list.

The estimate and BOQ screens keep type-it-yourself entry; this only fills the
four fields on request, so a picked rate is still fully editable afterwards —
the library is a starting point, not a lock.
"""

import tkinter as tk
from tkinter import ttk, messagebox


class _Picker:
    COLUMNS = ('code', 'category', 'description', 'unit', 'rate')

    def __init__(self, parent, rows):
        self._all = rows
        self.result = None

        self.top = tk.Toplevel(parent)
        self.top.title('Pick from Rate Book')
        self.top.transient(parent.winfo_toplevel())
        self.top.geometry('720x460')

        bar = ttk.Frame(self.top); bar.pack(fill='x', padx=10, pady=(10, 4))
        ttk.Label(bar, text='Search').pack(side='left')
        self.query = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.query)
        ent.pack(side='left', fill='x', expand=True, padx=(6, 0))
        self.query.trace_add('write', lambda *_a: self._filter())

        self.tree = ttk.Treeview(self.top, columns=self.COLUMNS,
                                 show='headings', height=14)
        widths = {'code': 110, 'category': 100, 'description': 320, 'unit': 60,
                  'rate': 90}
        for col in self.COLUMNS:
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=widths[col],
                             anchor='e' if col == 'rate' else 'w')
        self.tree.pack(fill='both', expand=True, padx=10, pady=4)
        self.tree.bind('<Double-1>', lambda _e: self._choose())
        self.tree.bind('<Return>', lambda _e: self._choose())

        btns = ttk.Frame(self.top); btns.pack(fill='x', padx=10, pady=(4, 10))
        ttk.Button(btns, text='Use Selected', command=self._choose,
                   style='Accent.TButton').pack(side='right')
        ttk.Button(btns, text='Cancel',
                   command=self.top.destroy).pack(side='right', padx=(0, 6))

        self._filter()
        ent.focus_set()
        self.top.grab_set()

    def _filter(self):
        q = self.query.get().strip().lower()
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for i, r in enumerate(self._all):
            hay = ' '.join(str(r.get(k, '') or '') for k in
                           ('code', 'category', 'description')).lower()
            if q and q not in hay:
                continue
            self.tree.insert('', 'end', iid=str(i), values=(
                r.get('code', ''), r.get('category', ''),
                r.get('description', ''), r.get('unit', ''),
                '{:,.2f}'.format(float(r.get('rate') or 0))))

    def _choose(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Nothing selected',
                                'Pick an item first.', parent=self.top)
            return
        r = self._all[int(sel[0])]
        self.result = {
            'code': r.get('code', '') or '',
            'description': r.get('description', '') or '',
            'unit': r.get('unit', '') or '',
            'rate': r.get('rate') or 0,
        }
        self.top.destroy()


def pick(parent, db_getter):
    """Show the rate-book picker; return the chosen row dict or None."""
    conn = db_getter()
    try:
        rows = [dict(r) for r in conn.execute(
            'SELECT code, category, description, unit, rate FROM rate_book '
            'ORDER BY category, code, id')]
    finally:
        conn.close()
    if not rows:
        messagebox.showinfo(
            'Rate Book is empty',
            'No rate-book items yet. Load the starter library from '
            'Tools › Reference library › Load CPWD Reference Data, then try '
            'again.', parent=parent)
        return None
    dlg = _Picker(parent, rows)
    parent.wait_window(dlg.top)
    return dlg.result
