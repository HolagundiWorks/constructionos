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
from tkinter import ttk, messagebox

from ui_guard import can_write

import bill_export
import programme
import report_open
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
        # Actuals are recorded separately from the plan so that editing the
        # plan never quietly rewrites history.
        Field('actual_start', 'Actually Started'),
        Field('actual_end', 'Actually Finished'),
        # Recorded while the reason is still known — six months later nobody
        # remembers whether it was the drawings or the labour.
        Field('delay_cause', 'If late, whose cause', kind='combo',
              options=[''] + programme.CAUSES, default=''),
        Field('delay_note', 'Delay note', width=200),
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


class BaselineView(ttk.Frame):
    """Frozen plan versus where the job actually is, and what that costs.

    The freeze is the whole feature. Until the plan is frozen, editing a date
    destroys the evidence of what slipped; after it, the comparison can be made
    months later when somebody asks.
    """

    COLUMNS = ('task_name', 'baseline_finish', 'finish', 'finish_slip',
               'cause', 'status', 'note')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._pmap = {}
        self._rows = []
        self._position = {}
        self.project_var = tk.StringVar()
        self.headline_var = tk.StringVar()
        self.ld_var = tk.StringVar()
        self.claim_var = tk.StringVar()
        self._build_ui()
        self.reload_projects()

    def _build_ui(self):
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(top, text='Project').pack(side='left')
        self.project_combo = ttk.Combobox(top, textvariable=self.project_var,
                                          width=26, state='readonly')
        self.project_combo.pack(side='left', padx=6)
        self.project_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='left')
        ttk.Button(top, text='Freeze Baseline',
                   command=self.freeze).pack(side='left', padx=8)
        ttk.Button(top, text='Print / Export',
                   command=self.export).pack(side='left')

        for var, colour in ((self.headline_var, None),
                            (self.ld_var, '#b00020'),
                            (self.claim_var, '#226622')):
            kw = {'foreground': colour} if colour else {}
            ttk.Label(self, textvariable=var, wraplength=980, justify='left',
                      font=('TkDefaultFont', 10, 'bold'), **kw).pack(
                anchor='w', padx=10)

        headings = {'task_name': 'Task', 'baseline_finish': 'Planned Finish',
                    'finish': 'Now Finishing', 'finish_slip': 'Slip (days)',
                    'cause': 'Cause', 'status': 'Status', 'note': 'Note'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=200 if col in ('task_name', 'note')
                             else 110, anchor='w')
        self.tree.tag_configure('late', background='#ffe3e3')
        self.tree.tag_configure('claim', background='#e4f1e8')
        self.tree.tag_configure('unattributed', background='#fff4e5')
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        ttk.Label(self, text=(
            'Green rows are delays with a cause that normally supports an '
            'extension of time. Amber rows are late with no cause recorded — '
            'those are days you cannot claim for, and the reason is easiest to '
            'establish now rather than at the final account. Liquidated '
            'damages are an estimate on the terms set against the project, not '
            'a statement of what will be charged.'),
            foreground='#666', wraplength=980, justify='left') \
            .pack(anchor='w', padx=10, pady=(0, 8))

    def reload_projects(self):
        conn = self.db_getter()
        try:
            opts = [(r['id'], r['name']) for r in conn.execute(
                'SELECT id, name FROM projects ORDER BY id DESC')]
        finally:
            conn.close()
        self._pmap = {'{} - {}'.format(i, n): i for i, n in opts}
        self.project_combo['values'] = list(self._pmap)
        if self._pmap and not self.project_var.get():
            self.project_var.set(next(iter(self._pmap)))
        self.refresh()

    def _project_id(self):
        return self._pmap.get(self.project_var.get().strip())

    def _tasks(self, conn, pid):
        return [dict(r) for r in conn.execute(
            'SELECT * FROM timeline_tasks WHERE project_id = ? '
            'ORDER BY start_date, id', (pid,))]

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        pid = self._project_id()
        if pid is None:
            self.headline_var.set('No project selected.')
            self.ld_var.set(''); self.claim_var.set('')
            return
        conn = self.db_getter()
        try:
            tasks = self._tasks(conn, pid)
            proj = conn.execute('SELECT * FROM projects WHERE id = ?',
                                (pid,)).fetchone()
        finally:
            conn.close()

        value = _col(proj, 'contract_value', 0) or _col(proj, 'budget', 0)
        pos = programme.position(
            tasks, contract_value=value,
            eot_granted_days=_col(proj, 'eot_granted_days', 0),
            pct_per_week=_col(proj, 'ld_pct_per_week',
                              programme.DEFAULT_LD_PCT_PER_WEEK),
            cap_pct=_col(proj, 'ld_cap_pct', programme.DEFAULT_LD_CAP_PCT))
        self._position = pos

        self._rows = [programme.task_variance(t) for t in tasks]
        for v in self._rows:
            slip = v['finish_slip']
            tag = ''
            if slip is not None and slip > 0:
                tag = ('claim' if v['cause'] in programme.EXCUSABLE
                       else 'unattributed' if not v['cause'] else 'late')
            self.tree.insert('', 'end', tags=(tag,), values=(
                v['task_name'], v['baseline_finish'] or '—',
                v['finish'] or '—',
                '—' if slip is None else ('+{}'.format(slip) if slip > 0
                                          else str(slip)),
                v['cause'] or '—', v['status'], v['note']))

        if not tasks:
            self.headline_var.set('No tasks on this project.')
            self.ld_var.set(''); self.claim_var.set('')
            return
        if not pos['baselined']:
            self.headline_var.set(
                'No baseline frozen yet — press Freeze Baseline to record '
                'today\'s plan as the one you will be measured against.')
            self.ld_var.set(''); self.claim_var.set('')
            return

        total = pos['total_delay_days']
        self.headline_var.set(
            'Planned finish {}   ->   now finishing {}   =   {} day(s) '
            'delay.   {} of {} tasks late.{}'.format(
                pos['baseline_finish'] or '—', pos['forecast_finish'] or '—',
                total if total is not None else '?', pos['late_tasks'],
                pos['baselined'],
                '   {} not baselined.'.format(pos['unbaselined'])
                if pos['unbaselined'] else ''))

        ld = pos['ld']
        if pos['net_delay_days'] > 0 and ld['exposure'] > 0:
            self.ld_var.set(
                'Liquidated damages exposure {:,.2f} — {} week(s) at {:g}% of '
                '{:,.2f}{}. Net delay {} day(s) after {} day(s) already '
                'granted.'.format(
                    ld['exposure'], ld['weeks_charged'], ld['pct_per_week'],
                    value, ' (at the {:g}% cap)'.format(ld['cap_pct'])
                    if ld['at_cap'] else '',
                    pos['net_delay_days'], pos['eot_granted_days']))
        elif pos['net_delay_days'] > 0:
            self.ld_var.set(
                'Net delay {} day(s). No contract value set on this project, '
                'so no exposure can be estimated.'.format(pos['net_delay_days']))
        else:
            self.ld_var.set('No net delay — no liquidated damages exposure.')

        bits = []
        if pos['claimable_days']:
            bits.append(
                '{} day(s) of delay have a cause that normally supports an '
                'extension of time. If granted, exposure falls to {:,.2f}.'
                .format(pos['claimable_days'], pos['exposure_if_claim_succeeds']))
        if pos['unattributed_tasks']:
            bits.append(
                '{} late task(s) have no cause recorded — days you cannot '
                'claim for.'.format(pos['unattributed_tasks']))
        self.claim_var.set('   '.join(bits))

    def freeze(self):
        """Record today's plan as the baseline. Warns hard before overwriting."""
        if not can_write():
            return
        pid = self._project_id()
        if pid is None:
            messagebox.showinfo('No project', 'Select a project first.')
            return
        conn = self.db_getter()
        try:
            tasks = self._tasks(conn, pid)
        finally:
            conn.close()
        payload = programme.baseline_payload(tasks)
        if not payload:
            messagebox.showinfo(
                'Nothing to freeze',
                'No task on this project has a planned finish date yet.')
            return

        warn = programme.rebaseline_warning(tasks)
        if warn['already_baselined']:
            # Re-baselining makes the slip disappear, and with it the claim.
            # Quote the real figures rather than a caution nobody reads.
            if not messagebox.askyesno(
                    'Overwrite the existing baseline?',
                    '{} task(s) are already baselined.\n\n'
                    'Re-freezing replaces the original plan with today\'s '
                    'dates. That erases {} day(s) of recorded delay and {} '
                    'day(s) currently supporting an extension-of-time claim — '
                    'the record that the delay happened at all.\n\n'
                    'Only do this if the programme has been formally revised '
                    'and accepted.\n\nOverwrite?'.format(
                        warn['already_baselined'], warn['delay_days_erased'],
                        warn['claimable_days_erased'])):
                return

        conn = self.db_getter()
        try:
            conn.executemany(
                'UPDATE timeline_tasks SET baseline_start = ?, '
                'baseline_end = ? WHERE id = ?',
                [(s, e, tid) for tid, s, e in payload])
            conn.commit()
        finally:
            conn.close()
        self.refresh()
        messagebox.showinfo(
            'Baseline frozen',
            '{} task(s) baselined. Changes to the plan from now on will show '
            'as slip against this.'.format(len(payload)))

    def export(self):
        if not self._rows:
            messagebox.showinfo('Nothing to export', 'No tasks to report.')
            return
        rows = [(v['task_name'], v['baseline_finish'] or '-',
                 v['finish'] or '-',
                 '-' if v['finish_slip'] is None else v['finish_slip'],
                 v['cause'] or '-', v['status'], v['note'])
                for v in self._rows]
        html = bill_export.build_statement_html(
            'Programme — baseline versus actual',
            ['Project: {}'.format(self.project_var.get()),
             self.headline_var.get(), self.ld_var.get(), self.claim_var.get(),
             'Liquidated damages are an estimate on the terms recorded '
             'against this project, not a statement of what will be charged. '
             'Days shown as claimable are what the record supports asking '
             'for; only the employer grants an extension.'],
            ['Task', 'Planned Finish', 'Now Finishing', 'Slip (days)',
             'Cause', 'Status', 'Note'],
            rows, summary=self.headline_var.get())
        report_open.save_and_open_html(html, 'programme_baseline.html')


