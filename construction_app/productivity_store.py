"""DB bridge for productivity KPIs — muster + plant logs + work done.

Tkinter-free. Joins attendance (via labor.site_id), plant_logs, and
work_done_entries. Pure ratios live in ``productivity``.
"""

import productivity
import wages


def site_rows(conn, from_date=None, to_date=None):
    """Per-site raw inputs: qty, labour_hours, plant operating/available hours."""
    sites = {r['id']: (r['name'] or 'Site {}'.format(r['id']))
             for r in conn.execute('SELECT id, name FROM sites')}

    labour_hrs = {}
    sql = ('SELECT l.site_id AS site_id, a.status, a.hours '
           'FROM attendance a JOIN labor l ON l.id = a.labor_id '
           'WHERE l.site_id IS NOT NULL')
    params = []
    if from_date:
        sql += ' AND a.att_date >= ?'
        params.append(from_date)
    if to_date:
        sql += ' AND a.att_date <= ?'
        params.append(to_date)
    for r in conn.execute(sql, params):
        sid = r['site_id']
        # Convert day-fraction to hours (8 h day) so labour_productivity fits.
        frac = wages.day_fraction(r['status'] or 'Present', r['hours'])
        labour_hrs[sid] = labour_hrs.get(sid, 0.0) + frac * 8.0

    work = {}
    sql = ('SELECT site_id, SUM(qty) AS q FROM work_done_entries '
           'WHERE site_id IS NOT NULL')
    params = []
    if from_date:
        sql += ' AND entry_date >= ?'
        params.append(from_date)
    if to_date:
        sql += ' AND entry_date <= ?'
        params.append(to_date)
    sql += ' GROUP BY site_id'
    for r in conn.execute(sql, params):
        work[r['site_id']] = float(r['q'] or 0)

    plant_op = {}
    plant_av = {}
    sql = ('SELECT site_id, '
           'SUM(COALESCE(hours_run, 0)) AS worked, '
           'SUM(COALESCE(hours_run, 0) + COALESCE(downtime_hrs, 0)) AS available '
           'FROM plant_logs WHERE site_id IS NOT NULL')
    params = []
    if from_date:
        sql += ' AND log_date >= ?'
        params.append(from_date)
    if to_date:
        sql += ' AND log_date <= ?'
        params.append(to_date)
    sql += ' GROUP BY site_id'
    for r in conn.execute(sql, params):
        plant_op[r['site_id']] = float(r['worked'] or 0)
        plant_av[r['site_id']] = float(r['available'] or 0)

    rows = []
    for sid, name in sites.items():
        lp = productivity.labour_productivity(work.get(sid, 0.0),
                                              labour_hrs.get(sid, 0.0))
        util = productivity.equipment_utilisation(
            plant_op.get(sid, 0.0), plant_av.get(sid, 0.0))
        rows.append({
            'site': name,
            'qty': work.get(sid, 0.0),
            'labour_hours': labour_hrs.get(sid, 0.0),
            'units_per_hour': lp['units_per_hour'],
            'hours_per_unit': lp['hours_per_unit'],
            'plant_util_pct': util,
        })
    return rows


def firm_summary(conn, from_date=None, to_date=None):
    """Firm totals using the same pure ratios as per-site rows."""
    rows = site_rows(conn, from_date, to_date)
    tot_qty = sum(r['qty'] for r in rows)
    tot_hrs = sum(r['labour_hours'] for r in rows)
    tot_op = 0.0
    tot_av = 0.0
    for r in rows:
        # Reconstruct plant hours from util when present is awkward; re-sum below.
        pass
    # Re-query plant totals once for firm util (honest aggregate).
    sql = ('SELECT SUM(COALESCE(hours_run, 0)) AS worked, '
           'SUM(COALESCE(hours_run, 0) + COALESCE(downtime_hrs, 0)) AS available '
           'FROM plant_logs')
    params = []
    where = []
    if from_date:
        where.append('log_date >= ?')
        params.append(from_date)
    if to_date:
        where.append('log_date <= ?')
        params.append(to_date)
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    prow = conn.execute(sql, params).fetchone()
    tot_op = float(prow['worked'] or 0) if prow else 0.0
    tot_av = float(prow['available'] or 0) if prow else 0.0
    lp = productivity.labour_productivity(tot_qty, tot_hrs)
    return {
        'units_per_hour': lp['units_per_hour'],
        'hours_per_unit': lp['hours_per_unit'],
        'plant_util_pct': productivity.equipment_utilisation(tot_op, tot_av),
        'qty': tot_qty,
        'labour_hours': tot_hrs,
        'sites': rows,
    }
