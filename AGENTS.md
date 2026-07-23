# AGENTS.md — ACO (Accelerated Construction Operations)

This file is written for an **AI coding agent** (Claude Code, Cursor, etc.)
that will read, modify, or extend this codebase. It documents architecture,
conventions, and gotchas that are not obvious from the code alone. Read this
in full before making changes.

If you are a human developer, `README.md` is the friendlier version of this
document. This one is denser and assumes you will grep the source while
reading.

**Every count and claim below was verified against the tree.** If you change
something this document describes, update it in the same commit — see §25 for
the one-command way to re-check the numbers.

---

## 0. Product vision (read this first)

**ACO** (**Accelerated Construction Operations**, formerly *Construction OS*)
is a **full ERP for Indian construction contractors** — a focused,
zero-dependency alternative to heavyweight suites, tailored to the civil
trade. It runs offline on one PC, keeps everything in a single SQLite file,
and is built entirely on the Python standard library.

**Brand:** short name `ACO`; full name in `branding.APP_FULL_NAME`; logo mark
kept and recoloured to Radiant Orange (`#FF4F18`). Installed data folder is
`%LOCALAPPDATA%\ACO` (legacy `Construction OS` still opened if present).

The **Indian context** matters throughout: money carries GST split into
CGST+SGST (intra-state) or IGST (inter-state); vendor payments are subject to
TDS; materials carry HSN codes; billing follows PWD/CPWA forms; dates are
`YYYY-MM-DD`. Preserve these conventions when extending (§11, §12).

The **audience** matters just as much (see `docs/PRODUCT.md`): a T2/T3 solo or
small contractor who thinks in cash-in / cash-out and *"kitna baaki"*, not
debits and credits. Cash-first views are the primary experience; the
double-entry Accounting tab is positioned as advanced / for-the-CA. Lead new
financial features from plain language.

Keep the founding constraints intact unless explicitly told otherwise:
**Python 3.8+ standard library only, tkinter GUI, single SQLite file, no pip
dependencies.** These are what let the whole ERP run anywhere Python runs, by
double-clicking one folder.

> **UI direction (owner decision, in progress):** the **desktop UI is being
> replatformed to native WinUI 3** (Windows-only, C#/.NET, stock Fluent
> components) — an *explicit, approved* departure from the tkinter /
> cross-platform / no-pip constraints **for the front-end only**. The **Python
> domain core + its tests stay** and are reused as a **localhost backend
> service** (JSON API **u0.14**) the WinUI 3 client calls. See
> [`docs/WINUI3-MIGRATION.md`](docs/WINUI3-MIGRATION.md),
> [`docs/UI-PRINCIPLES-AND-GUIDELINES.md`](docs/UI-PRINCIPLES-AND-GUIDELINES.md)
> (Fluent / Windows 11 principles), and
> [`docs/APP-ARCHITECTURE.md`](docs/APP-ARCHITECTURE.md). Until WinUI reaches
> workflow parity, the tkinter app remains a shipping UI; the constraints above
> still govern all **domain/backend** work (which the WinUI move does *not*
> relax).
>
> **Two environments:** cloud agent (headless Python — domain/API/tests/docs) and
> local Windows (WinUI / display / .NET / sidecars). **Living status** (done vs
> pending) is **only** in [`docs/ROADMAP.md`](docs/ROADMAP.md). History:
> [`docs/CHANGELOG.md`](docs/CHANGELOG.md). Research (single report):
> [`docs/RESEARCH.md`](docs/RESEARCH.md). Do not recreate deleted status docs
> (`CLOUD-TASKS`, gap-and-roadmap, completeness audits, split `RESEARCH-*`).
> Local WinUI work follows the UI principles doc; cloud agents do not invent
> custom chrome or claim WinUI screenshots from Linux.

### What is built

Effectively the whole ERP surface is built. As of this writing the app is
**196 Python modules** (**133** of them AST tkinter-free), **85 tables**, **61
indexes**, and **744 passing tests** (5 skipped without display). Rather than a
feature checklist that
rots, the honest summary is:

- **Operations**: sites, warehouses, vendors, clients, materials, labour,
  equipment, stock ledger, attendance, muster roll, payroll, advances, plant
  maintenance + fuel, consumption reconciliation, site registers, quality
  (ITP/NCR), safety (permits/incidents/LTIFR), closeout/snags.
- **Commercial**: quotations, estimates, contracts, rate book, rate analysis
  (CPWD DAR), quantity takeoff, bid/no-bid scoring, variations, running bills,
  tax invoices.
- **Civil billing**: BOQ per contract, Measurement Book, measurement-driven RA
  bills, deviation statement, CPWA form outputs (Form 21/23/26) — §15.
- **Procurement**: requisitions, sourcing/quote comparison, purchase orders,
  goods receipt with **three-way match**, vendor invoices, subcontractor work
  orders and running bills — §7.
- **Project management**: project umbrella, per-project drill-down, CPM/critical
  path, baseline-vs-actual programme, LD exposure, Earned Value (SPI/CPI/EAC),
  weekly look-ahead (PPC), risk and opportunity registers — §22.
- **Money & accounting**: cash-first payments/receipts, payment-to-bill
  allocation, ageing, cash-flow forecast, retention register, approvals,
  GST/TDS registers with HSN summary, compliance calendar, double-entry ledger
  with auto-posting → trial balance, P&L, balance sheet — §9, §17.
- **Intelligence**: a rule-based advisory engine with honest confidence levels,
  risk detection, drift detection, forecasting, and plain-language narration —
  all computed on-device, no model required (`advisory.py`, `risk_detect.py`,
  `drift.py`, `forecast.py`, `narrative.py`).
- **AI assistant**: retrieval-augmented, read-only text-to-SQL over a local
  bundled model — §21.
- **Browser / LAN**: a stdlib HTTP server exposing the same SQLite file to the
  office network — §23.
- **Trust & ease**: first-run wizard, sample data, Hindi/Hinglish labels, a
  rail+stage UI with light/dark, and a no-stack-trace error handler.

Genuine remaining gaps are in §14 — and **only** the ones there. Do not infer a
gap from this document's silence; grep first.

## 1. Stack

- **Language/runtime**: Python 3.8+, standard library only.
- **GUI**: `tkinter` / `tkinter.ttk` (no web framework for the desktop app).
- **Web**: `http.server` for the optional LAN front end — still stdlib (§23).
- **Persistence**: SQLite via `sqlite3`, a single file created on first run and
  seeded with a default chart of accounts (§9).
- **No package dependencies.** Do not add `pip install` requirements unless
  explicitly asked — this is a deliberate design constraint. (PyInstaller is
  fetched into a throwaway build-only venv by `installer/build.ps1`, so the
  shipped app stays pure-stdlib.)
