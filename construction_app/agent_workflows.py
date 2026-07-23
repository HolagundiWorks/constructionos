"""Multi-agent workflows — ordered handoffs between ACO agents.

No tkinter. Each workflow is a recipe: run tools for agent A, then B, …
and attach gated follow-ups for human approval. See
``docs/AI-FOUNDRY-AGENTS.md`` §5.
"""

import agents_catalog as catalog
import agent_tools
import followups

# workflow_id → ordered steps {agent, tools, title}
WORKFLOWS = {
    'variation_impact': {
        'name': 'Variation order impact',
        'summary': (
            'Drawing scope → BOQ → estimate → planning → procurement → '
            'finance → executive summary. All steps are proposals.'
        ),
        'steps': (
            {'agent': catalog.DRAWING, 'tools': ('sidecar_status', 'pdf_extract_hint'),
             'title': 'Scope the design change'},
            {'agent': catalog.BOQ, 'tools': ('boq_overview', 'deviation_hint',
                                             'measurement_progress'),
             'title': 'Quantity / BOQ impact'},
            {'agent': catalog.ESTIMATION, 'tools': ('rate_book_summary',
                                                    'lessons_rates',
                                                    'project_cost_hint'),
             'title': 'Price the change'},
            {'agent': catalog.PLANNING, 'tools': ('programme_delay', 'lookahead_ppc'),
             'title': 'Schedule / LD impact'},
            {'agent': catalog.PROCUREMENT, 'tools': ('requisition_open',
                                                     'match_summary'),
             'title': 'Material / vendor impact'},
            {'agent': catalog.FINANCE, 'tools': ('money_snapshot', 'cashflow_hint'),
             'title': 'Cash / margin impact'},
            {'agent': catalog.EXECUTIVE, 'tools': ('advisories', 'top_risks'),
             'title': 'Executive summary'},
        ),
        'gated_followups': (
            {
                'action': 'Draft a variation register entry for human review',
                'where': 'Billing › Variations',
                'gated': True,
            },
        ),
    },
    'procurement_30d': {
        'name': 'Next 30 days procurement',
        'summary': 'Open requisitions, PO match risk, vendor flags.',
        'steps': (
            {'agent': catalog.PROCUREMENT, 'tools': ('requisition_open', 'open_pos',
                                                     'match_summary', 'vendor_flags'),
             'title': 'Procurement picture'},
            {'agent': catalog.FINANCE, 'tools': ('cashflow_hint', 'money_snapshot'),
             'title': 'Cash available to buy'},
            {'agent': catalog.EXECUTIVE, 'tools': ('advisories',),
             'title': 'Owner brief'},
        ),
        'gated_followups': (
            {
                'action': 'Draft purchase requisitions / POs from open site needs',
                'where': 'Purchases › Requisitions',
                'gated': True,
            },
        ),
    },
    'executive_brief': {
        'name': 'Executive weekly brief',
        'summary': 'Money, risks, PPC, EVM — one pack for the owner.',
        'steps': (
            {'agent': catalog.EXECUTIVE, 'tools': ('money_snapshot', 'top_risks',
                                                   'advisories', 'evm_portfolio',
                                                   'lookahead_ppc'),
             'title': 'Portfolio snapshot'},
            {'agent': catalog.FINANCE, 'tools': ('ageing_summary', 'retention_due',
                                                 'gst_totals'),
             'title': 'Money depth'},
            {'agent': catalog.SITE, 'tools': ('open_ncrs', 'open_snags'),
             'title': 'Site quality pressure'},
        ),
        'gated_followups': (
            {
                'action': 'Open the weekly review pack',
                'where': 'Money › Review',
                'gated': False,
            },
        ),
    },
    'site_daily': {
        'name': 'Site engineer daily',
        'summary': 'Muster, inspections, NCRs, snags, open RFIs.',
        'steps': (
            {'agent': catalog.SITE, 'tools': ('muster_hint', 'inspection_pass_rate',
                                              'open_ncrs', 'open_snags'),
             'title': 'Site status'},
            {'agent': catalog.DOCUMENT, 'tools': ('open_rfis',),
             'title': 'Blocking RFIs'},
            {'agent': catalog.SAFETY, 'tools': ('incident_summary', 'open_permits',
                                               'ltifr_summary'),
             'title': 'Safety'},
        ),
        'gated_followups': (
            {
                'action': 'Save today’s muster / DPR after review',
                'where': 'Operations › Muster',
                'gated': True,
            },
        ),
    },
    'cash_chase': {
        'name': 'Cash chase',
        'summary': 'Receivables ageing + retention due + cash forecast.',
        'steps': (
            {'agent': catalog.FINANCE, 'tools': ('money_snapshot', 'ageing_summary',
                                                 'retention_due', 'cashflow_hint'),
             'title': 'Money pressure'},
            {'agent': catalog.DOCUMENT, 'tools': ('contract_list',),
             'title': 'Contracts to bill against'},
            {'agent': catalog.EXECUTIVE, 'tools': ('advisories',),
             'title': 'Owner actions'},
        ),
        'gated_followups': (
            {
                'action': 'Draft collection calls / RA bill generation for review',
                'where': 'Billing › RA Bills',
                'gated': True,
            },
        ),
    },
    'quality_closeout': {
        'name': 'Quality close-out',
        'summary': 'NCRs, snags, inspections, then executive risk view.',
        'steps': (
            {'agent': catalog.SITE, 'tools': ('open_ncrs', 'open_snags',
                                              'inspection_pass_rate'),
             'title': 'Quality register'},
            {'agent': catalog.SAFETY, 'tools': ('incident_summary',),
             'title': 'Related HSE pressure'},
            {'agent': catalog.EXECUTIVE, 'tools': ('top_risks', 'advisories'),
             'title': 'Board brief'},
        ),
        'gated_followups': (
            {
                'action': 'Close NCRs / snags after site sign-off',
                'where': 'Operations › Quality / Closeout',
                'gated': True,
            },
        ),
    },
    'sourcing_award': {
        'name': 'Sourcing award pack',
        'summary': 'Quote compare + vendor flags + cash check before PO.',
        'steps': (
            {'agent': catalog.PROCUREMENT, 'tools': ('quote_compare', 'vendor_flags',
                                                     'requisition_open'),
             'title': 'Sourcing'},
            {'agent': catalog.FINANCE, 'tools': ('money_snapshot', 'cashflow_hint'),
             'title': 'Can we pay?'},
            {'agent': catalog.EXECUTIVE, 'tools': ('advisories',),
             'title': 'Approve award'},
        ),
        'gated_followups': (
            {
                'action': 'Mark selected quote and draft PO for human confirm',
                'where': 'Purchases › Sourcing / Purchase Orders',
                'gated': True,
            },
        ),
    },
}


