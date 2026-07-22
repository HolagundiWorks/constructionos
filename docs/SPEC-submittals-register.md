# Spec — Submittals Register (document control)

**Implementation-ready specification. Report only — no code in this document.**
_Written 2026-07-21 against `main` @ `7335f2a`. Closes the one document-control
gap left open by `docs/REPORT-sop-gap-analysis.md` (§ Remaining) and tracked in
`docs/ROADMAP.md` Phase 8 › Remaining open items._

---

## 1. Why (and why it's distinct)

A **submittal** is the contractor saying, before ordering/installing:
_"here is the specific material, make, or shop drawing I intend to use — approve
it."_ The architect/engineer/PMC returns **Approved / Approved as noted /
Revise & resubmit / Rejected**. It is a *pre-execution quality gate*: building or
ordering ahead of approval is rework or a rejected material on site.

It must **not** be folded into the existing `rfis` table. The three
document-control artefacts are deliberately separate (research §2.6):

| Artefact | Question it answers | Exists today |
|---|---|---|
| **RFI** | "The documents are unclear/conflicting — what is correct?" | ✅ `rfis`, Sourcing › RFIs |
| **Drawing revision** | "Which drawing copy is current on site?" | ✅ `drawings`, Sourcing › Drawings |
| **Submittal** | "Is the material/make/shop-drawing I propose acceptable?" | ❌ **this spec** |

Conflating submittals with RFIs is a named cause of unpaid scope creep; keep the
table and the tab section separate.

## 2. Scope & audience

- **In scope:** a register of proposed materials/makes/shop drawings, their
  approval status and turnaround, per site/contract, printable.
- **Audience:** contractors doing **PMC / departmental / institutional** work
  with a formal approval chain. A jobbing contractor rarely needs it → this ships
  **behind the module toggle**, off-path, low priority.
- **Out of scope:** file/attachment storage (offline single-file app — record the
  reference, not the PDF); a multi-round revision *thread* (model resubmittals as
  a new row referencing the prior, see §4).

## 3. Placement

Add as a **fourth register** in the existing Sourcing tab, next to RFIs and
Drawings — it is the same "document control" family and the user already goes
there for RFIs.

- `tab_sourcing.py` › `build_sourcing_tab`: add
  `nb.add(build_submittals(nb, db_getter), text='Submittals')` after Drawings.
- Follows the same builder shape as `build_rfis` / `build_drawings`
  (a `CrudFrame` or the same lightweight register frame they use).

## 4. Data model

One table, mirroring the `rfis` conventions (status enum, dated fields, free-text
`remarks`). No child table — a resubmittal is a **new row** whose
`supersedes_id` points at the previous one (same pattern as drawing revisions
using `superseded`).

```
CREATE TABLE IF NOT EXISTS submittals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submittal_no TEXT,                       -- e.g. SUB/2026-27/001 (see §7)
    site_id INTEGER REFERENCES sites(id),
    contract_id INTEGER REFERENCES contracts(id),
    spec_ref TEXT,                           -- BOQ item / spec clause it satisfies
    title TEXT,                              -- "M30 admixture — make X"
    submittal_type TEXT DEFAULT 'Material',  -- Material / Make / Shop Drawing / Sample
    submitted_date TEXT,
    submitted_by TEXT,
    required_by TEXT,                        -- date approval is needed to hold programme
    status TEXT DEFAULT 'Submitted',
        -- Submitted / Approved / Approved as noted / Revise & resubmit / Rejected
    reviewer TEXT,                           -- architect / EIC / PMC
    reviewed_date TEXT,
    review_remarks TEXT,
    supersedes_id INTEGER REFERENCES submittals(id),  -- prior row on resubmit
    remarks TEXT
);
```

**Migration & index** (match the existing pattern):
- Table goes in the `SCHEMA` string beside `rfis`/`drawings` (Wave-4 block ~line
  609). It's a brand-new table, so `CREATE TABLE IF NOT EXISTS` in SCHEMA is
  enough — no `_ADD_COLUMNS` entry needed (that list is only for *columns added
  to existing* tables).
- Add an index in the tail block:
  `CREATE INDEX IF NOT EXISTS idx_submittals_status ON submittals(status);`