- **Business maths lives in pure, tkinter-free modules** — **133** AST-pure
  (includes web). This is the testable core; extend it there rather than burying
  new maths inside GUI callbacks.
- **Tests**: a committed stdlib `unittest` suite (no pytest, matching the no-pip
  rule). Add to it whenever you touch maths.

## 2. Running & verifying your changes

```bash
cd construction_app
python main.py
```

The full sweep used to validate changes, from the repo root:

```bash
python -m unittest discover -s tests               # 744 tests (GUI smoke needs display)
cd construction_app && python -m compileall -q .   # syntax check every module
python -c "import db; db.init_db(); print('ok')"   # schema + CoA seed check
```

The suite takes roughly a minute. It is in three layers (see
`docs/TEST_PLAN.md`):

- **`tests/test_core.py`** (~4,700 lines) — the pure business maths and the
  posting engine, driven end-to-end against a temporary SQLite database.
  Headless.
- **`tests/test_web.py`** — the browser/LAN layer: routing, sessions, the login
  gate, rendering. Headless.
- **`tests/test_smoke_tabs.py`** — builds **every** tab against the sample book
  under light **and** dark, catching data-dependent build errors. Needs a
  display; auto-skips on a headless box.

That last one is the reason a GUI change can still be verified cheaply: if you
have a display, `discover` runs it automatically. On a headless box it skips —
so **say so explicitly if you could not exercise the GUI**; don't claim you
tested a UI you couldn't render.

If you need to import a GUI module headlessly, stub `tkinter` (a fake package
with `ttk`, `messagebox`, `filedialog` submodules exposing no-op widget
classes) on `PYTHONPATH`. The **133** tkinter-free modules need no such trick.

## 3. Code layout — the layer model

`construction_app/` is flat (no packages) and large. Don't look for a file list
here; it would rot. Learn the **four layers** instead, then use the naming
rules to find or place any module.

```
construction_app/
├── <name>.py          PURE layer — business maths, DB access, no tkinter.
├── tab_<name>.py      GUI layer — the tkinter tab over a pure module.
├── web*.py            BROWSER layer — the LAN front end (§23).
└── resources/         Committed brand assets (logos, .ico).
```

**The naming rule is load-bearing**: a `tab_*.py` module is GUI; nearly
everything else is tkinter-free and unit-testable. The handful of non-`tab_`
GUI modules are shared UI infrastructure — `crud_frame`, `shell`, `theme`,
`widgets`, `errors`, `ui_guard`, `report_open`, `ratebook_picker`.

**The pairing rule**: most features are a pure module plus its tab —
`risk.py`/`tab_risk.py`, `retention.py`/`tab_retention.py`,
`quality.py`/`tab_quality.py`, `plant.py`/`tab_plant.py`, and so on. When you
add a feature, follow the pair. When you look for maths, drop the `tab_`.

**Registers that persist** add a third `*_store.py` module holding the SQL over
the pure scoring module — `risk_store.py`, `opportunity_store.py`,
`lessons_store.py`, `portfolio_store.py`. Keep scoring pure and SQL in the
store.

### The load-bearing infrastructure modules

Know these before touching anything:

| Module | Why it matters |
|---|---|
| `db.py` | The entire schema in one `SCHEMA` string + `get_conn()` + `init_db()` + CoA seed + indexes + column migrations (§10). |
| `modules.py` | `SECTIONS_CATALOG` — the **single source of truth** for section→tab grouping, shared by `main.py` and the Tools toggle panel (§11). |
| `main.py` | Entry point: `company.apply_active()`, DB init, company+login dialog, theme, wizard, then the rail. `BUILDERS` maps each module label to its widget. |
| `company.py` | Multi-firm registry (`companies.json`), create/export/import, carry-forward, `apply_active` / `select_company`. |
| `shell.py` | `RailStage` — the rail + stage shell. **The app is not a top-level Notebook** (§24). |
| `crud_frame.py` | `CrudFrame` + `Field` — the list+form widget behind every simple tab (§4). |
| `tab_documents.py` | `DocumentFrame` — header + line-items documents (§5). |
| `isodate.py` | The one tolerant date parser every dated pure module must use (§11). |
| `finance.py` | GST/TDS/invoice/reconciliation maths — the tax core (§12). |
| `posting.py` / `journal_post.py` | Pure posting rules, and the idempotent engine that applies them (§9). |
| `ui_guard.py` | The one-line write guard for role-based access (§20). |
| `paths.py` | Where files live when run from source vs installed. Use it; never hardcode. |
| `tokens.py` / `theme.py` | Design tokens shared by desktop **and** web; the tkinter theme over them (§24). |

### Where new code goes

- Flat single-table form (a master or a transaction log) → a `CrudFrame` in an
  existing or new `tab_*.py` (§4).
- Header-with-line-items document whose total is just the sum of item amounts →
  reuse `DocumentFrame` (§5).
- Header+items with **computed columns beyond a simple sum** → a bespoke tab
  that reuses the *pattern* but delegates maths to a pure module.
  `tab_billing.py` and `tab_vendor_invoice.py` are the reference examples (§6).
- New tax/accounting maths → a pure function in `finance.py`.
- New domain maths → a **new pure module** plus a test, then its `tab_`.

## 4. The `CrudFrame` abstraction

`crud_frame.py` defines two things:

- **`Field(key, label, kind='text', width=110, options=None, options_func=None, default='', remember=False)`**
  Describes one form field / table column.
  - `kind='text'` → plain `ttk.Entry`, stored as string.
  - `kind='number'` → `ttk.Entry` parsed with `float()` on save.
  - `kind='combo'` → read-only `ttk.Combobox` from a static `options=[...]`.
  - `kind='fk'` → read-only `ttk.Combobox` populated by `options_func(conn)`
    returning `[(id, label), ...]`. The combobox displays `"{id} - {label}"`;
    `CrudFrame` parses the leading id back out on save via
    `raw.split(' - ')[0]` (first ` - ` only, so labels may contain ` - `). Be
    aware of this coupling if you change the display format.
  - `default=TODAY` prefills today's date; `remember=True` persists the last
    value per `last:<table>:<column>` and prefills it next time. Both exist to
    cut typing — apply them to new ops tabs.