def list_workflows():
    out = []
    for wid, wf in WORKFLOWS.items():
        out.append({
            'id': wid,
            'name': wf['name'],
            'summary': wf['summary'],
            'step_count': len(wf['steps']),
            'agents': [s['agent'] for s in wf['steps']],
        })
    return out


def get(workflow_id):
    wf = WORKFLOWS.get((workflow_id or '').strip().lower())
    if wf is None:
        return None
    return {
        'id': (workflow_id or '').strip().lower(),
        'name': wf['name'],
        'summary': wf['summary'],
        'steps': [dict(s, tools=list(s['tools'])) for s in wf['steps']],
        'gated_followups': [dict(f) for f in wf['gated_followups']],
    }


def run(conn, workflow_id, context=None):
    """Execute every step’s tools; return structured handoff trail.

    ``context`` is free-form notes from the user (e.g. variation description) —
    stored on the payload for the UI, not executed as SQL.
    """
    wid = (workflow_id or '').strip().lower()
    spec = WORKFLOWS.get(wid)
    if spec is None:
        return {'ok': False, 'error': 'Unknown workflow', 'workflow_id': wid}

    steps_out = []
    for i, step in enumerate(spec['steps']):
        agent = catalog.get(step['agent'])
        results = {}
        for tool in step['tools']:
            results[tool] = agent_tools.run_tool(tool, conn)
        steps_out.append({
            'index': i + 1,
            'agent': step['agent'],
            'agent_name': (agent or {}).get('name'),
            'title': step['title'],
            'tools': results,
        })

    followup_rows = [dict(f) for f in spec['gated_followups']]
    # Optional: attach variation follow-ups when relevant
    if wid == 'variation_impact':
        for f in followups.for_event(followups.VARIATION_APPROVED, context or {}):
            followup_rows.append(dict(f, payload=context or {}))

    return {
        'ok': True,
        'workflow_id': wid,
        'name': spec['name'],
        'summary': spec['summary'],
        'context': context or {},
        'steps': steps_out,
        'followups': followup_rows,
        'gated_count': sum(1 for f in followup_rows if f.get('gated')),
        'note': (
            'Proposals only — confirm any money/date action in the ERP UI. '
            'Foundry Local may narrate this pack when the engine is running.'
        ),
    }
