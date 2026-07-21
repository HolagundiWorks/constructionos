"""A working-calendar scheduling engine — the MS-Project core, in pure stdlib.

``cpm.py`` gives a finish-to-start critical path on raw calendar-day offsets.
This is the richer engine the Gantt runs on:

* a **working calendar** — a work-week (e.g. Mon–Sat for a 6-day site) plus a
  holiday list, so durations are *working* days and dates skip Sundays and
  holidays;
* **typed dependencies** — ``FS`` / ``SS`` / ``FF`` / ``SF`` with a **lag**
  (± working days), written on the task the MS-Project way, e.g. ``3FS+2`` (start
  2 working days after task 3 finishes), ``5SS``, ``7FF-1``;
* **auto-scheduling** — a forward pass places every task from the project start
  date honouring its predecessors and the calendar; a backward pass gives late
  dates, **total/free float** and the **critical path**;
* **% complete** and a **WBS** roll-up so a parent (summary) task spans its
  children and shows their weighted progress.

The scheduling maths runs in **working-day index space** (0 = the first working
day on/after the project start), which keeps the forward/backward passes to the
same well-worn CPM formulas as ``cpm.py`` — only the mapping to real dates knows
about weekends and holidays. No tkinter, no DB: ``schedule(...)`` takes plain
task dicts and returns a plain result, so it is fully unit-testable.
"""

from datetime import timedelta

import isodate

FS, SS, FF, SF = 'FS', 'SS', 'FF', 'SF'
TYPES = (FS, SS, FF, SF)

# Mon..Sun, '1' = working. Default: 6-day week (Sunday off) — the common Indian
# construction pattern.
DEFAULT_WORK_WEEK = '1111110'
_EPS = 1e-6


# --------------------------------------------------------------- calendar
class Calendar:
    """A work-week + holidays, and the working-day arithmetic on top."""

    def __init__(self, work_week=DEFAULT_WORK_WEEK, holidays=None):
        ww = str(work_week or '').strip()
        if len(ww) != 7 or set(ww) - set('01') or '1' not in ww:
            ww = DEFAULT_WORK_WEEK
        self.work = [c == '1' for c in ww]          # index 0 = Monday
        self.holidays = set()
        for h in holidays or []:
            d = isodate.parse(h) if isinstance(h, str) else h
            if d is not None:
                self.holidays.add(d)

    def is_working(self, d):
        return self.work[d.weekday()] and d not in self.holidays

    def next_working(self, d):
        while not self.is_working(d):
            d += timedelta(days=1)
        return d

    def working_list(self, start, count):
        """The first ``count`` working days on/after ``start`` (a date list)."""
        out = []
        d = self.next_working(start)
        while len(out) < count:
            out.append(d)
            d += timedelta(days=1)
            d = self.next_working(d)
        return out


# ------------------------------------------------------------- predecessors
def parse_predecessors(text):
    """Parse an MS-Project predecessor string into ``(ref, type, lag)`` tuples.

    ``ref`` is the raw id-or-name token; ``type`` one of FS/SS/FF/SF (FS default);
    ``lag`` an integer number of working days (0 default, may be negative).
    ``'3FS+2, 5SS-1; 7'`` -> ``[('3','FS',2), ('5','SS',-1), ('7','FS',0)]``.
    """
    out = []
    for raw in _split(text):
        token = raw.strip()
        if not token:
            continue
        typ, lag = FS, 0
        # trailing signed lag
        i = len(token)
        while i > 0 and (token[i - 1].isdigit()
                         or (token[i - 1] in '+-' and i >= 2
                             and token[i - 2] not in '+-')):
            i -= 1
        # find a +/- that begins the lag
        lag_str = ''
        for j in range(len(token) - 1, -1, -1):
            if token[j] in '+-':
                tail = token[j:]
                if tail[1:].isdigit():
                    lag_str = tail
                    token = token[:j]
                break
            if not token[j].isdigit():
                break
        if lag_str:
            try:
                lag = int(lag_str)
            except ValueError:
                lag = 0
        up = token.upper()
        for t in TYPES:
            if up.endswith(t):
                typ = t
                token = token[:-2]
                break
        ref = token.strip()
        if ref:
            out.append((ref, typ, lag))
    return out


def _split(text):
    if not text:
        return []
    out, cur = [], ''
    for ch in str(text):
        if ch in ',;\n':
            out.append(cur); cur = ''
        else:
            cur += ch
    out.append(cur)
    return out


