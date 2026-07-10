# AGENTS.md — Construction Management System

This file is written for an **AI coding agent** (Claude Code, Cursor, etc.)
that will read, modify, or extend this codebase. It documents architecture,
conventions, and gotchas that are not obvious from the code alone. Read this
in full before making changes.

If you are a human developer, `README.md` is the friendlier version of this
document. This one is denser and assumes you will grep the source while
reading.

---

## 1. What this project is

A single-user desktop app for managing a construction company's operations:
sites/warehouses, vendors, clients, materials, labor, equipment, stock
ledgers, attendance, payroll, advances, quotations, estimates, contracts,
running bills, equipment hire, and project timelines.

- **Language/runtime**: Python 3.8+, standard library only.
- **GUI**: `tkinter` / `tkinter.ttk` (no web server, no external UI framework).
- **Persistence**: SQLite via `sqlite3`, single file `construction.db`
  created next to the code on first run.
- **No package dependencies.** Do not add `pip install` requirements unless
  explicitly asked — this is a deliberate design constraint so the app runs
  anywhere Python runs.
- **No tests currently exist.** There is no test harness, no CI config, no
  `requirements.txt`. If you add automated tests, use `unittest` (stdlib) and
  put them in a new `tests/` folder; don't introduce `pytest` as a hard
  dependency without confirming with the user first.

## 2. Running & verifying your changes

```bash
cd construction_app
python main.py
```

There is no headless test suite. To verify a change without a display:

```bash
python -m py_compile <changed_file>.py     # syntax check
python -c "import db; db.init_db(); print('ok')"   # schema sanity check
```

If your sandbox has no `tkinter` (common in minimal containers — `apt-get
install python3-tk` may be needed and may fail without network access),
`py_compile` plus manual code review is the fallback verification method.
Say so explicitly if you cannot launch the GUI — don't claim you tested a
UI you couldn't render.

Because logic (payroll math, running-bill math, hire-cost math, duration
math) lives inline inside GUI callback methods rather than in separately
tested pure functions, **read the callback body carefully by eye** when
changing calculations — there's no unit test safety net yet. If you're
adding non-trivial business logic, consider extracting it into a standalone
function at module level (like `_compute_hire_total` and
`_compute_duration` already are) so it *can* be unit tested later, and so
you can `python -c` exercise it directly.

## 3. File map & responsibilities

```
construction_app/
├── main.py                 # Entry point. Builds the ttk.Notebook, wires every tab in one place.
├── db.py                   # SQLite schema (single SCHEMA string) + get_conn() + init_db().
├── crud_frame.py           # Generic reusable "list + form" widget (CrudFrame) and Field descriptor.
├── tab_masters.py          # Sites, Clients, Materials, Labor, Equipment master CRUD (all thin CrudFrame wrappers).
├── tab_vendor.py           # Vendor master (delegates to tab_masters) + a read-only spend/hire rollup view.
├── tab_warehouse.py        # Material ledger (CrudFrame) + a computed-on-the-fly stock summary view.
├── tab_labor.py            # Attendance (CrudFrame), Advances (CrudFrame), Payroll (bespoke, has "Generate" logic).
├── tab_documents.py        # DocumentFrame generic class (header + line items) → used for Quotations & Estimates. Contracts is a plain CrudFrame.
├── tab_billing.py          # BillingTab: bespoke header+items UI for Bills/Running Bills with running-total math.
├── tab_equipment_hire.py   # Equipment Hire CrudFrame + _compute_hire_total on_save hook.
├── tab_timeline.py         # TimelineTab: CrudFrame for tasks + a hand-drawn Canvas Gantt chart.
└── construction.db         # Created at runtime — never commit this file; it's user data, not source.
```

**Rule of thumb for where new code goes**: if it's a flat, single-table
form (a "master" or a simple transaction log), it belongs in a `CrudFrame`
instance, ideally added to an existing `tab_*.py` file or a new one
following the same pattern. If it's a header-with-line-items document
(like a quotation/invoice), extend or reuse `DocumentFrame` in
`tab_documents.py` rather than writing another bespoke class — only
`tab_billing.py` deviates from that pattern, and only because running-bill
math needed extra computed columns the generic frame doesn't support.

## 4. The `CrudFrame` abstraction (read before touching any master/simple tab)

`crud_frame.py` defines two things:

- **`Field(key, label, kind='text', width=110, options=None, options_func=None, default='')`**
  Describes one form field / table column.
  - `kind='text'` → plain `ttk.Entry`, stored as string.
  - `kind='number'` → plain `ttk.Entry`, but parsed with `float()` on save;
    shows an error dialog if not numeric.
  - `kind='combo'` → read-only `ttk.Combobox` populated from a static
    `options=[...]` list.
  - `kind='fk'` → read-only `ttk.Combobox` populated dynamically by calling
    `options_func(conn)`, which must return `[(id, label), ...]`. The
    combobox displays `"{id} - {label}"` strings; `CrudFrame` parses the
    leading id back out when saving. **This string-parsing is the reason
    labels must not contain `" - "` in a way that's ambiguous** — if you add
    an `options_func` whose label itself contains " - ", the id-extraction
    (`raw.split(' - ')[0]`) will still work because it splits only on the
    first occurrence, but be aware of this coupling before changing the
    format string in `_collect_values`/`_refresh_fk_options`.

- **`CrudFrame(parent, db_getter, table, fields, title, extra_where='', order_by='id DESC', on_save=None)`**
  A `ttk.Frame` containing: a `Treeview` list, an auto-generated form (3
  fields per row, wraps automatically), and Add/Update/Delete/Clear/Refresh
  buttons. It does raw `INSERT`/`UPDATE`/`DELETE` against `table` using the
  `fields` list — **it has no idea about foreign key cascades or business
  rules**, so any side effects (like recomputing a total, or updating a
  derived column) must be done via the `on_save(conn, row_id, values_dict)`
  callback, which is invoked after insert/update. See
  `_compute_hire_total` (`tab_equipment_hire.py`) and `_compute_duration`
  (`tab_timeline.py`) for the pattern: fetch/compute inside `on_save`,
  `UPDATE` the derived column, `commit()`, and don't raise — wrap in
  `try/except: pass` because these are best-effort auto-fills, not
  validated business rules.

  **Important existing behavior to preserve**: `on_save` receives a
  `conn` that the `CrudFrame` itself will `close()` immediately after the
  callback returns. Do not close it yourself inside the callback, and do
  not expect the connection to remain usable after `on_save` returns.

  **Deletion has no cascade logic** — `CrudFrame.delete_selected` does a
  bare `DELETE FROM {table} WHERE id = ?`. Because `db.py`'s schema enables
  `PRAGMA foreign_keys = ON` but most child tables don't declare
  `ON DELETE CASCADE` (only `quotation_items`, `estimate_items`, and
  `bill_items` do), deleting a parent row referenced elsewhere (e.g.
  deleting a `labor` row that has `attendance`/`advances`/`payroll` history)
  will raise a `sqlite3.IntegrityError` that surfaces as an uncaught
  exception, not a friendly dialog. **This is a known gap** — if asked to
  "fix delete errors" or "handle foreign key constraint errors," the fix
  belongs in `CrudFrame.delete_selected` (wrap in try/except and show a
  `messagebox.showerror` explaining the row is in use) rather than in each
  individual tab.

## 5. The `DocumentFrame` abstraction (Quotations, Estimates)

`tab_documents.py`'s `DocumentFrame` is a header (`ttk.Treeview` + form) on
top and a line-items grid (its own `Treeview` + form) on the bottom, joined
by a foreign key column (`fk_col`, e.g. `quotation_id`). Selecting a header
row loads only that document's items into the lower grid. Every add/update/
delete of a line item calls `_recalc_total`, which re-sums the item table
and writes the total into the header row's `total_col`
(`total_amount`/`total_estimate`). **The header total is therefore always
derived, never hand-entered** — there is no field for it in `header_fields`
for this reason; don't add one.

To add a new header+items document type (e.g. "Purchase Orders"):
1. Add `purchase_orders` and `purchase_order_items` tables to `db.py`'s
   `SCHEMA` string, matching the shape of `quotations`/`quotation_items`
   (header needs an `id` and a total column; items need `id`, the fk column,
   `description`, `unit`, `qty`, `rate`, `amount`).
2. Add a `build_purchase_orders_tab(parent, db_getter)` function in
   `tab_documents.py` that constructs and returns a `DocumentFrame(...)`,
   following `build_quotations_tab` as the template.
3. Register it in `main.py`'s `nb.add(...)` list.

## 6. `BillingTab` (Bills / Running Bills) — why it's bespoke

