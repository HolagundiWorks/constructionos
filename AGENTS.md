# AGENTS.md — Construction OS (Construction ERP)

This file is written for an **AI coding agent** (Claude Code, Cursor, etc.)
that will read, modify, or extend this codebase. It documents architecture,
conventions, and gotchas that are not obvious from the code alone. Read this
in full before making changes.

If you are a human developer, `README.md` is the friendlier version of this
document. This one is denser and assumes you will grep the source while
reading.

---

## 0. Product vision (read this first)

Construction OS is growing from a site-operations tool into a **full-fledged
ERP for Indian construction contractors** — think a focused, single-file,
zero-dependency Dolibarr for the construction trade. The trajectory is:

- **Operations** (built): sites/warehouses, vendors, clients, materials,
  labor, equipment, stock ledger, attendance, payroll, advances, timelines.
- **Commercial** (built): quotations, estimates, contracts, running bills
  (with printable bill export).
- **Procurement** (built): purchase orders, vendor invoices, and PO↔invoice
  reconciliation.
- **Civil billing** (built): BOQ per contract, a Measurement Book, and
  measurement-driven RA (Running Account) bills with abstract export — see §15.
- **Site execution & quality** (built): material consumption reconciliation
  (theoretical vs actual) and site registers (DPR, cube tests, material tests,
  plant log) — see §16.
- **Finance & accounting** (built): GST (CGST/SGST/IGST) and TDS computation, a
  chart of accounts, a double-entry journal, a trial balance, and **P&L +
  balance sheet** on the posted ledger (`reports.py`).
- **Money & compliance** (built): payments & receipts, party balances, cash
  book, home dashboard; GST registers (output incl. RA/running bills, input,
  HSN summary, 3B-style net position) and a TDS register.
- **Insight** (built): site profitability, receivables/payables, **ageing**
  (0-30/30-60/60-90/90+), **contract/BOQ progress %**, and **material budget
  vs actual**.
- **Auto-posting** (built): idempotent journal entries for tax invoices, vendor
  invoices, payments, paid payroll, and subcontractor bills (`journal_post`).
- **Subcontractor/work-order billing** (built): work orders + sub running bills
  with retention & works-contract TDS (`subcontract.py`, `tab_subcontract.py`).
- **Trust & ease** (built): first-run setup wizard, today-default + remember-
  last low-typing entry, Hindi/Hinglish navigation (`i18n.py`), and an app-wide
  no-stack-trace error handler (`errors.py`).
- **Next** (not built — see §14): running/RA bills posted with a retention-
  receivable account; e-invoice / e-way-bill integration; embeddings for the
  assistant; multi-year / multi-firm files.

The **Indian context** matters: money figures carry GST split into CGST+SGST
(intra-state) or IGST (inter-state); vendor payments are subject to TDS;
materials carry HSN codes; dates are `YYYY-MM-DD`. Preserve these conventions
when extending (see §11 and §12).

Keep the founding constraints intact unless explicitly told otherwise:
**Python 3.8+ standard library only, tkinter GUI, single SQLite file, no pip
dependencies.** These are what let the whole ERP run anywhere Python runs, by
double-clicking one folder.

## 1. What this project is (stack)

- **Language/runtime**: Python 3.8+, standard library only.
- **GUI**: `tkinter` / `tkinter.ttk` (no web server, no external UI framework).
- **Persistence**: SQLite via `sqlite3`, single file `construction.db`
  created next to the code on first run (and seeded with a default chart of
  accounts — see §9).
- **No package dependencies.** Do not add `pip install` requirements unless
  explicitly asked — this is a deliberate design constraint.
- **Business/tax/accounting maths lives in pure functions** in `finance.py`
  (GST, TDS, reconciliation, double-entry checks) and in a few module-level
  helpers (`days_present_for`, `compute_net_payable`, `_compute_hire_total`,
  `_compute_duration`, `bill_export.build_bill_html`). This is the testable
  core; extend it there rather than burying new maths inside GUI callbacks.
- **Tests**: there is now a committed suite in `tests/test_core.py` (stdlib
  `unittest`, no pytest, no CI yet). Run it from the repo root with
  `python -m unittest discover -s tests`. It covers the pure money maths
  (finance, civil, money, wages, numbering, statutory, ageing, analytics,
  estimate, subcontract, reports) and drives the **posting engine end-to-end
  against a temporary SQLite database**. Add to it whenever you touch maths;
  don't add `pytest` as a hard dependency without confirming with the user.

## 2. Running & verifying your changes

```bash
cd construction_app
python main.py
```

To verify without a display, run these three from the repo root — they are the
full sweep used to validate changes:

```bash
python -m unittest discover -s tests               # 58 tests: maths + posting
cd construction_app && python -m py_compile *.py   # syntax check every module
python -c "import db; db.init_db(); print('ok')"   # schema + CoA seed check
```

The test suite needs no display: it never imports tkinter.

Most containers have **no `tkinter`**. The GUI modules `import tkinter` at the
top, so they can't be imported headlessly as-is. Two working strategies (both
used to validate this codebase):

1. **Test the pure layer directly** — `finance.py` and `bill_export.py` have
   no tkinter import, so `python -c "import finance; ..."` works anywhere.
2. **Stub tkinter** — drop a fake `tkinter` package (with `ttk`, `messagebox`,
   `filedialog` submodules exposing no-op widget classes) on `PYTHONPATH` to
   import the GUI modules and smoke-test wiring. This catches import/typo
   errors without rendering anything.

Say so explicitly if you cannot launch the GUI — don't claim you tested a UI
you couldn't render. Read calculation callbacks by eye; there's no unit-test
safety net committed yet.

## 3. File map & responsibilities