**Status lifecycle:**
`Submitted → {Approved | Approved as noted}` (proceed) ·
`Submitted → Revise & resubmit` (create a new row, set its `supersedes_id`) ·
`Submitted → Rejected` (stop). "Approved as noted" counts as approved for the
gate but flags that the reviewer added conditions.

## 5. Module registration (mirrors any new tab)

- `modules.SECTIONS_CATALOG`: no new top-level label needed — it lives *inside*
  the existing **Sourcing** module, so it inherits Sourcing's toggle. (If a
  separate toggle is wanted, add `'Submittals'` under `Purchases` and a
  `BUILDERS` entry; otherwise nothing to wire.)
- `i18n.py`: add a `'Submittals'` label (hi / hi_en) only if it becomes its own
  tab; as a Sourcing sub-tab the sub-tab text can stay English like the others.

## 6. Register view (UI)

Same look as RFIs/Drawings:
- **Columns:** No · Title · Type · Spec Ref · Submitted · Required By · Status ·
  Reviewer · Reviewed.
- **Row tags:** overdue (required_by past, still Submitted) → `theme.wash('bad')`;
  approved → `theme.wash('good')`; rejected → a warn wash. (Use `theme.wash`,
  never a hard-coded hex — the design-system guardrail test forbids new literals.)
- **Form fields:** all of the above; `status`, `submittal_type` as read-only
  combos; dates default via the low-typing `TODAY` convention.
- **Print / Export:** a submittals-status register via
  `bill_export.build_statement_html` + `report_open.save_and_open_html`, like
  the other Sourcing exports.

## 7. Numbering (optional, reuse existing)

If auto-numbering is wanted, reuse `numbering.next_number(existing, prefix,
date, width, fy_reset)` with a `SUB` prefix — the same helper the tax invoice
uses. Or leave `submittal_no` free-text like `rfi_no`. Recommend free-text to
start (matches RFIs); add the series later if a user asks.

## 8. Dashboard / KPI hook (small, high-value)

Mirror the existing **"RFIs awaiting an answer"** advisory (`dashboard.py`
~line 278–370):

- In `dashboard.collect`, add:
  - `s['submittals_open']` = count `WHERE status = 'Submitted'`
  - `s['submittals_overdue']` = count where `required_by < today` and still
    `Submitted` (reuse `ageing.days_between`).
- Add an advisory row: _"Submittals awaiting approval (N, M overdue)"_ →
  verdict `watch` (or `act` if any overdue), linking **Purchases › Sourcing**.
- Overdue submittals also belong in the **per-project drill-down** alongside open
  RFIs/NCRs (the v1.0 project drill-down already lists those — add submittals to
  that query).

## 9. Tests (match `tests/test_core.py` style)

- **Schema:** `init_db` creates `submittals`; every column referenced by the tab
  spec exists (the web/masters tests already assert this pattern).
- **Lifecycle (pure, if a helper is extracted):** if a `submittals.py` pure
  module is added (e.g. `is_open(status)`, `is_overdue(required_by, status,
  as_on)`, `next_on_resubmit(...)`), unit-test those with `python -c` / unittest
  — no DB, matching the pure-module convention. Otherwise test at the DB level.
- **Smoke:** the Sourcing tab still builds with the new sub-tab (headless stub).
- **Guardrail:** no new `foreground='#…'` literal (design-system test).

## 10. Effort & sequencing

- **Effort: S–M.** One table + one register frame cloned from `build_rfis` + a
  small dashboard hook. No new pure maths required (optional tiny helper).
- **Priority: P2 / low.** Not a money leak; matters only for formal-approval
  contracts. Ship behind the Sourcing module toggle.
- **Definition of done:** table + Sourcing › Submittals register (CRUD + status +
  print) + overdue advisory + project-drilldown line + tests green + a
  `docs/CHANGELOG.md` entry; flip the ⏳ in `ROADMAP.md` Phase 8 › Remaining.

## 11. Explicitly NOT doing

- No attachment/file store (offline single-file thesis).
- No merge into `rfis` (keeps the scope-creep confusion out).
- No approval *workflow engine* — a status field + reviewer/date is enough for
  this audience; the app already has `approvals` for gated sign-offs if a formal
  gate is later wanted.
