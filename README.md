# Construction OS

*Developed by Human Centric Works, Hospet.*

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Dependencies: none](https://img.shields.io/badge/pip%20dependencies-none-brightgreen.svg)
![Tests](https://img.shields.io/badge/tests-454%20passing-brightgreen.svg)

A single-user desktop **ERP for Indian construction contractors** — a focused,
zero-dependency alternative to heavyweight suites, tailored to the civil trade.
It runs offline on one PC, keeps everything in a single SQLite file, and is
built **entirely on the Python standard library**: `tkinter` for the UI,
`sqlite3` for storage. No pip packages, no web server, no build step, no cloud.

> Built for small civil contractors in tier-2 / tier-3 cities — offline, on one
> PC, minimal typing. See [`docs/PRODUCT.md`](docs/PRODUCT.md),
> [`docs/ROADMAP.md`](docs/ROADMAP.md) and [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md).

## Highlights

- **Intelligent home dashboard** — the whole business in one glance: a KPI band
  (cash, receivables with a past-90-day note, payables, net position, billed /
  collected this month, retention), a rule-based **advisory** engine that ranks
  what to do and attaches an honest **confidence** (High for a hard fact, Low
  for thin data), a **bottlenecks** scoreboard of where work and money sit
  still, and a **decisions-pending** queue — all computed on-device, no model
  required.
- **Project management** — a project umbrella (client + site + budget + LD
  terms), a per-project **drill-down** (budget vs cost, margin, programme slip
  + LD exposure, retention, open snags / RFIs / NCRs), a **Gantt** with
  critical-path / baseline-vs-actual, and a weekly **look-ahead** (PPC).
- **Civil billing** — a BOQ per contract, a **Measurement Book** (Nos × L × B ×
  D), measurement-driven **RA bills** with printable abstract, a PWD-style
  **deviation statement**, CPWA-form outputs (Form 23 MB, Form 26 recoveries,
  Muster Roll Form 21), and a configurable invoice number series.
- **Rate analysis + reference library** — build a per-unit rate on the CPWD DAR
  skeleton, and load a starter **CPWD reference library**: standard civil items
  (rate book), current material rates, and **consumption norms** — the material
  split for concrete, masonry, plastering and other civil work. Pick a priced
  item straight into an estimate or BOQ.
- **Procurement** — requisitions → PO → **goods receipt** (3-way match) →
  vendor invoices with GST/TDS; subcontractor work orders and running bills.
- **Money & accounts** — cash-first payments & receipts, reconciled
  receivables/payables ageing, cash-flow forecast, retention register, GST/TDS
  registers with HSN summary, and a double-entry ledger with one-click
  auto-posting → trial balance, P&L and balance sheet.
- **Compliance & plant** — a statutory filing calendar (GST, TDS, PF, ESI,
  cess), plant preventive-maintenance + fuel analysis, HSE and quality (ITP
  hold-points, NCRs, snag list / handover readiness).
- **Made to adopt** — a first-run wizard, **Load Sample Data** (a realistic demo
  book in its own file), **Hindi / Hinglish** labels, an HCW **rail + stage** UI
  with a **light / dark** toggle, and a friendly dialog instead of any error
  trace.
- **Optional login** — off by default (opens straight in). Turn on sign-in with
  user accounts and roles (Admin / Operator / Viewer), **versioned PBKDF2**
  password hashing (600k iterations, upgraded transparently on login), account
  lockout, and an audit log.
- **Optional AI assistant** — ask questions about your own data in plain English
  via a **local Ollama** model, using retrieval-augmented, **read-only**
  text-to-SQL (engine-enforced `query_only`); deterministic quick answers work
  without it.

## Requirements

- Python 3.8+
- Tk support (`tkinter`). On minimal Linux installs: `sudo apt-get install python3-tk`.

No other dependencies.

## Run it

```bash
cd construction_app
python main.py
```

On first launch the app creates `construction.db` next to the code — that file
is your data (not tracked in git; back it up). To explore with realistic data,
open **Tools › Company Files › Load Sample Data**.

## Install it (Windows — no Python needed)

Build a double-click Windows package from `installer/` (PyInstaller is fetched
into a throwaway build-only venv, so the shipped app stays pure-stdlib):

```powershell
cd installer
.\build.ps1              # PyInstaller + Inno Setup  -> Setup.exe
.\build.ps1 -Portable   # or a portable .zip (no Inno Setup needed)
```

An installed build stores the user's data in `%LOCALAPPDATA%\Construction OS`,
so it runs from a read-only Program Files folder and an uninstall never deletes
their books. See [`installer/README.md`](installer/README.md).

## The sections

A left **rail** switches between sections; each opens a **stage** of related
tabs. Sections can be toggled off per-firm in Tools.

- **Home** — the intelligent dashboard (KPIs, advisories, bottlenecks, decisions).
- **Assistant** — ask-your-data (optional local LLM).
- **Masters** — Sites, Clients, Vendors, Materials, Labour, Equipment.
- **Project Management** — Projects (+ per-project drill-down), Timeline/Gantt
  (CPM, baseline vs actual, LD/EOT), Look-ahead (PPC).
- **Operations** — Warehouse, Muster & Wages, Labour Ops, Equipment Hire, Plant
  (PM + fuel), Consumption reconciliation, Site Reports, Quality, Safety,
  Closeout.
- **Billing** — Rate Book, Rate Analysis, Bid / No-Bid, Quotations, Estimates,
  Contracts, BOQ / RA Bills, Variations, Running Bills, Tax Invoice.
- **Purchases** — Sourcing, Purchase Orders, Goods Receipt, Vendor Invoices,
  Subcontractors.
- **Money** — Key Numbers (KPI board), Approvals, Cash & Parties, Cash Flow,
  Retention, Insight.
- **Accounts** — GST & TDS, Compliance calendar, Accounting (journal, trial
  balance, P&L, balance sheet).
- **Tools** — Backup & Settings, Company Files (multi-firm / multi-year, Load
  Sample Data, Load CPWD Reference Data), Modules, Users & Security, Audit Log.

## Architecture

Pure business maths lives in tkinter-free modules (`money`, `civil`, `finance`,
`ageing`, `allocation`, `retention`, `programme`, `advisory`, `refdata` …) so it
is unit-testable headless; the `tab_*` modules are the GUI over them. Schema is
one string in `db.py` with additive column migrations. The single source of
truth for the section→tab grouping is `modules.SECTIONS_CATALOG`.

For a dense architecture-and-conventions guide (the reusable `CrudFrame` /
`DocumentFrame` abstractions, the business rules, the schema, and the
intentional scope cuts to flag rather than "fix"), see **[`AGENTS.md`](AGENTS.md)**.

## Tests

Standard-library `unittest` only — no pytest, matching the no-pip rule.

```bash
python -m unittest discover -s tests
```

Two layers (see [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md)):

- **`tests/test_core.py`** — the pure business maths and the posting engine
  (tax, civil quantities, wages, ageing, allocation, retention, programme/LD,
  the advisory engine, the reference data, password security, double-entry).
  Headless, ~2s.
- **`tests/test_smoke_tabs.py`** — builds every tab against the sample book
  under light **and** dark, catching data-dependent build errors. Needs a
  display; auto-skips on a headless box.

## Contributing

Issues and pull requests are welcome. Please keep the two hard rules: **no pip
dependencies** (standard library only) and **new business logic goes in a pure,
tkinter-free module with a unit test**. Run `python -m unittest discover -s tests`
before opening a PR; read `AGENTS.md` first.

## Security

Passwords use salted, versioned PBKDF2-HMAC-SHA256 (600k iterations) with a
constant-time verify, account lockout, and an audit log. The database itself is
**not** encrypted at rest — stdlib SQLite has no at-rest encryption, and a
native crypto dependency is deliberately avoided; for sensitive deployments,
put the data folder on an OS-encrypted volume. To report a vulnerability,
open an issue marked *security* or contact the maintainer.

## License

Construction OS is free software under the **GNU Affero General Public License
v3.0 or later** — see [`LICENSE`](LICENSE). In short: you may use, study, share
and modify it, but if you distribute a modified version — **including offering
it over a network** — you must make your source available under the same
license.

Copyright © 2026 Human Centric Works.
