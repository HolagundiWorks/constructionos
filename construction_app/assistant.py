"""RAG assistant over the contractor's own data (retrieval-augmented text-to-SQL).

Pipeline for a free-text question:
  1. **Retrieve** the schema docs + few-shot examples most relevant to the
     question (keyword overlap — small, stdlib, no embeddings).
  2. **Generate** a single read-only SQL SELECT with a local Ollama model,
     grounded in that retrieved context.
  3. **Validate + execute** the SQL safely (SELECT-only, single statement,
     LIMIT-capped, and run under ``PRAGMA query_only`` so writes are impossible
     even if validation is bypassed).
  4. **Generate** a plain-language summary of the result rows.

Also exposes deterministic **quick answers** (cash in hand, receivables, …) that
work with zero LLM, so the tab is useful even when Ollama isn't running.

All of this is DB + stdlib only and unit-testable; only steps 2 and 4 call the
LLM. Read-only by construction — the assistant can never modify data.
"""

import re

import db
import ollama_client


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
    'quotations', 'quotation_items', 'equipment'}


# ------------------------------------------------------------------ config
def get_config(conn):
    """Return (model, host) from app_settings, falling back to defaults."""
    rows = {r['key']: r['value'] for r in conn.execute(
        "SELECT key, value FROM app_settings WHERE key IN "
        "('assistant_model', 'assistant_host')")}
    model = (rows.get('assistant_model') or '').strip() or ollama_client.DEFAULT_MODEL
    host = (rows.get('assistant_host') or '').strip() or ollama_client.DEFAULT_HOST
    return model, host


# ---------------------------------------------------------------- retrieval
def _tokens(text):
    return set(re.findall(r'[a-z0-9]+', (text or '').lower()))


def retrieve(question, k_tables=9, k_examples=4):
    """Rank schema docs + examples by keyword overlap with the question."""
    q = _tokens(question)

    def score_doc(d):
        return len(q & _tokens(d['table'] + ' ' + d['keywords'] + ' ' + d['desc']))
    docs = sorted(SCHEMA_DOCS, key=score_doc, reverse=True)
    chosen = [d for d in docs if score_doc(d) > 0][:k_tables] or docs[:6]

    def score_ex(e):
        return len(q & _tokens(e['q']))
    exs = sorted(EXAMPLES, key=score_ex, reverse=True)[:k_examples]
    return chosen, exs


def build_sql_prompt(question, docs, examples):
    schema = '\n'.join(
        '- {}({}) — {}'.format(d['table'], d['columns'], d['desc']) for d in docs)
    shots = '\n'.join('Q: {}\nSQL: {}'.format(e['q'], e['sql']) for e in examples)
    return ('Schema (only these tables/columns exist):\n{}\n\n'
            'Examples:\n{}\n\n'
            'Q: {}\nSQL:'.format(schema, shots, question))


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
def answer(question, model=None, host=None):
    """Full RAG turn. Returns a dict: {sql, columns, rows, summary} or {error}."""
    host = host or ollama_client.DEFAULT_HOST
    model = model or ollama_client.DEFAULT_MODEL
    if not ollama_client.available(host):
        return {'error': "Ollama isn't running. Start it (`ollama serve`) and pull "
                         "a model (`ollama pull {}`), or use the quick buttons "
                         "above which work without it.".format(model)}
    docs, examples = retrieve(question)
    try:
        raw = ollama_client.generate(build_sql_prompt(question, docs, examples),
                                     model=model, host=host, system=SQL_SYSTEM)
    except ollama_client.OllamaError as exc:
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
        return ollama_client.generate(prompt, model=model, host=host).strip()
    except ollama_client.OllamaError:
        # Generation of prose failed but we still have the data.
        if not rows:
            return 'No matching records found.'
        return 'Found {} row(s). See the table below.'.format(len(rows))


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
