"""Critical Path Method over the programme's tasks.

No tkinter, no database.

The timeline already lets tasks name a dependency, but the field was inert
free text — it drew nothing and computed nothing. This module turns those
links into the one answer a programme exists to give: **which tasks cannot slip
by a single day without pushing the whole job late.** Those are the tasks worth
guarding; everything else has float to absorb a bad week.

This pairs directly with the baseline work (`programme.py`). A slip on a task
with float costs nothing; the same slip on a critical task is exactly what runs
into liquidated damages. Knowing which is which is the difference between
worrying about the right task and worrying about all of them.

The method is standard CPM: order the tasks so every task follows its
predecessors, sweep forward for the earliest each can start and finish, sweep
back for the latest each can without delaying the end, and the slack between
the two is the float. Float of zero is the critical path.

Two honesty constraints:

* A **cycle** ("A waits for B, B waits for A") has no valid schedule. The
  module refuses to invent one — it returns the tasks caught in the loop and
  computes no floats, because a confident schedule built on a contradiction is
  worse than a clear "these dependencies contradict each other".
* A dependency naming a task that does not exist is **reported, not dropped**.
  Silently ignoring it would quietly shorten the critical path and understate
  the risk.
"""

from datetime import date, timedelta


def _num(value, default=0.0):
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _parse(value):
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _split_deps(text):
    """Free-text dependency field -> list of raw tokens.

    Split on commas, semicolons and newlines only, never on spaces — task
    names contain spaces ('Site clearance'), and splitting on them would turn
    one predecessor into several unresolved fragments.
    """
    if not text:
        return []
    parts = str(text).replace(';', ',').replace('\n', ',').split(',')
    return [p.strip() for p in parts if p.strip()]


def resolve_predecessors(tasks):
    """Turn each task's free-text ``dependency`` into predecessor ids.

    A token is matched first as an exact task id, then case-insensitively as a
    task name. ``tasks`` are dicts with id / task_name / dependency. Returns
    ``(resolved, unresolved)`` where ``resolved`` adds a ``predecessors`` list
    of ids and ``unresolved`` lists ``(task_id, token)`` that matched nothing —
    a self-reference counts as unresolved rather than a zero-length loop.
    """
    by_id = {str(t.get('id')): t.get('id') for t in tasks}
    by_name = {}
    for t in tasks:
        name = str(t.get('task_name', '') or '').strip().lower()
        if name:
            by_name.setdefault(name, t.get('id'))

    resolved, unresolved = [], []
    for t in tasks:
        preds = []
        for token in _split_deps(t.get('dependency')):
            target = by_id.get(token)
            if target is None:
                target = by_name.get(token.lower())
            if target is None or target == t.get('id'):
                unresolved.append((t.get('id'), token))
            elif target not in preds:
                preds.append(target)
        row = dict(t)
        row['predecessors'] = preds
        resolved.append(row)
    return resolved, unresolved


def task_duration(task):
    """Duration in days: the stated ``duration_days`` if given, else the
    inclusive span of start/end dates, else zero (a milestone)."""
    d = _num(task.get('duration_days'))
    if d > 0:
        return d
    s, e = _parse(task.get('start_date')), _parse(task.get('end_date'))
    if s and e and e >= s:
        return (e - s).days + 1
    return 0.0


def _topo_order(nodes, preds):
    """Kahn's algorithm. Returns ``(order, cycle)``; ``cycle`` is the set of
    ids that could not be ordered (empty when the graph is acyclic)."""
    succ = {n: [] for n in nodes}
    indeg = {n: 0 for n in nodes}
    for n in nodes:
        for p in preds[n]:
            if p in nodes:
                succ[p].append(n)
                indeg[n] += 1
    queue = [n for n in nodes if indeg[n] == 0]
    order = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for s in succ[n]:
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
    cycle = [n for n in nodes if n not in order]
    return order, cycle


def analyse(tasks):
    """Full CPM pass over resolved tasks (each with a ``predecessors`` list).

    Returns per-task early/late start & finish, total and free float, and a
    ``critical`` flag; plus the project duration, the critical task ids in
    order, and any ``cycle``. When a cycle exists no floats are computed — the
    schedule is contradictory and any numbers would be fiction.
    """
    nodes = [t.get('id') for t in tasks]
    task_by_id = {t.get('id'): t for t in tasks}
    preds = {t.get('id'): [p for p in t.get('predecessors', []) if p in task_by_id]
             for t in tasks}
    dur = {nid: task_duration(task_by_id[nid]) for nid in nodes}

    order, cycle = _topo_order(nodes, preds)
    if cycle:
        return {'tasks': {}, 'ordered': [], 'project_duration': None,
                'critical_ids': [], 'critical_path': [], 'cycle': cycle}

    succ = {n: [] for n in nodes}
    for n in nodes:
        for p in preds[n]:
            succ[p].append(n)

    es, ef = {}, {}
    for n in order:
        es[n] = max((ef[p] for p in preds[n]), default=0.0)
        ef[n] = es[n] + dur[n]
    project = max(ef.values(), default=0.0)

    lf, ls = {}, {}
    for n in reversed(order):
        lf[n] = min((ls[s] for s in succ[n]), default=project)
        ls[n] = lf[n] - dur[n]

    out = {}
    for n in nodes:
        total_float = round(ls[n] - es[n], 3)
        free_float = round(min((es[s] for s in succ[n]), default=project)
                           - ef[n], 3)
        out[n] = {
            'id': n, 'name': task_by_id[n].get('task_name', ''),
            'duration': round(dur[n], 3),
            'early_start': round(es[n], 3), 'early_finish': round(ef[n], 3),
            'late_start': round(ls[n], 3), 'late_finish': round(lf[n], 3),
            'total_float': total_float, 'free_float': max(free_float, 0.0),
            'critical': abs(total_float) < 1e-6,
        }
    critical_ids = [n for n in order if out[n]['critical']]
    return {
        'tasks': out,
        'ordered': order,
        'project_duration': round(project, 3),
        'critical_ids': critical_ids,
        'critical_path': [out[n]['name'] for n in critical_ids],
        'cycle': [],
    }


def schedule_from(tasks, project_start=None):
    """Convenience: resolve dependencies, run CPM, and (if a start date is
    given) map early start/finish to calendar dates. Returns the ``analyse``
    result plus ``unresolved`` and, per task, ``start_date``/``finish_date``."""
    resolved, unresolved = resolve_predecessors(tasks)
    result = analyse(resolved)
    result['unresolved'] = unresolved
    start = _parse(project_start)
    if start and not result['cycle']:
        for n, info in result['tasks'].items():
            info['start_date'] = (start + timedelta(
                days=int(info['early_start']))).isoformat()
            info['finish_date'] = (start + timedelta(
                days=max(int(info['early_finish']) - 1, 0))).isoformat()
    return result


def summarise(result):
    """Headline counts for a schedule view or a KPI feed."""
    result = result or {}
    if result.get('cycle'):
        return {'ok': False, 'cycle': len(result['cycle']),
                'critical': 0, 'total': 0, 'project_duration': None,
                'unresolved': len(result.get('unresolved', []))}
    tasks = result.get('tasks', {})
    return {
        'ok': True,
        'cycle': 0,
        'total': len(tasks),
        'critical': len(result.get('critical_ids', [])),
        'project_duration': result.get('project_duration'),
        'unresolved': len(result.get('unresolved', [])),
    }