```
construction_app/
├── main.py                 # Entry point. Optional login gate, then the grouped/toggle-aware ttk.Notebook.
├── db.py                   # SQLite schema (single SCHEMA string) + get_conn() (WAL + FK + busy_timeout) + init_db() + CoA seed + indexes.
├── security.py             # PURE password hashing: salted PBKDF2-HMAC-SHA256 + constant-time verify + policy. No tkinter/DB.
├── auth.py                 # Users/auth/audit (DB): create_user, authenticate (+lockout), roles, security_enabled toggle, audit(). No tkinter.
├── session.py              # PURE process-wide current user/role holder (is_admin, can_write). No tkinter/DB.
├── branding.py             # PURE app name ("Construction OS") + developer credit ("Human Centric Works, Hospet").
├── projman.py              # PURE project maths: milestone_progress (amount-weighted), budget_status. No tkinter/DB.
├── tab_projects.py         # Projects + Milestones (CrudFrames) + a computed Project Overview dashboard.
├── assets.py               # Brand logos: file paths + base64 data-URI/`<img>` for HTML letterheads. No tkinter/DB.
├── ollama_client.py        # Stdlib (urllib) client for a LOCAL Ollama server: available()/list_models()/generate(). No pip.
├── assistant.py            # RAG text-to-SQL over the DB: schema docs, retrieval, validate_sql, read-only safe_execute, answer(), quick_answers. No tkinter.
├── tab_assistant.py        # "Assistant" tab: ask-your-data chat (threaded), quick answers, dynamic result table.
├── resources/              # logo_square.png, logo_rectangle.png, app.ico (committed binary brand assets).
├── tab_login.py            # Startup login dialog (shown only when security is enabled).
├── tab_security.py         # Users & Security + Audit Log tabs (live under Tools).
├── isodate.py              # PURE tolerant ISO-date parse: parse(value) -> date or None (narrows datetime, tolerates whitespace/time part). Shared by every dated pure module. No tkinter/DB/deps.
├── finance.py              # PURE tax/accounting maths: GST split, TDS, invoice roll-up, PO reconciliation, double-entry checks. No tkinter/DB.
├── posting.py              # PURE double-entry posting rules: balanced journal lines per document type (uses CoA codes). No tkinter/DB.
├── journal_post.py         # Auto-posting engine: idempotent post_all(conn) → journal entries from tax/vendor invoices, payments, paid payroll, sub bills. DB-only, no tkinter.
├── reports.py              # PURE financial statements on the ledger: profit_and_loss + balance_sheet (from account debit/credit totals). No tkinter/DB.
├── ageing.py               # PURE receivable/payable ageing: FIFO-settle dated bills by receipts, bucket the remainder 0-30/30-60/60-90/90+. No tkinter/DB.
├── analytics.py            # PURE progress/budget: contract_progress (measured÷BOQ) + material_budget (value). No tkinter/DB.
├── numbering.py            # PURE document numbering: Indian financial year + configurable invoice series (prefix + FY reset). No tkinter/DB.
├── subcontract.py          # PURE subcontractor bill maths: retention + works-contract TDS → net payable (reuses civil + finance). No tkinter/DB.
├── statutory.py            # PURE optional labour statutory maths: EPF, ESI, BOCW labour cess. No tkinter/DB.
├── i18n.py                 # Navigation-layer vernacular string table (English/Hindi/Hinglish) + language toggle; t(key) with English fallback. No tkinter.
├── errors.py               # App-wide Tk report_callback_exception handler → plain-language dialog (no stack trace reaches the user).
├── tab_subcontract.py      # Subcontractors: Work Orders (DocumentFrame) + Sub Bills (value-based, retention/TDS/net, printable).
├── tab_statutory.py        # Standalone PF/ESI/labour-cess calculator (off the main flow), under Muster & Wages.
├── tab_wizard.py           # First-run setup wizard: firm details + first site + first client, shown once on a fresh book.
├── civil.py                # PURE civil maths: measurement-book qty, RA-bill qty split & totals, consumption reconciliation, cube strength. No tkinter/DB.
├── money.py                # PURE cash-first maths: signed cash, running/closing balance, party outstanding. No tkinter/DB.
├── numwords.py             # PURE Indian rupees-in-words (lakh/crore) for printed invoices. No tkinter/DB.
├── wages.py                # PURE day-fraction + gross/deduction/net wage maths (shared by muster/payout/payroll). No tkinter/DB.
├── bill_export.py          # PURE HTML builders: bill, RA abstract, GST tax invoice (+words), generic statement. No tkinter/DB.
├── crud_frame.py           # Generic reusable "list + form" widget (CrudFrame) and Field descriptor.
├── tab_masters.py          # Sites, Clients, Materials (with std rate), Labor (+ optional PF/ESI no), Equipment, Rate Book masters + *_options fk helpers.
├── tab_vendor.py           # Vendor master (CrudFrame) + a read-only spend/hire rollup view.
├── tab_warehouse.py        # Material ledger (CrudFrame) + a computed-on-the-fly stock summary view.
├── tab_labor.py            # Attendance (CrudFrame), Advances (CrudFrame), Payroll (bespoke). days_present_for = wages.day_fraction.
├── tab_muster.py           # Muster roll (fast daily attendance) + weekly wage payout (feeds Payments) + thekedar master & ledger.
├── tab_documents.py        # DocumentFrame generic class (header + line items, with Print/Export) -> Quotations, Purchase Orders. Contracts is a plain CrudFrame.
├── estimate.py             # PURE estimate roll-up (subtotal→contingency→taxable→GST→grand total), ported from CBS. No tkinter/DB.
├── tab_estimate.py         # Estimates (bespoke, ported from Construction-Billing-System): contingency + GST + grand total + printable estimate document.
├── tab_billing.py          # BillingTab: bespoke Bills/Running Bills with running-total math + "Make Bill" HTML export (bill_export).
├── tab_tax_invoice.py      # GST Tax Invoices (outward, to clients): HSN, CGST/SGST/IGST, printable invoice with amount-in-words.
├── tab_vendor_invoice.py   # Vendor invoices (bespoke, GST/TDS via finance) + PO↔invoice ReconciliationView.
├── tab_boq_ra.py           # BOQ per contract + Measurement Book + RA bills + Deviation Statement (PWD-style tendered-vs-executed).
├── tab_consumption.py      # Consumption norms + work-done log + theoretical-vs-actual reconciliation view.
├── tab_site_reports.py     # DPR, Cube Tests (auto strength/result), Material Tests, Plant Log (CrudFrames).
├── tab_home.py             # Plain-language dashboard: cash in hand, receivables, payables, active sites, month billed/collected.
├── tab_money.py            # Payments & Receipts + Party Balances + Cash Book (cash-first, Phase 1).
├── tab_insight.py          # Site Profitability + Contract Progress (measured/BOQ) + Material Budget + Receivables/Payables + Ageing. Computed + printable.
├── tab_gst.py              # GST & TDS: Output GST (tax invoices + RA/running bills), Input GST, HSN summary, net-position, TDS register. Computed + printable.
├── tab_accounting.py       # Chart of Accounts + Journal + Trial Balance + Profit & Loss + Balance Sheet (reports.py) — ADVANCED / for the CA.
├── tab_tools.py            # Backup & Restore + Firm details (incl. Works GST %) + Invoice number series + Language + Modules + AI settings.
├── tab_equipment_hire.py   # Equipment Hire CrudFrame + _compute_hire_total on_save hook.
├── tab_timeline.py         # TimelineTab: CrudFrame for tasks + a hand-drawn Canvas Gantt chart.
└── construction.db         # Created at runtime — never commit; it's user data, not source (git-ignored).
```

**Where new code goes**:
- Flat single-table form (a "master" or a transaction log) → a `CrudFrame`
  instance in an existing or new `tab_*.py`.
- Header-with-line-items document whose header total is just the sum of item
  amounts (quotation/estimate/PO shape) → reuse `DocumentFrame`
  (`tab_documents.py`); see §5.