- **`CrudFrame(parent, db_getter, table, fields, title, extra_where='', order_by='id DESC', on_save=None)`**
  A `ttk.Frame` with a `Treeview` list, an auto-generated form, and
  Add/Update/Delete/Clear/Refresh buttons, running raw SQL against `table`. It
  has **no idea about foreign keys or business rules**; any derived column or
  side effect goes in `on_save(conn, row_id, values_dict)`, invoked after
  insert/update. See `_compute_hire_total` / `_compute_duration` / `_compute_cube`
  for the pattern: compute, `UPDATE` the derived column, `commit()`, and never
  raise — wrap in `try/except: pass`, because these are best-effort auto-fills
  the user may override.

  **`on_save` connection lifetime**: `CrudFrame` `close()`s the `conn` right
  after the callback returns. Don't close it yourself, don't stash it.

  **Deletion does not cascade at the app level** — `delete_selected` issues a
  bare `DELETE FROM {table} WHERE id = ?`. With `PRAGMA foreign_keys = ON`,
  deleting a parent still referenced by a non-cascading child raises
  `sqlite3.IntegrityError`; this is **caught** and shown as a plain-language
  dialog ("this record is still used elsewhere…"), never a stack trace. To make
  a table cascade, add `ON DELETE CASCADE` in the schema — don't add per-tab
  delete logic.

  **Writes are role-guarded** — see §20.

## 5. The `DocumentFrame` abstraction

`tab_documents.py`'s `DocumentFrame` is a header (`Treeview` + form) over a
line-items grid, joined by a foreign key column (`fk_col`). Selecting a header
loads only that document's items. Every item change calls `_recalc_total`,
which re-sums the items into the header's `total_col`. **The header total is
always derived** — there is no field for it in `header_fields`; don't add one.
Item amount is auto-computed as `qty * rate`. It also carries a Print/Export
button rendering via `bill_export.build_statement_html`.

For **purchase orders**, `total_amount` is the **pre-tax items subtotal**;
`gst_pct` is header metadata only, realised downstream when a vendor invoice is
booked against the PO. `DocumentFrame` has no tax concept — a GST-inclusive
live PO total would be a bespoke change.

To add another header+items document type:
1. Add `<thing>` and `<thing>_items` tables to `db.py`'s `SCHEMA` (header needs
   `id` + a total column; items need `id`, the fk column, `description`, `unit`,
   `qty`, `rate`, `amount`, and `ON DELETE CASCADE` on the fk).
2. Add a `build_<thing>_tab(parent, db_getter)` returning a `DocumentFrame`.
3. Register it in `modules.SECTIONS_CATALOG` **and** `main.BUILDERS` (§11).

## 6. `BillingTab` (Running Bills) — bespoke

Running bills need a computed `previous_billed` that `DocumentFrame` has no
concept of, so `tab_billing.py` is bespoke:

```
previous_billed = SUM(net_payable) FROM bills
                   WHERE contract_id = <this contract>
                   AND status IN ('Approved', 'Paid')
                   [AND id != <this bill, when updating>]

net_payable = work_done_value - previous_billed - retention_amt - other_deductions
```

`Draft`/`Submitted` bills are excluded from `previous_billed`. Consequence:
changing a bill's status to Approved/Paid changes `previous_billed` (hence
`net_payable`) for every *subsequent* bill on that contract, but does **not**
retroactively recompute bills saved earlier (§14).

`bill_items` are a BOQ breakdown that do **not** auto-drive `work_done_value`:
the user clicks **"Sum Items → Work Done Value"**, then **"Update Selected"** to
persist. Intentional two-step.

**Export**: `bill_export.py` is a pure module (no tkinter/DB) exposing nine HTML
builders — `build_bill_html`, `build_ra_bill_html`, `build_tax_invoice_html`,
`build_statement_html`, `build_estimate_html`, `build_muster_roll_html`,
`build_unpaid_wages_html`, `build_mb_html`, `build_ra_pwd_html`. Keep rendering
logic there, not in GUI handlers. HTML → browser → print / Save-as-PDF is the
deliberate stdlib-only substitute for a PDF library.

## 7. Procurement — requisition → PO → receipt → invoice

**Purchase Orders** (`DocumentFrame`, §5): vendor, site, dates, `gst_pct`, and a
lifecycle `status` (Draft→Sent→Partially Received→Received→Closed/Cancelled).
`purchase_order_items.material_id` lets a line name a master material, so a
goods receipt can move real stock instead of guessing from free text.

**Goods Receipt + three-way match** (`procurement.py`, `tab_grn.py`): receipts
(`goods_receipts`/`grn_items`) are matched PO ↔ GRN ↔ invoice. This is the
procurement gate; maths is pure in `procurement.py`.

**Vendor Invoices** (`tab_vendor_invoice.py`, bespoke): line items give a
pre-tax `subtotal`; `finance.invoice_totals(subtotal, gst_pct, tds_pct, interstate)`
rolls it up:

```
tax_amount   = GST on subtotal (CGST+SGST intra-state, or IGST inter-state)
total_amount = subtotal + tax_amount           (invoice gross value)
tds_amount   = TDS on the pre-GST subtotal     (withheld from payment)
net_payable  = total_amount - tds_amount       (actually paid to the vendor)
```

Those five columns are **always derived** — `_recalc` runs on every item and
header change; never hand-enter them.

**Reconciliation** (`ReconciliationView`): compares each invoice's pre-tax
subtotal against its linked PO's via `finance.reconcile(...)`, flagging
`Matched` / `Over-billed` / `Under-billed` / `No PO` with a variance and
variance-%. This totals-level view still exists alongside the stricter GRN
three-way match above; the tolerance is an absolute amount entered in the view.

**Sourcing** (`sourcing.py`, `tab_sourcing.py`): quote comparison, a
three-factor vendor rating (`vendors.quality`/`delivery`/`price` plus an
`approved` flag), RFIs and drawing revisions. Three factors, not ten —
deliberately, because a ten-factor scorecard for a firm with eleven suppliers is
a form nobody fills in twice.

## 8. Labour & payroll

Wage maths lives in `wages.py` and is shared by every labour surface:
`day_fraction` (`Present`=1.0, `Half Day`=0.5, `Overtime`=`1 + max(0, hours-8)/8`,
`Absent`=0) and `wage_net(days, daily_wage, open_advance_balance)` →
`{gross, deduction, net}`, where deduction is
`min(open_advance_balance, gross)` and net is never negative.

- **Muster Roll** (`tab_muster.py`): site + date → every `status='Active'`
  labourer in an editable grid, pre-filled from existing attendance. **Save
  Muster** writes one `attendance` row per labourer per day, `DELETE`ing any
  existing row for that `(labor_id, att_date)` first — the `attendance` table
  has no unique constraint, so this delete-then-insert is what enforces
  one-mark-per-day. `muster.py` shapes it into CPWA Form 21.
- **Weekly Payout**: site + week-start → 7-day window; per labourer, days =
  Σ`day_fraction`, then `wages.wage_net`. **Record as Payments** inserts a
  `payments` row per positive net so wages flow into the cash book. It does
  **not** mark advances recovered and does **not** dedupe — running it twice
  records twice (§14).
