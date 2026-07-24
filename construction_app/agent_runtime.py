"""Agent runtime — route a question to one or more ACO agents and run tools.

No tkinter. Deterministic by default (tools + knowledge retrieve). When a
provider is available (Foundry Local, or Azure Foundry if configured),
optionally asks for a short plain-language summary — never for writes.

See ``agent_provider.py`` and ``docs/AI-FOUNDRY-AGENTS.md``.
"""

import agent_provider
import agent_tools
import agents_catalog as catalog
import knowledge_base

# Lightweight intent → agent id (first match wins). Falls back to executive.
_ROUTE_HINTS = (
    (('estimate', 'rate book', 'costing', 'productivity rate', 'price the'),
     catalog.ESTIMATION),
    (('boq', 'bill of quantities', 'duplicate item', 'waterproofing',
      'measured vs', 'deviation'),
     catalog.BOQ),
    (('drawing', 'dwg', 'pdf takeoff', 'cad', 'slab', 'column', 'grid',
      'revision', 'takeoff', 'vlm'),
     catalog.DRAWING),
    (('procure', 'purchase', 'vendor', 'quotation', 'grn', 'three-way',
      'requisition', 'material demand'),
     catalog.PROCUREMENT),
    (('schedule', 'critical path', 'cpm', 'lookahead', 'look-ahead', 'ppc',
      'delay', 'ld exposure', 'programme'),
     catalog.PLANNING),
    (('cash', 'gst', 'tds', 'invoice', 'retention', 'ageing', 'cash flow',
      'budget variance', 'payable', 'receivable', 'pnl', 'p&l'),
     catalog.FINANCE),
    (('rfi', 'submittal', 'contract document', 'method statement',
      'correspondence'),
     catalog.DOCUMENT),
    (('muster', 'inspection', 'ncr', 'snag', 'concrete poured', 'dpr',
      'site engineer'),
     catalog.SITE),
    (('safety', 'incident', 'ltifr', 'permit to work', 'toolbox'),
     catalog.SAFETY),
    (('over budget', 'top risk', 'executive', 'portfolio', 'which project',
      'owner', 'board'),
     catalog.EXECUTIVE),
)


def route(question, agent_id=None):
    """Resolve agent id from explicit id or question hints."""
    if agent_id:
        a = catalog.get(agent_id)
        if a:
            return a['id']
    q = ' '.join((question or '').lower().split())
    for phrases, aid in _ROUTE_HINTS:
        if any(p in q for p in phrases):
            return aid
    return catalog.EXECUTIVE


def _deterministic_summary(agent, question, tool_results):
    """Offline floor — bullet the tool bases and any headline numbers."""
    lines = [
        '{} — proposals only (human approves money/dates).'.format(
            agent['name']),
    ]
    if question:
        lines.append('Ask: {}'.format(question.strip()[:200]))
    for name, result in tool_results.items():
        if not isinstance(result, dict):
            continue
        basis = result.get('basis') or name
        if not result.get('ok', True):
            lines.append('• {} — unavailable ({})'.format(
                name, result.get('error') or 'error'))
            continue
        bits = []
        for key in ('cash', 'receivable', 'payable', 'total', 'count',
                    'at_risk', 'ppc', 'first_time_pass_pct',
                    'attendance_rows_7d', 'takeoff_count', 'ltifr'):
            if key in result and result[key] is not None:
                bits.append('{}={}'.format(key, result[key]))
        if 'items' in result and isinstance(result['items'], list):
            bits.append('items={}'.format(len(result['items'])))
        if 'buckets' in result and isinstance(result['buckets'], dict):
            bits.append('aged_total={}'.format(
                result['buckets'].get('total')))
        lines.append('• {}: {}{}'.format(
            name, basis,
            (' — ' + ', '.join(bits)) if bits else ''))
    return '\n'.join(lines)


def ask(conn, question, agent_id=None, use_model=True):
    """Run one agent turn: route → tools → knowledge → summary.

    Returns a payload safe for ``POST /api/agents/ask``.
    """
    aid = route(question, agent_id=agent_id)
    agent = catalog.get(aid)
    if agent is None:
        return {'ok': False, 'error': 'Unknown agent', 'agent_id': aid}

    knowledge = knowledge_base.retrieve(question or agent['summary'])
    tool_results = {}
    for tool in agent['tools']:
        tool_results[tool] = agent_tools.run_tool(tool, conn)

    summary = None
    provider_name = 'deterministic'
    model_used = False
    if use_model:
        summary, provider_name = agent_provider.summarize(
            conn, agent, question, tool_results, knowledge)
        model_used = summary is not None and provider_name != 'none'
    if not summary:
        summary = _deterministic_summary(agent, question, tool_results)
        if not model_used:
            provider_name = 'deterministic'

    gated = []
    for result in tool_results.values():
        if isinstance(result, dict) and result.get('gated'):
            gated.append({
                'action': result.get('action') or 'Review draft',
                'where': result.get('where') or 'ERP',
                'gated': True,
            })

    return {
        'ok': True,
        'agent_id': aid,
        'agent': agent,
        'question': question or '',
        'knowledge': knowledge,
        'tools': tool_results,
        'summary': summary,
        'model_used': model_used,
        'followups': gated,
        'gated_count': len(gated),
        'provider': provider_name if model_used else 'deterministic',
    }


def ask_multi(conn, question, agent_ids=None, use_model=False):
    """Run several agents (explicit ids or auto route + executive)."""
    ids = list(agent_ids or [])
    if not ids:
        ids = [route(question), catalog.EXECUTIVE]
    seen, ordered = set(), []
    for i in ids:
        if i not in seen and catalog.get(i):
            seen.add(i)
            ordered.append(i)
    turns = [ask(conn, question, agent_id=i, use_model=use_model)
             for i in ordered]
    return {
        'ok': True,
        'question': question or '',
        'turns': turns,
        'agents': ordered,
    }