- Header+items document with **computed columns beyond a simple sum** (running
  bills' `previous_billed`, vendor invoices' GST/TDS) → a bespoke tab that
  reuses the *pattern* but adds its own maths, delegating the maths to
  `finance.py`. `tab_billing.py` and `tab_vendor_invoice.py` are the two
  examples.
- New tax/accounting maths → a pure function in `finance.py`, unit-checkable
  with `python -c`.

## 4. The `CrudFrame` abstraction (read before touching any master/simple tab)

`crud_frame.py` defines two things:

- **`Field(key, label, kind='text', width=110, options=None, options_func=None, default='')`**
  Describes one form field / table column.
  - `kind='text'` → plain `ttk.Entry`, stored as string.
  - `kind='number'` → `ttk.Entry` parsed with `float()` on save (error dialog
    if not numeric).
  - `kind='combo'` → read-only `ttk.Combobox` from a static `options=[...]`.
  - `kind='fk'` → read-only `ttk.Combobox` populated by `options_func(conn)`,
    which returns `[(id, label), ...]`. The combobox displays `"{id} - {label}"`
    strings; `CrudFrame` parses the leading id back out on save via
    `raw.split(' - ')[0]` (splits on the first ` - ` only, so labels may
    themselves contain ` - `). Be aware of this coupling if you change the
    display format in `_collect_values`/`_refresh_fk_options`.

- **`CrudFrame(parent, db_getter, table, fields, title, extra_where='', order_by='id DESC', on_save=None)`**
  A `ttk.Frame` with a `Treeview` list, an auto-generated form (3 fields per
  row), and Add/Update/Delete/Clear/Refresh buttons. It runs raw
  `INSERT`/`UPDATE`/`DELETE` against `table` from the `fields` list. It has
  **no idea about foreign keys or business rules**; any derived column or side
  effect goes in the `on_save(conn, row_id, values_dict)` callback, invoked
  after insert/update. See `_compute_hire_total` and `_compute_duration` for
  the pattern: compute, `UPDATE` the derived column, `commit()`, and never
  raise — wrap in `try/except: pass` because these are best-effort auto-fills.

  **`on_save` connection lifetime**: `CrudFrame` `close()`s the `conn` right
  after the callback returns. Don't close it yourself, and don't stash it for
  later.

  **Deletion has no cascade logic** — `delete_selected` does a bare
  `DELETE FROM {table} WHERE id = ?`. With `PRAGMA foreign_keys = ON`, deleting
  a parent still referenced by a **non-cascading** child (e.g. a `labor` row
  with `attendance`/`advances`/`payroll`, or an `account` referenced by
  `journal_lines`) raises `sqlite3.IntegrityError`. As of Phase 4 this is
  **caught** in `delete_selected` and shown as a plain-language dialog ("this
  record is still used elsewhere…") instead of a stack trace — the delete is
  still a bare, non-cascading `DELETE`, it just fails gracefully. To make a
  specific table cascade, add `ON DELETE CASCADE` in the schema (see the
  `*_items` tables); don't add per-tab delete logic.

## 5. The `DocumentFrame` abstraction (Quotations, Estimates, Purchase Orders)

`tab_documents.py`'s `DocumentFrame` is a header (`Treeview` + form) on top and
a line-items grid on the bottom, joined by a foreign key column (`fk_col`).
Selecting a header loads only that document's items. Every item add/update/
delete calls `_recalc_total`, which re-sums the items and writes the total into
the header's `total_col`. **The header total is always derived** — there is no
field for it in `header_fields`; don't add one. Item amount is auto-computed as
`qty * rate`.

Three document types use it today: `build_quotations_tab` (`total_amount`),
`build_estimates_tab` (`total_estimate`), and `build_purchase_orders_tab`
(`total_amount`). For **purchase orders**, `total_amount` is the **pre-tax
items subtotal**; `gst_pct` is header metadata only (GST is realised
downstream when a vendor invoice is booked against the PO — DocumentFrame has
no tax concept). If you need a GST-inclusive PO total shown live, that's a
bespoke change, not something DocumentFrame supports.

To add another header+items document type, follow `build_purchase_orders_tab`:
1. Add `<thing>` and `<thing>_items` tables to `db.py`'s `SCHEMA` (header
   needs `id` + a total column; items need `id`, the fk column,
   `description`, `unit`, `qty`, `rate`, `amount`, and `ON DELETE CASCADE` on
   the fk).
2. Add a `build_<thing>_tab(parent, db_getter)` returning a `DocumentFrame`.
3. Register it in `main.py`.

## 6. `BillingTab` (Bills / Running Bills) — bespoke, plus bill export

Running bills need a computed `previous_billed` that `DocumentFrame` has no
concept of, so `tab_billing.py` is bespoke. Core formula in `add_bill`/
`update_bill`:

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
retroactively recompute bills saved earlier (still a known gap — see §14).

`bill_items` are a BOQ breakdown that do **not** auto-drive `work_done_value`:
the user clicks **"Sum Items -> Work Done Value"** to pull the item total into
the header, then **"Update Selected"** to persist. Intentional two-step.

**Bill export ("Make Bill")**: the "Make Bill (Export)" button fetches the
selected bill + its contract/client/site + items, calls
`bill_export.build_bill_html(...)`, writes the HTML through a save dialog, and
opens it in the browser (print / Save-as-PDF). `build_bill_html` is a **pure
function** (no tkinter/DB) so it's unit-checkable; keep the rendering logic
there, not in the GUI handler. This is the stdlib-only substitute for PDF
export — there is deliberately no PDF library.

## 7. Procurement — Purchase Orders & Vendor Invoices

**Purchase Orders** (`tab_documents.py`, DocumentFrame — see §5): header carries
vendor, site, dates, `gst_pct`, and a lifecycle `status`
(Draft→Sent→Partially Received→Received→Closed/Cancelled). `total_amount` is the
pre-tax subtotal.

**Vendor Invoices** (`tab_vendor_invoice.py`, bespoke): header + items like a
bill, but the money figures are **tax-driven**. Line items give a pre-tax
`subtotal`; `finance.invoice_totals(subtotal, gst_pct, tds_pct, interstate)`
rolls it up:

```
tax_amount   = GST on subtotal (CGST+SGST intra-state, or IGST inter-state)
total_amount = subtotal + tax_amount           (invoice gross value)
tds_amount   = TDS on the pre-GST subtotal      (withheld from payment)
net_payable  = total_amount - tds_amount        (actually paid to the vendor)
```

Those five columns are **always derived** — `_recalc` runs on every item change
and every header edit; never hand-enter them. An invoice may optionally link to
a `purchase_order_id`.

