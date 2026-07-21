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

from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

from ui_guard import can_write

import bill_export
import cpm
import isodate
import programme
import report_open
import scheduler
import theme
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


def task_options(conn):
    """Every timeline task, for the WBS-parent picker."""
    return [(r['id'], r['task_name']) for r in conn.execute(
        'SELECT id, task_name FROM timeline_tasks ORDER BY task_name')]


def _split_holidays(text):
    """A holiday string ('2026-01-26, 2026-08-15') to a list of ISO dates."""
    return [tok.strip() for tok in scheduler._split(text or '') if tok.strip()]


def _wbs_depth(info, tmap):
    """Outline depth of each task from its parent_id chain (0 = top level)."""
    depth = {}

    def d(i, guard):
        if i in depth:
            return depth[i]
        pid = (tmap.get(i) or {}).get('parent_id')
        if pid in info and pid != i and pid not in guard:
            depth[i] = d(pid, guard | {i}) + 1
        else:
            depth[i] = 0
        return depth[i]

    for i in info:
        d(i, set())
    return depth


def _build_tasks(parent, db_getter):
    fields = [
        Field('project_id', 'Project', kind='fk', options_func=project_options),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('task_name', 'Task'),
        Field('parent_id', 'Parent (WBS)', kind='fk', options_func=task_options),
        Field('start_date', 'Start (YYYY-MM-DD)'),
        Field('end_date', 'End (YYYY-MM-DD)'),
        Field('duration_days', 'Duration (working days)', kind='number',
              default='0'),
        # MS-Project-style typed predecessors: "3FS+2, 5SS" — resolved by id or
        # task name, scheduled on the project's working calendar. A milestone is
        # a task of duration 0.
        Field('dependency', 'Predecessors (e.g. 3FS+2)'),
        Field('pct_complete', '% Complete', kind='number', default='0'),
        Field('status', 'Status', kind='combo',
              options=TASK_STATUSES, default='Not Started'),
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
    """A working-calendar Gantt driven by ``scheduler``: bars auto-placed from
    typed dependencies, the critical path in red, % complete shaded, milestones
    as diamonds, the baseline underneath, dependency arrows, weekend/holiday
    shading and a today line. "Auto-schedule" writes the computed dates back to
    the tasks."""

    ROW_H = 26
    LEFT_PAD = 220
    TOP_PAD = 48
    RIGHT_PAD = 40

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._project_map = {}

        controls = ttk.Frame(self)
        controls.pack(fill='x', padx=8, pady=6)
        ttk.Label(controls, text='Project').pack(side='left')
        self.project_var = tk.StringVar()
        self.project_combo = ttk.Combobox(controls, textvariable=self.project_var,
                                          width=26, state='readonly')
        self.project_combo.pack(side='left', padx=4)
        self.project_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        ttk.Button(controls, text='Refresh', command=self.refresh) \
            .pack(side='left', padx=6)
        ttk.Button(controls, text='Auto-schedule', style='Accent.TButton',
                   command=self.auto_schedule).pack(side='left', padx=(2, 6))
        self.headline = ttk.Label(controls, text='', style='Muted.TLabel')
        self.headline.pack(side='left', padx=8)

        wrap = ttk.Frame(self); wrap.pack(fill='both', expand=True, padx=8, pady=6)
        self.canvas = tk.Canvas(wrap, bg=theme.palette()['surface'],
                                highlightthickness=0)
        vsb = ttk.Scrollbar(wrap, orient='vertical', command=self.canvas.yview)
        hsb = ttk.Scrollbar(wrap, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.refresh()

    def _pid(self):
        raw = self.project_var.get()
        return self._project_map.get(raw)

    def _load(self, pid):
        conn = self.db_getter()
        try:
            popts = [(r['id'], r['name']) for r in conn.execute(
                'SELECT id, name FROM projects ORDER BY name')]
            self._project_map = {'{} - {}'.format(i, n): i for i, n in popts}
            self.project_combo['values'] = list(self._project_map.keys())
            if pid is None and popts:
                pid = popts[0][0]
                self.project_var.set('{} - {}'.format(popts[0][0], popts[0][1]))
            project = tasks = None
            if pid is not None:
                project = conn.execute('SELECT * FROM projects WHERE id = ?',
                                       (pid,)).fetchone()
                tasks = [dict(r) for r in conn.execute(
                    'SELECT * FROM timeline_tasks WHERE project_id = ? '
                    'ORDER BY start_date, id', (pid,))]
        finally:
            conn.close()
        return project, tasks

    def refresh(self):
        project, tasks = self._load(self._pid())
        self.canvas.delete('all')
        if not project:
            self.headline.configure(text='')
            self.canvas.create_text(16, 20, anchor='w', text='No project yet.',
                                    fill=theme.palette()['muted'])
            return
        if not tasks:
            self.headline.configure(text='')
            self.canvas.create_text(16, 20, anchor='w',
                                    text='No tasks on this project yet — add '
                                         'them on the Tasks sub-tab.',
                                    fill=theme.palette()['muted'])
            return
        start = project['start_date'] or _col(project, 'start_date')
        result = scheduler.schedule(
            tasks, project_start=start,
            work_week=_col(project, 'work_week', scheduler.DEFAULT_WORK_WEEK),
            holidays=_split_holidays(_col(project, 'holidays')))
        if result['cycle']:
            self.headline.configure(text='Dependency loop — cannot schedule.')
            names = {t['id']: t.get('task_name') for t in tasks}
            self.canvas.create_text(
                16, 20, anchor='w', fill=theme.palette()['error'],
                text='These tasks depend on each other in a circle: {}'.format(
                    ', '.join(str(names.get(i, i)) for i in result['cycle'])))
            return
        self._draw(result, tasks, project)

    # -------------------------------------------------------------- drawing
    def _draw(self, result, tasks, project):
        pal = theme.palette()
        info = result['tasks']
        tmap = {t['id']: t for t in tasks}
        resolved, _un = scheduler.resolve(tasks)
        preds_map = {t['id']: t.get('preds', []) for t in resolved}
        depth = _wbs_depth(info, tmap)
        cal = scheduler.Calendar(
            _col(project, 'work_week', scheduler.DEFAULT_WORK_WEEK),
            _split_holidays(_col(project, 'holidays')))

        rows = sorted(info.values(), key=lambda t: (t['es'], t['id']))
        dates = [d for t in info.values()
                 for d in (t['start_date'], t['finish_date']) if d]
        for t in tasks:               # include baselines in the span
            for k in ('baseline_start', 'baseline_end'):
                if t.get(k):
                    dates.append(t[k])
        dmin = min(isodate.parse(d) for d in dates)
        dmax = max(isodate.parse(d) for d in dates)
        span = max((dmax - dmin).days, 1)

        avail = max(self.canvas.winfo_width() - self.LEFT_PAD - self.RIGHT_PAD,
                    520)
        ppd = min(16.0, max(3.0, avail / span))
        chart_w = self.LEFT_PAD + span * ppd + self.RIGHT_PAD

        def x_of(d):
            return self.LEFT_PAD + (isodate.parse(d) - dmin).days * ppd

        n = len(rows)
        height = self.TOP_PAD + n * self.ROW_H + 24

        # weekend / holiday shading + month gridlines
        d = dmin
        while d <= dmax:
            if not cal.is_working(d):
                x = self.LEFT_PAD + (d - dmin).days * ppd
                self.canvas.create_rectangle(
                    x, self.TOP_PAD - 6, x + ppd, height - 12,
                    fill=pal['canvas'], outline='')
            if d.day == 1 or d == dmin:
                x = self.LEFT_PAD + (d - dmin).days * ppd
                self.canvas.create_line(x, self.TOP_PAD - 6, x, height - 12,
                                        fill=pal['hairline'])
                self.canvas.create_text(x + 2, 14, anchor='w',
                                        text=d.strftime('%b %Y'),
                                        fill=pal['muted'],
                                        font=('TkDefaultFont', 8))
            d += timedelta(days=1)

        # today line
        today = date.today()
        if dmin <= today <= dmax:
            x = self.LEFT_PAD + (today - dmin).days * ppd
            self.canvas.create_line(x, self.TOP_PAD - 8, x, height - 12,
                                    fill=pal['error'], dash=(3, 3))
            self.canvas.create_text(x, self.TOP_PAD - 14, text='today',
                                    fill=pal['error'], font=('TkDefaultFont', 7))

        row_y = {}
        for idx, t in enumerate(rows):
            row_y[t['id']] = self.TOP_PAD + idx * self.ROW_H

        # dependency arrows (behind bars)
        for succ in rows:
            for pid, typ, _lag in preds_map.get(succ['id'], []):
                if pid not in info:
                    continue
                self._arrow(info[pid], succ, typ, x_of, row_y, pal)

        # bars
        for idx, t in enumerate(rows):
            y = self.TOP_PAD + idx * self.ROW_H
            name = (t['name'] or '')
            indent = 6 + depth.get(t['id'], 0) * 14
            summ = t.get('is_summary')
            self.canvas.create_text(
                indent, y + self.ROW_H / 2, anchor='w', text=name[:26],
                fill=pal['ink'],
                font=('TkDefaultFont', 9, 'bold' if summ else 'normal'))

            if not t['start_date'] or not t['finish_date']:
                continue
            x0 = x_of(t['start_date'])
            x1 = max(x_of(t['finish_date']) + ppd, x0 + 3)
            top, bot = y + 5, y + self.ROW_H - 7
            # baseline (thin, underneath) if present
            bt = tmap.get(t['id'], {})
            if bt.get('baseline_start') and bt.get('baseline_end'):
                bx0 = x_of(bt['baseline_start'])
                bx1 = x_of(bt['baseline_end']) + ppd
                self.canvas.create_rectangle(bx0, bot, bx1, bot + 4,
                                             fill=pal['muted'], outline='')
            if t['milestone']:
                cx, cy = x0, (top + bot) / 2
                r = 6
                self.canvas.create_polygon(cx, cy - r, cx + r, cy, cx, cy + r,
                                           cx - r, cy, fill=pal['ink'],
                                           outline='')
                continue
            base = pal['error'] if t['critical'] else pal['info']
            if summ:
                # summary bracket rather than a solid bar
                self.canvas.create_rectangle(x0, top + 3, x1, top + 6,
                                             fill=pal['ink'], outline='')
                self.canvas.create_polygon(x0, top + 3, x0, top + 11,
                                           x0 + 6, top + 3, fill=pal['ink'])
                self.canvas.create_polygon(x1, top + 3, x1, top + 11,
                                           x1 - 6, top + 3, fill=pal['ink'])
            else:
                self.canvas.create_rectangle(x0, top, x1, bot, fill=base,
                                             outline=pal['hairline'])
                pct = t['pct'] or 0
                if pct > 0:
                    px = x0 + (x1 - x0) * min(pct, 100) / 100.0
                    self.canvas.create_rectangle(
                        x0, top + (bot - top) * 0.30, px,
                        bot - (bot - top) * 0.30, fill=pal['ink'], outline='')

        # headline
        s = scheduler.summarise(result)
        self.headline.configure(
            text='Finish {}   ·   {} critical   ·   {:.0f}% complete'.format(
                s['project_finish'] or '—', s['critical'], s['pct_complete']))
        self.canvas.configure(scrollregion=(0, 0, chart_w, height))

    def _arrow(self, pred, succ, typ, x_of, row_y, pal):
        if not pred['finish_date'] or not succ['start_date']:
            return
        # FS/FF start from predecessor finish; SS/SF from its start.
        px = x_of(pred['finish_date']) + (0 if typ in ('SS', 'SF') else 6)
        if typ in ('SS', 'SF'):
            px = x_of(pred['start_date'])
        py = row_y[pred['id']] + self.ROW_H / 2
        # FS/SS land on successor start; FF/SF on its finish.
        sx = x_of(succ['start_date']) if typ in ('FS', 'SS') \
            else x_of(succ['finish_date'])
        sy = row_y[succ['id']] + self.ROW_H / 2
        mid = max(px + 6, sx - 8)
        self.canvas.create_line(px, py, mid, py, mid, sy, sx, sy,
                                fill=pal['helper'], width=1,
                                arrow='last', arrowshape=(6, 7, 2))

    def auto_schedule(self):
        if not can_write():
            return
        pid = self._pid()
        project, tasks = self._load(pid)
        if not project or not tasks:
            return
        start = project['start_date']
        if not start:
            messagebox.showinfo(
                'Set a project start date',
                'Give this project a Start Date (Project Management › Projects) '
                'so the schedule has an anchor to compute from.')
            return
        result = scheduler.schedule(
            tasks, project_start=start,
            work_week=_col(project, 'work_week', scheduler.DEFAULT_WORK_WEEK),
            holidays=_split_holidays(_col(project, 'holidays')))
        if result['cycle']:
            messagebox.showerror('Cannot schedule',
                                 'Fix the dependency loop first.')
            return
        if not messagebox.askyesno(
                'Auto-schedule',
                'Compute start/finish dates for every task from its '
                'predecessors and the working calendar, and write them onto the '
                'tasks? Existing dates will be overwritten (baselines and '
                'actuals are not touched).'):
            return
        conn = self.db_getter()
        try:
            for tid, ti in result['tasks'].items():
                if ti['start_date'] and ti['finish_date']:
                    conn.execute(
                        'UPDATE timeline_tasks SET start_date = ?, end_date = ? '
                        'WHERE id = ?',
                        (ti['start_date'], ti['finish_date'], tid))
            conn.commit()
        finally:
            conn.close()
        self.refresh()


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
        self.tree.tag_configure('late', background=theme.wash('bad'))
        self.tree.tag_configure('claim', background=theme.wash('good'))
        self.tree.tag_configure('unattributed', background=theme.wash('warn'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        ttk.Label(self, text=(
            'Green rows are delays with a cause that normally supports an '
            'extension of time. Amber rows are late with no cause recorded — '
            'those are days you cannot claim for, and the reason is easiest to '
            'establish now rather than at the final account. Liquidated '
            'damages are an estimate on the terms set against the project, not '
            'a statement of what will be charged.'),
            foreground=theme.palette()['muted'], wraplength=980, justify='left') \
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


class CriticalPathView(ttk.Frame):
    """Which tasks cannot slip without delaying the whole job.

    Reads each task's dependency field (free text — task names or ids,
    separated by commas), runs the critical path method, and shows the float
    on every task. Zero float is the critical path: guard those, the rest have
    slack. Cycles and dependencies that name a missing task are surfaced, not
    swallowed, because a schedule that hides its own contradictions is worse
    than one that admits them.
    """

    COLUMNS = ('task_name', 'duration', 'start', 'finish', 'total_float',
               'free_float', 'critical')

    def __init__(self, parent, db_getter):
        super().__init__(parent)
        self.db_getter = db_getter
        self._pmap = {}
        self._rows = []
        self.project_var = tk.StringVar()
        self.headline_var = tk.StringVar()
        self.warn_var = tk.StringVar()
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
        ttk.Button(top, text='Print / Export',
                   command=self.export).pack(side='left', padx=6)

        ttk.Label(self, textvariable=self.headline_var,
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10)
        ttk.Label(self, textvariable=self.warn_var, foreground=theme.palette()['error'],
                  wraplength=980, justify='left').pack(anchor='w', padx=10)

        headings = {'task_name': 'Task', 'duration': 'Days', 'start': 'Earliest Start',
                    'finish': 'Earliest Finish', 'total_float': 'Total Float',
                    'free_float': 'Free Float', 'critical': 'On Critical Path'}
        self.tree = ttk.Treeview(self, columns=self.COLUMNS, show='headings')
        for col in self.COLUMNS:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=220 if col == 'task_name' else 110,
                             anchor='w')
        self.tree.tag_configure('critical', background=theme.wash('bad'))
        self.tree.pack(fill='both', expand=True, padx=8, pady=4)

        ttk.Label(self, text=(
            'Total float is how many days a task can slip before the project '
            'end moves; free float is how far it can slip before disturbing '
            'the next task. A task on the critical path has zero of both — a '
            'day lost there is a day lost on the whole job, and the day that '
            'runs into liquidated damages. Set a task\'s Dependency to the '
            'name(s) of the task(s) it waits for, separated by commas.'),
            foreground=theme.palette()['muted'], wraplength=980, justify='left') \
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

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = []
        pid = self._project_id()
        if pid is None:
            self.headline_var.set('No project selected.')
            self.warn_var.set('')
            return
        conn = self.db_getter()
        try:
            tasks = [dict(r) for r in conn.execute(
                'SELECT * FROM timeline_tasks WHERE project_id = ? '
                'ORDER BY start_date, id', (pid,))]
            proj = conn.execute('SELECT start_date FROM projects WHERE id = ?',
                                (pid,)).fetchone()
        finally:
            conn.close()

        result = cpm.schedule_from(tasks, _col(proj, 'start_date'))
        s = cpm.summarise(result)

        if not tasks:
            self.headline_var.set('No tasks on this project.')
            self.warn_var.set('')
            return
        if result['cycle']:
            names = ', '.join(t['task_name'] for t in tasks
                              if t['id'] in result['cycle'])
            self.headline_var.set('Cannot compute a schedule — the '
                                  'dependencies contradict each other.')
            self.warn_var.set('These tasks depend on each other in a loop: {}. '
                              'Fix the dependency chain and refresh.'.format(names))
            return

        # order tasks by early start for reading
        ordered = sorted(result['tasks'].values(),
                         key=lambda v: (v['early_start'], v['name']))
        for v in ordered:
            self._rows.append(v)
            self.tree.insert('', 'end', tags=('critical',) if v['critical'] else (),
                             values=(
                v['name'], '{:g}'.format(v['duration']),
                v.get('start_date', '{:g}'.format(v['early_start'])),
                v.get('finish_date', '{:g}'.format(v['early_finish'])),
                '{:g}'.format(v['total_float']), '{:g}'.format(v['free_float']),
                'YES' if v['critical'] else ''))

        self.headline_var.set(
            'Project duration {:g} days.   {} of {} task(s) on the critical '
            'path.'.format(s['project_duration'], s['critical'], s['total']))
        if s['unresolved']:
            miss = '; '.join('"{}" (on {})'.format(
                tok, next((t['task_name'] for t in tasks if t['id'] == tid), tid))
                for tid, tok in result['unresolved'][:5])
            self.warn_var.set('{} dependency reference(s) matched no task and '
                              'were ignored: {}. The critical path may be '
                              'understated until these are fixed.'.format(
                                  s['unresolved'], miss))
        else:
            self.warn_var.set('')

    def export(self):
        if not self._rows:
            messagebox.showinfo('Nothing to export', 'No schedule to report.')
            return
        rows = [(v['name'], '{:g}'.format(v['duration']),
                 v.get('start_date', '{:g}'.format(v['early_start'])),
                 v.get('finish_date', '{:g}'.format(v['early_finish'])),
                 '{:g}'.format(v['total_float']), '{:g}'.format(v['free_float']),
                 'YES' if v['critical'] else '') for v in self._rows]
        html = bill_export.build_statement_html(
            'Critical path — {}'.format(self.project_var.get()),
            [self.headline_var.get(), self.warn_var.get() or ''],
            ['Task', 'Days', 'Earliest Start', 'Earliest Finish',
             'Total Float', 'Free Float', 'Critical'],
            rows, summary=self.headline_var.get())
        report_open.save_and_open_html(html, 'critical_path.html')


def project_schedule(conn, project_id):
    """CPM result for one project — used by the KPI dashboard."""
    tasks = [dict(r) for r in conn.execute(
        'SELECT * FROM timeline_tasks WHERE project_id = ?', (project_id,))]
    proj = conn.execute('SELECT start_date FROM projects WHERE id = ?',
                        (project_id,)).fetchone()
    return cpm.schedule_from(tasks, _col(proj, 'start_date'))


def build_timeline_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(_build_tasks(nb, db_getter), text='Tasks')
    nb.add(BaselineView(nb, db_getter), text='Baseline vs Actual')
    nb.add(CriticalPathView(nb, db_getter), text='Critical Path')
    nb.add(GanttView(nb, db_getter), text='Gantt Chart View')
    return nb
