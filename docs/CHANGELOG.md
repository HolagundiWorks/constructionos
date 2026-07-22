# Changelog — Construction OS

Notable changes, newest first. Dates are `YYYY-MM-DD`. This log records *what*
changed and *where* it lives; `docs/ROADMAP.md` tracks the phase status and
`AGENTS.md` §23 documents the architecture of the later modules.

---

## 2026-07-22 — Browser / LAN access: RA bills + more registers

- **RA bills in the browser** — record a running-account bill's value and the
  CPWA **Form-26 recoveries** (security deposit, income-tax TDS, labour cess),
  reusing the desktop's pure `civil.ra_bill_totals` so both compute identical
  retention/TDS/cess/net, then posts via `journal_post.post_all`. The detailed
  Measurement Book (per-item measurements, part-rates, printed Form 23/26) stays
  on the desktop. Verified: SD 2.5% / TDS 2% / cess 1% on ₹1,00,000 → 2500 /
  2000 / 1000, net 94,500, cumulative 1,50,000, and a balanced `RABill` entry.
- **Three more editable registers** — Projects, Milestones and the Rate Book now
  add/edit/delete in the browser (same drift-guarded `web_masters` path).

---

## 2026-07-22 — Browser / LAN access: money documents that post (Stage 3b)

- **Record money in the browser** — payments, tax invoices, vendor invoices and
  running bills. Each writes the document with the *same* derived amounts the
  desktop computes (GST, TDS, net payable, retention, incremental bill value),
  then posts through the shared, idempotent `journal_post.post_all`, so the
  double entry is produced by `posting.py`'s rules and never re-implemented.
- Create + view only (records of fact). Posting is state-gated — a **Draft** bill
  saves without posting; every posted entry balances (verified: payment 5000,
  tax invoice 118000 incl. +18% GST, vendor invoice 59000 / net 58000, running
  bill 150000 with retention 7500 / net 142500). Gated on role + session CSRF;
  a posting hiccup is swallowed so it never loses the saved document.
- `web_docs.py` (tkinter-free specs + `compute()` per document); `webapp.py`
  `_doc_create` route + `_can_create`; `webserver.py` keeps blank POST values.
  This completes the browser money-entry parity except the measurement-book RA
  workflow, which stays on the desktop.

---

## 2026-07-21 — Rate Realisation: the lessons-learned loop

- **Feed what things actually cost back into the rate library.** A new **Rate
  Realisation** view (Billing › Rate Book, second sub-tab) puts each material's
  **achieved** purchase rate next to its **standard/reference** rate. The
  achieved rate is *quantity-weighted* from the goods-received ledger — a
  500-bag order at ₹402 outweighs a 5-bag top-up at ₹450 — so it reflects what
  the job really paid, not a plain average.
- **One click closes the loop.** "Apply Achieved → Standard" (per-selection or
  all-drifted) rewrites `materials.rate`, which flows into estimates, rate
  analysis and the material budget — so the next estimate is priced on reality.
  Scope is a single finished site (a job's lessons at closeout) or all sites (a
  periodic refresh).
- **Honest by construction.** Nothing auto-applies; the number of purchases
  behind each achieved rate is shown so a one-off spike can't silently reset a
  good standard, a material with no purchase history is skipped (no-data, not a
  zero), and a **Viewer cannot apply**. Pure maths in `lessons.py`
  (`weighted_rate`, `realise`), UI in `tab_lessons.py`; 7 new tests (weighted
  average, over/under/no-data classification, and the admin-applies /
  viewer-blocked write-back).

---

## 2026-07-21 — Submittals register (document control)