**Reconciliation** (`ReconciliationView`): compares each invoice's pre-tax
`subtotal` against the pre-tax subtotal (`total_amount`) of its linked PO via
`finance.reconcile(po_subtotal, invoice_subtotal, tolerance)`, flagging
`Matched` / `Over-billed` / `Under-billed` / `No PO` with a variance and
variance-%. **Reconciliation is totals-level only** — it does not match
line-by-line or quantity-by-quantity (a known gap — §14). The tolerance is an
absolute amount entered in the view.

## 8. Payroll generation (`tab_labor.py`, `PayrollFrame.generate_payroll`)

- Attendance → fractional days present via `days_present_for`, which is now
  `wages.day_fraction` (the rule lives in `wages.py`, shared with the muster
  roll and weekly payout): `Present`=1.0, `Half Day`=0.5,
  `Overtime`=`1 + max(0, hours-8)/8`, `Absent`=0.
- `gross_amount = days_present * labor.daily_wage`; deduction =
  `min(open_advance_balance, gross_amount)` — the whole gross/deduction/net
  calc is also in `wages.wage_net`. Never negative net pay. (Monthly payroll in
  `PayrollFrame` still computes inline; the weekly payout in §19 uses
  `wages.wage_net` directly.)
- **Idempotency guard**: generation is a no-op for a `(labor_id, month, year)`
  that already has a `payroll` row — it skips, doesn't update. No
  regenerate/delete UI yet (§14).
- Only `status='Active'` labor is included.
- Payroll does **not** post to the accounting journal automatically (§14).

## 9. Accounting — chart of accounts, journal, trial balance

`tab_accounting.py`, an inner notebook of three views, backed by three tables
(§10). Pure checks live in `finance.py`.

- **Chart of Accounts**: a `CrudFrame` over `accounts` (`code`, `name`,
  `type` ∈ Asset/Liability/Income/Expense/Equity, self-referential
  `parent_id` fk, `is_active`). A **default construction CoA is seeded once**
  by `db.seed_default_accounts` on first run (no-op if any account exists) —
  see `db.DEFAULT_ACCOUNTS` (Cash, Bank, AR, Materials Inventory, Input GST
  Credit, AP, GST Payable, TDS Payable, Retention Payable, Owner Equity,
  Contract Revenue, and the site expense accounts).
- **Journal** (`JournalFrame`, bespoke double-entry): a `journal_entries`
  header + `journal_lines`, where **each line is a debit XOR a credit** against
  one account (`_collect_line` rejects a line with both). Header
  `total_debit`/`total_credit` are derived from the lines on every change, and
  a live label uses `finance.is_balanced` to show Balanced / diff. The UI
  **allows saving an unbalanced entry** (so you can build it up line by line) —
  balancing is surfaced, not enforced at write time. If you add a "post"
  action, that's where to enforce `is_balanced` hard.
- **Trial Balance** (`TrialBalance`): sums debit/credit per account across all
  journal lines, hides unused accounts, shows a TOTAL row, and reports whether
  the books balance via `finance.is_balanced(total_debit, total_credit)`.

**The double-entry invariant**: for the trial balance to balance, every saved
journal entry should itself balance. `finance.account_net` gives an account's
signed balance in its normal direction if you build ledger/P&L views later.

