"""RAG assistant over the contractor's own data (retrieval-augmented text-to-SQL).

Pipeline for a free-text question:
  1. **Retrieve** the schema docs + few-shot examples most relevant to the
     question (keyword overlap — small, stdlib, no embeddings).
  2. **Generate** a single read-only SQL SELECT with the local Foundry Local
     model, grounded in that retrieved context.
  3. **Validate + execute** the SQL safely (SELECT-only, single statement,
     LIMIT-capped, and run under ``PRAGMA query_only`` so writes are impossible
     even if validation is bypassed).
  4. **Generate** a plain-language summary of the result rows.

Also exposes deterministic **quick answers** (cash in hand, receivables, …) that
work with zero LLM, so the tab is useful even when the AI engine isn't running.

All of this is DB + stdlib only and unit-testable; only steps 2 and 4 call the
LLM. Read-only by construction — the assistant can never modify data.
"""

import re

import db
import foundry_client


# ---------------------------------------------------------------- knowledge
# Curated, human-written descriptions of the queryable tables. This is the
# "retrieved" grounding — kept concise and accurate so the model writes correct
# SQL. Keep in sync with db.py when columns change.
SCHEMA_DOCS = [
    {'table': 'clients', 'keywords': 'client customer owner party owes receivable',
     'columns': 'id, name, contact_person, phone, email, address',
     'desc': 'Clients the contractor bills.'},
    {'table': 'vendors', 'keywords': 'vendor supplier payable owe purchase',
     'columns': 'id, name, contact_person, phone, gst_no, address',
     'desc': 'Suppliers/vendors the contractor buys from.'},
    {'table': 'sites', 'keywords': 'site project location warehouse',
     'columns': 'id, name, location, site_type, status',
     'desc': 'Construction sites / warehouses.'},
    {'table': 'contracts', 'keywords': 'contract agreement site client value',
     'columns': 'id, contract_no, site_id, client_id, contract_value, status',
     'desc': 'Contracts; link a client and a site. bills/ra_bills reference contract_id.'},
    {'table': 'bills', 'keywords': 'bill running invoice work done net payable status',
     'columns': 'id, contract_id, bill_no, bill_date, status, net_payable',
     'desc': "Running bills. status in Draft/Submitted/Approved/Paid. net_payable is the amount due."},
    {'table': 'ra_bills', 'keywords': 'ra running account bill measurement net payable',
     'columns': 'id, contract_id, bill_no, bill_date, status, this_bill_value, net_payable',
     'desc': 'RA (running account) bills per contract. status Approved/Paid counts as billed.'},
    {'table': 'tax_invoices', 'keywords': 'tax invoice gst sale client output',
     'columns': 'id, invoice_no, client_id, invoice_date, subtotal, tax_amount, total_amount, status',
     'desc': 'GST tax invoices raised to clients (outward sales).'},
    {'table': 'vendor_invoices', 'keywords': 'vendor invoice purchase gst tds payable input',
     'columns': 'id, invoice_no, vendor_id, invoice_date, subtotal, tax_amount, tds_amount, total_amount, net_payable',
     'desc': 'Vendor invoices (inward purchases). net_payable is owed to the vendor.'},
    {'table': 'payments', 'keywords': 'payment receipt cash paid received money party mode bank upi',
     'columns': "id, pay_date, direction, party_type, party_id, party_name, mode, amount, site_id",
     'desc': "Money in/out. direction 'Receipt' (in) or 'Payment' (out). party_type Client/Vendor/Labour/Other. mode Cash/Bank/UPI/Cheque."},
    {'table': 'material_ledger', 'keywords': 'material stock ledger in out qty rate consumption',
     'columns': "id, txn_date, site_id, material_id, txn_type, qty, rate, vendor_id",
     'desc': "Material stock movements. txn_type 'IN' (received) or 'OUT' (issued). value = qty*rate."},
    {'table': 'materials', 'keywords': 'material item unit cement steel sand',
     'columns': 'id, name, unit, category, hsn_code', 'desc': 'Material master.'},
    {'table': 'labor', 'keywords': 'labour worker wage daily attendance site',
     'columns': 'id, name, site_id, skill, daily_wage, status',
     'desc': 'Labour master. daily_wage per day. status Active/Inactive.'},
    {'table': 'attendance', 'keywords': 'attendance present absent muster days labour',
     'columns': "id, labor_id, att_date, status, hours",
     'desc': "Daily attendance. status Present/Half Day/Overtime/Absent."},
    {'table': 'estimates', 'keywords': 'estimate boq quotation grand total contingency',
     'columns': 'id, est_number, title, site_id, estimate_date, status, total_estimate',
     'desc': 'Priced estimates. total_estimate is the grand total.'},
    {'table': 'equipment_hire', 'keywords': 'equipment hire rent machinery vendor site cost',
     'columns': 'id, equipment_name, vendor_id, site_id, hire_type, rate, total_amount',
     'desc': 'Hired equipment and its cost (total_amount).'},
    {'table': 'projects', 'keywords': 'project budget progress client site status job',
     'columns': 'id, name, client_id, site_id, start_date, end_date, budget, status',
     'desc': 'Projects — group a client + site + budget. Tasks/milestones link to a project.'},
    {'table': 'milestones', 'keywords': 'milestone project progress target payment stage',
     'columns': "id, project_id, name, target_date, actual_date, amount, status",
     'desc': "Project milestones. status Pending/Done."},
    {'table': 'work_orders', 'keywords': 'work order subcontractor petti theka sub awarded',
     'columns': 'id, wo_no, vendor_id, site_id, contract_id, wo_date, retention_pct, tds_pct, status, total_amount',
     'desc': 'Work orders awarded to subcontractors (vendor_id is the sub). total_amount is the WO value.'},
    {'table': 'sub_bills', 'keywords': 'subcontractor sub bill running retention tds net payable petti',
     'columns': 'id, work_order_id, bill_no, bill_date, status, this_bill_value, retention_amt, tds_amount, net_payable',
     'desc': "Subcontractor running bills against a work order. net_payable is owed to the sub. status Approved/Paid counts as billed."},
    {'table': 'rate_book', 'keywords': 'rate book schedule rates specification standard item price',
     'columns': 'id, code, category, description, unit, rate, specification',
     'desc': 'Standard priced items (schedule of rates) with specifications.'},
    {'table': 'boq_items', 'keywords': 'boq item tender quantity rate amount contract',
     'columns': 'id, contract_id, item_no, description, unit, qty, rate, amount',
     'desc': 'Tendered BOQ items per contract. qty is the BOQ (tendered) quantity.'},
]

