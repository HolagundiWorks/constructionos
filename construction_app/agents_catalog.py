"""Specialized AI agent catalog for ACO (Foundry multi-agent roster).

No tkinter, no model calls. Each agent is a persona + tool allow-list +
example prompts. The ERP remains the system of record; agents only *propose*.
See ``docs/AI-FOUNDRY-AGENTS.md``.
"""

# Stable ids — used in API paths and workflow steps.
ESTIMATION = 'estimation'
BOQ = 'boq'
DRAWING = 'drawing'
PROCUREMENT = 'procurement'
PLANNING = 'planning'
FINANCE = 'finance'
DOCUMENT = 'document'
SITE = 'site'
SAFETY = 'safety'
EXECUTIVE = 'executive'

AGENTS = (
    {
        'id': ESTIMATION,
        'name': 'Estimation Agent',
        'audience': 'Estimator',
        'summary': 'Cost estimates, rate suggestions, anomaly hints vs history.',
        'tools': ('rate_book_summary', 'estimate_totals', 'lessons_rates',
                  'project_cost_hint'),
        'examples': (
            'Estimate structural work using the rate book.',
            'Which rates look high vs our achieved lessons?',
        ),
    },
    {
        'id': BOQ,
        'name': 'BOQ Agent',
        'audience': 'Estimator / QS',
        'summary': 'BOQ completeness, duplicates, measured vs tendered.',
        'tools': ('boq_overview', 'boq_duplicates', 'measurement_progress',
                  'deviation_hint'),
        'examples': (
            'Review the BOQ for missing waterproofing items.',
            'Show measured vs BOQ progress on the active contract.',
        ),
    },
    {
        'id': DRAWING,
        'name': 'Drawing Intelligence Agent',
        'audience': 'QS / Engineer',
        'summary': 'PDF/drawing extract drafts; VLM sidecar when available.',
        'tools': ('sidecar_status', 'pdf_extract_hint', 'takeoff_status'),
        'examples': (
            'Extract text from the latest drawing PDF.',
            'Is the vision sidecar ready for takeoff assist?',
        ),
    },
    {
        'id': PROCUREMENT,
        'name': 'Procurement Agent',
        'audience': 'Buyer',
        'summary': 'PO / GRN match, vendor risk, next-period demand hints.',
        'tools': ('match_summary', 'open_pos', 'vendor_flags',
                  'requisition_open', 'quote_compare'),
        'examples': (
            'Prepare procurement for the next 30 days.',
            'Which POs are over-invoiced without a GRN?',
        ),
    },
    {
        'id': PLANNING,
        'name': 'Planning Agent',
        'audience': 'Project Manager',
        'summary': 'CPM float, PPC, delay and LD exposure.',
        'tools': ('lookahead_ppc', 'programme_delay', 'evm_portfolio'),
        'examples': (
            'Which tasks are on the critical path?',
            'What is this week’s plan reliability (PPC)?',
        ),
    },
    {
        'id': FINANCE,
        'name': 'Finance Agent',
        'audience': 'Owner / CA',
        'summary': 'Cash, ageing, cash-flow, GST/TDS, retention due.',
        'tools': ('money_snapshot', 'ageing_summary', 'cashflow_hint',
                  'gst_totals', 'retention_due', 'pnl_hint'),
        'examples': (
            'Expected cash flow next month?',
            'How much retention is due for release?',
        ),
    },
    {
        'id': DOCUMENT,
        'name': 'Document Intelligence Agent',
        'audience': 'PM / Admin',
        'summary': 'RFIs, submittals, contracts — find and summarise.',
        'tools': ('open_rfis', 'open_submittals', 'contract_list'),
        'examples': (
            'Show open RFIs.',
            'List contracts still active.',
        ),
    },
    {
        'id': SITE,
        'name': 'Site Engineer Copilot',
        'audience': 'Site Engineer',
        'summary': 'Muster, inspections, NCRs, snags, weekly pours.',
        'tools': ('open_ncrs', 'open_snags', 'inspection_pass_rate',
                  'muster_hint'),
        'examples': (
            'Show pending inspections and open NCRs.',
            'Which snags are still open?',
        ),
    },
    {
        'id': SAFETY,
        'name': 'Safety Agent',
        'audience': 'HSE',
        'summary': 'Incidents, permits, safety headlines.',
        'tools': ('incident_summary', 'ltifr_summary', 'open_permits'),
        'examples': (
            'Summarise recent incidents.',
            'Any open work permits?',
        ),
    },
    {
        'id': EXECUTIVE,
        'name': 'Executive Copilot',
        'audience': 'Owner',
        'summary': 'Portfolio KPIs, top risks, advisories in plain language.',
        'tools': ('money_snapshot', 'top_risks', 'advisories',
                  'evm_portfolio', 'lookahead_ppc'),
        'examples': (
            'Which projects are over budget?',
            'What are the top five project risks?',
        ),
    },
)

_BY_ID = {a['id']: a for a in AGENTS}


def list_agents():
    """All agents as plain dicts (API-safe)."""
    return [dict(a, tools=list(a['tools']), examples=list(a['examples']))
            for a in AGENTS]


def get(agent_id):
    """One agent dict or None."""
    a = _BY_ID.get((agent_id or '').strip().lower())
    if a is None:
        return None
    return dict(a, tools=list(a['tools']), examples=list(a['examples']))


def ids():
    return tuple(_BY_ID.keys())
