"""Live-book soft-signal → prediction drafts (E5 floor over the SQLite file).

No tkinter. Reads PPC weeks, open RFI ages, and optional programme slip hints,
runs ``drift.assess_drift``, and stages ``signal_feed`` risk drafts. Default is
**preview only** — ``apply_drafts`` is opt-in so a human still owns the register.
"""

from datetime import date

import drift
import isodate
import planning
import signal_feed


def _today():
    return date.today()


def _get(row, key, default=None):
    try:
        val = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if val is None else val


def ppc_series(conn, limit=8):
    """Recent week-start PPC values (oldest → newest), from ``commitments``."""
    weeks = {}
    try:
        rows = conn.execute(
            'SELECT week_start, status FROM commitments '
            'WHERE week_start IS NOT NULL AND week_start != "" '
            'ORDER BY week_start'
        ).fetchall()
    except Exception:
        return []
    for r in rows:
        wk = _get(r, 'week_start') or ''
        weeks.setdefault(wk, []).append(r)
    labels = sorted(weeks.keys())[-int(limit):]
    series = []
    for lab in labels:
        val = planning.ppc(weeks[lab])
        if val is not None:
            series.append(float(val))
    return series


def rfi_age_series(conn, limit=8):
    """Ages (days) of currently open RFIs, oldest first — a rising series hurts."""
    try:
        rows = conn.execute(
            "SELECT raised_date FROM rfis "
            "WHERE status IS NULL OR status = '' OR lower(status) = 'open' "
            "ORDER BY raised_date"
        ).fetchall()
    except Exception:
        return []
    today = _today()
    ages = []
    for r in rows:
        d = isodate.parse(_get(r, 'raised_date'))
        if d is None:
            continue
        ages.append(float((today - d).days))
    # Keep the oldest-open ages as a short history proxy (last N open RFIs).
    return ages[-int(limit):]


def soft_signals(conn):
    """Dict suitable for ``drift.assess_drift`` gathered from the live book."""
    return {
        'ppc_series': ppc_series(conn),
        'slip_series': [],  # programme slip history not stored as a series yet
        'rfi_age_series': rfi_age_series(conn),
        'low_conf_measurements': 0,
    }


def suggest(conn, project_id=None, apply=False, username='system'):
    """Preview (and optionally apply) prediction drafts from live soft signals.

    Returns::

        {
          'signals': soft-signal dict,
          'drift': drift.assess_drift result,
          'drafts': [register-ready risk dicts],
          'applied_ids': [...],
        }
    """
    signals = soft_signals(conn)
    drift_result = drift.assess_drift(signals)
    drafts = signal_feed.collect(
        drift=drift_result, project_id=project_id)
    applied = []
    if apply and drafts:
        applied = signal_feed.apply_drafts(
            conn, drafts, username=username, dedupe=True)
    return {
        'signals': signals,
        'drift': drift_result,
        'drafts': drafts,
        'applied_ids': applied,
        'applied': bool(applied),
    }