- **The last document-control gap is closed.** A **submittal** — the
  pre-execution approval of a proposed material / make / shop drawing ("approve
  what I intend to use") — is now a register in **Purchases › Sourcing ›
  Submittals**, beside RFIs and drawing revisions. Deliberately a *separate*
  table from `rfis`: an RFI is a question about the documents, a submittal is a
  proposal for approval, and conflating them is a known cause of scope-creep
  confusion.
- Status lifecycle: Submitted → Approved / Approved as noted / Revise & resubmit
  / Rejected. A resubmittal is a new row whose `supersedes_id` cites the prior
  (traceability, informational — no self-FK, so a blank never breaks an insert).
- `submittals.py` (pure): `is_open` / `is_approved` / `is_overdue` — only an
  undecided submittal is open, and only an open one past its required-by date is
  overdue (a decided one is out of the reviewer's court). `dashboard.collect`
  counts open submittals and flags overdue ones with an **advisory** that goes
  `act` when any is overdue (else `watch`), mirroring the RFI advisory.
- Ships behind the existing Sourcing module toggle; mostly relevant to PMC /
  departmental work. Verified: schema applies clean, Sourcing tab builds
  headlessly, 7 new unit tests (pure lifecycle + a DB-backed dashboard count)
  pass, full suite green apart from the pre-existing real-display GUI smoke test.

---

## 2026-07-21 — Browser / LAN access: Estimates (Stage 3a)

- **Prepare a priced estimate in the browser** — header + line items, with
  add/remove line rows. The roll-up (subtotal → contingency → taxable → GST →
  grand total) reuses the *same* pure `estimate.estimate_totals` as the desktop,
  and the grand total is stored on save. Estimates never touch the ledger, so
  this stays clear of the double-entry engine (reserved for bills / RA bills).
- `webserver.py`/`webapp.py`: repeated form fields (`li_qty`, `li_rate`, …) are
  now kept as aligned per-row lists (`form_multi`, `keep_blank_values`), so a
  blank cell can't shift a column. Write routes generalised beyond the flat
  Masters (`_is_writable`, `_guard_write`); create/edit gated on role + session
  CSRF; edit replaces line items transactionally (no duplicates); web edits
  audit-logged. A tiny inline script adds/removes rows (no framework).
- The estimate record view shows the line items and the computed totals.

---

## 2026-07-21 — One HCW-UI design system for desktop + web (strict rule)

- **`tokens.py`** — a pure, tkinter-free single source of truth ported verbatim
  from the kit's authoritative `hcwux/src/tokens.ts`: Fog-Gray canvas, Pure-White
  cards, Coal-Black ink, the one Radiant-Orange accent (fills/active only; links
  are slate), and the shape law — square surfaces (0 radius), 4px buttons, 8px
  dialogs, 3px tab/nav alert rule. Both skins read from it.
- **Desktop** (`theme.py`) now sources its palettes from `tokens.py` (no value
  change — it already matched), and **24 tabs** had ad-hoc hex text colours
  (`#555`, `#8a5a00`, `#2e7d32` …) replaced with `theme.palette()[role]`, so
  every text colour flips correctly in dark mode.
- **Web** (`webrender.py`) CSS is now **generated from the same tokens** and
  corrected to the kit's shape: square cards/inputs/tables (was rounded), 4px
  buttons, 8px dialog cards, and a white **instrument rail** (was a dark
  sidebar) whose active row wears the 3px accent inset rule.
- Guardrails: tests lock the tokens to the kit's values, assert the web CSS
  carries the token values (can't drift from the desktop), and forbid any new
  ad-hoc `foreground='#…'` literal from re-entering the app.

---

## 2026-07-21 — Browser / LAN access: Masters data entry (Stage 2)

- **Add / edit / delete the Masters in the browser** — sites, clients, vendors,
  materials, labour, equipment. First write surface on the way to full parity
  (Billing → Money next).
- `web_masters.py`: a **tkinter-free** spec mirroring the desktop CRUD field-for-
  field (so the headless server needs no Tk import), plus value coercion matching
  `CrudFrame._collect_values` (number→float, fk→id, combo whitelist). A
  `tests/test_web.py` guard checks every field is a real column and every fk
  query runs — the web spec can't silently drift from the schema.
- `webapp.py` write routes: `/t/<m>/new`, `/t/<m>/<id>/edit`, `/t/<m>/<id>/delete`,
  gated on `can_write(role)` (Viewer → 403) with a **per-session CSRF token** on
  every form; delete catches `IntegrityError` (won't orphan linked rows) and web
  edits hit the same audit log (`web_create`/`web_update`/`web_delete`).
- `webrender.py`: form controls (text/number/combo/fk/textarea), error list, and
  a POST-only delete button.

---

## 2026-07-21 — Browser / LAN access

- **Use the app in a browser, no client install.** A built-in web server
  (`http.server`, still pure standard library — no web framework, no pip) serves
  Construction OS over the office LAN at `http://<host>:<port>`. It shares the
  **same SQLite file** and business logic as the desktop; `db.get_conn`'s
  per-request WAL connections make concurrent browser readers safe.
- **Login required, roles reused.** The web layer always authenticates against
  the desktop `auth` accounts (PBKDF2, lockout, audit log); the first visit
  bootstraps the admin. Viewers are read-only. The `users` table (hashes) and
  app config are never browsable; CSRF-guarded login, `HttpOnly`/`SameSite=Lax`
  cookies.
- **This turn:** the foundation + all **read views** (dashboard KPIs/advisories/
  bottlenecks/decisions, and every register with search, pagination and a record
  view). Write flows are staged next (Masters → Billing → Money) toward full
  read/write parity.
- Files: `webserver.py` (server + start/stop lifecycle), `webapp.py`
  (`handle(request)→response`, socket-free/testable), `webrender.py` (HCW-styled,
  theme-aware, responsive HTML), `netinfo.py` (LAN URLs), `web_main.py` (headless
  `--host/--port`). Launcher in **Tools › Web / LAN access**. See `docs/LAN.md`.

---

## 2026-07-21 — Takeoff + inbuilt offline AI

- **Bluebeam-style quantity takeoff.** Measure straight off a scaled drawing:
  calibrate the scale once, then run a polyline for length, a polygon for area
  (× depth for volume), or click-count. Live quantities, totals by unit,
  save/load, and **Send to Estimate**. Pure engine `takeoff.py` (shoelace area,
  polyline length, scale-from-calibration); `pdf_render.py` renders a PDF page to
  PNG via an external poppler/Ghostscript when present (tkinter shows PNG, not
  PDF); `tab_takeoff.py` is the Canvas markup UI under **Billing**;
  `takeoffs`/`takeoff_items` tables.
- **Inbuilt offline AI model.** The assistant's default is now
  **`qwen2.5-coder:1.5b`** — tuned for its NL→SQL, ~1 GB, Apache-2.0. The
  installer can bundle it (run `installer\fetch_payload.ps1` first): Ollama
  installs silently and the model GGUF is laid beside the app, registered offline
  by a one-time in-app `ollama create` (`model_provision.py`, wired into
  **Assistant › AI Engine**). Result: the assistant runs with no internet, out of
  the box. Lean builds without the payload still pull a model on first use.

---

## 2026-07-21 — v1.0.0: intelligent dashboard, HCW UI, production hardening

The 1.0 release. Everything below stays pure standard library (tkinter +
sqlite3), no pip.

- **UI — HCW rail + stage.** Replaced the top tab-bar with a left rail (identity,
  pictogram nav, settings at the foot) and a work stage, on the HolagundiWorks
  design kit. Added a **light / dark** toggle — including a dark-mode logo, the
  black artwork lifted to near-white by a stdlib PNG tinter
  (`tools/logo_tint.py`) — pill-switch module toggles, sub-tab pictograms, and a
  theme-wide semantic colour system (`theme.wash`) so status rows read right in
  both schemes.
- **Intelligent home dashboard.** KPI band + a rule-based **advisory** engine
  (`advisory.py`) that ranks actions with an honest **confidence**, a
  **bottlenecks** scoreboard and a **decisions-pending** queue, all from
  `dashboard.collect`. On-device and explainable; no model required.
- **Project Management** as its own section (Projects + Timeline + Look-ahead),
  with a per-project **drill-down** (cost/margin, programme slip + LD, retention,
  open snags / RFIs / NCRs). Operations slimmed to daily execution.
- **CPWD reference library** (`refdata.py`) — standard civil items, current
  material rates and consumption norms (the material split for concrete,
  masonry, plastering …); a **rate-book picker** wires those into Estimates and
  BOQ. **Load Sample Data** (`sampledata.py`) seeds a realistic demo book.
- **Security hardening.** Versioned PBKDF2 password hashes (600k iterations,
  transparently upgraded on login; legacy hashes still verify), a
  password ≠ username guard, and an audit confirming no SQL-injection surface
  (all interpolation is hardcoded identifiers; the LLM's SQL is `query_only`).
- **Licensing & docs.** Released under **AGPL-3.0** (`LICENSE`); rewrote the
  README for GitHub; added `docs/TEST_PLAN.md`.
- **Tests.** A real suite now: `tests/test_core.py` (pure maths + posting +
  security) and `tests/test_smoke_tabs.py` (builds every tab on the sample book,
  both themes). 454 tests.

## 2026-07-19 — Backlog completion (autopilot pass)

Completed the remaining planned (⏳) items across every roadmap phase. All new
business maths lives in pure, `python -c`-testable modules; all 31 tabs build
clean. Founding constraints unchanged (Python stdlib only, tkinter, single
SQLite file, no pip).

### Phase 2 — Get paid & submit (now ✅)
- **Print / Export on every document** — `report_open.save_and_open_html`
  helper; DocumentFrame "Print / Export" (quotations, POs) and a vendor-invoice
  export with GST/TDS breakup.
- **Configurable invoice number series** — `numbering.py` (Indian financial
  year, prefix + FY-reset formatting, next-serial by scanning numbers in use);
  tax-invoice auto-numbering honours it (e.g. `INV/2026-27/001`). Config in
  Tools → Invoice Number Series.
- **Rate Book / Specification library** — `rate_book` table + master under
  Billing (schedule of standard priced items with specs).
- **PWD deviation statement** — `civil.deviation` + a Deviation view in
  BOQ / RA Bills (tendered vs executed → excess/saving).

### Phase 3 — Labour (now ✅)
- **Optional PF / ESI / labour-cess** — `statutory.py` (EPF, ESI split, BOCW
  cess); optional `pf_no`/`esi_no` on the labour master; a standalone
  "Statutory" calculator under Muster & Wages. Nothing auto-deducts.

### Phase 4 — Trust & ease (now ✅)
- **First-run setup wizard** (`tab_wizard.py`) — firm details + first site +
  first client, shown once on a fresh book.
- **Guided low-typing entry** — `CrudFrame`/`Field` `default=TODAY` and
  `remember=True`: dates prefill today, Site (etc.) remembers the last choice
  per table+column. Applied across the ops tabs.
- **Vernacular UI** (`i18n.py`) — Hindi/Hinglish navigation labels with English
  fallback; language toggle in Tools.
- **App-wide error safety net** (`errors.py`) — a Tk `report_callback_exception`
  handler turns any uncaught callback error into a plain-language dialog (full
  traceback still logged). No stack trace ever reaches the user.

### Phase 5 — Compliance (now ✅)
- **RA / running bills in Output GST** — outward GST now spans tax invoices +
  RA + running bills (works-contract supply at a configurable Works GST %), with
  a Source column so RA-only billers are covered.
- **HSN-wise summary** — GSTR-1-style HSN/SAC taxable + CGST/SGST/IGST.

### Phase 6 — Insight (now ✅)
- **Receivable / payable ageing** (`ageing.py`) — FIFO-settle dated bills by
  receipts/payments, bucket the remainder 0-30/30-60/60-90/90+.
- **Contract / BOQ progress %** and **material budget vs actual** (value)
  (`analytics.py`).

### Phase 7 — Advanced (✅)
- **P&L + Balance Sheet** on the posted ledger (`reports.py`) in Accounting.
- **Payroll & subcontractor auto-posting** — `posting.payroll_lines`,
  `posting.sub_bill_lines`, and new `journal_post` loops (idempotent).
- **Subcontractor / work-order billing** — `subcontract.py`, tables
  `work_orders` (+items) and `sub_bills`, and `tab_subcontract.py` (work orders +
  sub running bills with retention & works-contract TDS).

### Assistant
- Schema docs + few-shot examples extended to the new modules (subcontractors,
  work orders, rate book, BOQ); results render a monospace **bar chart** for
  (label, number) answers (`assistant.text_bar_chart`).

### Schema additions
- Tables: `work_orders`, `work_order_items`, `sub_bills`, `rate_book`.
- Columns: `materials.rate`, `labor.pf_no`, `labor.esi_no` (idempotent
  migrations in `db._ADD_COLUMNS`).
- `app_settings` config keys: `works_gst_pct`, `invoice_prefix` /
  `invoice_width` / `invoice_fy_reset`, `language`, `setup_done`, and
  `last:<table>:<column>` remember-last values.

### New modules (all pure unless noted)
`report_open.py` (DB/tk helper), `numbering.py`, `ageing.py`, `analytics.py`,
`reports.py`, `subcontract.py`, `statutory.py`, `i18n.py`, `errors.py` (tk),
`tab_subcontract.py`, `tab_statutory.py`, `tab_wizard.py`.