def resolve(tasks):
    """Attach a ``preds`` list of ``(pred_id, type, lag)`` to each task, from its
    ``dependency`` string. Returns ``(resolved, unresolved)`` where unresolved is
    ``[(task_id, token)]`` for references that match no id or name."""
    by_id = {}
    by_name = {}
    for t in tasks:
        tid = t.get('id')
        by_id[str(tid)] = tid
        name = (t.get('task_name') or '').strip().lower()
        if name:
            by_name.setdefault(name, tid)
    resolved, unresolved = [], []
    for t in tasks:
        preds = []
        for ref, typ, lag in parse_predecessors(t.get('dependency')):
            pid = by_id.get(ref.strip())
            if pid is None:
                pid = by_name.get(ref.strip().lower())
            if pid is None or pid == t.get('id'):
                unresolved.append((t.get('id'), ref))
                continue
            preds.append((pid, typ, lag))
        c = dict(t)
        c['preds'] = preds
        resolved.append(c)
    return resolved, unresolved


# --------------------------------------------------------------- durations
def duration_days(task):
    """A task's duration in **working days**. ``duration_days`` if > 0, else the
    inclusive span of its dates in working days, else 0 (a milestone)."""
    d = _num(task.get('duration_days'))
    if d and d > 0:
        return float(d)
    s = isodate.parse(task.get('start_date'))
    e = isodate.parse(task.get('end_date'))
    if s and e and e >= s:
        return float((e - s).days + 1)
    return 0.0


def is_milestone(task):
    return duration_days(task) <= 0


# --------------------------------------------------------------- topo order
def _topo(ids, preds):
    indeg = {i: 0 for i in ids}
    succ = {i: [] for i in ids}
    for i in ids:
        for p, _t, _l in preds.get(i, []):
            if p in indeg:
                indeg[i] += 1
                succ[p].append(i)
    queue = [i for i in ids if indeg[i] == 0]
    order = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for s in succ[n]:
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
    cycle = [i for i in ids if i not in order]
    return order, succ, cycle