# Few-shot (question -> SQL) examples grounded in the schema above.
EXAMPLES = [
    {'q': 'How much cash do I have in hand?',
     'sql': "SELECT COALESCE(SUM(CASE WHEN direction='Receipt' THEN amount ELSE -amount END),0) AS cash_in_hand FROM payments WHERE mode='Cash'"},
    {'q': 'How much does client Sharma owe me?',
     'sql': "SELECT c.name, (SELECT COALESCE(SUM(net_payable),0) FROM ra_bills r JOIN contracts k ON k.id=r.contract_id WHERE k.client_id=c.id AND r.status IN ('Approved','Paid')) - (SELECT COALESCE(SUM(amount),0) FROM payments p WHERE p.party_type='Client' AND p.party_id=c.id AND p.direction='Receipt') AS outstanding FROM clients c WHERE c.name LIKE '%Sharma%'"},
    {'q': 'Total billed this month',
     'sql': "SELECT COALESCE(SUM(net_payable),0) AS billed FROM ra_bills WHERE status IN ('Approved','Paid') AND substr(bill_date,1,7)=strftime('%Y-%m','now')"},
    {'q': 'Which vendors do I still owe money to?',
     'sql': "SELECT v.name, COALESCE(SUM(vi.net_payable),0) - (SELECT COALESCE(SUM(amount),0) FROM payments p WHERE p.party_type='Vendor' AND p.party_id=v.id AND p.direction='Payment') AS payable FROM vendors v JOIN vendor_invoices vi ON vi.vendor_id=v.id GROUP BY v.id HAVING payable > 0 ORDER BY payable DESC"},
    {'q': 'How many bags of cement went out from site A?',
     'sql': "SELECT COALESCE(SUM(l.qty),0) AS qty_out FROM material_ledger l JOIN materials m ON m.id=l.material_id JOIN sites s ON s.id=l.site_id WHERE l.txn_type='OUT' AND m.name LIKE '%cement%' AND s.name LIKE '%A%'"},
    {'q': 'List labour present today',
     'sql': "SELECT l.name FROM attendance a JOIN labor l ON l.id=a.labor_id WHERE a.att_date=date('now') AND a.status IN ('Present','Overtime','Half Day')"},
    {'q': 'How much do I owe subcontractors?',
     'sql': "SELECT COALESCE(SUM(net_payable),0) AS sub_payable FROM sub_bills WHERE status IN ('Approved','Paid')"},
    {'q': 'Total retention withheld from subcontractors',
     'sql': "SELECT COALESCE(SUM(retention_amt),0) AS retention FROM sub_bills"},
    {'q': 'Which BOQ items are over-run on contract C1?',
     'sql': "SELECT b.description, b.qty AS boq_qty, COALESCE((SELECT SUM(m.quantity) FROM measurements m WHERE m.boq_item_id=b.id),0) AS executed FROM boq_items b JOIN contracts k ON k.id=b.contract_id WHERE k.contract_no LIKE '%C1%' AND COALESCE((SELECT SUM(m.quantity) FROM measurements m WHERE m.boq_item_id=b.id),0) > b.qty"},
    {'q': 'Total TDS deducted on vendor invoices this year',
     'sql': "SELECT COALESCE(SUM(tds_amount),0) AS tds FROM vendor_invoices WHERE substr(invoice_date,1,4)=strftime('%Y','now')"},
]

