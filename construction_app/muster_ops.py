"""Muster grid + weekly wage payout — pure store over ``wages``.

Extracted from the desktop muster tab so the JSON API can load a site+date
grid, save attendance, compute a 7-day payout, and record cash payments
(idempotent per labourer+week narration). No tkinter.
"""

from datetime import datetime, timedelta

import wages

STATUSES = ('Present', 'Absent', 'Half Day', 'Overtime')


def _parse_day(value):
    raw = (value or '').strip()
    if not raw:
        raise ValueError('att_date / week_start must be YYYY-MM-DD')
    try:
        return datetime.strptime(raw[:10], '%Y-%m-%d')
    except ValueError as exc:
        raise ValueError('att_date / week_start must be YYYY-MM-DD') from exc


def recover_advances(conn, labor_id, amount):
    """FIFO-recover open advances (same behaviour as the desktop tab)."""
    remaining = round(float(amount or 0), 2)
    if remaining <= 0:
        return
    advances = conn.execute(
        "SELECT id, amount, recovered FROM advances "
        "WHERE labor_id = ? AND status = 'Open' ORDER BY adv_date, id",
        (labor_id,)).fetchall()
    for adv in advances:
        if remaining <= 0:
            break
        outstanding = round((adv['amount'] or 0) - (adv['recovered'] or 0), 2)
        if outstanding <= 0:
            continue
        take = min(outstanding, remaining)
        new_recovered = round((adv['recovered'] or 0) + take, 2)
        status = 'Closed' if new_recovered >= (adv['amount'] or 0) - 1e-6 else 'Open'
        conn.execute(
            'UPDATE advances SET recovered = ?, status = ? WHERE id = ?',
            (new_recovered, status, adv['id']))
        remaining = round(remaining - take, 2)


def load_grid(conn, site_id, att_date):
    """Active labour at ``site_id`` for ``att_date``, prefilled from attendance."""
    site_id = int(site_id)
    day = _parse_day(att_date).strftime('%Y-%m-%d')
    labour = conn.execute(
        "SELECT id, name, skill, daily_wage FROM labor "
        "WHERE status = 'Active' AND site_id = ? ORDER BY name",
        (site_id,)).fetchall()
    existing = {
        r['labor_id']: r for r in conn.execute(
            'SELECT labor_id, status, hours FROM attendance '
            'WHERE att_date = ? AND labor_id IN '
            '(SELECT id FROM labor WHERE site_id = ?)',
            (day, site_id))
    }
    rows = []
    for lab in labour:
        ex = existing.get(lab['id'])
        status = (ex['status'] if ex else 'Present') or 'Present'
        if status not in STATUSES:
            status = 'Present'
        hours = float(ex['hours'] if ex and ex['hours'] is not None else 8)
        rows.append({
            'labor_id': lab['id'],
            'name': lab['name'],
            'skill': lab['skill'],
            'daily_wage': lab['daily_wage'],
            'status': status,
            'hours': hours,
            'existing': ex is not None,
        })
    return {
        'site_id': site_id,
        'att_date': day,
        'rows': rows,
        'statuses': list(STATUSES),
    }


def save_grid(conn, site_id, att_date, rows):
    """Replace one-mark-per-day attendance for the given labour rows."""
    site_id = int(site_id)
    day = _parse_day(att_date).strftime('%Y-%m-%d')
    saved = 0
    for raw in rows or []:
        try:
            labor_id = int(raw.get('labor_id'))
        except (TypeError, ValueError):
            continue
        status = (raw.get('status') or 'Present').strip()
        if status not in STATUSES:
            status = 'Present'
        try:
            hours = float(raw.get('hours') if raw.get('hours') is not None else 8)
        except (TypeError, ValueError):
            hours = 8.0
        conn.execute(
            'DELETE FROM attendance WHERE labor_id = ? AND att_date = ?',
            (labor_id, day))
        conn.execute(
            'INSERT INTO attendance (labor_id, att_date, status, hours) '
            'VALUES (?, ?, ?, ?)',
            (labor_id, day, status, hours))
        saved += 1
    conn.commit()
    return {'site_id': site_id, 'att_date': day, 'saved': saved}


def compute_payout(conn, site_id, week_start):
    """7-day wage payout for Active labour on a site (skips zero-day/zero-net)."""
    site_id = int(site_id)
    start = _parse_day(week_start)
    end = start + timedelta(days=6)
    s, e = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
    labour = conn.execute(
        "SELECT id, name, daily_wage FROM labor "
        "WHERE status = 'Active' AND site_id = ? ORDER BY name",
        (site_id,)).fetchall()
    rows = []
    for lab in labour:
        atts = conn.execute(
            'SELECT status, hours FROM attendance WHERE labor_id = ? '
            'AND att_date BETWEEN ? AND ?', (lab['id'], s, e)).fetchall()
        days = round(sum(wages.day_fraction(a['status'], a['hours'])
                         for a in atts), 2)
        adv = conn.execute(
            "SELECT COALESCE(SUM(amount - recovered), 0) AS b FROM advances "
            "WHERE labor_id = ? AND status = 'Open'",
            (lab['id'],)).fetchone()['b']
        w = wages.wage_net(days, lab['daily_wage'], adv)
        if days == 0 and w['net'] == 0:
            continue
        rows.append({
            'labor_id': lab['id'], 'name': lab['name'],
            'days': days, **w,
        })
    total_net = round(sum(r['net'] for r in rows), 2)
    return {
        'site_id': site_id,
        'week_start': s,
        'week_end': e,
        'rows': rows,
        'total_net': total_net,
        'payable_count': sum(1 for r in rows if r['net'] > 0),
    }


def record_payout(conn, site_id, week_start, rows=None):
    """Insert cash wage payments; skip labourers already recorded for the week.

    When ``rows`` is omitted, recomputes from attendance. Marks advance
    deductions recovered. Returns counts.
    """
    site_id = int(site_id)
    if rows is None:
        payload = compute_payout(conn, site_id, week_start)
        rows = payload['rows']
        s, e = payload['week_start'], payload['week_end']
    else:
        start = _parse_day(week_start)
        end = start + timedelta(days=6)
        s, e = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
    narration = 'Wages {} to {}'.format(s, e)
    recorded = skipped = 0
    payment_ids = []
    for r in rows:
        if float(r.get('net') or 0) <= 0:
            continue
        labor_id = int(r['labor_id'])
        exists = conn.execute(
            "SELECT 1 FROM payments WHERE party_type='Labour' "
            "AND party_id=? AND narration=? LIMIT 1",
            (labor_id, narration)).fetchone()
        if exists:
            skipped += 1
            continue
        cur = conn.execute(
            "INSERT INTO payments (pay_date, direction, party_type, "
            "party_id, party_name, mode, amount, site_id, narration) "
            "VALUES (?, 'Payment', 'Labour', ?, ?, 'Cash', ?, ?, ?)",
            (e, labor_id, r.get('name') or '', float(r['net']),
             site_id, narration))
        recover_advances(conn, labor_id, r.get('deduction') or 0)
        payment_ids.append(cur.lastrowid)
        recorded += 1
    conn.commit()
    return {
        'site_id': site_id,
        'week_start': s,
        'week_end': e,
        'narration': narration,
        'recorded': recorded,
        'skipped': skipped,
        'payment_ids': payment_ids,
    }
