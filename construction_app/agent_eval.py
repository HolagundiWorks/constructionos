"""Golden-question evaluation harness for ACO agents (Foundry Phase A/C).

No tkinter, no live model required. Runs deterministic routing + tool success
checks so we can measure agent quality before/without Azure Foundry eval.
Optional ``use_model`` adds a soft "summary non-empty" check when a provider
is up — never fails the suite if the engine is off.
"""

import agent_runtime
import agents_catalog as catalog

# question, expected_agent_id, required_tools (subset that must ok=True)
GOLDEN = (
    {
        'id': 'fin-cash',
        'question': 'How much cash and receivable do I have?',
        'agent': catalog.FINANCE,
        'tools': ('money_snapshot',),
    },
    {
        'id': 'proc-match',
        'question': 'Which POs are over-invoiced without a GRN?',
        'agent': catalog.PROCUREMENT,
        'tools': ('match_summary',),
    },
    {
        'id': 'plan-ppc',
        'question': 'What is this week plan reliability PPC?',
        'agent': catalog.PLANNING,
        'tools': ('lookahead_ppc',),
    },
    {
        'id': 'boq-dup',
        'question': 'Review the BOQ for duplicate line items',
        'agent': catalog.BOQ,
        'tools': ('boq_duplicates',),
    },
    {
        'id': 'exec-risk',
        'question': 'What are the top project risks for the board?',
        'agent': catalog.EXECUTIVE,
        'tools': ('top_risks',),
    },
    {
        'id': 'site-ncr',
        'question': 'Show open NCRs and snags on site',
        'agent': catalog.SITE,
        'tools': ('open_ncrs', 'open_snags'),
    },
    {
        'id': 'doc-rfi',
        'question': 'List open RFIs',
        'agent': catalog.DOCUMENT,
        'tools': ('open_rfis',),
    },
    {
        'id': 'safe-incident',
        'question': 'Summarise recent safety incidents and LTIFR',
        'agent': catalog.SAFETY,
        'tools': ('incident_summary',),
    },
    {
        'id': 'est-rates',
        'question': 'Estimate using the rate book and lessons',
        'agent': catalog.ESTIMATION,
        'tools': ('rate_book_summary',),
    },
    {
        'id': 'draw-sidecar',
        'question': 'Is the drawing VLM sidecar ready for takeoff?',
        'agent': catalog.DRAWING,
        'tools': ('sidecar_status',),
    },
    {
        'id': 'draw-delta',
        'question': 'Diff the latest drawing revision and quantify the change',
        'agent': catalog.DRAWING,
        'tools': ('revision_delta_hint',),
    },
)


def run_case(conn, case, use_model=False):
    """Execute one golden case. Returns a result dict with pass/fail flags."""
    routed = agent_runtime.route(case['question'])
    route_ok = routed == case['agent']
    turn = agent_runtime.ask(
        conn, case['question'], agent_id=case['agent'], use_model=use_model)
    tool_ok = True
    tool_detail = {}
    for name in case.get('tools') or ():
        result = (turn.get('tools') or {}).get(name) or {}
        ok = bool(result.get('ok', False))
        tool_detail[name] = ok
        if not ok:
            tool_ok = False
    summary_ok = bool((turn.get('summary') or '').strip())
    passed = route_ok and tool_ok and summary_ok and turn.get('ok')
    return {
        'id': case['id'],
        'question': case['question'],
        'expected_agent': case['agent'],
        'routed_agent': routed,
        'route_ok': route_ok,
        'tool_ok': tool_ok,
        'tools': tool_detail,
        'summary_ok': summary_ok,
        'model_used': bool(turn.get('model_used')),
        'provider': turn.get('provider'),
        'passed': bool(passed),
    }


def run_suite(conn, use_model=False, cases=None):
    """Run all (or selected) golden cases; return roll-up."""
    selected = list(cases or GOLDEN)
    results = [run_case(conn, c, use_model=use_model) for c in selected]
    passed = sum(1 for r in results if r['passed'])
    return {
        'ok': True,
        'total': len(results),
        'passed': passed,
        'failed': len(results) - passed,
        'pass_rate': (
            round(100.0 * passed / len(results), 1) if results else None),
        'use_model': bool(use_model),
        'results': results,
        'note': (
            'Deterministic routing + tool ok checks. Model narration is '
            'optional and does not fail the suite when the engine is off.'
        ),
    }


def list_cases():
    return [
        {'id': c['id'], 'question': c['question'], 'agent': c['agent'],
         'tools': list(c.get('tools') or ())}
        for c in GOLDEN
    ]