SQL_SYSTEM = (
    "You are a careful SQLite analyst for a construction-contractor app. "
    "Given a question and the relevant schema, output exactly ONE read-only "
    "SQLite SELECT statement that answers it. Rules: SELECT only (never INSERT/"
    "UPDATE/DELETE/DDL/PRAGMA); use only the tables/columns given; prefer "
    "COALESCE(SUM(...),0) for totals; use LIKE '%name%' for name matches; "
    "use date('now')/strftime for date logic. Reply with only the SQL inside a "
    "```sql code block, no explanation.")

_WRITE_WORDS = re.compile(
    r'\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|'
    r'vacuum|reindex|truncate|grant|commit|begin)\b', re.IGNORECASE)
_VALID_TABLES = {d['table'] for d in SCHEMA_DOCS} | {
    'boq_items', 'measurements', 'ra_bill_items', 'bill_items', 'estimate_items',
    'tax_invoice_items', 'vendor_invoice_items', 'thekedars', 'thekedar_entries',
    'accounts', 'journal_entries', 'journal_lines', 'timeline_tasks', 'advances',
    'payroll', 'work_done_entries', 'consumption_norms', 'daily_progress',
    'cube_tests', 'material_tests', 'plant_logs', 'purchase_orders',
    'quotations', 'quotation_items', 'equipment', 'projects', 'milestones',
    'work_orders', 'work_order_items', 'sub_bills', 'rate_book', 'boq_items'}


# ------------------------------------------------------------------ config
def get_config(conn):
    """Return (model, host). The model is **hardcoded** — the app ships one
    built-in model (``foundry_client.DEFAULT_MODEL``) and there is no picker.
    The host is Foundry Local's dynamically-discovered OpenAI endpoint; a stored
    ``assistant_host`` overrides it (e.g. to point at another machine on the
    LAN)."""
    row = conn.execute("SELECT value FROM app_settings WHERE key = "
                       "'assistant_host'").fetchone()
    host = ((row['value'] if row else '') or '').strip() or foundry_client.endpoint()
    return foundry_client.DEFAULT_MODEL, host


# ---------------------------------------------------------------- retrieval
#
# Ranking is TF-IDF cosine over the schema catalog, not raw keyword overlap.
# Overlap counts every shared word equally, so a common token like 'site' or
# 'date' — which appears in most tables — pulls in the wrong table as strongly
# as a rare, discriminating one like 'retention' or 'muster'. TF-IDF down-
# weights the common tokens and normalises by document length, so the table
# that is *distinctively* about the question wins. It is not neural embeddings
# (those would need a model and a pip/native dependency, which the stdlib-only
# rule forbids) — it is the honest stdlib vector-space retrieval, and it is
# what matters as the catalog grows.
import math
from collections import Counter


def _tokens(text):
    return set(re.findall(r'[a-z0-9]+', (text or '').lower()))


def _counts(text):
    return Counter(re.findall(r'[a-z0-9]+', (text or '').lower()))


def _doc_text(d):
    return '{} {} {}'.format(d['table'], d['keywords'], d['desc'])


