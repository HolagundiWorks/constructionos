# Construction OS

*Developed by Human Centric Works, Hospet.*

A single-user desktop **ERP for Indian construction contractors** — a focused,
zero-dependency alternative to heavyweight suites like Dolibarr, tailored to the
construction trade. It covers site operations, procurement, commercial
documents, and the beginnings of full accounting:

- **Projects** — a project umbrella (client + site + budget + milestones)
  with a live overview: budget vs cost-to-date vs billed, margin, and progress.
- **Operations** — sites/warehouses, vendors, clients, materials, labor,
  equipment, stock ledger, attendance, payroll, advances, project timelines.
- **Commercial** — quotations, estimates, contracts, running bills (with a
  printable bill export).
- **Estimates** — priced BOQ estimates with contingency and GST rolled up to a
  grand total, and a printable estimate document (amount in words).
- **Civil billing** — a BOQ per contract, a Measurement Book (Nos × L × B × D),
  measurement-driven RA (Running Account) bills with a printable abstract, and a
  PWD-style **deviation statement** (tendered vs executed, excess/saving).
- **Rate Book** — a schedule of standard priced items with specifications, to
  reuse when preparing estimates and BOQs.
- **Tax invoices** — GST tax invoices for clients (HSN/SAC, CGST/SGST/IGST,
  amount in words), printable, with a **configurable number series** (prefix +
  financial-year reset, e.g. `INV/2026-27/001`).
- **Procurement** — purchase orders, vendor invoices with GST/TDS, PO↔invoice
  reconciliation, and print/export on every document.
- **Subcontractors** — work orders and subcontractor running bills with
  retention and works-contract TDS, printable.
- **Site & quality** — material consumption reconciliation (theoretical vs
  actual), daily progress reports, cube-test and material-test registers, and a
  plant/machinery log.