**Auto-posting** (Phase 7): the Journal's **"Auto-Post Documents"** button runs
`journal_post.post_all(conn)`, which posts a balanced entry for every tax
invoice, vendor invoice, payment, **paid payroll run**, and **subcontractor
bill** (Approved/Paid) not already posted. The posting *rules* (which accounts,
debit vs credit) live in the pure `posting.py`; the engine in `journal_post.py`
resolves account codes to ids, checks `journal_entries.(source, source_id)` for
idempotency, and inserts. Because every generated entry balances, the trial
balance stays balanced no matter how many documents are posted — and the
**Profit & Loss / Balance Sheet** views (`reports.py`) read straight off the
resulting per-account totals. **Running bills and RA bills to clients are still
not auto-posted** (their client-withheld retention is an asset the seeded CoA
doesn't model — see §14). If you add a document type, add a `*_lines` rule in
`posting.py` and a loop in `post_all`, keeping each entry balanced.

## 10. Database schema quick reference

All tables live in one `SCHEMA` string in `db.py`. `get_conn()` sets per
connection: **`foreign_keys = ON`** (FKs won't enforce otherwise — any script/
test opening SQLite outside `db.get_conn()` must re-issue it), **`journal_mode =
WAL`** + **`synchronous = NORMAL`** (crash-resilient writes), and
**`busy_timeout = 5000`** (a second short-lived connection waits instead of
raising "database is locked"). WAL adds `-wal`/`-shm` sidecar files next to
`construction.db` — the backup/restore in `tab_tools` copies the main file; a
checkpoint on a clean close folds the WAL back in, so a plain file copy is
consistent between operations. Hot-path **indexes** are declared at the end of
`SCHEMA` (after their tables) — add new ones there.

**Adding a column to an existing table**: `CREATE TABLE IF NOT EXISTS` never
alters a table that already exists, so a new column won't reach an older
`construction.db`. Update the `SCHEMA` `CREATE` (for fresh installs) **and** add
the column to `db._ADD_COLUMNS` — `_apply_column_migrations` (run by
`init_db`) issues an idempotent `ALTER TABLE ... ADD COLUMN` per missing column.
(This is the lightweight stand-in for a real migration framework.)

Relationships at a glance:
```
sites 1──* labor / material_ledger / equipment_hire / timeline_tasks
          / estimates / contracts / equipment(current_site_id)
          / purchase_orders

vendors 1──* material_ledger(vendor_id, meaningful only for txn_type='IN')
            / equipment_hire / purchase_orders / vendor_invoices

clients 1──* quotations / contracts
labor   1──* attendance / advances / payroll   (labor also carries optional pf_no/esi_no)
contracts 1──* bills            (running bill chain — §6)
contracts 1──* boq_items 1──* measurements     (measurement book — §15)

quotations       1──* quotation_items        (ON DELETE CASCADE)
estimates        1──* estimate_items         (ON DELETE CASCADE)
bills            1──* bill_items             (ON DELETE CASCADE)
purchase_orders  1──* purchase_order_items    (ON DELETE CASCADE)
purchase_orders  1──* vendor_invoices         (purchase_order_id, nullable)
vendor_invoices  1──* vendor_invoice_items    (ON DELETE CASCADE)

work_orders      1──* work_order_items         (ON DELETE CASCADE)
work_orders      1──* sub_bills                (work_order_id; subcontractor billing — §7)
rate_book                                      (standalone schedule of rates / specs)

accounts        1──* journal_lines            (account_id, NO cascade)
accounts        1──* accounts                 (parent_id self-reference)
journal_entries 1──* journal_lines            (ON DELETE CASCADE)
```

Newer tables (see the relevant §): `work_orders`, `work_order_items`,
`sub_bills` (subcontractor billing), `rate_book` (rate/spec library), plus the
`materials.rate` and `labor.pf_no`/`esi_no` columns. `app_settings` also holds
config keys added along the way: `works_gst_pct`, `invoice_prefix` /
`invoice_width` / `invoice_fy_reset`, `language`, `setup_done`, and
`last:<table>:<column>` remember-last values.

**Seven** child tables declare `ON DELETE CASCADE`: `quotation_items`,
`estimate_items`, `bill_items`, `purchase_order_items`,
`vendor_invoice_items`, `work_order_items`, `journal_lines`. Everything else
relies on app-level `delete_*` methods to clean up children (e.g.
`DocumentFrame.delete_header` deletes items before the header).
`CrudFrame.delete_selected` does **not** cascade for any table — the §4 gap. In
particular, deleting an `account` referenced by a `journal_line`, a
`work_order` referenced by a `sub_bill`, or a `vendor`/`site` referenced by
children, raises `IntegrityError` — now shown as a friendly dialog both by the
CrudFrame guard and the app-wide handler in `errors.py`.

## 11. Conventions to follow when extending

- **Dates are plain `TEXT` `YYYY-MM-DD`**, validated ad hoc with
  `datetime.strptime` in `try/except`, no date-picker widget. Other code
  (payroll month/year `strftime` queries, hire/duration calculators, the Gantt)
  assumes this format. In the **pure modules**, parse dates through
  `isodate.parse(value)` (→ `date` or `None`, never raises) rather than
  hand-rolling another tolerant parser — ten modules each grew their own copy
  and the copies drifted, one of them into a `TypeError` on datetime input.
- **Money/qty are `REAL` (float)**, not `Decimal`. `finance.money(x)` coerces
  and rounds to 2 decimals at boundaries; use it for new tax/accounting maths.
  Never compare floats for equality — use the `eps` in `finance.is_balanced`.
- **Indian tax**: GST always splits via `finance.split_gst` (CGST+SGST intra,
  IGST inter — driven by the `interstate` flag); TDS via `finance.compute_tds`
  on the pre-GST base. Materials carry `hsn_code`. Don't hardcode a GST rate —
  it's a per-document field (`gst_pct`), defaulting to 18.
- **Double-entry**: money that moves should be expressible as balanced journal
  lines. Keep new accounting maths in `finance.py`.
- **No ORM.** Raw SQL over `sqlite3.Row`-returning connections (rows indexable
  by column name). Keep this style.
- **SQL string-building uses only trusted, hardcoded table/column names**
  (never user input) via f-strings; **values always go through `?`
  placeholders.** Preserve this split.
- **Every tab module exposes either `build_*_tab(parent, db_getter)` returning
  a widget, or a class taking `(parent, db_getter)` subclassing `ttk.Frame`** —
  both are just callables `builder(parent, db_getter)`. Tabs with several views
  (Vendor, Warehouse, Labour Ops, Muster, Vendor Invoices, Money, Insight, GST,
  Accounting, Timeline, …) return an inner `ttk.Notebook`.
- **Adding a tab / where it appears**: the section grouping + order is the
  `modules.SECTIONS_CATALOG` list — `[(section title, [tab label, ...])]` —
  which is the single source of truth shared by `main.py` and the Tools toggle
  panel. `main.py` maps each label to a widget in its `BUILDERS` dict and
  `_section` builds a sub-notebook per section (so the top bar stays ~8 tabs,
  not ~25). **To add a tab**: add its label to a section in
  `modules.SECTIONS_CATALOG` **and** an entry in `main.BUILDERS` (the two must
  agree — a label with no builder KeyErrors at startup). Home and Tools are the
  only single, ungrouped, always-on top-level tabs.
- **Module toggles**: every catalog label is a switchable module. State lives in
  `app_settings` as `module:<label>` (`'1'`/`'0'`, absent = on); helpers are in
  `modules.py` (`enabled_map`, `is_enabled`, `set_states`). `main.py` reads them
  once at startup and skips disabled tabs (and any section left empty). The
  Tools tab's **Modules** panel edits them; changes apply on next launch because
  the Notebook is built once. A builder that already returns a Notebook just
  nests one level deeper — that's expected.
- **`db.get_conn` is passed as `db_getter` (a callable, not a live
  connection)** — every operation opens a fresh short-lived connection and
  closes it. No shared/long-lived connection; don't hold one across callbacks.

## 12. Indian-context cheatsheet (for finance work)

- **GST**: intra-state supply → CGST + SGST (rate split in half); inter-state →
  IGST (full rate). `finance.split_gst(taxable, gst_pct, interstate)`.
- **TDS**: withheld from the vendor payment, computed on the pre-GST base.
  `finance.compute_tds(taxable, tds_pct)`. Booked to `TDS Payable`.
- **Input GST Credit** (asset) vs **GST Payable** (liability): purchases accrue
  input credit; sales/bills accrue output GST payable. The seeded CoA has both.
- **Retention**: withheld from running bills (`retention_amt`), a liability
  until released — seeded as `Retention Payable`.
- **HSN codes** live on `materials`. Place-of-supply / interstate is a boolean
  on `vendor_invoices` today (extend to a state field if you build GST returns).

## 13. Verifying finance/accounting changes

The pure layer is the safety net. Quick checks that should always hold:

```bash
python -c "import finance as f; \
  assert f.split_gst(10000,18)['cgst']==900; \
  assert f.invoice_totals(10000,18,2)['net_payable']==11600; \
  assert f.reconcile(10000,10500,100)['status']=='Over-billed'; \
  assert f.is_balanced(1500,1500) and not f.is_balanced(1500,1400); \
  print('finance ok')"
python -c "import db; db.init_db(); \
  c=db.get_conn(); \
  print('accounts seeded:', c.execute('SELECT COUNT(*) FROM accounts').fetchone()[0])"
```

## 14. Known gaps / things to flag rather than silently "fix"

Intentional scope cuts, not bugs — mention to the user before changing, since
"fixing" is a feature request:
- **Auto-posting covers only tax invoices, vendor invoices, and payments**
  (§9, `journal_post.post_all`). **Running bills and RA bills are not posted**
  (client-withheld retention would need a retention-receivable asset the seeded
  CoA lacks), and payroll is not posted (wages reach the journal only when paid
  via a Labour payment). Auto-posting is a manual "Auto-Post Documents" action,
  not automatic on save, and there is no un-post/reverse (delete the journal
  entry to re-post).
- **Reconciliation is totals-level only** — no line/quantity matching, no
  three-way match against goods received (§7).
- **No GST returns / GSTR summaries, no ageing/outstanding, no P&L / balance
  sheet** — trial balance and the GST/TDS registers are the only
  financial report so far.
- **PO `total_amount` is pre-tax**; there's no GST-inclusive PO total (§5).
- No retroactive recompute of prior bills' `previous_billed` when a later
  bill's status changes (§6).
- No cascade-delete handling in `CrudFrame` — but delete now fails gracefully
  with a friendly dialog instead of a stack trace (§4).
- No regenerate/delete affordance for payroll rows (§8).
- `dependency` in timeline tasks is inert metadata; the Gantt ignores it.
- No PDF export, but printable **HTML** export (browser → print / Save-as-PDF)
  now covers bills, RA bills/abstracts, **GST tax invoices**, and **party
  statement + cash book** (`bill_export.build_*`). Quotations, estimates, POs,
  and vendor invoices still have no export.
- Tax-invoice **seller details** (name/GSTIN/address) come from `app_settings`
  keys `company_name`/`seller_gstin`/`seller_address`, editable in the **Tools**
  tab's "Firm Details" panel; blank until the contractor fills them in.
- Tax invoices **auto-number** as `INV-<serial>` (count-based) only when the
  number is left blank — there's no configurable prefix/financial-year series
  yet, and count-based numbering can collide if invoices are deleted.
- **RA "previous quantity" only counts Approved/Paid RA bills** (mirrors §6),
  so generating multiple *Draft* RA bills before approving them can
  double-count quantities. Approve each RA bill before generating the next.
- **Consumption reconciliation matches activities by exact name string**
  (`consumption_norms.activity == work_done_entries.activity`) — a typo means
  no theoretical figure. There's no dropdown/foreign-key linking the two yet.
- **Cube result is a per-cube `strength >= grade` check**, not the statistical
  IS 456 acceptance criterion over a sample set.
- **Security is opt-in and off by default** (§20). When off there is no session
  and everything is writable (single-user mode) — that is the intended default
  for a solo contractor. Roles gate the UI (`session.can_write`/`is_admin`), not
  the DB; there is no row-level security and no at-rest DB encryption (stdlib
  SQLite has none — SQLCipher would break the no-dependency rule). Per-tab
  write/delete gating for Viewers is only partially wired (Tools/user
  management is gated; most data tabs are not yet).
- No committed automated tests (the pure functions in `finance.py`, `civil.py`,
  and `bill_export.py` are the intended first target — see §2/§13/§18).

## 15. Civil billing — BOQ, Measurement Book, RA bills (`tab_boq_ra.py`)

This is the civil-contracting billing spine, and it is **measurement-driven**
(unlike the generic `BillingTab` in §6, which takes a hand-typed work-done
value). All arithmetic lives in `civil.py`; the tab is a three-view inner
notebook.

- **BOQ** (`BOQFrame`): priced items per contract (`boq_items`: `item_no`,
  `description`, `unit`, `qty`, `rate`, `amount = qty*rate`). Pick a contract,
  then add/edit its items. Deleting a BOQ item cascades its measurements.
- **Measurement Book** (`MeasurementFrame`): site measurements against a BOQ
  item (`measurements`). Quantity = **Nos × L × B × D** via
  `civil.measurement_quantity`, where a **blank dimension counts as 1** (so a
  running-metre item is `Nos × Length`, a count is just `Nos`). Blank dims are
  stored as SQL `NULL`; the live "Quantity" label updates as you type. The MB
  grid is filtered to the selected contract.
- **RA bills** (`RABillFrame`): "Generate RA Bill" snapshots, for every BOQ
  item on the contract, `upto_qty` (cumulative measured quantity with
  `mb_date <= bill_date`), `previous_qty` (sum of `current_qty` from prior
  **Approved/Paid** RA bills — §6 convention, see §14 caveat), and
  `current_qty = upto - previous`, priced at the BOQ rate. `civil.ra_bill_totals`
  then derives `this_bill_value`, `cumulative_value`, `retention_amt`
  (`this_bill_value × retention% ` ), and `net_payable`. The header row and the
  per-item `ra_bill_items` abstract are stored together; **an RA bill is a
  snapshot** — it does not live-recompute when later measurements are added
  (regenerate/replace if measurements change before approval). Status moves
  Draft→Submitted→Approved→Paid; "Export Abstract (HTML)" writes the standard
  RA abstract via `bill_export.build_ra_bill_html`.

If you add subcontractor RA bills later, reuse this pattern (BOQ→MB→RA) rather
than the generic BillingTab.

## 16. Site execution & quality (`tab_consumption.py`, `tab_site_reports.py`)

**Material consumption reconciliation** (`tab_consumption.py`, inner notebook):
- **Norms** (`consumption_norms`): material consumed per unit of an activity
  (e.g. 6.0 bags cement / cum of 'M20 Concrete'). A `CrudFrame`.
- **Work Done** (`work_done_entries`): executed activity quantities per site. A
  `CrudFrame`.
- **Reconciliation** (`ReconciliationView`, computed): for a site,
  theoretical = `SUM(work.qty × norm.qty_per_unit)` grouped by material
  (activities joined **by exact name** — §14 caveat), actual = `SUM(OUT` ledger
  `qty)` per material; variance & wastage% via `civil.reconcile_consumption`.
  Over-consumption rows are tinted red.

**Site registers** (`tab_site_reports.py`, four `CrudFrame`s):
- **Daily Progress** (`daily_progress`): weather/labour/plant/work summary.
- **Cube Tests** (`cube_tests`): `strength_mpa` and Pass/Fail `result` are
  auto-filled on save by `_compute_cube` (an `on_save` hook using
  `civil.cube_strength` = `load_kN × 1000 / area_mm²` and `civil.cube_result`
  vs `civil.grade_target`). Same best-effort/manual-override pattern as the
  hire/duration auto-calcs — it never raises.
- **Material Tests** (`material_tests`) and **Plant Log** (`plant_logs`): plain
  registers.

## 17. Money — cash-first, the primary financial UX (`tab_money.py`, `tab_home.py`)

**Audience reminder** (see `docs/PRODUCT.md`): the user is a T2/T3 solo
contractor who thinks in cash-in / cash-out and "kitna baaki", NOT debits and
credits. So the **cash-first** views are the primary financial experience; the
double-entry **Accounting** tab (§9) is repositioned as advanced / for-the-CA.
Lead new financial features from here, in plain language.

- **`payments`** is one table for both directions: `direction` is `Receipt`
  (money in) or `Payment` (money out); `party_type` ∈ Client/Vendor/Labour/Other
  with a nullable `party_id` into the matching master plus a denormalized
  `party_name` snapshot (so a statement still reads correctly if the master row
  changes or the party was free-typed). `mode` ∈ Cash/Bank/UPI/Cheque.
- **`app_settings`** is a tiny key/value table; today it holds `cash_opening`
  (the cash book's opening balance). Use it for other simple singletons.
- **Payments & Receipts** (`PaymentsFrame`): bespoke form; the Party combo
  repopulates from the chosen Party Type. `_parse_combo` turns an `"id - name"`
  selection back into `(id, name)`, or `(None, free-text)` for Other.
- **Party Balances** (`PartyLedgerView`): a running statement of that party's
  payments plus a headline outstanding. For a **Client**, billed =
  `SUM(net_payable)` of Approved/Paid `bills` + `ra_bills` on that client's
  contracts, settled = client receipts. For a **Vendor**, billed =
  `SUM(vendor_invoices.net_payable)`, settled = vendor payments.
  `money.party_outstanding(billed, settled)` gives "owes us" / "we owe".
- **Cash Book** (`CashBookView`): the digital bahi-khata — `mode='Cash'`
  entries (optionally site-filtered) turned into a running balance over the
  saved opening via `money.running_balance` / `closing_balance`.
- **Home** (`tab_home.py`): computes cash-in-hand, receivables, payables, active
  sites, and month billed/collected on demand from the same tables. Nothing
  stored. All maths through `money.py`.

Caveats (also in §14): receivables/payables here are a **cash-vs-billed
approximation**, not a reconciled ledger; party matching keys on
`party_id` (falling back to `party_name` for free-typed parties), so a
mistyped name starts a separate balance line.

## 18. Verifying civil & money changes

`civil.py` is pure; assertions that should always hold:

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

## 19. Labour — muster roll, weekly payout, thekedars (`tab_muster.py`)

How a T2/T3 site actually handles labour (see PRODUCT.md job #4). Wage maths is
in `wages.py`.

- **Muster Roll** (`MusterRollFrame`): pick a site + date, Load pulls every
  `status='Active'` labourer assigned to that site into an editable grid,
  pre-filled from any existing `attendance` for that date. Mark individually,
  or "All Present"/"All Absent". **Save Muster** writes one `attendance` row per
  labourer per day — it `DELETE`s any existing row for that `(labor_id,
  att_date)` first, so re-saving a day replaces rather than duplicates. (The
  `attendance` table has no unique constraint; this delete-then-insert is what
  enforces one-mark-per-day.)
- **Weekly Payout** (`WeeklyPayoutFrame`): site + week-start → a 7-day window;
  per labourer, days = Σ`wages.day_fraction` over that week's attendance, then
  `wages.wage_net(days, daily_wage, open_advance_balance)`. **Export Payout
  Sheet** prints via `build_statement_html`; **Record as Payments** inserts a
  `payments` row (`direction='Payment'`, `party_type='Labour'`, `mode='Cash'`)
  per positive net, so wages flow straight into the cash book (§17). It does
  **not** mark advances recovered or dedupe — running it twice records twice.
- **Thekedars** (`thekedars` master via `CrudFrame`) + **Thekedar Ledger**
  (`ThekedarLedgerFrame`): a labour contractor's running account —
  `entry_type='Work'` increases what we owe, `'Paid'` decreases it; balance via
  `money.running_balance`. Printable.

## 20. Security & robustness (opt-in login, roles, audit)

**Opt-in by design.** The app ships with security **off** — it opens straight
in, single-user, so the solo contractor keeps zero-friction access (PRODUCT.md).
An office with staff turns it on in **Tools > Users & Security**; that requires
at least one active **Admin** first (`auth` won't let you enable login or demote/
deactivate the last admin). `main.py` shows `tab_login.LoginDialog` at startup
only when `auth.security_enabled` **and** at least one user exists.

- **Passwords**: `security.py` — salted **PBKDF2-HMAC-SHA256** (120k iters),
  constant-time verify (`hmac.compare_digest`), light policy. Never store or log
  plaintext. Stored as `users.salt` + `users.password_hash` (hex).
- **Lockout**: `auth.authenticate` increments `failed_attempts` and sets
  `locked=1` at `MAX_FAILED` (5); an Admin clears it via Unlock. Failure
  messages are generic (no user enumeration).
- **Roles** (`session.ROLES`): Admin (all, incl. user management), Operator
  (day-to-day), Viewer (read-only — `session.can_write()` is False). Gating is
  in the **UI**: check `session.is_admin()` / `can_write()` before a privileged
  action. When security is off there is no session and both default to
  full-access (single-user) — so gate as `(not security_enabled) or is_admin()`
  for bootstrap-friendly panels (see `SecurityTab._management_allowed`).
- **Viewer read-only enforcement**: every write entry point calls
  `ui_guard.can_write()` (a one-line `if not can_write(): return`) — a Viewer
  sees a "read-only" dialog and the write is skipped. It's enforced centrally in
  `CrudFrame` (add/update/delete) and `DocumentFrame`, and in each bespoke
  financial tab's write methods (payments, tax/vendor invoices, bills, estimate,
  BOQ/measurement/RA, muster save + payout, journal + auto-post, payroll). When
  you add a new write action, add the same guard as its first line.
  `ui_guard` is a thin tkinter wrapper so `session` stays GUI-free.
- **Audit log**: `auth.audit(conn, actor, action, entity, entity_id, detail)`
  appends to `audit_log`; logins, failures, user-management, and the security
  toggle are recorded. Viewable in **Tools > Audit Log**. `audit()` is
  best-effort and never raises into the caller. If you add sensitive actions
  (deletes, restores, bulk edits), call `audit()` from them.
- **Robustness**: see §10 for WAL / `busy_timeout` / FK pragmas and the hot-path
  indexes. Every DB op still uses a fresh short-lived `get_conn()`.

**Branding** (`assets.py` + `resources/`): the bundled "Construction Operations
System" logos brand the app — window/taskbar icon (`main._apply_app_icon`, square
PNG via `iconphoto` + `.ico` via `iconbitmap` on Windows), the Home header and
login dialog (`tk.PhotoImage`, Tk 8.6+ reads PNG), and every printed document's
letterhead (`assets.logo_html()` embeds the rectangular logo as a base64 `data:`
URI so the HTML stays self-contained). All logo loads **fail soft** — a missing
file or old Tk just falls back to text, never an error. To rebrand, replace the
files in `resources/` (keep the names); `bill_export._LOGO_TAG` re-reads on
import.

Everything except the dialogs is DB/pure and unit-testable: exercise
`security.hash_password/verify_password` and `auth.*` (create/authenticate/
lockout/roles/audit) against a real connection with no GUI.

## 21. AI Assistant — RAG over your data (`assistant.py`, `tab_assistant.py`)

An "ask your data in plain language" tab (top-level, always on). It answers
questions about the contractor's **own records** via **retrieval-augmented
text-to-SQL** with a **local Ollama** model.

**No-pip / offline preserved.** The only new capability is `ollama_client.py`,
which talks to a *local* Ollama HTTP server with stdlib `urllib` — no Python
package, and localhost so still offline. The tradeoff: the assistant needs the
user to install Ollama separately and `ollama pull` a model. Everything **fails
soft** — with Ollama absent the tab still shows deterministic **quick answers**
and a clear "start Ollama" status; the rest of the app is unaffected.

Pipeline (`assistant.answer`): `retrieve` ranks the curated `SCHEMA_DOCS` +
few-shot `EXAMPLES` by keyword overlap (the "R"; no embeddings) → Ollama writes
one SQL `SELECT` grounded in that context → `extract_sql` + `validate_sql`
(SELECT/WITH only, single statement, write/PRAGMA/ATTACH keywords blocked, a
`LIMIT` injected) → `safe_execute` runs it under **`PRAGMA query_only = ON`**
(engine-level read-only — defence in depth over validation) → Ollama summarises
the rows in plain language.

Rules for extending:
- **Read-only, always.** Never route model output to a writable connection.
  Keep both `validate_sql` (deny-list + SELECT-only) and `query_only` (engine
  guard); don't drop either.
- When you add/rename tables or columns, **update `SCHEMA_DOCS`** (and
  `_VALID_TABLES`) so the model stays grounded — stale schema text = wrong SQL.
- Add high-value patterns as **`EXAMPLES`** (few-shot) rather than prompt prose;
  keep example SQL correct against the real schema.
- Deterministic **`quick_answers`** must never need the LLM — they're the
  offline floor. Model config (`assistant_model`/`assistant_host`) lives in
  `app_settings`, edited in Tools.
- The LLM call is slow, so the tab runs it on a **background thread** and
  marshals back with `after`; keep that off the UI thread.

## 22. Project management (`tab_projects.py`, `projman.py`)

The **Projects** section (top-level, its own module in `SECTIONS_CATALOG`) is the
umbrella that ties a job together — added because the app previously jumped
straight from sites/contracts to documents with no project layer.

- **`projects`** table: name, client, site, start/end, budget, status. A thin
  `CrudFrame`.
- **`milestones`** table (`ON DELETE CASCADE` from projects): name, target/actual
  date, optional `amount` (payment-stage value), status Pending/Done. A
  `CrudFrame`.
- **`timeline_tasks.project_id`** links Gantt tasks to a project (added to the
  CREATE and to `_ADD_COLUMNS` for existing DBs; the timeline task form has a
  Project fk).
- **Project Overview** (`ProjectOverview`, bespoke, read-only): for the chosen
  project it computes **budget vs cost-to-date** (material issued + labour cash
  paid + equipment hire on the project's site) vs **billed** (Approved/Paid
  bills + RA bills on that site's contracts), the **margin so far**, budget
  **used %**, and **milestone progress** (`projman.milestone_progress` —
  amount-weighted when milestones carry amounts, else a count ratio), plus open
  task count. All the site-scoped cost/revenue queries mirror the Insight tab.

Caveat: project cost/revenue is derived **via the project's `site_id`** (not a
hard project↔transaction link), so two projects sharing a site would share those
figures — fine for the common one-site-per-project case; note it if you add
multi-project sites.

## 23. Later modules (billing, compliance, insight, subcontractors, trust)

This section indexes the modules added after the core ERP, so an agent extending
them knows where the maths and UI live. Every pure module below is `python -c`
testable and has no tkinter/DB.

**Billing & documents**
- `numbering.py` — `financial_year` (Indian Apr–Mar), `build_number`,
  `next_serial`/`next_number`. Drives tax-invoice auto-numbering; config in
  `app_settings` (`invoice_prefix`/`invoice_width`/`invoice_fy_reset`), edited in
  Tools. Serial is derived by scanning numbers already in use, so it's robust to
  deletes/manual numbers. Reuse it for other document series.
- `DocumentFrame` now has a **Print / Export** button (`tab_documents.py`) →
  quotations & POs render via `bill_export.build_statement_html`; the vendor
  invoice tab has its own export with GST/TDS breakup.
- Rate Book / Specification library: `rate_book` table + `build_rate_book_tab`
  (a plain CrudFrame under Billing) — a PWD-style schedule of rates to reuse.
- Deviation statement: `civil.deviation` (tendered BOQ vs executed measured qty
  → excess/saving) + the `DeviationStatement` view in `tab_boq_ra.py`.

**Compliance (`tab_gst.py`)**
- Output GST now spans tax invoices **plus** RA + running bills (works-contract
  supply at `app_settings.works_gst_pct`, default 18), with a Source column.
- `hsn_summary` — GSTR-1-style HSN/SAC-wise taxable + tax from tax-invoice items.

**Insight (`tab_insight.py`)**
- `ageing.py` — FIFO-settle a party's dated bills by total receipts/payments,
  then bucket the remainder 0-30/30-60/60-90/90+. Receivables age client bills +
  RA bills; payables age vendor invoices.
- `analytics.py` — `contract_progress` (measured value ÷ BOQ value, uncapped so
  deviations show) and `material_budget` (theoretical vs actual consumption
  valued at the material's `rate`).

**Accounting reports (`reports.py`)**
- `profit_and_loss` and `balance_sheet` from per-account debit/credit totals
  (the same rows the trial balance uses); current-period profit folds into
  equity so the sheet ties out. Views in `tab_accounting.py`.

**Subcontractors (Phase 7, §7-style)**
- `subcontract.py` — `sub_bill_totals` (retention via `civil.ra_bill_totals` +
  works-contract TDS via `finance.compute_tds`). Tables `work_orders` (+items)
  and `sub_bills`. UI `tab_subcontract.py`. Posting rule
  `posting.sub_bill_lines` + a `post_all` loop (Approved/Paid).

**Labour statutory (optional, off the main flow)**
- `statutory.py` — EPF, ESI (below-threshold split), BOCW labour cess. Optional
  `labor.pf_no`/`esi_no` fields; a standalone `StatutoryCalculator`
  (`tab_statutory.py`) under Muster & Wages. Nothing auto-deducts.

**Trust & ease (Phase 4)**
- `tab_wizard.py` — one-time first-run setup (firm details + first site/client),
  gated on `app_settings.setup_done` and empty masters.
- Low-typing: `crud_frame.Field(default=TODAY, remember=True)` — date fields
  prefill today; `remember` persists the last value per `last:<table>:<column>`
  and prefills it next time. Applied across the CrudFrame ops tabs.
- `i18n.py` — navigation-layer vernacular (English/Hindi/Hinglish) with English
  fallback; `main` localises tab/section labels via `i18n.t` (internal label
  keys stay English so `BUILDERS`/toggles are unaffected). Language in
  `app_settings.language`, toggled in Tools.
- `errors.py` — `install(root)` sets `report_callback_exception` so any uncaught
  callback error becomes a plain-language dialog (full traceback still logged to
  stderr). No stack trace ever reaches the user.

**When you extend these**: keep new maths in the pure module, add a `python -c`
assertion, wire the tab, and register any new top-level module in
`modules.SECTIONS_CATALOG` + `main.BUILDERS` + (optionally) an `i18n` entry.
