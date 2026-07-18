# Contractor-OS

A single-user desktop **ERP for Indian construction contractors** — a focused,
zero-dependency alternative to heavyweight suites like Dolibarr, tailored to the
construction trade. It covers site operations, procurement, commercial
documents, and the beginnings of full accounting:

- **Operations** — sites/warehouses, vendors, clients, materials, labor,
  equipment, stock ledger, attendance, payroll, advances, project timelines.
- **Commercial** — quotations, estimates, contracts, running bills (with a
  printable bill export).
- **Estimates** — priced BOQ estimates with contingency and GST rolled up to a
  grand total, and a printable estimate document (amount in words).
- **Civil billing** — a BOQ per contract, a Measurement Book (Nos × L × B × D),
  and measurement-driven RA (Running Account) bills with a printable abstract.
- **Tax invoices** — GST tax invoices for clients (HSN/SAC, CGST/SGST/IGST,
  amount in words), printable to hand over or share.
- **Procurement** — purchase orders, vendor invoices with GST/TDS, and
  PO↔invoice reconciliation.
- **Site & quality** — material consumption reconciliation (theoretical vs
  actual), daily progress reports, cube-test and material-test registers, and a
  plant/machinery log.
- **Money (cash-first)** — payments & receipts, party balances ("who owes
  whom"), a cash/day book with running balance, and a plain-language home
  dashboard (cash in hand, receivables, payables).
- **Insight** — site-wise profitability (revenue vs material/labour/hire) and
  receivables/payables at a glance.
- **GST & TDS** — output/input GST registers, a net-position summary, and a
  TDS register, month-filtered and printable (for return time).
- **Finance (advanced)** — GST (CGST/SGST/IGST) and TDS computation, a seeded
  chart of accounts, a double-entry journal with one-click auto-posting of
  invoices & payments, and a trial balance (for the CA).

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
  weekly payout, thekedar ledger), Labour Ops (attendance/advances/payroll),
  Equipment Hire, Consumption reconciliation, Site Reports, Timeline/Gantt.
- **Billing** — Quotations, Estimates, Contracts, BOQ / RA Bills, Running Bills,
  Tax Invoice.
- **Purchases** — Purchase Orders, Vendor Invoices (with PO reconciliation).
- **Money** — Cash & Parties (payments, party balances, cash book), Insight
  (site profitability, receivables/payables).
- **Accounts** — GST & TDS registers, and Accounting (chart of accounts,
  journal with auto-posting, trial balance).
- **Tools** — backup & restore, firm details, and **Modules** (switch off
  any tab you don't use to declutter the UI).

## Project layout

```
construction_app/
├── main.py                 # Entry point; builds the grouped, toggle-aware tabbed window
├── modules.py              # Module catalog (sections→tabs) + on/off toggles
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
