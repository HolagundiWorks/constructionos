# AGENTS.md — Contractor-OS (Construction ERP)

This file is written for an **AI coding agent** (Claude Code, Cursor, etc.)
that will read, modify, or extend this codebase. It documents architecture,
conventions, and gotchas that are not obvious from the code alone. Read this
in full before making changes.

If you are a human developer, `README.md` is the friendlier version of this
document. This one is denser and assumes you will grep the source while
reading.

---

## 0. Product vision (read this first)

Contractor-OS is growing from a site-operations tool into a **full-fledged
ERP for Indian construction contractors** — think a focused, single-file,
zero-dependency Dolibarr for the construction trade. The trajectory is:

- **Operations** (built): sites/warehouses, vendors, clients, materials,
  labor, equipment, stock ledger, attendance, payroll, advances, timelines.
- **Commercial** (built): quotations, estimates, contracts, running bills
  (with printable bill export).
- **Procurement** (built): purchase orders, vendor invoices, and PO↔invoice
  reconciliation.
- **Finance & accounting** (foundation built): GST (CGST/SGST/IGST) and TDS
  computation, a chart of accounts, a double-entry journal, and a trial
  balance.
- **Next** (not built — see §14): auto-posting business documents (bills,
  vendor invoices, payroll) into the journal; GST returns (GSTR-style
  summaries); ageing/outstanding reports; payments & receipts; multi-site P&L.

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
- **Tests**: there is still no committed automated test suite or CI. When you
  change or add maths, exercise the pure functions with `python -c` (see §2)
  and, if adding substantial logic, put real tests in a new `tests/` folder
  using stdlib `unittest` — don't add `pytest` as a hard dependency without
  confirming with the user.

## 2. Running & verifying your changes

```bash
cd construction_app
python main.py
```

There is no headless test suite. To verify without a display:

```bash
python -m py_compile *.py                          # syntax check every module
python -c "import db; db.init_db(); print('ok')"   # schema + CoA seed check
```

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
├── main.py                 # Entry point. Builds the ttk.Notebook, wires every tab in one place.
├── db.py                   # SQLite schema (single SCHEMA string) + get_conn() + init_db() + default CoA seed.
├── finance.py              # PURE tax/accounting maths: GST split, TDS, invoice roll-up, PO reconciliation, double-entry checks. No tkinter/DB.
├── bill_export.py          # PURE build_bill_html(): renders a running bill to a printable HTML string. No tkinter/DB.
├── crud_frame.py           # Generic reusable "list + form" widget (CrudFrame) and Field descriptor.
├── tab_masters.py          # Sites, Clients, Materials, Labor, Equipment master CRUD + shared *_options fk helpers.
├── tab_vendor.py           # Vendor master (CrudFrame) + a read-only spend/hire rollup view.
├── tab_warehouse.py        # Material ledger (CrudFrame) + a computed-on-the-fly stock summary view.
├── tab_labor.py            # Attendance (CrudFrame), Advances (CrudFrame), Payroll (bespoke). days_present_for() is the extracted rule.
├── tab_documents.py        # DocumentFrame generic class (header + line items) → Quotations, Estimates, Purchase Orders. Contracts is a plain CrudFrame.
├── tab_billing.py          # BillingTab: bespoke Bills/Running Bills with running-total math + "Make Bill" HTML export (bill_export).
├── tab_vendor_invoice.py   # Vendor invoices (bespoke, GST/TDS via finance) + PO↔invoice ReconciliationView.
├── tab_accounting.py       # Chart of Accounts (CrudFrame) + JournalFrame (double-entry) + TrialBalance report.
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
  `journal_lines`) raises `sqlite3.IntegrityError` as an uncaught exception,
  not a friendly dialog. **Known gap** — if asked to "fix delete errors,"
  wrap `CrudFrame.delete_selected` in try/except and show a `messagebox`
  explaining the row is in use, rather than patching each tab.

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

- Attendance → fractional days present via the extracted `days_present_for`:
  `Present`=1.0, `Half Day`=0.5, `Overtime`=`1 + max(0, hours-8)/8`,
  `Absent`=0.