- **Monthly Payroll** (`tab_labor.py`): generation is a no-op for a
  `(labor_id, month, year)` that already has a `payroll` row — it skips, doesn't
  update. Only `status='Active'` labour is included. Paid payroll **is**
  auto-posted (§9).
- **Thekedars** (labour contractors): a master plus a running ledger —
  `entry_type='Work'` increases what we owe, `'Paid'` decreases it.
- **Statutory** (`statutory.py`, optional, off the main flow): EPF, ESI,
  BOCW labour cess, with optional `labor.pf_no`/`esi_no`. Nothing auto-deducts.

## 9. Accounting — chart of accounts, journal, statements, auto-posting

`tab_accounting.py` is an inner notebook over three tables (`accounts`,
`journal_entries`, `journal_lines`). Pure checks live in `finance.py`, posting
rules in `posting.py`, statements in `reports.py`.

- **Chart of Accounts**: a `CrudFrame` over `accounts` (`code`, `name`, `type` ∈
  Asset/Liability/Income/Expense/Equity, self-referential `parent_id`,
  `is_active`). A **default construction CoA is seeded once** by
  `db.seed_default_accounts` on first run (no-op if any account exists).
- **Journal** (bespoke double-entry): each line is a debit XOR a credit against
  one account (`_collect_line` rejects both). Header `total_debit`/`total_credit`
  are derived on every change, with a live `finance.is_balanced` indicator. The
  UI **allows saving an unbalanced entry** so you can build it up line by line —
  balancing is surfaced, not enforced at write time. If you add a "post" action,
  that is where to enforce `is_balanced` hard.
- **Trial Balance / P&L / Balance Sheet**: `reports.profit_and_loss` and
  `reports.balance_sheet` read straight off per-account debit/credit totals —
  the same rows the trial balance uses. Current-period profit folds into equity
  so the sheet ties out.

### Auto-posting

The Journal's **"Auto-Post Documents"** button runs `journal_post.post_all(conn)`,
which posts a balanced entry for every unposted document across **seven
sources**:

| Source | Filter | Rule in `posting.py` |
|---|---|---|
| `tax_invoices` | `status != 'Cancelled'` | `tax_invoice_lines` |
| `vendor_invoices` | all | `vendor_invoice_lines` |
| `payments` | all | `payment_lines` |
| `sub_bills` | `Approved`/`Paid` | `sub_bill_lines` |
| `ra_bills` | `Approved`/`Paid` | `ra_bill_lines` |
| `bills` (running) | `Approved`/`Paid` | `ra_bill_lines` |
| `payroll` | `status = 'Paid'` | `payroll_lines` |

Idempotency is via `journal_entries.(source, source_id)`, so re-running only
posts new documents. Because every generated entry balances, the trial balance
stays balanced no matter how many documents are posted.

Account codes are constants at the top of `posting.py` — including
`RETENTION_RECEIVABLE = '1400'` and `TDS_RECEIVABLE = '1500'`, which is what
lets client-withheld retention on RA/running bills post correctly as an asset.

If you add a document type: add a `*_lines` rule in `posting.py`, add a loop in
`post_all`, and keep each entry balanced. Auto-posting is a **manual action**,
not automatic on save, and there is **no un-post/reverse** — delete the journal
entry to re-post (§14).

## 10. Database schema

All **85 tables** and **61 indexes** live in one `SCHEMA` string in `db.py`.
`get_conn()` sets per connection:

- **`foreign_keys = ON`** — FKs won't enforce otherwise. Any script or test
  opening SQLite outside `db.get_conn()` must re-issue this.
- **`journal_mode = WAL`** + **`synchronous = NORMAL`** — crash-resilient writes.
- **`busy_timeout = 5000`** — a second short-lived connection waits instead of
  raising "database is locked". This matters more now that the LAN server (§23)
  can be hitting the same file as the desktop app.

WAL adds `-wal`/`-shm` sidecar files; a checkpoint on clean close folds the WAL
back in, so the plain file copy that backup/restore does is consistent between
operations.

**Adding a column to an existing table**: `CREATE TABLE IF NOT EXISTS` never
alters a table that already exists, so a new column won't reach an older
database. Update the `SCHEMA` `CREATE` (for fresh installs) **and** add the
column to `db._ADD_COLUMNS` — `_apply_column_migrations` (run by `init_db`)
issues an idempotent `ALTER TABLE ... ADD COLUMN` per missing column. This is
the lightweight stand-in for a real migration framework, and it is the single
most commonly missed step when extending the schema.

**Cascades**: 21 `ON DELETE CASCADE` declarations exist in the schema — every
`*_items` child, `journal_lines`, `milestones`, and more. Everything else relies
on app-level `delete_*` methods to clean up children (e.g.
`DocumentFrame.delete_header` deletes items before the header).
`CrudFrame.delete_selected` never cascades; it fails gracefully instead (§4).

Core relationships:

```
sites 1──* labor / material_ledger / equipment_hire / timeline_tasks
          / estimates / contracts / equipment(current_site_id) / purchase_orders
vendors 1──* material_ledger(vendor_id, txn_type='IN') / equipment_hire
            / purchase_orders / vendor_invoices / quotes
clients 1──* quotations / contracts
labor   1──* attendance / advances / payroll
projects 1──* milestones (CASCADE) / timeline_tasks(project_id)
contracts 1──* bills                      (running bill chain — §6)
contracts 1──* boq_items 1──* measurements (measurement book — §15)
purchase_orders 1──* purchase_order_items (CASCADE) / vendor_invoices / goods_receipts
goods_receipts  1──* grn_items
work_orders     1──* work_order_items (CASCADE) / sub_bills
accounts        1──* journal_lines (account_id, NO cascade) / accounts(parent_id)
journal_entries 1──* journal_lines (CASCADE)
payments        1──* payment_allocations   (payment → bill settlement)
```

`app_settings` is a key/value table for singletons: `cash_opening`,
`works_gst_pct`, `invoice_prefix`/`invoice_width`/`invoice_fy_reset`, `language`,
`setup_done`, `theme`, assistant config, `module:<label>` toggles, and
`last:<table>:<column>` remember-last values.

## 11. Conventions to follow when extending

- **Dates are plain `TEXT` `YYYY-MM-DD`.** In pure modules, parse through
  `isodate.parse(value)` (→ `date` or `None`, never raises) rather than
  hand-rolling another tolerant parser — ten modules each grew their own copy and
  the copies drifted, one into a `TypeError` on datetime input. `strict=True`
  refuses a time part instead of truncating (the muster roll relies on this).
- **Money/qty are `REAL` (float)**, not `Decimal`. `finance.money(x)` coerces and
  rounds to 2 decimals at boundaries. Never compare floats for equality — use the
  `eps` in `finance.is_balanced`.
