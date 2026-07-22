"""Assemble the weekly Review Pack from the live database (E4 surfacing).

``review_pack.build`` is deliberately DB-free and tkinter-free; this is its thin
bridge. It collects the dashboard snapshot, the portfolio EVM roll-up and the
opportunity register, then hands them to ``review_pack.build`` so the desktop tab
and the browser page render **one identical pack** — the report can never say two
different things on two screens.

DB-only, no tkinter. Cost figures come from :mod:`project_rollup` (also
tkinter-free), so a head-less caller — the web server, a test — can assemble
the same pack.
"""

import dashboard
import evm
import opportunity_store
import review_pack


def assemble(conn, generated=None):
    """Return a ``review_pack.build`` dict built from the current database.

    The portfolio EVM is attached only when there is a project worth measuring
    (otherwise the EVM block is honestly absent, not a row of zeroes), and the
    opportunity register is passed through as plain dicts so its summary rolls
    up from the stored figures.
    """
    snapshot = dashboard.collect(conn)
    _rows, port = evm.portfolio_evm(conn)
    opportunities = [dict(r) for r in
                     opportunity_store.list_opportunities(conn)]
    return review_pack.build(
        snapshot,
        evm=(port if port['projects'] else None),
        opportunities=opportunities,
        generated=generated)
