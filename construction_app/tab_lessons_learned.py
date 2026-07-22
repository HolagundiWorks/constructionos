"""Lessons Learned register — the on-screen register over ``lessons_store``.

Distinct from Rate Realisation (``tab_lessons.py`` / ``lessons.py``). This tab
is the continuous-improvement register: capture what went well or badly, with a
recommendation that feeds the next job. Maths/vocabulary in
``lessons_register``; persistence in ``lessons_store``. Writes gated via
``ui_guard``.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import lessons_register as lessons
import lessons_store
import theme
from ui_guard import can_write
from widgets import make_sortable
from tab_masters import project_options

_OUTCOMES = list(lessons.OUTCOMES)
_SOURCES = list(lessons.SOURCES)
_STATUSES = list(lessons.STATUSES)
_CATEGORIES = list(lessons.CATEGORIES)


class LessonsLearnedTab(ttk.Frame):
    COLS = ('title', 'category', 'outcome', 'source', 'status', 'owner')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self.selected_id = None
        self._proj_map = {}
        self.vars = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        pal = theme.palette()
        ttk.Label(self, text='Lessons Learned',
                  font=('TkDefaultFont', 14, 'bold')).pack(
            anchor='w', padx=12, pady=(12, 2))
        self.summary_var = tk.StringVar()
        ttk.Label(self, textvariable=self.summary_var, foreground=pal['muted'],
                  wraplength=760, justify='left').pack(
            anchor='w', padx=12, pady=(0, 6))

        bar = ttk.Frame(self); bar.pack(fill='x', padx=12, pady=2)
        ttk.Label(bar, text='Project').pack(side='left')
        self.filter_proj = ttk.Combobox(bar, width=20, state='readonly')
        self.filter_proj.pack(side='left', padx=(4, 10))
        self.filter_proj.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Label(bar, text='Status').pack(side='left')
        self.filter_status = ttk.Combobox(
            bar, width=12, state='readonly', values=['All'] + _STATUSES)
        self.filter_status.set('All')
        self.filter_status.pack(side='left', padx=(4, 10))
        self.filter_status.bind('<<ComboboxSelected>>', lambda e: self.refresh())

        lf = ttk.Frame(self); lf.pack(fill='both', expand=True, padx=12, pady=4)
        self.tree = ttk.Treeview(lf, columns=self.COLS, show='headings',
                                 height=9)
        heads = {'title': 'Lesson', 'category': 'Category', 'outcome': 'Outcome',
                 'source': 'Source', 'status': 'Status', 'owner': 'Owner'}
        widths = {'title': 260, 'category': 100, 'outcome': 80, 'source': 90,
                  'status': 80, 'owner': 100}
        for c in self.COLS:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor='w')
        vsb = ttk.Scrollbar(lf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.tag_configure('feed', background=theme.wash('warn'))
        self._resort = make_sortable(self.tree)

        form = ttk.LabelFrame(self, text='Details')
        form.pack(fill='x', padx=12, pady=4)
        fields = [
            ('title', 'Title', 'entry'),
            ('category', 'Category', _CATEGORIES),
            ('outcome', 'Outcome', _OUTCOMES),
            ('source', 'Source', _SOURCES),
            ('status', 'Status', _STATUSES),
            ('owner', 'Owner', 'entry'),
            ('impact_value', 'Impact ₹ / days', 'entry'),
            ('tags', 'Tags', 'entry'),
            ('description', 'What happened', 'entry'),
            ('root_cause', 'Root cause', 'entry'),
            ('recommendation', 'Recommendation', 'entry'),
            ('remarks', 'Remarks', 'entry'),
        ]
        for idx, (key, label, kind) in enumerate(fields):
            cell = ttk.Frame(form)
            cell.grid(row=idx // 3, column=idx % 3, padx=6, pady=4, sticky='w')
            ttk.Label(cell, text=label, width=14).pack(side='left')
            var = tk.StringVar()
            self.vars[key] = var
            if isinstance(kind, list):
                w = ttk.Combobox(cell, textvariable=var, width=18,
                                 state='readonly', values=kind)
            else:
                w = ttk.Entry(cell, textvariable=var, width=20)
            w.pack(side='left')
        self.vars['outcome'].set(lessons.NEUTRAL)
        self.vars['source'].set(lessons.OBSERVATION)
        self.vars['status'].set(lessons.OPEN)

        btns = ttk.Frame(self); btns.pack(fill='x', padx=12, pady=(2, 10))
        ttk.Button(btns, text='Add', command=self.add).pack(side='left', padx=3)
        ttk.Button(btns, text='Update', command=self.update).pack(
            side='left', padx=3)
        ttk.Button(btns, text='Mark Applied', command=self.mark_applied).pack(
            side='left', padx=3)
        ttk.Button(btns, text='Delete', command=self.delete).pack(
            side='left', padx=3)
        ttk.Button(btns, text='Clear', command=self.clear).pack(
            side='left', padx=3)
        ttk.Button(btns, text='Refresh', command=self.refresh).pack(
            side='left', padx=3)

    def _collect(self):
        title = self.vars['title'].get().strip()
        if not title:
            messagebox.showinfo('Lessons', 'A lesson needs a title.')
            return None
        try:
            impact = float(self.vars['impact_value'].get() or 0)
        except ValueError:
            messagebox.showerror('Lessons', 'Impact must be a number.')
            return None
        return {
            'project_id': self._proj_map.get(self.filter_proj.get()),
            'title': title,
            'category': self.vars['category'].get().strip(),
            'outcome': self.vars['outcome'].get().strip() or lessons.NEUTRAL,
            'source': self.vars['source'].get().strip() or lessons.OBSERVATION,
            'status': self.vars['status'].get().strip() or lessons.OPEN,
            'owner': self.vars['owner'].get().strip(),
            'impact_value': impact,
            'tags': self.vars['tags'].get().strip(),
            'description': self.vars['description'].get().strip(),
            'root_cause': self.vars['root_cause'].get().strip(),
            'recommendation': self.vars['recommendation'].get().strip(),
            'remarks': self.vars['remarks'].get().strip(),
        }

    def refresh(self):
        conn = self.db_getter()
        try:
            self._proj_map = {'{} - {}'.format(i, n): i
                              for i, n in project_options(conn)}
            self.filter_proj['values'] = ['All projects'] + list(self._proj_map)
            if not self.filter_proj.get():
                self.filter_proj.set('All projects')
            pid = self._proj_map.get(self.filter_proj.get())
            status = self.filter_status.get()
            status = None if status in ('', 'All') else status
            rows = lessons_store.list_lessons(conn, project_id=pid, status=status)
            summ = lessons_store.summary(conn, project_id=pid)
        finally:
            conn.close()
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            tags = ('feed',) if lessons.is_feed_forward(r) else ()
            self.tree.insert('', 'end', iid=str(r['id']), tags=tags, values=(
                r['title'] or '', r['category'] or '', r['outcome'] or '',
                r['source'] or '', r['status'] or '', r['owner'] or ''))
        ff = summ.get('feed_forward_count', 0)
        self.summary_var.set(
            '{n} lessons · {ap} applied · {ff} still to feed forward · '
            'outcomes +{pos}/−{neg}/={neu}'.format(
                n=summ.get('count', 0), ap=summ.get('applied', 0), ff=ff,
                pos=summ.get('by_outcome', {}).get(lessons.POSITIVE, 0),
                neg=summ.get('by_outcome', {}).get(lessons.NEGATIVE, 0),
                neu=summ.get('by_outcome', {}).get(lessons.NEUTRAL, 0)))
        self._resort()

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        conn = self.db_getter()
        try:
            r = lessons_store.get(conn, self.selected_id)
        finally:
            conn.close()
        if not r:
            return
        for key in self.vars:
            val = r[key] if key in r.keys() else ''
            self.vars[key].set('' if val is None else str(val))

    def add(self):
        if not can_write():
            return
        vals = self._collect()
        if vals is None:
            return
        conn = self.db_getter()
        try:
            lessons_store.add(conn, **vals)
        finally:
            conn.close()
        self.clear()
        self.refresh()

    def update(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('Lessons', 'Select a lesson first.')
            return
        vals = self._collect()
        if vals is None:
            return
        conn = self.db_getter()
        try:
            lessons_store.update(conn, self.selected_id, **vals)
        finally:
            conn.close()
        self.refresh()

    def mark_applied(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('Lessons', 'Select a lesson first.')
            return
        conn = self.db_getter()
        try:
            lessons_store.set_status(conn, self.selected_id, lessons.APPLIED)
        finally:
            conn.close()
        self.refresh()

    def delete(self):
        if not can_write():
            return
        if self.selected_id is None:
            messagebox.showinfo('Lessons', 'Select a lesson first.')
            return
        if not messagebox.askyesno('Delete', 'Delete this lesson?'):
            return
        conn = self.db_getter()
        try:
            lessons_store.delete(conn, self.selected_id)
        finally:
            conn.close()
        self.clear()
        self.refresh()

    def clear(self):
        self.selected_id = None
        for v in self.vars.values():
            v.set('')
        self.vars['outcome'].set(lessons.NEUTRAL)
        self.vars['source'].set(lessons.OBSERVATION)
        self.vars['status'].set(lessons.OPEN)
        self.tree.selection_remove(self.tree.selection())


def build_lessons_learned_tab(parent, db_getter):
    return LessonsLearnedTab(parent, db_getter)
