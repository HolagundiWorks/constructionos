"""Timeline / CPM read model for ``GET /api/timeline``.

No tkinter. Loads ``timeline_tasks`` for a project, runs ``cpm.schedule_from``,
and optionally a baseline-vs-actual programme position.
"""

import cpm
import programme


def _col(row, key, default=None):
    if row is None:
        return default
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


def load_tasks(conn, project_id):
    return [dict(r) for r in conn.execute(
        'SELECT * FROM timeline_tasks WHERE project_id = ? ORDER BY id',
        (int(project_id),))]


def project_schedule(conn, project_id):
    tasks = load_tasks(conn, project_id)
    proj = conn.execute(
        'SELECT start_date FROM projects WHERE id = ?', (int(project_id),)
    ).fetchone()
    return cpm.schedule_from(tasks, _col(proj, 'start_date'))


def project_delay_position(conn, project_id):
    proj = conn.execute(
        'SELECT * FROM projects WHERE id = ?', (int(project_id),)
    ).fetchone()
    if proj is None:
        return None
    tasks = load_tasks(conn, project_id)
    return programme.position(
        tasks,
        contract_value=_col(proj, 'contract_value', 0) or 0,
        ld_pct_per_week=_col(proj, 'ld_pct_per_week',
                             programme.DEFAULT_LD_PCT_PER_WEEK),
        cap_pct=_col(proj, 'ld_cap_pct', programme.DEFAULT_LD_CAP_PCT))


def worst_delay(conn):
    worst = None
    for r in conn.execute(
            "SELECT id, name FROM projects WHERE status != 'Closed'"):
        pos = project_delay_position(conn, r['id'])
        if not pos or not pos.get('baselined'):
            continue
        pos = dict(pos)
        pos['project_id'] = r['id']
        pos['project'] = r['name']
        if worst is None or pos['ld']['exposure'] > worst['ld']['exposure']:
            worst = pos
    return worst


def assemble(conn, project_id):
    """Full timeline payload for one project."""
    project_id = int(project_id)
    proj = conn.execute(
        'SELECT id, name, start_date, end_date, status, contract_value, '
        'ld_pct_per_week, ld_cap_pct FROM projects WHERE id = ?',
        (project_id,)).fetchone()
    if proj is None:
        return None
    tasks = load_tasks(conn, project_id)
    schedule = cpm.schedule_from(tasks, _col(proj, 'start_date'))
    summary = cpm.summarise(schedule)
    position = programme.position(
        tasks,
        contract_value=_col(proj, 'contract_value', 0) or 0,
        ld_pct_per_week=_col(proj, 'ld_pct_per_week',
                             programme.DEFAULT_LD_PCT_PER_WEEK),
        cap_pct=_col(proj, 'ld_cap_pct', programme.DEFAULT_LD_CAP_PCT))
    # Flatten CPM task map for JSON clients.
    cpm_tasks = []
    task_info = schedule.get('tasks') or {}
    for t in tasks:
        info = task_info.get(t['id']) or task_info.get(str(t['id'])) or {}
        variance = programme.task_variance(t)
        cpm_tasks.append({
            **t,
            'early_start': info.get('early_start'),
            'early_finish': info.get('early_finish'),
            'late_start': info.get('late_start'),
            'late_finish': info.get('late_finish'),
            'total_float': info.get('total_float'),
            'free_float': info.get('free_float'),
            'critical': bool(info.get('critical')),
            'cpm_start_date': info.get('start_date'),
            'cpm_finish_date': info.get('finish_date'),
            'variance': variance,
        })
    return {
        'project': dict(proj),
        'tasks': cpm_tasks,
        'summary': summary,
        'critical_path': schedule.get('critical_path') or [],
        'critical_ids': schedule.get('critical_ids') or [],
        'cycle': schedule.get('cycle') or [],
        'unresolved': [
            {'task_id': a, 'token': b}
            for a, b in (schedule.get('unresolved') or [])
        ],
        'position': position,
        'cols': [
            {'key': 'task_name', 'label': 'Task'},
            {'key': 'duration_days', 'label': 'Days', 'align': 'right'},
            {'key': 'start_date', 'label': 'Plan start'},
            {'key': 'end_date', 'label': 'Plan end'},
            {'key': 'total_float', 'label': 'Float', 'align': 'right'},
            {'key': 'critical', 'label': 'Critical'},
            {'key': 'pct_complete', 'label': '%', 'align': 'right'},
        ],
    }