Running bills need a computed `previous_billed` (sum of prior
Approved/Paid bills on the *same contract*) that `DocumentFrame` has no
concept of, so `tab_billing.py` implements its own header+items UI by hand
rather than reusing `DocumentFrame`. The core formula, in
`BillingTab.add_bill` / `update_bill`:

```
previous_billed = SUM(net_payable) FROM bills
                   WHERE contract_id = <this contract>
                   AND status IN ('Approved', 'Paid')
                   [AND id != <this bill, when updating>]

net_payable = work_done_value - previous_billed - retention_amt - other_deductions
```

Bills in `Draft`/`Submitted` status are **excluded** from `previous_billed`
for other bills — only `Approved`/`Paid` bills count as "already paid out."
This means: **changing a bill's status to Approved/Paid changes the
`previous_billed` (and therefore `net_payable`) of every *subsequent* bill
on that contract, but does NOT retroactively recompute bills that were
already saved before the status change.** If asked to fix this, the correct
approach is to recompute `previous_billed`/`net_payable` for all bills on a
contract, ordered by id/date, whenever any bill on that contract is saved
or its status changes — currently that recompute only happens for the one
bill being added/edited.

Line items on a bill (`bill_items`) are a separate bill-of-quantities
breakdown; they do **not** automatically drive `work_done_value` — the user
must click "Sum Items -> Work Done Value" to pull the item total into the
header field, then click "Update Selected" to persist it. This two-step
flow is intentional (lets users override work-done value independent of
the itemized breakup) but is a common point of confusion — if asked to
"auto-update work done value," that's the place to change (either recalc on
every item change like `DocumentFrame` does, or leave as a manual pull —
confirm which behavior is wanted before changing it).

## 7. Payroll generation (`tab_labor.py`, `LaborTab.generate_payroll`)

Business rule, encoded only here (not reusable/tested elsewhere):

- Attendance days map to fractional "days present":
  `Present` = 1.0, `Half Day` = 0.5, `Overtime` = `1 + max(0, hours-8)/8`
  (i.e. a full day plus a fractional bonus for hours beyond 8), `Absent` =
  0 (not counted at all).
- `gross_amount = days_present * labor.daily_wage`.
- Deduction = `min(open_advance_balance, gross_amount)`, where
  `open_advance_balance = SUM(amount - recovered)` over that labor's
  `advances` rows with `status='Open'`. Deduction never exceeds gross (no
  negative net pay).
- **Idempotency guard**: generation is a no-op for a `(labor_id, month,
  year)` combination that already has a `payroll` row — it silently skips,
  it does not update. To regenerate, the existing row must be deleted first
  (there is currently no UI button for this — only a delete would require
  adding a `CrudFrame`-style delete to the payroll Treeview, which doesn't
  exist yet; the payroll tab is list+generate+mark-paid only, no per-row
  edit/delete). If asked to add "regenerate/delete payroll," build a small
  action bound to `self.tree.selection()` similar to `mark_paid`.
- Only labor with `status='Active'` are included in a payroll run.
- This function is a good candidate for extraction into a pure, testable
  function — currently it's a method that opens its own connection. (The
  day-fraction rule *is* already extracted to `days_present_for`.)

## 8. Equipment hire cost auto-calc (`tab_equipment_hire.py`)

`_compute_hire_total(conn, row_id, values)` runs as `on_save` on the
`equipment_hire` `CrudFrame`. If both `hire_start` and `hire_end` parse as
`YYYY-MM-DD`, it computes `days = (end - start).days + 1` (inclusive), then:
- `Daily` → `days * rate`
- `Monthly` → `(days / 30.0) * rate` (simple 30-day month approximation, not
  calendar-accurate)
- `Hourly` → `days * 8 * rate` (assumes 8-hour standard day when only date
  range is given, not actual logged hours)
- else → `rate` unchanged

If dates are missing/unparseable, whatever the user typed into
`total_amount` is left untouched (manual override). This is a deliberate
"best-effort auto-fill, manual override always wins" pattern — same as
`_compute_duration` in `tab_timeline.py`. Keep that pattern if you touch
this code: don't make the auto-calc clobber a manually-entered value when
inputs are invalid.

## 9. Timeline / Gantt (`tab_timeline.py`)

