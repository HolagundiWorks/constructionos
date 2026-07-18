"""Project timeline: a task CrudFrame plus a hand-drawn Canvas Gantt chart.

``_compute_duration`` auto-fills ``duration_days`` from the date range via the
same best-effort on_save pattern as ``_compute_hire_total``. The Gantt view
draws bars on a raw ``tk.Canvas`` (no charting library), proportionally between
the min and max task dates. Bar colours are keyed by ``status`` in
``status_colors``; an unmatched status falls back to the default blue — so the
task-entry status list and ``status_colors`` must be kept in sync.

``dependency`` is inert free-text metadata: no validation, no cross-reference,
no effect on the chart.
"""

from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk

from crud_frame import CrudFrame, Field
from tab_masters import site_options, project_options


TASK_STATUSES = ['Not Started', 'In Progress', 'Completed', 'On Hold', 'Delayed']

# Keep this map in sync with TASK_STATUSES above.
status_colors = {
    'Not Started': '#9e9e9e',
    'In Progress': '#42a5f5',
    'Completed': '#66bb6a',
    'On Hold': '#ffa726',
    'Delayed': '#ef5350',
}
DEFAULT_COLOR = '#42a5f5'


def _compute_duration(conn, row_id, values):
    """Best-effort auto-fill of duration_days from start/end dates."""
    try:
        d0 = datetime.strptime(values.get('start_date', ''), '%Y-%m-%d')
        d1 = datetime.strptime(values.get('end_date', ''), '%Y-%m-%d')
        duration = (d1 - d0).days + 1  # inclusive
        if duration <= 0:
            return
        conn.execute('UPDATE timeline_tasks SET duration_days = ? WHERE id = ?',
                     (duration, row_id))
        conn.commit()
    except Exception:
        pass


def _build_tasks(parent, db_getter):
    fields = [
        Field('project_id', 'Project', kind='fk', options_func=project_options),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('task_name', 'Task'),
        Field('start_date', 'Start (YYYY-MM-DD)'),
        Field('end_date', 'End (YYYY-MM-DD)'),
        Field('duration_days', 'Duration (auto)', kind='number', default='0'),
        Field('status', 'Status', kind='combo',
              options=TASK_STATUSES, default='Not Started'),
        Field('dependency', 'Dependency'),
    ]
    return CrudFrame(parent, db_getter, 'timeline_tasks', fields,
                     'Timeline Tasks', order_by='start_date, id',
                     on_save=_compute_duration)


class GanttView(ttk.Frame):
    ROW_H = 28
    LEFT_PAD = 160
    TOP_PAD = 40
    RIGHT_PAD = 40

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._site_map = {}

        controls = ttk.Frame(self)
        controls.pack(fill='x', padx=8, pady=6)
        ttk.Label(controls, text='Site filter').pack(side='left')
        self.site_var = tk.StringVar(value='All')
        self.site_combo = ttk.Combobox(controls, textvariable=self.site_var,
                                       width=22, state='readonly')
        self.site_combo.pack(side='left', padx=4)
        ttk.Button(controls, text='Refresh', command=self.refresh) \
            .pack(side='left', padx=6)

        self.canvas = tk.Canvas(self, bg='white', height=400)
        self.canvas.pack(fill='both', expand=True, padx=8, pady=6)
        self.refresh()

    def refresh(self):
        conn = self.db_getter()
        try:
            options = [(s['id'], s['name'])
                       for s in conn.execute('SELECT id, name FROM sites ORDER BY name')]
            self._site_map = {'{} - {}'.format(sid, name): sid
                              for sid, name in options}
            self.site_combo['values'] = ['All'] + list(self._site_map.keys())

            where = ''
            params = []
            sel = self.site_var.get()
            if sel != 'All' and sel in self._site_map:
                where = 'WHERE site_id = ?'
                params.append(self._site_map[sel])
            sql = ('SELECT task_name, start_date, end_date, status '
                   'FROM timeline_tasks {} '
                   'ORDER BY start_date, id'.format(where))
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()

        self._draw(rows)

    def _draw(self, rows):
        self.canvas.delete('all')

        tasks = []
        for r in rows:
            try:
                d0 = datetime.strptime(r['start_date'], '%Y-%m-%d')
                d1 = datetime.strptime(r['end_date'], '%Y-%m-%d')
            except (TypeError, ValueError):
                continue  # skip tasks with unparseable dates
            if d1 < d0:
                d1 = d0
            tasks.append((r['task_name'], d0, d1, r['status']))

        if not tasks:
            self.canvas.create_text(20, 20, anchor='w',
                                    text='No dated tasks to display.')
            return

        min_date = min(t[1] for t in tasks)
        max_date = max(t[2] for t in tasks)
        span_days = max((max_date - min_date).days, 1)

        width = max(self.canvas.winfo_width(), 700)
        chart_w = width - self.LEFT_PAD - self.RIGHT_PAD
        px_per_day = chart_w / span_days

        # Axis: start and end date labels.
        self.canvas.create_text(self.LEFT_PAD, 16, anchor='w',
                                text=min_date.strftime('%Y-%m-%d'),
                                font=('TkDefaultFont', 8))
        self.canvas.create_text(self.LEFT_PAD + chart_w, 16, anchor='e',
                                text=max_date.strftime('%Y-%m-%d'),
                                font=('TkDefaultFont', 8))

        for idx, (name, d0, d1, status) in enumerate(tasks):
            y = self.TOP_PAD + idx * self.ROW_H
            self.canvas.create_text(8, y + self.ROW_H / 2, anchor='w',
                                    text=(name or '')[:22],
                                    font=('TkDefaultFont', 9))
            x0 = self.LEFT_PAD + (d0 - min_date).days * px_per_day
            x1 = self.LEFT_PAD + ((d1 - min_date).days + 1) * px_per_day
            color = status_colors.get(status, DEFAULT_COLOR)
            self.canvas.create_rectangle(x0, y + 4, x1, y + self.ROW_H - 4,
                                         fill=color, outline='#555555')

        total_h = self.TOP_PAD + len(tasks) * self.ROW_H + 20
        self.canvas.configure(scrollregion=(0, 0, width, total_h))


def build_timeline_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(_build_tasks(nb, db_getter), text='Tasks')
    nb.add(GanttView(nb, db_getter), text='Gantt Chart View')
    return nb