- **Indian tax**: GST always via `finance.split_gst` (CGST+SGST intra, IGST
  inter, driven by the `interstate` flag); TDS via `finance.compute_tds` on the
  pre-GST base. Don't hardcode a GST rate — it's a per-document field
  (`gst_pct`), defaulting to 18.
- **Double-entry**: money that moves should be expressible as balanced journal
  lines.
- **No ORM.** Raw SQL over `sqlite3.Row`-returning connections. Keep this style.
- **SQL string-building uses only trusted, hardcoded table/column names** via
  f-strings; **values always go through `?` placeholders.** Preserve this split —
  it is the entire injection defence.
- **`db.get_conn` is passed as `db_getter` (a callable, not a live connection)**
  — every operation opens a fresh short-lived connection and closes it. Don't
  hold one across callbacks.
- **Every tab module exposes either `build_*_tab(parent, db_getter)` returning a
  widget, or a class taking `(parent, db_getter)` subclassing `ttk.Frame`** —
  both are just callables `builder(parent, db_getter)`. Tabs with several views
  return an inner `ttk.Notebook`.
- **Adding a tab**: add its label to a section in `modules.SECTIONS_CATALOG`
  **and** an entry in `main.BUILDERS`. The two must agree — a label with no
  builder `KeyError`s at startup. Optionally add a pictogram to
  `main.MODULE_ICONS` and an `i18n` entry.
- **Module toggles**: every catalog label is switchable. State lives in
  `app_settings` as `module:<label>` (`'1'`/`'0'`, absent = on); helpers in
  `modules.py`. `main.py` reads them once at startup and skips disabled tabs (and
  any section left empty), so **changes apply on next launch**.
- **Paths**: use `paths.py`. An installed build stores data in
  `%LOCALAPPDATA%\ACO` so the app runs from a read-only Program
  Files folder (legacy `%LOCALAPPDATA%\Construction OS` still opened if
  present); hardcoding a path next to the code breaks that.
- **Write guards**: every write entry point starts with `ui_guard.can_write()`
  (§20).

## 12. Indian-context cheatsheet

- **GST**: intra-state → CGST + SGST (rate split in half); inter-state → IGST
  (full rate). `finance.split_gst(taxable, gst_pct, interstate)`.
- **TDS**: withheld from the vendor payment, computed on the pre-GST base.
  `finance.compute_tds(taxable, tds_pct)`. Booked to `TDS Payable`; TDS withheld
  *from us* by a client goes to `TDS Receivable` (1500).
- **Input GST Credit** (asset) vs **GST Payable** (liability): purchases accrue
  input credit; sales accrue output GST payable.
- **Retention**: withheld from running/RA bills — `Retention Payable` (2300) when
  we withhold from a subcontractor, `Retention Receivable` (1400) when a client
  withholds from us. `retention.py` handles release and defect-liability timing.
- **HSN codes** live on `materials` and drive the GSTR-1-style HSN summary.
- **Financial year** is April–March — `numbering.financial_year` and the
  compliance calendar both depend on this.
- **CPWA/PWD forms**: Form 21 (muster roll), Form 23 (measurement book), Form 26
  (RA bill abstract with statutory recoveries). `muster.py`, `mb.py`,
  `mb_report.py`, and the `bill_export` builders produce them.

## 13. Verifying finance/accounting changes

The pure layer is the safety net. Quick checks that should always hold:

```bash
python -c "import finance as f; \
  assert f.split_gst(10000,18)['cgst']==900; \
  assert f.invoice_totals(10000,18,2)['net_payable']==11600; \
  assert f.reconcile(10000,10500,100)['status']=='Over-billed'; \
  assert f.is_balanced(1500,1500) and not f.is_balanced(1500,1400); \
  print('finance ok')"
```

Prefer adding a case to `tests/test_core.py` over a one-off `python -c`; the
suite is the thing that will catch a regression six months from now.

## 14. Known gaps / things to flag rather than silently "fix"

Intentional scope cuts and honest limitations — **verified as still true**.
Mention them to the user before changing, since "fixing" one is a feature
request, not a bug fix.

- **Auto-posting is a manual action with no reverse.** `post_all` covers seven
  document types (§9) but runs only when the user clicks "Auto-Post Documents",
  and there is no un-post — you delete the journal entry to re-post.
- **The journal accepts unbalanced entries at write time** (§9). Deliberate, so
  an entry can be built line by line.
- **No retroactive recompute of prior bills' `previous_billed`** when a later
  bill's status changes (§6).
- **RA "previous quantity" only counts Approved/Paid RA bills** (mirrors §6), so
  generating multiple *Draft* RA bills before approving them can double-count
  quantities. Approve each RA bill before generating the next.
- **An RA bill is a snapshot** — it does not live-recompute when later
  measurements are added. Regenerate before approval if measurements changed.
- **PO `total_amount` is pre-tax**; there is no GST-inclusive live PO total (§5).
- **`CrudFrame` delete never cascades** — it fails gracefully with a friendly
  dialog instead (§4). Add `ON DELETE CASCADE` in the schema if a table needs it.
- **Weekly payout does not dedupe or mark advances recovered** — running it twice
  records the payments twice (§8).
- **No regenerate/delete affordance for payroll rows** (§8).
- **Consumption reconciliation matches activities by exact name string**
  (`consumption_norms.activity == work_done_entries.activity`) — a typo means no
  theoretical figure. There is no dropdown/FK linking the two.
- **Cube result is a per-cube `strength >= grade` check**, not the statistical IS
  456 acceptance criterion over a sample set.
- **No PDF library.** Export is HTML → browser → print / Save-as-PDF (§6).
  (`pdf_render.py` goes the *other* direction — PDF page → PNG, so a drawing can
  be traced in the takeoff canvas — and it shells out to an external tool that
  may not be present. It fails soft.)
- **Project cost/revenue is derived via the project's `site_id`**, not a hard
  project↔transaction link, so two projects sharing a site would share those
  figures. Fine for the common one-site-per-project case; note it if you add
  multi-project sites.
- **Party matching keys on `party_id`**, falling back to `party_name` for
  free-typed parties — so a mistyped name starts a separate balance line.
- **Security is opt-in and off by default** (§20). Roles gate the UI, not the DB;
  there is no row-level security and **no at-rest encryption** (stdlib SQLite has
  none, and SQLCipher would break the no-dependency rule). For sensitive
  deployments, put the data folder on an OS-encrypted volume.
- **The LAN server is plain HTTP for a trusted network** (§23). Put it behind an
  HTTPS reverse proxy for anything wider — see `docs/LAN.md`.
