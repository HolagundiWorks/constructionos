# Contractor-OS

A single-user desktop **ERP for Indian construction contractors** — a focused,
zero-dependency alternative to heavyweight suites like Dolibarr, tailored to the
construction trade. It covers site operations, procurement, commercial
documents, and the beginnings of full accounting:

- **Operations** — sites/warehouses, vendors, clients, materials, labor,
  equipment, stock ledger, attendance, payroll, advances, project timelines.
- **Commercial** — quotations, estimates, contracts, running bills (with a
  printable bill export).
- **Civil billing** — a BOQ per contract, a Measurement Book (Nos × L × B × D),
  and measurement-driven RA (Running Account) bills with a printable abstract.
- **Procurement** — purchase orders, vendor invoices with GST/TDS, and
  PO↔invoice reconciliation.
- **Site & quality** — material consumption reconciliation (theoretical vs
  actual), daily progress reports, cube-test and material-test registers, and a
  plant/machinery log.
- **Finance** — GST (CGST/SGST/IGST) and TDS computation, a seeded chart of
  accounts, a double-entry journal, and a trial balance.

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

The UI is a single tabbed window. Tabs group into five areas:

- **Masters** — Sites, Clients, Vendors, Materials, Labor, Equipment.
- **Operations** — Warehouse (material ledger + live stock summary),
  Labor Ops (attendance, advances, payroll generation), Equipment Hire
  (with automatic cost calculation from the hire period).
- **Procurement** — Purchase Orders (header + line items), Vendor Invoices
  (GST/TDS auto-computed), and PO↔invoice reconciliation.
- **Commercial** — Quotations and Estimates (header + line items with
  auto-totalling), Contracts, and Bills / Running Bills (running-total math
  plus a "Make Bill" printable HTML export).
- **Accounting** — Chart of Accounts, a double-entry Journal, and a Trial
  Balance report.
- **Planning** — Timeline tasks plus a hand-drawn Gantt chart view.

## Project layout

```
construction_app/
├── main.py                 # Entry point; builds the tabbed window
├── db.py                   # SQLite schema + connection helpers + default chart of accounts
├── finance.py              # Pure GST/TDS/reconciliation/double-entry maths (testable)
├── civil.py                # Pure civil maths: measurement qty, RA bills, consumption, cube strength (testable)
├── bill_export.py          # Pure printable bill / RA-abstract HTML generators (testable)
├── crud_frame.py           # Generic "list + form" widget reused by most tabs
├── tab_masters.py          # Sites, Clients, Materials, Labor, Equipment
├── tab_vendor.py           # Vendors + spend/hire rollup
├── tab_warehouse.py        # Material ledger + stock summary
├── tab_labor.py            # Attendance, Advances, Payroll
├── tab_documents.py        # Quotations, Estimates, Purchase Orders, Contracts
├── tab_billing.py          # Bills / Running Bills + bill export
├── tab_boq_ra.py           # BOQ, Measurement Book, RA bills
├── tab_consumption.py      # Consumption norms, work done, reconciliation
├── tab_site_reports.py     # DPR, cube/material tests, plant log
├── tab_vendor_invoice.py   # Vendor invoices (GST/TDS) + reconciliation
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
