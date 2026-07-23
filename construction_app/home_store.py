"""Home aggregate payload for ``GET /api/home`` (P3).

Composes the dashboard snapshot + advisories with a few cheap companion
blocks so the WinUI Home page can load in one round-trip. No tkinter.
Every nested block fails soft — a missing table or helper must not take
the whole Home response down.
"""

import advisory
import dashboard


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def assemble(conn, include=None):
    """Build the Home payload.

    ``include`` is an optional iterable of block names. Default is all:
    ``workflow``, ``match``, ``risks``, ``lookahead``, ``evm``.
    """
    wanted = set(include or (
        'workflow', 'match', 'risks', 'lookahead', 'evm'))
    snap = dashboard.collect(conn)
    advisories = advisory.build(snap)
    out = {
        'snapshot': snap,
        'advisories': advisories,
        'blocks': {},
    }

    if 'workflow' in wanted:
        def _wf():
            import workflow
            import workflow_state
            state = workflow_state.infer(conn)
            return workflow.all_progress(state)
        progress = _safe(_wf, {})
        # Strip non-JSON ``next`` callables / objects to plain dicts.
        clean = {}
        for name, info in (progress or {}).items():
            nxt = info.get('next')
            if nxt is not None and not isinstance(nxt, (dict, str, type(None))):
                try:
                    nxt = dict(nxt)
                except Exception:  # noqa: BLE001
                    nxt = str(nxt)
            clean[name] = {
                'done': info.get('done'),
                'total': info.get('total'),
                'pct': info.get('pct'),
                'next': nxt,
                'complete': info.get('complete'),
            }
        out['blocks']['workflow'] = clean

    if 'match' in wanted:
        def _match():
            import procurement
            pos = conn.execute(
                'SELECT id, total_amount FROM purchase_orders').fetchall()
            recv, inv = {}, {}
            for r in conn.execute(
                    'SELECT g.purchase_order_id AS pid, SUM(gi.amount) AS a '
                    'FROM grn_items gi JOIN goods_receipts g ON g.id = gi.grn_id '
                    "WHERE g.status = 'Posted' GROUP BY g.purchase_order_id"):
                recv[r['pid']] = r['a'] or 0
            for r in conn.execute(
                    'SELECT purchase_order_id AS pid, SUM(subtotal) AS a '
                    'FROM vendor_invoices WHERE purchase_order_id IS NOT NULL '
                    'GROUP BY purchase_order_id'):
                inv[r['pid']] = r['a'] or 0
            matches = [
                procurement.three_way(
                    p['total_amount'], recv.get(p['id'], 0),
                    inv.get(p['id'], 0), 100)
                for p in pos]
            return procurement.summarise(matches)
        out['blocks']['match'] = _safe(_match, {
            'at_risk': 0.0, 'awaiting_delivery': 0.0,
            'received_not_invoiced': 0.0, 'problem_count': 0, 'total_count': 0})

    if 'risks' in wanted:
        def _risks():
            import risk_store
            open_rows = risk_store.list_risks(conn, status='Open')
            return {
                'open': len(open_rows),
                'top': [
                    {'id': r['id'], 'title': r['title'], 'score': r['score'],
                     'expected_exposure': r['expected_exposure']}
                    for r in list(open_rows)[:5]
                ],
            }
        out['blocks']['risks'] = _safe(_risks, {'open': 0, 'top': []})

    if 'lookahead' in wanted:
        def _la():
            import lookahead_store
            return lookahead_store.lookahead(conn, weeks=4)
        la = _safe(_la, None)
        if la is not None:
            out['blocks']['lookahead'] = {
                'ppc': la.get('ppc'),
                'ppc_average': la.get('ppc_average'),
                'promised': la.get('promised'),
                'done': la.get('done'),
                'miss_reasons': la.get('miss_reasons') or [],
            }

    if 'evm' in wanted:
        def _evm():
            import evm
            rows, port = evm.portfolio_evm(conn)
            return {'portfolio': port, 'projects': rows}
        out['blocks']['evm'] = _safe(_evm, None)

    return out