- **The assistant needs a local model to do anything beyond quick answers** (§21),
  and its SQL is model-generated — correct-looking output can still be the wrong
  question. It is read-only by construction, so the failure mode is a wrong
  answer, not a corrupted book.

## 15. Civil billing — BOQ, Measurement Book, RA bills

This is the civil-contracting billing spine, and it is **measurement-driven**
(unlike the generic `BillingTab` in §6, which takes a hand-typed work-done
value). Arithmetic lives in `civil.py` and `mb.py`; `tab_boq_ra.py` is the UI.

- **BOQ** (`boq_items`): priced items per contract — `item_no`, `description`,
  `unit`, `qty`, `rate`, `amount = qty*rate`. Deleting a BOQ item cascades its
  measurements.
- **Measurement Book** (`measurements`): quantity = **Nos × L × B × D** via
  `civil.measurement_quantity`, where a **blank dimension counts as 1** (a
  running-metre item is `Nos × Length`; a count is just `Nos`). Blank dims are
  stored as SQL `NULL`; the live Quantity label updates as you type. `mb.py`
  adds structure, integrity checks and CMB eligibility; `measured_by`/
  `checked_by` exist because the Works Manual wants a signature per set.
- **RA bills**: "Generate RA Bill" snapshots, per BOQ item, `upto_qty`
  (cumulative measured with `mb_date <= bill_date`), `previous_qty` (sum of
  `current_qty` from prior Approved/Paid RA bills), and
  `current_qty = upto - previous`, priced at the BOQ rate.
  `civil.ra_bill_totals` derives `this_bill_value`, `cumulative_value`,
  `retention_amt`, and `net_payable`. Status moves
  Draft→Submitted→Approved→Paid. Exports: the standard RA abstract, plus CPWA
  **Form 23** (measurement book) and **Form 26** (PWD abstract with the
  statutory recovery block) via `mb_report.py`.
- **Deviation statement**: `civil.deviation` (tendered BOQ vs executed measured
  qty → excess/saving), shown in `tab_boq_ra.py`.
- **Variations** (`variation.py`, `tab_variations.py`): the change-order register
  that protects revenue when scope moves outside the BOQ.

If you add subcontractor RA bills, reuse this pattern (BOQ→MB→RA), not the
generic `BillingTab`.

## 16. Site execution & quality

**Consumption reconciliation** (`tab_consumption.py`): norms
(`consumption_norms`, e.g. 6.0 bags cement / cum of 'M20 Concrete') × work done
(`work_done_entries`) gives theoretical consumption; actual is the `OUT` ledger
quantity per material; variance and wastage% via `civil.reconcile_consumption`.
Over-consumption rows are tinted red. Activities join **by exact name** (§14).

**Site registers** (`tab_site_reports.py`): Daily Progress, Cube Tests
(`strength_mpa` and Pass/Fail auto-filled by an `on_save` hook using
`civil.cube_strength` = `load_kN × 1000 / area_mm²`), Material Tests, Plant Log.

**Quality** (`quality.py`, `tab_quality.py`): ITP hold points, inspections,
NCRs. **Safety** (`hse.py`, `tab_hse.py`): work permits, incidents, LTIFR,
toolbox talks, inductions. **Plant** (`plant.py`): preventive-maintenance
schedule, service history, fuel analysis. **Closeout** (`closeout.py`): snag
list and handover readiness.

## 17. Money — cash-first, the primary financial UX

The cash-first views are the primary financial experience (§0); Accounting is
advanced. Lead new financial features from here, in plain language.

- **`payments`** is one table for both directions: `direction` is `Receipt` or
  `Payment`; `party_type` ∈ Client/Vendor/Labour/Other with a nullable
  `party_id` plus a denormalized `party_name` snapshot (so a statement still
  reads correctly if the master row changes or the party was free-typed);
  `mode` ∈ Cash/Bank/UPI/Cheque.
- **Allocation** (`allocation.py`, `tab_allocate.py`, `payment_allocations`):
  spread a payment across the bills it settles. This is what turns the
  cash-vs-billed approximation into a reconciled position.
- **Party Balances**: a running statement plus a headline outstanding, via
  `money.party_outstanding(billed, settled)`.
- **Cash Book**: the digital bahi-khata — `mode='Cash'` entries turned into a
  running balance over `app_settings.cash_opening` via `money.running_balance` /
  `closing_balance`.
- **Ageing** (`ageing.py`): FIFO-settle a party's dated bills by receipts, bucket
  the remainder 0-30/30-60/60-90/90+.
- **Cash Flow** (`cashflow.py`), **Retention** (`retention.py`), **Approvals**
  (`approval.py`), **Key Numbers** (`tab_kpi.py`), **Insight**
  (`tab_insight.py`, over `analytics.py`) complete the money section.
- **Home** (`tab_home.py` over `dashboard.py` + `advisory.py`): a KPI band, a
  ranked advisory list with honest **confidence** (High for a hard fact, Low for
  thin data), a bottlenecks scoreboard, and a decisions-pending queue. All
  computed on demand; nothing stored; no model required.

## 18. Verifying civil & money changes

```bash
python -c "import civil as c; \
  assert c.measurement_quantity(4,3,2,'')==24.0; \
  assert c.ra_current(120,100,250)==(20,5000.0); \
  assert c.ra_bill_totals(100000,400000,5,2000)['net_payable']==93000; \
  assert c.cube_strength(450,22500)==20.0 and c.cube_result(20,'M20')=='Pass'; \
  print('civil ok')"

python -c "import money as m; \
  assert m.running_balance([1000,-400,200],100)==[1100,700,900]; \
  assert m.closing_balance([1000,-400,200],100)==900; \
  assert m.party_outstanding(50000,30000)==20000; \
  print('money ok')"

python -c "import wages as w; \
  assert w.day_fraction('Overtime',12)==1.5; \
  assert w.wage_net(6,700,1000)=={'gross':4200.0,'deduction':1000.0,'net':3200.0}; \
  print('wages ok')"
```

## 19. Reference data & rate build-up

- **`refdata.py`** — a starter **CPWD reference library**: standard civil items
  (rate book), current material rates, and consumption norms (the material split
  for concrete, masonry, plastering). Loaded from Tools; lets a fresh book be
  useful before any data entry.
- **`rateanalysis.py`** — build a per-unit rate on the CPWD **Analysis of Rates**
  skeleton (material + labour + plant + overhead + profit).
- **`ratebook_picker.py`** — a modal picker so a priced item can be pulled
  straight into an estimate or BOQ.
- **`takeoff.py`** / `tab_takeoff.py` — quantity takeoff measured off a drawing
  on a canvas, with `pdf_render.py` converting a PDF page to a backdrop image.
