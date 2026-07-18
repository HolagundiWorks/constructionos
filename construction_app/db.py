"""SQLite persistence layer.

The entire schema lives in the single ``SCHEMA`` string below. ``get_conn``
returns a fresh short-lived connection with ``PRAGMA foreign_keys = ON`` and a
``sqlite3.Row`` row factory; ``init_db`` executes the schema (idempotent via
``CREATE TABLE IF NOT EXISTS``).

There is no long-lived shared connection: every operation opens a connection,
does its work, and closes it. The rest of the app receives ``get_conn`` itself
(a callable) as ``db_getter`` and calls it per operation.
"""

import os
import sqlite3

# Database file lives next to the code so the app is self-contained and runs
# from anywhere Python runs.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "construction.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT,
    site_type TEXT DEFAULT 'Site',
    status TEXT DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    address TEXT
);

CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    gst_no TEXT,
    address TEXT
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    unit TEXT,
    category TEXT,
    hsn_code TEXT
);

CREATE TABLE IF NOT EXISTS labor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    site_id INTEGER REFERENCES sites(id),
    skill TEXT,
    daily_wage REAL DEFAULT 0,
    phone TEXT,
    status TEXT DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    current_site_id INTEGER REFERENCES sites(id),
    status TEXT DEFAULT 'Available'
);

CREATE TABLE IF NOT EXISTS material_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_date TEXT,
    site_id INTEGER REFERENCES sites(id),
    material_id INTEGER REFERENCES materials(id),
    txn_type TEXT DEFAULT 'IN',
    qty REAL DEFAULT 0,
    rate REAL DEFAULT 0,
    vendor_id INTEGER REFERENCES vendors(id),
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS equipment_hire (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_name TEXT NOT NULL,
    vendor_id INTEGER REFERENCES vendors(id),
    site_id INTEGER REFERENCES sites(id),
    hire_type TEXT DEFAULT 'Daily',
    rate REAL DEFAULT 0,
    hire_start TEXT,
    hire_end TEXT,
    total_amount REAL DEFAULT 0,
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS timeline_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    task_name TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    duration_days REAL DEFAULT 0,
    status TEXT DEFAULT 'Not Started',
    dependency TEXT
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    labor_id INTEGER REFERENCES labor(id),
    att_date TEXT,
    status TEXT DEFAULT 'Present',
    hours REAL DEFAULT 8,
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS advances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    labor_id INTEGER REFERENCES labor(id),
    adv_date TEXT,
    amount REAL DEFAULT 0,
    recovered REAL DEFAULT 0,
    status TEXT DEFAULT 'Open',
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS payroll (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    labor_id INTEGER REFERENCES labor(id),
    month INTEGER,
    year INTEGER,
    days_present REAL DEFAULT 0,
    gross_amount REAL DEFAULT 0,
    deduction REAL DEFAULT 0,
    net_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'Unpaid',
    generated_date TEXT
);

CREATE TABLE IF NOT EXISTS quotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    quote_date TEXT,
    valid_until TEXT,
    status TEXT DEFAULT 'Draft',
    notes TEXT,
    total_amount REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quotation_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quotation_id INTEGER REFERENCES quotations(id) ON DELETE CASCADE,
    description TEXT,
    unit TEXT,
    qty REAL DEFAULT 0,
    rate REAL DEFAULT 0,
    amount REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    estimate_date TEXT,
    status TEXT DEFAULT 'Draft',
    notes TEXT,
    total_estimate REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS estimate_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estimate_id INTEGER REFERENCES estimates(id) ON DELETE CASCADE,
    description TEXT,
    unit TEXT,
    qty REAL DEFAULT 0,
    rate REAL DEFAULT 0,
    amount REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_no TEXT,
    site_id INTEGER REFERENCES sites(id),
    client_id INTEGER REFERENCES clients(id),
    contract_value REAL DEFAULT 0,
    retention_pct REAL DEFAULT 0,
    start_date TEXT,
    end_date TEXT,
    status TEXT DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER REFERENCES contracts(id),
    bill_no TEXT,
    bill_date TEXT,
    status TEXT DEFAULT 'Draft',
    work_done_value REAL DEFAULT 0,
    previous_billed REAL DEFAULT 0,
    retention_amt REAL DEFAULT 0,
    other_deductions REAL DEFAULT 0,
    net_payable REAL DEFAULT 0,
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS bill_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER REFERENCES bills(id) ON DELETE CASCADE,
    description TEXT,
    unit TEXT,
    qty REAL DEFAULT 0,
    rate REAL DEFAULT 0,
    amount REAL DEFAULT 0
);