- `gross_amount = days_present * labor.daily_wage`.
- Deduction = `min(open_advance_balance, gross_amount)` where
  `open_advance_balance = SUM(amount - recovered)` over that labor's `advances`
  with `status='Open'`. Never negative net pay.
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
journal entry should itself balance. Nothing auto-posts business documents into
the journal yet — the journal is manual-entry only (§14). `finance.account_net`
gives an account's signed balance in its normal direction if you build ledger/
P&L views later.

## 10. Database schema quick reference

All tables live in one `SCHEMA` string in `db.py`. FKs are declared but
**`PRAGMA foreign_keys = ON` is per-connection** in `get_conn()` — any script/
test opening SQLite outside `db.get_conn()` must re-issue the pragma or FK
constraints silently won't enforce.

Relationships at a glance:
```
sites 1──* labor / material_ledger / equipment_hire / timeline_tasks
          / estimates / contracts / equipment(current_site_id)
          / purchase_orders

vendors 1──* material_ledger(vendor_id, meaningful only for txn_type='IN')
            / equipment_hire / purchase_orders / vendor_invoices

clients 1──* quotations / contracts
labor   1──* attendance / advances / payroll
contracts 1──* bills            (running bill chain — §6)

quotations       1──* quotation_items        (ON DELETE CASCADE)
estimates        1──* estimate_items         (ON DELETE CASCADE)
bills            1──* bill_items             (ON DELETE CASCADE)
purchase_orders  1──* purchase_order_items    (ON DELETE CASCADE)
purchase_orders  1──* vendor_invoices         (purchase_order_id, nullable)
vendor_invoices  1──* vendor_invoice_items    (ON DELETE CASCADE)

accounts        1──* journal_lines            (account_id, NO cascade)
accounts        1──* accounts                 (parent_id self-reference)
journal_entries 1──* journal_lines            (ON DELETE CASCADE)
```

**Six** child tables declare `ON DELETE CASCADE`: `quotation_items`,
`estimate_items`, `bill_items`, `purchase_order_items`,
`vendor_invoice_items`, `journal_lines`. Everything else relies on app-level
`delete_*` methods to clean up children (e.g. `DocumentFrame.delete_header`
deletes items before the header). `CrudFrame.delete_selected` does **not**
cascade for any table — the §4 gap. In particular, deleting an `account`
referenced by a `journal_line`, or a `vendor`/`site` referenced by children,
raises `IntegrityError`.

## 11. Conventions to follow when extending

- **Dates are plain `TEXT` `YYYY-MM-DD`**, validated ad hoc with
  `datetime.strptime` in `try/except`, no date-picker widget. Other code
  (payroll month/year `strftime` queries, hire/duration calculators, the Gantt)
  assumes this format.
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
  a widget, or a class taking `(parent, db_getter)` subclassing `ttk.Frame`.**
  `main.py` adds each via `nb.add(widget_or_builder(nb, db.get_conn), text=...)`.
  Match this so new tabs plug in identically. Tabs with several views (Vendor,
  Warehouse, Labor Ops, Vendor Invoices, Accounting, Timeline) return an inner
  `ttk.Notebook`.
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
- **No auto-posting to the journal.** Bills, vendor invoices, and payroll do
  **not** create `journal_entries` automatically; the journal is manual-entry
  only. Wiring these to post balanced entries (Dr Materials Consumed / Input
  GST, Cr Accounts Payable / TDS Payable, etc.) is the next big step.
- **Reconciliation is totals-level only** — no line/quantity matching, no
  three-way match against goods received (§7).
- **No GST returns / GSTR summaries, no ageing/outstanding, no payments &
  receipts ledger, no P&L / balance sheet** — trial balance is the only
  financial report so far.
- **PO `total_amount` is pre-tax**; there's no GST-inclusive PO total (§5).
- No retroactive recompute of prior bills' `previous_billed` when a later
  bill's status changes (§6).
- No cascade-delete handling in `CrudFrame` (§4/§10).
- No regenerate/delete affordance for payroll rows (§8).
- `dependency` in timeline tasks is inert metadata; the Gantt ignores it.
- No PDF export (bills have printable **HTML** export via `bill_export`;
  quotations/estimates/POs/invoices do not export yet).
- No authentication/multi-user support.
- No committed automated tests (the pure functions in `finance.py`/
  `bill_export.py` are the intended first target — see §2/§13).