- **`lessons.py`** / `lessons_register.py` / `lessons_store.py` — achieved rate
  vs standard rate, closing the loop back into the rate library.

## 20. Security & robustness (opt-in login, roles, audit)

**Opt-in by design.** The app ships with security **off** — credentials are
optional so the solo contractor keeps zero-friction access. An office with
staff turns security on in **Tools › Users & Security**; that requires at least
one active **Admin** first (`auth` won't let you enable login or demote/
deactivate the last admin). `main.py` **always** shows the boot dialog so the
user can **select a company** (registry in `companies.json` via `company.py`),
then Sign in when that book has security on, or **Continue** when it does not.
`company.apply_active()` runs before `init_db` so the last-chosen file opens.

- **Passwords** (`security.py`): salted, **versioned** PBKDF2-HMAC-SHA256 at
  **600,000 iterations** (OWASP 2023 floor), constant-time verify via
  `hmac.compare_digest`. The stored hash is **self-describing** —
  `pbkdf2_sha256$<iterations>$<hex>` — and `needs_upgrade` detects a
  below-current-cost hash so it is transparently re-hashed on next successful
  login. Legacy bare-hex hashes are read as the old 120k cost and upgraded.
  Never store or log plaintext.
- **Lockout**: `auth.authenticate` increments `failed_attempts` and sets
  `locked=1` at `MAX_FAILED` (5); an Admin clears it. Failure messages are
  generic — no user enumeration.
- **Roles** (`session.ROLES`): Admin (all, incl. user management), Operator
  (day-to-day), Viewer (read-only). When security is off there is no session and
  both `is_admin()` and `can_write()` default to full access — so gate
  bootstrap-friendly panels as `(not security_enabled) or is_admin()`.
- **Viewer read-only enforcement**: every write entry point calls
  `ui_guard.can_write()` — a one-line `if not can_write(): return`. A Viewer sees
  a "read-only" dialog and the write is skipped. It is enforced centrally in
  `CrudFrame` and `DocumentFrame`, and in each bespoke tab's write methods.
  **When you add a write action, add the guard as its first line.** `ui_guard` is
  a thin tkinter wrapper so `session` stays GUI-free.
- **Audit log**: `auth.audit(conn, actor, action, entity, entity_id, detail)`
  appends to `audit_log`; logins, failures, user management and the security
  toggle are recorded. Best-effort — it never raises into the caller. If you add
  sensitive actions (deletes, restores, bulk edits), call it.
- **Error handling**: `errors.install(root)` sets `report_callback_exception` so
  any uncaught callback error becomes a plain-language dialog (full traceback
  still to stderr). **No stack trace ever reaches the user.**

## 21. AI Assistant — RAG over your data

An "ask your data in plain language" tab answering questions about the
contractor's **own records** via retrieval-augmented text-to-SQL against a
**local** model.