def _col(row, key, default=None):
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


def project_delay_position(conn, project_id):
    """Programme position for one project — used by the KPI dashboard."""
    tasks = [dict(r) for r in conn.execute(
        'SELECT * FROM timeline_tasks WHERE project_id = ?', (project_id,))]
    proj = conn.execute('SELECT * FROM projects WHERE id = ?',
                        (project_id,)).fetchone()
    value = _col(proj, 'contract_value', 0) or _col(proj, 'budget', 0)
    return programme.position(
        tasks, contract_value=value,
        eot_granted_days=_col(proj, 'eot_granted_days', 0),
        pct_per_week=_col(proj, 'ld_pct_per_week',
                          programme.DEFAULT_LD_PCT_PER_WEEK),
        cap_pct=_col(proj, 'ld_cap_pct', programme.DEFAULT_LD_CAP_PCT))


def worst_delay(conn):
    """The project with the largest LD exposure, for the KPI dashboard."""
    worst = None
    for r in conn.execute("SELECT id, name FROM projects "
                          "WHERE status != 'Closed'"):
        pos = project_delay_position(conn, r['id'])
        if not pos['baselined']:
            continue
        pos['project'] = r['name']
        if worst is None or pos['ld']['exposure'] > worst['ld']['exposure']:
            worst = pos
    return worst


def build_timeline_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(_build_tasks(nb, db_getter), text='Tasks')
    nb.add(BaselineView(nb, db_getter), text='Baseline vs Actual')
    nb.add(GanttView(nb, db_getter), text='Gantt Chart View')
    return nb
