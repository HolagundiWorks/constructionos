"""Federated portfolio read model (E2.1) — roll up across firm/year files.

DB-only, tkinter-free. Construction OS keeps each firm/year in its **own** SQLite
file (the offline-first guarantee: a site keeps working with no network, and no
central server owns its data). The enterprise question — "across every job we
run, where is the exposure?" — is answered here by *reading* each file and
pooling, never by moving the data into one place. Each file stays authoritative;
this is a read model over them.

Deliberately read-only: files are opened in SQLite read-only mode, so a roll-up
can never write to a project's book. It pools the registers this codebase owns
(projects, risks, opportunities, lessons) because those are unambiguous across
files; money-snapshot roll-up (which needs the dashboard's collectors) layers on
top later, per file, the same way.
"""

import sqlite3

import risk_store
import opportunity_store
import lessons_store


def open_readonly(path):
    """Open a firm/year file read-only. A roll-up must never be able to write to
    a project's book, so this uses SQLite's ``mode=ro`` rather than trusting
    discipline."""
    conn = sqlite3.connect('file:{}?mode=ro'.format(path), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _count(conn, table):
    try:
        return conn.execute('SELECT COUNT(*) AS n FROM {}'.format(table)) \
            .fetchone()['n']
    except sqlite3.Error:
        return 0


def file_rollup(conn, name=None):
    """One file's contribution to the portfolio: project count and the three
    register summaries. Tolerant of an older file that lacks a table (returns
    zeros) so a mixed-vintage portfolio still rolls up."""
    try:
        risks = risk_store.summary(conn)
    except sqlite3.Error:
        risks = {'count': 0, 'needs_action': 0, 'total_expected_exposure': 0.0}
    try:
        opps = opportunity_store.summary(conn)
    except sqlite3.Error:
        opps = {'count': 0, 'pursue_now': 0, 'total_expected_value': 0.0}
    try:
        less = lessons_store.summary(conn)
    except sqlite3.Error:
        less = {'count': 0, 'feed_forward_count': 0}
    return {
        'name': name,
        'projects': _count(conn, 'projects'),
        'risks': risks,
        'opportunities': opps,
        'lessons': less,
    }


def roll_up(paths):
    """Pool several firm/year files into one portfolio view.

    ``paths`` is a list of file paths (or ``(name, path)`` pairs). Returns pooled
    totals — projects, risk exposure and count-needing-action, opportunity
    upside, lessons still to feed forward — plus the per-file breakdown so a
    dashboard can point at the file that needs attention. A file that cannot be
    opened is skipped and named in ``unreadable`` rather than taking the whole
    roll-up down.
    """
    per_file = []
    unreadable = []
    totals = {
        'projects': 0,
        'risk_count': 0, 'risk_needs_action': 0, 'risk_exposure': 0.0,
        'opportunity_count': 0, 'opportunity_pursue_now': 0,
        'opportunity_value': 0.0,
        'lessons_count': 0, 'lessons_to_apply': 0,
    }
    for item in paths or []:
        name, path = item if isinstance(item, (tuple, list)) else (item, item)
        try:
            conn = open_readonly(path)
        except sqlite3.Error:
            unreadable.append(name)
            continue
        try:
            fr = file_rollup(conn, name=name)
        finally:
            conn.close()
        per_file.append(fr)
        totals['projects'] += fr['projects']
        totals['risk_count'] += fr['risks'].get('count', 0)
        totals['risk_needs_action'] += fr['risks'].get('needs_action', 0)
        totals['risk_exposure'] += fr['risks'].get('total_expected_exposure', 0.0)
        totals['opportunity_count'] += fr['opportunities'].get('count', 0)
        totals['opportunity_pursue_now'] += \
            fr['opportunities'].get('pursue_now', 0)
        totals['opportunity_value'] += \
            fr['opportunities'].get('total_expected_value', 0.0)
        totals['lessons_count'] += fr['lessons'].get('count', 0)
        totals['lessons_to_apply'] += fr['lessons'].get('feed_forward_count', 0)

    totals['risk_exposure'] = round(totals['risk_exposure'], 2)
    totals['opportunity_value'] = round(totals['opportunity_value'], 2)
    return {
        'files': len(per_file),
        'totals': totals,
        'per_file': per_file,
        'unreadable': unreadable,
    }