**No-pip / offline preserved.** `foundry_client.py` talks to **Microsoft Foundry
Local**'s *local* OpenAI-compatible daemon with stdlib `urllib` — no Python
package, localhost only; the daemon's dynamic port is discovered from
`foundry status -o json` (`foundry_service.endpoint`). The app ships **one
built-in model** (`qwen2.5-coder-1.5b`, ~1.8 GB, Apache-2.0, an optimized ONNX
build from Foundry Local's catalogue that auto-uses the local CPU/GPU/NPU);
`foundry_service.py` wraps the CLI (`server start/stop`, `model download/load/
unload`) and its `provision()` downloads + loads the model on first Start. The
only user-facing control is **Start / Stop** under the **AI Engine** rail row —
no model picker, no accounts. Everything **fails soft**: with the engine off (or
Foundry Local not installed), the tab still shows deterministic **quick answers**
and a clear status, and the rest of the app is unaffected. (Replaced the earlier
Ollama integration; `ollama_*`/`model_provision.py` were removed.)

Pipeline (`assistant.answer`): `retrieve` ranks curated `SCHEMA_DOCS` +
few-shot `EXAMPLES` by keyword overlap (no embeddings) → the model writes one
SQL `SELECT` grounded in that context → `extract_sql` + `validate_sql`
(SELECT/WITH only, single statement, write/PRAGMA/ATTACH keywords blocked, a
`LIMIT` injected) → `safe_execute` runs it under **`PRAGMA query_only = ON`** →
the model summarises the rows in plain language.

Rules for extending:
- **Read-only, always.** Never route model output to a writable connection. Keep
  **both** `validate_sql` (deny-list + SELECT-only) and `query_only` (engine
  guard) — defence in depth. Don't drop either.
- When you add or rename tables/columns, **update `SCHEMA_DOCS`** (and
  `_VALID_TABLES`) so the model stays grounded. Stale schema text = wrong SQL.
- Add high-value patterns as **`EXAMPLES`** (few-shot), not prompt prose; keep
  example SQL correct against the real schema.
- Deterministic **`quick_answers`** must never need the model — they are the
  offline floor.
- The model call is slow: the tab runs it on a **background thread** and marshals
  back with `after`. Keep it off the UI thread.
- `capture.py` is the draft-and-confirm scaffold under AI-assisted entry —
  nothing the model produces is written without the user confirming.

### Multi-agent copilots (Foundry platform)

Beside the general Assistant, ACO exposes **persona agents** (estimation, BOQ,
drawing, procurement, planning, finance, document, site, safety, executive)
orchestrated in stdlib:

- `agents_catalog.py` — roster; `agent_tools.py` — read-only / draft tools;
  `knowledge_base.py` — TF-IDF grounding snippets; `agent_runtime.py` — route +
  ask; `agent_workflows.py` — multi-agent handoffs (`variation_impact`, …).
- JSON: `GET /api/agents`, `POST /api/agents/ask`, `POST /api/agents/workflow`.
- Plan: [`docs/AI-FOUNDRY-AGENTS.md`](docs/AI-FOUNDRY-AGENTS.md). Phase A is
  local orchestration; Azure AI Foundry cloud Agents are **opt-in Phase C**
  behind the same propose/confirm seam — never silent money writes.

## 22. Project management & programme

- **`projects`** (name, client, site, dates, budget, LD terms) + **`milestones`**
  (`ON DELETE CASCADE`), both `CrudFrame`s, plus a bespoke read-only
  **drill-down**: budget vs cost-to-date, margin, budget used %, milestone
  progress (`projman.milestone_progress` — amount-weighted when milestones carry
  amounts, else a count ratio), programme slip and LD exposure, retention, open
  snags/RFIs/NCRs. Cost/revenue is derived via the project's `site_id` (§14).
- **`scheduler.py`** — a working-calendar scheduling engine (the MS-Project core
  in pure stdlib): working days, holidays, durations.
- **`cpm.py`** — the Critical Path Method over the programme's tasks: early/late
  dates, float, the critical path, and **dependency-loop detection**.
- **`timeline_tasks.dependency`** holds **typed MS-Project-style predecessors**
  (`"3FS+2, 5SS"` — resolved by id or name, FS/SS/FF/SF with lag). The Gantt
  (`tab_timeline.py`, hand-drawn on a raw `tk.Canvas`, no charting library) draws
  dependency arrows, shades % complete, marks milestones as diamonds, shows the
  baseline underneath, and paints the **critical path in red**. A dependency loop
  is reported to the user rather than hanging.
  *(Note: that module's own docstring still describes `dependency` as inert
  free-text with no effect on the chart. It is wrong — trust the code.)*
- **`programme.py`** — baseline-versus-actual, delay attribution, LD exposure.
- **`earnedvalue.py`** / **`evm.py`** — EVM: PV/EV/AC → SPI, CPI, EAC, per
  project and rolled up.
- **`planning.py`** — weekly look-ahead, PPC (percent plan complete), and CVR.
- **`risk.py`** / `risk_detect.py` / `risk_store.py` — deterministic risk scoring,
  plus automatic detection that turns the dashboard snapshot into scored risks.
- **`opportunity.py`** / `opportunity_store.py` — the upside twin of risk.
- **`review_pack.py`** / `review_assemble.py` — the automated weekly review pack;
  `portfolio_store.py` rolls up across firm/year files.
- **`drift.py`**, **`forecast.py`**, **`followups.py`**, **`narrative.py`** —
  weak-signal drift detection, trend forecasting, event-driven follow-on
  suggestions, and plain-language narration of the numbers.

## 23. Browser / LAN access

A built-in web server lets anyone on the office network open Construction OS in
a browser — no client install. Still pure standard library (`http.server`, no
framework), serving **the same SQLite file** as the desktop app.

| Module | Role |
|---|---|
| `webserver.py` | The HTTP plumbing (threading server, routing entry). |
| `webapp.py` | The application: routing, sessions, login gate, handlers. |
| `webrender.py` | HTML as plain strings — the view layer. |
| `web_masters.py` | Writable master-data specs, **tkinter-free** by design. |
| `web_docs.py` | Postable money documents (payments, tax invoices, vendor invoices). |
| `web_main.py` | Headless entry point. |
| `netinfo.py` | Finds LAN addresses so the launcher can print shareable URLs. |

Start it from **Tools › Web / LAN access**, or headless:

```bash
cd construction_app
python web_main.py                 # 0.0.0.0:8080
python web_main.py --port 9000
```

Rules for extending:
- **Login is required** and reuses the app's accounts + PBKDF2 hashing (§20); the
  first visit creates the admin. Roles apply — Viewers are read-only.
- **Keep the web modules tkinter-free.** They must import on a headless box; the
  desktop and web layers share only pure modules and `db.py`.
- Share design tokens via `tokens.py` rather than duplicating CSS values (§24).
- It is **plain HTTP for a trusted LAN** (§14). See `docs/LAN.md`.
- `tests/test_web.py` covers this layer — extend it alongside.

## 24. The UI shell, theme, and tokens

**The app is not a top-level `ttk.Notebook`.** `main.py` builds a
`shell.RailStage`: a left **rail** of sections, each opening a **stage** holding
that section's sub-notebook, built **lazily** the first time the row is opened.
Rail entries are Home, Assistant, Process, AI Engine, one row per enabled
section from `modules.SECTIONS_CATALOG` (persona-filtered via `menu.resolve`),
then Tools. A status footer carries a live AI indicator.

The catalog is **8 sections over 52 toggleable modules**: Masters, Project
Management, Controls, Operations, Billing, Purchases, Money, Accounts. Home,
Assistant, Process, AI Engine and Tools are always on and not in the catalog.

- **`tokens.py`** — HCW-UI design tokens, the single source of truth for **both**
  the tkinter theme and the web CSS. Change a colour here, not in a widget.
- **`theme.py`** — the tkinter theme over those tokens, with **light/dark**.
  `theme.apply(root, mode)` runs before any UI is built so classic-widget
  defaults take effect; mode persists in `app_settings`.
- **`widgets.py`** — small shared widgets tkinter/ttk doesn't ship.
- **Branding** (`assets.py`, `branding.py`, `resources/`): window/taskbar icon,
  Home header, login dialog, and every printed document's letterhead
  (`assets.logo_html()` embeds the logo as a base64 `data:` URI so exported HTML
  stays self-contained). All logo loads **fail soft** — a missing file or old Tk
  falls back to text, never an error. To rebrand, replace the files in
  `resources/`, keeping the names.

When you add a tab, it inherits the theme automatically — but
`tests/test_smoke_tabs.py` builds every tab in **both** light and dark, so a
hardcoded colour will fail the suite. Use `theme`/`tokens`.

## 25. Keeping this document honest

This file drifted badly once: it claimed 58 tests when there were hundreds,
described a `ttk.Notebook` shell that had been replaced by the rail, listed ~50
of 150+ modules, and flagged P&L, balance sheet, ageing, three-way match, FY
invoice numbering and CPM dependencies as "not built" when all shipped. An agent
reading it would have rebuilt working features.

So: **when you change something described here, update the section in the same
commit.** Same rule for `CLAUDE.md` and `docs/ROADMAP.md` status lines.

### Documentation map (agents)

| Need | Use this | Do not |
|---|---|---|
| Done vs pending | `docs/ROADMAP.md` | Second roadmap / task backlog files |
| What changed | `docs/CHANGELOG.md` | Paste shipped narratives into ROADMAP |
| Market / Fluent / CPWD research | `docs/RESEARCH.md` | Split `RESEARCH-*` / audit / gap-roadmap files |
| WinUI how-to | `WINUI3-MIGRATION` + `UI-PRINCIPLES` + `.github/instructions/winui3.instructions.md` | Custom chrome “improvements” |
| Product who/why | `docs/PRODUCT.md` + `docs/BRAND.md` | — |

To re-check the headline numbers before trusting them:

```bash
python -m unittest discover -s tests 2>&1 | tail -3        # test count
ls construction_app/*.py | wc -l                            # module count
grep -c 'CREATE TABLE IF NOT EXISTS' construction_app/db.py # table count
grep -c 'CREATE INDEX IF NOT EXISTS' construction_app/db.py # index count
```

Module purity (tkinter-free vs GUI) is worth re-deriving with a short `ast`
script over `construction_app/*.py` rather than trusting the prose in §0 / §1.

And treat **module docstrings with the same suspicion** — at least one
(`tab_timeline.py`) still describes behaviour the module no longer has (§22).
When a docstring and the code disagree, the code wins; fix the docstring.