# --------------------------------------------------------------- the engine
def schedule(tasks, project_start=None, work_week=DEFAULT_WORK_WEEK,
             holidays=None):
    """Auto-schedule ``tasks`` from ``project_start`` on a working calendar.

    Returns a dict: ``{'tasks': {id: info}, 'ordered', 'cycle', 'unresolved',
    'project_finish', 'critical_ids', 'finish_index'}``. Each ``info`` carries
    ``start_date``/``finish_date`` (ISO), working-day ``es/ef/ls/lf`` indices,
    ``total_float``/``free_float`` (working days), ``critical`` and ``pct``.

    On a dependency cycle it returns early with the offending ids in ``cycle``
    and no dates (a schedule that hides its own contradiction is worse than one
    that admits it)."""
    resolved, unresolved = resolve(tasks)
    ids = [t.get('id') for t in resolved]
    tmap = {t.get('id'): t for t in resolved}
    preds = {t.get('id'): t.get('preds', []) for t in resolved}
    dur = {i: duration_days(tmap[i]) for i in ids}

    order, succ, cycle = _topo(ids, preds)
    if cycle:
        return {'tasks': {}, 'ordered': [], 'cycle': cycle,
                'unresolved': unresolved, 'project_finish': None,
                'critical_ids': [], 'finish_index': 0}

    # forward pass in working-day index space (continuous: [es, ef))
    es, ef = {}, {}
    for n in order:
        lo = 0.0
        for p, typ, lag in preds[n]:
            if typ == FS:
                lo = max(lo, ef[p] + lag)
            elif typ == SS:
                lo = max(lo, es[p] + lag)
            elif typ == FF:
                lo = max(lo, ef[p] + lag - dur[n])
            elif typ == SF:
                lo = max(lo, es[p] + lag - dur[n])
        es[n] = max(0.0, lo)
        ef[n] = es[n] + dur[n]

    finish_index = max((ef[n] for n in ids), default=0.0)

    # backward pass
    lf, ls = {}, {}
    for n in reversed(order):
        hi = finish_index
        first = True
        for s in succ[n]:
            typ, lag = _dep(preds[s], n)
            if typ == FS:
                bound = ls[s] - lag
            elif typ == SS:
                bound = (ls[s] - lag) + dur[n]
            elif typ == FF:
                bound = lf[s] - lag
            elif typ == SF:
                bound = (lf[s] - lag) + dur[n]
            else:
                bound = finish_index
            hi = bound if first else min(hi, bound)
            first = False
        lf[n] = hi
        ls[n] = lf[n] - dur[n]

    # dates
    cal = Calendar(work_week, holidays)
    start = isodate.parse(project_start) if project_start else None
    horizon = int(finish_index) + 5
    horizon = max(horizon, 10)
    wdays = cal.working_list(start, horizon + 2) if start else []

    def date_for(idx, is_finish):
        if not wdays:
            return None
        i = int(round(idx))
        if is_finish:
            i = max(i - 1, 0)          # ef is exclusive; last working day is ef-1
        i = min(max(i, 0), len(wdays) - 1)
        return wdays[i].isoformat()

    out = {}
    crit = []
    for n in ids:
        tf = round(ls[n] - es[n], 3)
        critical = abs(tf) < _EPS or tf < 0
        if critical:
            crit.append(n)
        # free float: earliest a successor could still start
        ff_slack = tf
        if succ[n]:
            slacks = []
            for s in succ[n]:
                typ, lag = _dep(preds[s], n)
                if typ in (FS, FF):
                    slacks.append(es[s] - ef[n] - lag if typ == FS
                                  else ef[s] - ef[n] - lag)
                else:
                    slacks.append(es[s] - es[n] - lag)
            ff_slack = round(max(min(slacks, default=tf), 0.0), 3)
        milestone = dur[n] <= _EPS
        out[n] = {
            'id': n, 'name': tmap[n].get('task_name'),
            'duration': dur[n],
            'es': es[n], 'ef': ef[n], 'ls': ls[n], 'lf': lf[n],
            'total_float': tf, 'free_float': ff_slack,
            'critical': critical, 'milestone': milestone,
            'pct': _clamp_pct(tmap[n].get('pct_complete')),
            'parent_id': tmap[n].get('parent_id'),
            'start_date': date_for(es[n], False),
            'finish_date': date_for(ef[n], True) if not milestone
            else date_for(es[n], False),
        }

    _rollup_wbs(out, ids, tmap)
    project_finish = None
    if out:
        project_finish = max((v['finish_date'] for v in out.values()
                              if v['finish_date']), default=None)
    return {'tasks': out, 'ordered': order, 'cycle': [],
            'unresolved': unresolved, 'project_finish': project_finish,
            'critical_ids': crit, 'finish_index': finish_index}


def _dep(pred_list, pred_id):
    for p, typ, lag in pred_list:
        if p == pred_id:
            return typ, lag
    return FS, 0


def _rollup_wbs(out, ids, tmap):
    """A parent (summary) task spans its children and shows their
    duration-weighted % complete. Children are tasks whose parent_id points at
    another task in the set."""
    children = {}
    for i in ids:
        pid = tmap[i].get('parent_id')
        if pid in out and pid != i:
            children.setdefault(pid, []).append(i)
    for pid, kids in children.items():
        starts = [out[k]['start_date'] for k in kids if out[k]['start_date']]
        finishes = [out[k]['finish_date'] for k in kids if out[k]['finish_date']]
        if starts:
            out[pid]['start_date'] = min(starts)
        if finishes:
            out[pid]['finish_date'] = max(finishes)
        total = sum(out[k]['duration'] for k in kids) or 1.0
        done = sum(out[k]['duration'] * out[k]['pct'] / 100.0 for k in kids)
        out[pid]['pct'] = round(done / total * 100.0, 1)
        out[pid]['is_summary'] = True


def summarise(result):
    tasks = result.get('tasks', {})
    return {
        'ok': not result.get('cycle'),
        'cycle': list(result.get('cycle', [])),
        'total': len(tasks),
        'critical': len(result.get('critical_ids', [])),
        'project_finish': result.get('project_finish'),
        'unresolved': len(result.get('unresolved', [])),
        'pct_complete': round(
            (sum(t['duration'] * t['pct'] for t in tasks.values())
             / (sum(t['duration'] for t in tasks.values()) or 1.0)), 1)
        if tasks else 0.0,
    }


# --------------------------------------------------------------- helpers
def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _clamp_pct(v):
    p = _num(v)
    return 0.0 if p < 0 else 100.0 if p > 100 else round(p, 1)
