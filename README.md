# Contractor-OS

A single-user desktop app for managing a construction company's day-to-day
operations — sites and warehouses, vendors, clients, materials, labor,
equipment, stock ledgers, attendance, payroll, advances, quotations,
estimates, contracts, running bills, equipment hire, and project timelines.

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

The UI is a single tabbed window. Tabs group into four areas:

- **Masters** — Sites, Clients, Vendors, Materials, Labor, Equipment.
- **Operations** — Warehouse (material ledger + live stock summary),
  Labor Ops (attendance, advances, payroll generation), Equipment Hire
  (with automatic cost calculation from the hire period).
- **Commercial** — Quotations and Estimates (header + line items with
  auto-totalling), Contracts, and Bills / Running Bills (with automatic
  running-total math across a contract).
- **Planning** — Timeline tasks plus a hand-drawn Gantt chart view.

## Project layout

```
construction_app/
├── main.py                 # Entry point; builds the tabbed window
├── db.py                   # SQLite schema + connection helpers
├── crud_frame.py           # Generic "list + form" widget reused by most tabs
├── tab_masters.py          # Sites, Clients, Materials, Labor, Equipment
├── tab_vendor.py           # Vendors + spend/hire rollup
├── tab_warehouse.py        # Material ledger + stock summary
├── tab_labor.py            # Attendance, Advances, Payroll
├── tab_documents.py        # Quotations, Estimates, Contracts
├── tab_billing.py          # Bills / Running Bills
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
