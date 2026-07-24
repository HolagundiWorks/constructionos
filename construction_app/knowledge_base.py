"""Curated knowledge snippets for agent retrieve (stdlib TF-IDF style).

No embeddings, no tkinter. Complements ``assistant.SCHEMA_DOCS`` with
product/SOP/agent guidance so answers stay grounded in ACO rules.
"""

import re

# Snippets: id, keywords, text. Keep short and accurate.
SNIPPETS = [
    {
        'id': 'rule-approve',
        'keywords': 'approve write money date agent draft confirm ai',
        'text': (
            'AI proposes; a human approves anything that moves money or a date. '
            'Agents return drafts and gated follow-ups — they never silent-write.'
        ),
    },
    {
        'id': 'rule-none',
        'keywords': 'undefined none zero infinity honesty',
        'text': (
            'Figures return None when undefined — never a fake 0 or infinity. '
            'Empty book ≠ error ≠ missing endpoint.'
        ),
    },
    {
        'id': 'gst-india',
        'keywords': 'gst cgst sgst igst tds interstate invoice',
        'text': (
            'Indian GST: intra-state CGST+SGST, inter-state IGST. TDS is on the '
            'pre-GST base. Use finance.split_gst / compute_tds.'
        ),
    },
    {
        'id': 'ppc-binary',
        'keywords': 'ppc lookahead commitment done miss reason last planner',
        'text': (
            'PPC is binary: only Done counts. A part-finished task is a miss — '
            'name the constraint (material, labour, drawing, weather, …).'
        ),
    },
    {
        'id': 'ra-mb',
        'keywords': 'ra bill measurement book boq quantity generate',
        'text': (
            'Civil RA bills are measurement-driven: BOQ → MB → Generate RA. '
            'Previous qty counts only Approved/Paid RA bills.'
        ),
    },
    {
        'id': 'three-way',
        'keywords': 'po grn invoice three-way match over-invoiced',
        'text': (
            'Procurement gate is PO ↔ GRN ↔ vendor invoice. Over-invoiced without '
            'receipt is money about to leave for goods that never arrived.'
        ),
    },
    {
        'id': 'cash-first',
        'keywords': 'cash baaki receivable payable owner contractor',
        'text': (
            'Lead with cash-in / cash-out and kitna baaki. Double-entry Accounting '
            'is advanced / for the CA.'
        ),
    },
    {
        'id': 'foundry-local',
        'keywords': 'foundry local model ollama azure agent offline',
        'text': (
            'Default model runtime is Foundry Local (on-device). Azure AI Foundry '
            'cloud Agents are opt-in later behind the same draft/confirm API.'
        ),
    },
    {
        'id': 'variation-flow',
        'keywords': 'variation change order vo impact drawing boq estimate',
        'text': (
            'Variation impact workflow: drawing scope → BOQ qty → estimate price → '
            'planning delay → procurement materials → finance cash → executive summary.'
        ),
    },
    {
        'id': 'drawing-delta',
        'keywords': 'drawing revision delta takeoff element vlm wall door quantity',
        'text': (
            'Drawing Phase D: AI/vector proposes elements (points+type); '
            'takeoff.measure yields quantity. Revision-delta classifies '
            'added/removed/modified; variation draft is gated for human approval. '
            'VLM weights are local L8 — core soft-fails without them.'
        ),
    },
    {
        'id': 'retention',
        'keywords': 'retention dlp defect liability release receivable',
        'text': (
            'Retention is earned money held until DLP. Client side is receivable; '
            'sub side is payable. Track releases separately.'
        ),
    },
]


def _tokens(text):
    return set(re.findall(r'[a-z0-9]+', (text or '').lower()))


def retrieve(question, limit=5):
    """Rank snippets by keyword overlap with ``question``."""
    q = _tokens(question)
    if not q:
        return []
    scored = []
    for s in SNIPPETS:
        keys = _tokens(s['keywords']) | _tokens(s['text'][:120])
        score = len(q & keys)
        if score:
            scored.append((score, s))
    scored.sort(key=lambda x: (-x[0], x[1]['id']))
    return [{'id': s['id'], 'text': s['text'], 'score': sc}
            for sc, s in scored[:limit]]