def _build_index(docs):
    """Precompute idf and each doc's tf-idf vector once, at import."""
    n = len(docs) or 1
    df = Counter()
    doc_counts = []
    for d in docs:
        c = _counts(_doc_text(d))
        doc_counts.append(c)
        for tok in c:
            df[tok] += 1
    idf = {tok: math.log((n + 1) / (freq + 1)) + 1.0 for tok, freq in df.items()}
    vecs = []
    for c in doc_counts:
        vec = {tok: tf * idf[tok] for tok, tf in c.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vecs.append((vec, norm))
    return idf, vecs


_IDF, _DOC_VECS = _build_index(SCHEMA_DOCS)


def _query_vector(text):
    vec = {tok: tf * _IDF.get(tok, 1.0) for tok, tf in _counts(text).items()}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return vec, norm


def _cosine(qvec, qnorm, dvec, dnorm):
    small, big = (qvec, dvec) if len(qvec) <= len(dvec) else (dvec, qvec)
    dot = sum(w * big.get(tok, 0.0) for tok, w in small.items())
    return dot / (qnorm * dnorm)


def retrieve(question, k_tables=9, k_examples=4, context=''):
    """Rank schema docs by TF-IDF cosine with the question (plus any prior
    context, so a terse follow-up still retrieves the right tables)."""
    query = '{} {}'.format(question or '', context or '').strip()
    qvec, qnorm = _query_vector(query)
    scored = [(_cosine(qvec, qnorm, dvec, dnorm), d)
              for d, (dvec, dnorm) in zip(SCHEMA_DOCS, _DOC_VECS)]
    scored.sort(key=lambda sd: sd[0], reverse=True)
    chosen = [d for s, d in scored if s > 0][:k_tables] or \
        [d for _s, d in scored[:6]]

    q = _tokens(query)
    exs = sorted(EXAMPLES, key=lambda e: len(q & _tokens(e['q'])),
                 reverse=True)[:k_examples]
    return chosen, exs


def build_sql_prompt(question, docs, examples, history=None):
    schema = '\n'.join(
        '- {}({}) — {}'.format(d['table'], d['columns'], d['desc']) for d in docs)
    shots = '\n'.join('Q: {}\nSQL: {}'.format(e['q'], e['sql']) for e in examples)
    # Give the model the last couple of questions so a follow-up like "and for
    # last month?" or "what about site B?" resolves against what came before.
    recent = [h for h in (history or []) if h.get('question')][-2:]
    convo = ''
    if recent:
        convo = ('Earlier questions in this conversation (the new question may '
                 'refer back to them):\n{}\n\n'.format(
                     '\n'.join('- {}'.format(h['question']) for h in recent)))
    return ('Schema (only these tables/columns exist):\n{}\n\n'
            'Examples:\n{}\n\n{}'
            'Q: {}\nSQL:'.format(schema, shots, convo, question))


# --------------------------------------------------------------- sql safety
def extract_sql(text):
    """Pull the SQL out of a model reply (fenced block or first SELECT/WITH)."""
    if not text:
        return ''
    m = re.search(r'```(?:sql)?\s*(.+?)```', text, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r'((?:select|with)\b.+)', text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def validate_sql(sql):
    """Return (ok, cleaned_sql_or_reason). SELECT-only, single statement, capped."""
    if not sql or not sql.strip():
        return False, 'No SQL produced.'
    cleaned = sql.strip().rstrip(';').strip()
    # Single statement only.
    if ';' in cleaned:
        return False, 'Only a single statement is allowed.'
    if not re.match(r'^\s*(select|with)\b', cleaned, re.IGNORECASE):
        return False, 'Only read-only SELECT queries are allowed.'
    if _WRITE_WORDS.search(cleaned):
        return False, 'The query contains a disallowed keyword.'
    # Cap rows.
    if not re.search(r'\blimit\b', cleaned, re.IGNORECASE):
        cleaned += ' LIMIT 500'
    return True, cleaned


def safe_execute(sql):
    """Run a validated SELECT read-only. Returns (columns, rows).

    Uses ``PRAGMA query_only = ON`` so the engine itself rejects any write —
    defence in depth on top of ``validate_sql``.
    """
    conn = db.get_conn()
    try:
        conn.execute('PRAGMA query_only = ON')
        cur = conn.execute(sql)
        columns = [c[0] for c in (cur.description or [])]
        rows = [list(r) for r in cur.fetchmany(500)]
    finally:
        conn.close()
    return columns, rows


# ---------------------------------------------------------------- answering
def answer(question, model=None, host=None, history=None):
    """Full RAG turn. Returns a dict: {sql, columns, rows, summary} or {error}.

    ``history`` is a list of prior turn dicts (each with a ``question`` key);
    it steers retrieval and is shown to the model so a follow-up question that
    refers back — "and for last month?", "what about the other site?" —
    resolves instead of being answered in a vacuum.
    """
    host = host or foundry_client.endpoint()
    model = model or foundry_client.DEFAULT_MODEL
    if not foundry_client.available(host):
        return {'error': "The AI engine isn't running. Turn it on in AI Engine "
                         "(or run `foundry model run {}`), or use the quick "
                         "buttons above which work without it.".format(model)}
    context = ' '.join(h.get('question', '')
                       for h in (history or [])[-2:])
    docs, examples = retrieve(question, context=context)
    try:
        raw = foundry_client.generate(
            build_sql_prompt(question, docs, examples, history=history),
            model=model, host=host, system=SQL_SYSTEM)
    except foundry_client.FoundryError as exc:
        return {'error': str(exc)}
    sql = extract_sql(raw)
    ok, cleaned = validate_sql(sql)
    if not ok:
        return {'error': '{}\n\nModel proposed:\n{}'.format(cleaned, sql)}
    try:
        columns, rows = safe_execute(cleaned)
    except Exception as exc:                       # noqa: BLE001
        return {'error': 'Query failed: {}\n\nSQL:\n{}'.format(exc, cleaned),
                'sql': cleaned}
    summary = _summarize(question, columns, rows, model, host)
    return {'sql': cleaned, 'columns': columns, 'rows': rows, 'summary': summary}


def _summarize(question, columns, rows, model, host):
    preview = [dict(zip(columns, r)) for r in rows[:30]]
    prompt = ('Question: {}\nResult columns: {}\nResult rows (JSON): {}\n\n'
              'Answer the question in one or two plain sentences for a '
              'contractor. Use Indian Rupee formatting for money. If there are '
              'no rows, say so.'.format(question, columns, preview))
    try:
        return foundry_client.generate(prompt, model=model, host=host).strip()
    except foundry_client.FoundryError:
        # Generation of prose failed but we still have the data.
        if not rows:
            return 'No matching records found.'
        return 'Found {} row(s). See the table below.'.format(len(rows))


# ------------------------------------------------------------- text charts
def text_bar_chart(columns, rows, width=40, max_bars=15):
    """A monospace bar chart when results look like (label, number) pairs.

    Picks the first text-ish column as the label and the first numeric column
    as the value; returns '' when the shape isn't chartable. Pure — the caller
    decides where to show it.
    """
    if not rows or len(columns) < 2:
        return ''

    def as_num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    value_idx = None
    for i in range(len(columns)):
        if all(as_num(r[i]) is not None for r in rows):
            value_idx = i
            break
    if value_idx is None:
        return ''
    label_idx = 0 if value_idx != 0 else (1 if len(columns) > 1 else 0)

    pairs = [(str(r[label_idx]), as_num(r[value_idx])) for r in rows][:max_bars]
    peak = max((abs(v) for _l, v in pairs), default=0)
    if not peak:
        return ''
    label_w = min(24, max(len(l) for l, _v in pairs))
    lines = ['{}  |  {}'.format(columns[label_idx], columns[value_idx])]
    for label, val in pairs:
        bar = '#' * int(round(abs(val) / peak * width))
        lines.append('{:<{w}} | {} {:,.2f}'.format(
            label[:label_w], bar, val, w=label_w))
    return '\n'.join(lines)


# ------------------------------------------------------- deterministic quick
# These need no LLM — they always work, offline, and are exact.
def quick_answers(conn):
    def scalar(sql, params=()):
        return conn.execute(sql, params).fetchone()[0] or 0

    cash = scalar("SELECT COALESCE(SUM(CASE WHEN direction='Receipt' THEN amount "
                  "ELSE -amount END),0) FROM payments WHERE mode='Cash'")
    billed = scalar("SELECT COALESCE(SUM(net_payable),0) FROM bills WHERE status IN ('Approved','Paid')")
    billed += scalar("SELECT COALESCE(SUM(net_payable),0) FROM ra_bills WHERE status IN ('Approved','Paid')")
    received = scalar("SELECT COALESCE(SUM(amount),0) FROM payments WHERE direction='Receipt' AND party_type='Client'")
    invoiced = scalar("SELECT COALESCE(SUM(net_payable),0) FROM vendor_invoices")
    paid = scalar("SELECT COALESCE(SUM(amount),0) FROM payments WHERE direction='Payment' AND party_type='Vendor'")
    ym = "strftime('%Y-%m','now')"
    month_billed = scalar("SELECT COALESCE(SUM(net_payable),0) FROM ra_bills "
                          "WHERE status IN ('Approved','Paid') AND substr(bill_date,1,7)=" + ym)
    return {
        'Cash in Hand': round(cash, 2),
        'Receivables (clients owe)': round(billed - received, 2),
        'Payables (we owe vendors)': round(invoiced - paid, 2),
        'Billed This Month': round(month_billed, 2),
    }