- **Money (cash-first)** — payments & receipts, party balances ("who owes
  whom"), a cash/day book with running balance, and a plain-language home
  dashboard (cash in hand, receivables, payables).
- **Insight** — site-wise profitability, **receivables/payables ageing**
  (0-30/30-60/60-90/90+), **contract/BOQ progress %**, and **material budget vs
  actual**.
- **GST & TDS** — output GST (tax invoices + RA/running bills) and input GST
  registers, an **HSN-wise summary**, a net-position (3B-style) summary, and a
  TDS register — month-filtered and printable (for return time).
- **Finance (advanced)** — GST (CGST/SGST/IGST) and TDS computation, a seeded
  chart of accounts, a double-entry journal with one-click auto-posting of
  invoices, payments, payroll & subcontractor bills, a trial balance, and a
  **Profit & Loss + Balance Sheet** on the ledger (for the CA).
- **Easy to adopt** — a **first-run setup wizard**, dates that default to today
  and fields that remember your last site, **Hindi/Hinglish** menu labels, and a
  friendly dialog instead of any error trace.
- **Security (optional)** — off by default (opens straight in). An office can
  switch on sign-in with user accounts, roles (Admin/Operator/Viewer), PBKDF2
  password hashing, account lockout, and an audit log.
- **AI Assistant (optional)** — ask questions about your own data in plain
  language ("how much does Sharma owe?", "cash received this month"). Uses a
  **local Ollama** model via retrieval-augmented, read-only text-to-SQL; quick
  deterministic answers work even without it. No cloud, no Python dependency.

> Built for small civil contractors in tier-2/tier-3 cities — offline, on one
> PC, minimal typing. See [`docs/PRODUCT.md`](docs/PRODUCT.md) and
> [`docs/ROADMAP.md`](docs/ROADMAP.md).

Built entirely on the Python standard library: **`tkinter`** for the GUI and
**`sqlite3`** for storage. No pip dependencies, no web server, no build step —
it runs anywhere Python runs.

## Requirements

- Python 3.8+
- Tk support (`tkinter`). On minimal Linux installs you may need
  `sudo apt-get install python3-tk`.

## Run it

```bash
cd construction_app
python main.py
```

On first launch the app creates a SQLite database file, `construction.db`,
next to the code. That file is your data — it is **not** tracked in git
(see `.gitignore`); back it up if it matters.

## What's inside

The UI is a single tabbed window. To keep the top tab bar uncluttered, tabs are
grouped into eight top-level sections, each holding its related tabs:

- **Home** — plain-language dashboard (cash in hand, receivables, payables).
- **Masters** — Sites, Clients, Vendors, Materials, Labour, Equipment.
- **Operations** — Warehouse (ledger + stock), Muster & Wages (muster roll,
  weekly payout, thekedar ledger, statutory PF/ESI/cess calculator), Labour Ops
  (attendance/advances/payroll), Equipment Hire, Consumption reconciliation,
  Site Reports, Timeline/Gantt.
- **Billing** — Rate Book, Quotations, Estimates, Contracts, BOQ / RA Bills
  (incl. deviation statement), Running Bills, Tax Invoice.
- **Purchases** — Purchase Orders, Vendor Invoices (with PO reconciliation),
  Subcontractors (work orders + sub bills).
- **Money** — Cash & Parties (payments, party balances, cash book), Insight
  (profitability, progress %, material budget, receivables/payables + ageing).
- **Accounts** — GST & TDS registers (with HSN summary), and Accounting (chart
  of accounts, journal with auto-posting, trial balance, P&L, balance sheet).
- **Tools** — Backup & Settings (backup/restore, firm details, invoice series,
  language, Modules),
  Users & Security (optional login, roles, lockout), and the Audit Log.

## Project layout

```
construction_app/
├── main.py                 # Entry point; optional login, then grouped toggle-aware window
├── modules.py              # Module catalog (sections→tabs) + on/off toggles
├── branding.py             # App name + developer credit
├── projman.py              # Pure project maths: progress, budget status (testable)
├── tab_projects.py         # Projects, Milestones, Project Overview dashboard
├── ollama_client.py        # Stdlib client for a local Ollama server (no pip)
├── assistant.py            # RAG text-to-SQL over your data (read-only) + quick answers
├── tab_assistant.py        # Ask-your-data assistant tab
├── security.py             # Pure PBKDF2 password hashing (testable)
├── auth.py                 # Users, authentication, lockout, audit log (DB)
├── session.py              # Current-user/role holder
├── db.py                   # SQLite schema + connection helpers + default chart of accounts
├── finance.py              # Pure GST/TDS/reconciliation/double-entry maths (testable)
├── posting.py              # Pure double-entry posting rules per document (testable)
├── journal_post.py         # Auto-post engine: documents → balanced journal entries
├── civil.py                # Pure civil maths: measurement qty, RA bills, consumption, cube strength (testable)
├── estimate.py             # Pure estimate roll-up: subtotal→contingency→GST→grand total (testable)
├── money.py                # Pure cash-first maths: signed cash, running balance, party outstanding (testable)
├── numwords.py             # Pure Indian rupees-in-words (lakh/crore) (testable)
├── wages.py                # Pure wage maths: day-fraction, gross/deduction/net (testable)
├── bill_export.py          # Pure printable HTML: bill, RA abstract, GST tax invoice, statement (testable)
├── tab_home.py             # Plain-language home dashboard
├── tab_money.py            # Payments & receipts, party balances, cash book
├── tab_insight.py          # Site profitability, receivables, payables
├── crud_frame.py           # Generic "list + form" widget reused by most tabs
├── tab_masters.py          # Sites, Clients, Materials, Labor, Equipment
├── tab_vendor.py           # Vendors + spend/hire rollup
├── tab_warehouse.py        # Material ledger + stock summary
├── tab_labor.py            # Attendance, Advances, Payroll
├── tab_muster.py           # Muster roll, weekly payout, thekedar ledger
├── tab_documents.py        # Quotations, Purchase Orders, Contracts
├── tab_estimate.py         # Estimates (contingency + GST + grand total + print)
├── tab_billing.py          # Bills / Running Bills + bill export
├── tab_tax_invoice.py      # GST tax invoices (HSN, CGST/SGST/IGST, print)
├── tab_boq_ra.py           # BOQ, Measurement Book, RA bills
├── tab_consumption.py      # Consumption norms, work done, reconciliation
├── tab_site_reports.py     # DPR, cube/material tests, plant log
├── tab_vendor_invoice.py   # Vendor invoices (GST/TDS) + reconciliation
├── tab_gst.py              # GST output/input registers, summary, TDS register
├── tab_accounting.py       # Chart of accounts, journal, trial balance
├── tab_equipment_hire.py   # Equipment hire + cost auto-calc
└── tab_timeline.py         # Timeline tasks + Gantt chart
```

## Verifying changes without a display

There's no automated test suite yet. Quick sanity checks:

```bash
cd construction_app
python -m py_compile *.py                          # syntax check
python -c "import db; db.init_db(); print('ok')"   # schema check
```

## For AI coding agents

See **[`AGENTS.md`](AGENTS.md)** — a dense architecture-and-conventions guide
covering the reusable abstractions (`CrudFrame`, `DocumentFrame`,
`BillingTab`), the business-logic rules (payroll, running bills, hire costs),
the schema, and the intentional scope cuts you should flag rather than
silently "fix."