-- ------------------------------------------------------------ procurement
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_no TEXT,
    vendor_id INTEGER REFERENCES vendors(id),
    site_id INTEGER REFERENCES sites(id),
    po_date TEXT,
    expected_date TEXT,
    status TEXT DEFAULT 'Draft',
    gst_pct REAL DEFAULT 18,
    notes TEXT,
    total_amount REAL DEFAULT 0   -- pre-tax items subtotal (derived by DocumentFrame)
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_order_id INTEGER REFERENCES purchase_orders(id) ON DELETE CASCADE,
    description TEXT,
    unit TEXT,
    qty REAL DEFAULT 0,
    rate REAL DEFAULT 0,
    amount REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vendor_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT,
    vendor_id INTEGER REFERENCES vendors(id),
    purchase_order_id INTEGER REFERENCES purchase_orders(id),
    invoice_date TEXT,
    received_date TEXT,
    interstate INTEGER DEFAULT 0,
    gst_pct REAL DEFAULT 18,
    tds_pct REAL DEFAULT 0,
    subtotal REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    tds_amount REAL DEFAULT 0,
    total_amount REAL DEFAULT 0,
    net_payable REAL DEFAULT 0,
    amount_paid REAL DEFAULT 0,
    status TEXT DEFAULT 'Received',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS vendor_invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_invoice_id INTEGER REFERENCES vendor_invoices(id) ON DELETE CASCADE,
    description TEXT,
    unit TEXT,
    qty REAL DEFAULT 0,
    rate REAL DEFAULT 0,
    amount REAL DEFAULT 0
);

-- ------------------------------------------------------------ accounting
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    name TEXT NOT NULL,
    type TEXT DEFAULT 'Asset',   -- Asset / Liability / Income / Expense / Equity
    parent_id INTEGER REFERENCES accounts(id),
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT,
    narration TEXT,
    reference TEXT,
    source TEXT DEFAULT 'Manual',  -- Manual / Bill / VendorInvoice / Payroll / PO
    source_id INTEGER,
    total_debit REAL DEFAULT 0,
    total_credit REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS journal_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journal_entry_id INTEGER REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_id INTEGER REFERENCES accounts(id),
    debit REAL DEFAULT 0,
    credit REAL DEFAULT 0,
    notes TEXT
);

-- --------------------------------------------- BOQ / measurement / RA billing
CREATE TABLE IF NOT EXISTS boq_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER REFERENCES contracts(id),
    item_no TEXT,
    description TEXT,
    unit TEXT,
    qty REAL DEFAULT 0,       -- tendered BOQ quantity
    rate REAL DEFAULT 0,
    amount REAL DEFAULT 0     -- qty * rate (derived)
);

CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boq_item_id INTEGER REFERENCES boq_items(id) ON DELETE CASCADE,
    contract_id INTEGER REFERENCES contracts(id),
    mb_date TEXT,
    mb_ref TEXT,              -- measurement book page / reference
    description TEXT,         -- location / particulars
    nos REAL,                 -- NULL => "not applicable" (counts as 1)
    length REAL,
    breadth REAL,
    depth REAL,
    quantity REAL DEFAULT 0,  -- Nos x L x B x D (derived)
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS ra_bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER REFERENCES contracts(id),
    bill_no TEXT,
    bill_date TEXT,
    status TEXT DEFAULT 'Draft',
    this_bill_value REAL DEFAULT 0,
    previous_value REAL DEFAULT 0,
    cumulative_value REAL DEFAULT 0,
    retention_pct REAL DEFAULT 0,
    retention_amt REAL DEFAULT 0,
    other_deductions REAL DEFAULT 0,
    net_payable REAL DEFAULT 0,
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS ra_bill_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ra_bill_id INTEGER REFERENCES ra_bills(id) ON DELETE CASCADE,
    boq_item_id INTEGER REFERENCES boq_items(id),
    upto_qty REAL DEFAULT 0,
    previous_qty REAL DEFAULT 0,
    current_qty REAL DEFAULT 0,
    rate REAL DEFAULT 0,
    current_amount REAL DEFAULT 0
);

-- --------------------------------------------- material consumption reconcil.
CREATE TABLE IF NOT EXISTS consumption_norms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity TEXT,            -- e.g. 'M20 Concrete'
    unit TEXT,                -- e.g. 'cum'
    material_id INTEGER REFERENCES materials(id),
    qty_per_unit REAL DEFAULT 0,   -- material consumed per unit of activity
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS work_done_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    activity TEXT,
    unit TEXT,
    qty REAL DEFAULT 0,
    entry_date TEXT,
    remarks TEXT
);