`_compute_duration` auto-fills `duration_days` from `start_date`/`end_date`
via the same `on_save` pattern as above. The `Gantt Chart View` sub-tab
draws bars on a raw `tk.Canvas` (no charting library) proportionally
between the min and max task dates across all tasks (or a filtered site).
Colors are keyed by `status` string match in `status_colors` — adding a new
status value to the `Field('status', ..., options=[...])` list in the entry
tab **without** adding a matching entry to `status_colors` in the chart tab
will silently fall back to the default blue rather than erroring; keep
these two lists in sync if you add a status.

`dependency` is currently a free-text field (task name string) with **no
validation, no cross-referencing, and no effect on the chart** — it's
metadata only, not a scheduling constraint. Don't assume changing a
predecessor task's dates cascades to dependents; it doesn't, and no code
path currently reads the `dependency` column at all. If asked to make
dependencies functional, that's new logic, not a bug fix.

## 10. Database schema quick reference

All tables live in one `SCHEMA` string in `db.py`. Foreign keys are
declared but **`PRAGMA foreign_keys = ON` is set per-connection** in
`get_conn()` — every new connection needs this pragma if you ever open
SQLite outside of `db.get_conn()` (e.g. in a script or test), or FK
constraints will silently not be enforced.

Relationships at a glance:
```
sites 1──* labor
sites 1──* material_ledger
sites 1──* equipment_hire
sites 1──* timeline_tasks
sites 1──* estimates
sites 1──* contracts
sites 1──* equipment (current_site_id)

vendors 1──* material_ledger (vendor_id, only meaningful for txn_type='IN')
vendors 1──* equipment_hire

clients 1──* quotations
clients 1──* contracts

labor 1──* attendance
labor 1──* advances
labor 1──* payroll

contracts 1──* bills   (running bill chain — see §6)

quotations 1──* quotation_items   (ON DELETE CASCADE)
estimates  1──* estimate_items    (ON DELETE CASCADE)
bills      1──* bill_items        (ON DELETE CASCADE)
```

Only the three `*_items` child tables have `ON DELETE CASCADE`. Everything
else relies on the app-level `delete_*` methods to manually clean up
children (see `DocumentFrame.delete_header`, which manually deletes items
before the header) — `CrudFrame.delete_selected` does **not** do this for
any table, which is the same gap noted in §4.

## 11. Conventions to follow when extending

- **Dates are plain `TEXT` in `YYYY-MM-DD`**, validated ad hoc with
  `datetime.strptime` wrapped in `try/except`, never with a date picker
  widget. Keep this format if you add date fields — other code (payroll
  month/year range queries, hire/duration calculators) assumes it.
- **Money/qty are `REAL` (float)**, not `Decimal` — acceptable for this
  app's scale, but be aware of float rounding if you add anything that
  compares totals for equality.
- **No ORM.** All queries are raw SQL strings via `sqlite3.Row`-returning
  connections (`conn.row_factory = sqlite3.Row` in `db.get_conn()`), so
  results are indexable by column name (`row['name']`) as well as by
  position. Keep using this style; don't introduce an ORM without asking.
- **String-built SQL uses only trusted, hardcoded table/column names**
  (never user input) interpolated via f-strings in `CrudFrame`/
  `DocumentFrame`; actual **values** always go through parameterized `?`
  placeholders. Preserve this split — never f-string a user-supplied value
  directly into a query.
- **Every tab module exposes either a `build_*_tab(parent, db_getter)`
  function returning a widget, or a class taking `(parent, db_getter)`
  and subclassing `ttk.Frame`.** `main.py` only ever calls one of these two
  patterns via `nb.add(widget_or_builder(nb, db.get_conn), text='...')`.
  Match this signature for anything new so it plugs into `main.py` the same
  way.
- `db.get_conn` is passed around as `db_getter` (a callable, not a live
  connection) because every operation opens a fresh short-lived connection
  and closes it — there is no long-lived shared connection or connection
  pool. Don't hold a connection open across GUI callbacks.

## 12. Known gaps / things an agent should flag rather than silently "fix"

These are intentional scope cuts from the original build, not accidents —
mention them to the user before changing behavior, since "fixing" them is a
feature request, not a bug fix:
- No authentication/multi-user support.
- No PDF/print export for quotations, estimates, or bills.
- No cascade-delete handling in `CrudFrame` (§4/§10).
- No retroactive recompute of prior bills' `previous_billed` when a later
  bill's status changes (§6).
- No regenerate/delete affordance for payroll rows (§7).
- `dependency` field in timeline tasks is inert metadata (§9).
- No automated tests.