-- --------------------------------------------- site reports & quality
CREATE TABLE IF NOT EXISTS daily_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    report_date TEXT,
    weather TEXT,
    labour_count REAL DEFAULT 0,
    plant_count REAL DEFAULT 0,
    work_summary TEXT,
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS cube_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    cast_date TEXT,
    test_date TEXT,
    grade TEXT,               -- e.g. 'M25'
    location TEXT,
    cube_id TEXT,
    age_days REAL DEFAULT 28,
    load_kn REAL DEFAULT 0,
    area_mm2 REAL DEFAULT 22500,   -- 150 mm cube
    strength_mpa REAL DEFAULT 0,   -- derived
    result TEXT,                   -- derived Pass/Fail
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS material_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    test_date TEXT,
    material TEXT,
    test_type TEXT,
    sample_ref TEXT,
    result TEXT,
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS plant_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    log_date TEXT,
    equipment TEXT,
    hours_run REAL DEFAULT 0,
    diesel_ltr REAL DEFAULT 0,
    downtime_hrs REAL DEFAULT 0,
    operator TEXT,
    remarks TEXT
);

-- --------------------------------------------- money (cash-first, Phase 1)
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pay_date TEXT,
    direction TEXT DEFAULT 'Receipt',   -- Receipt (money in) / Payment (money out)
    party_type TEXT DEFAULT 'Client',   -- Client / Vendor / Labour / Other
    party_id INTEGER,                   -- id into the relevant master (nullable)
    party_name TEXT,                    -- snapshot for display
    mode TEXT DEFAULT 'Cash',           -- Cash / Bank / UPI / Cheque
    amount REAL DEFAULT 0,
    ref_no TEXT,
    site_id INTEGER REFERENCES sites(id),
    against_type TEXT,                  -- Bill / RABill / VendorInvoice / OnAccount
    against_id INTEGER,
    narration TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- --------------------------------------------- GST tax invoices (outward)
CREATE TABLE IF NOT EXISTS tax_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT,
    client_id INTEGER REFERENCES clients(id),
    contract_id INTEGER REFERENCES contracts(id),
    invoice_date TEXT,
    place_of_supply TEXT,
    interstate INTEGER DEFAULT 0,
    gst_pct REAL DEFAULT 18,
    status TEXT DEFAULT 'Draft',
    subtotal REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    total_amount REAL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS tax_invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tax_invoice_id INTEGER REFERENCES tax_invoices(id) ON DELETE CASCADE,
    description TEXT,
    hsn_code TEXT,
    unit TEXT,
    qty REAL DEFAULT 0,
    rate REAL DEFAULT 0,
    amount REAL DEFAULT 0
);

-- --------------------------------------------- labour contractors (thekedars)
CREATE TABLE IF NOT EXISTS thekedars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    site_id INTEGER REFERENCES sites(id),
    skill_type TEXT,
    status TEXT DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS thekedar_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thekedar_id INTEGER REFERENCES thekedars(id) ON DELETE CASCADE,
    entry_date TEXT,
    entry_type TEXT DEFAULT 'Work',   -- Work (we owe more) / Paid (we paid)
    description TEXT,
    amount REAL DEFAULT 0,
    remarks TEXT
);
"""


# A minimal construction-company chart of accounts, seeded once on first run.
DEFAULT_ACCOUNTS = [
    ('1000', 'Cash', 'Asset'),
    ('1010', 'Bank', 'Asset'),
    ('1100', 'Accounts Receivable', 'Asset'),
    ('1200', 'Materials Inventory', 'Asset'),
    ('1300', 'Input GST Credit', 'Asset'),
    ('2000', 'Accounts Payable', 'Liability'),
    ('2100', 'GST Payable', 'Liability'),
    ('2200', 'TDS Payable', 'Liability'),
    ('2300', 'Retention Payable', 'Liability'),
    ('3000', 'Owner Equity', 'Equity'),
    ('4000', 'Contract Revenue', 'Income'),
    ('5000', 'Materials Consumed', 'Expense'),
    ('5100', 'Labor & Wages', 'Expense'),
    ('5200', 'Equipment Hire', 'Expense'),
    ('5300', 'Subcontractor Charges', 'Expense'),
    ('5900', 'Other Site Expenses', 'Expense'),
]


def get_conn():
    """Open a fresh connection with FK enforcement and row-by-name access.

    Every caller must open, use, and close its own connection. Foreign keys are
    OFF by default in SQLite, so the pragma must be re-issued on every new
    connection — including any script or test that opens the db outside this
    function.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create every table if it does not already exist, then seed the CoA."""
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        seed_default_accounts(conn)
    finally:
        conn.close()


def seed_default_accounts(conn):
    """Insert the default chart of accounts once (no-op if any account exists)."""
    existing = conn.execute('SELECT COUNT(*) AS c FROM accounts').fetchone()['c']
    if existing:
        return
    conn.executemany(
        'INSERT INTO accounts (code, name, type) VALUES (?, ?, ?)',
        DEFAULT_ACCOUNTS)
    conn.commit()
