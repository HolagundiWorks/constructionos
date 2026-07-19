# Construction OS — Roadmap

_Last updated: 2026-07-19 (every item re-audited against the code)_

Audience: **small civil contractors in tier-2 / tier-3 Indian cities** (see
`PRODUCT.md`). Every phase is judged by one question: _does this help a solo
contractor bill, get paid, pay, and stay in control — offline, on their own PC,
with minimal typing?_

Legend: ✅ done · 🚧 in progress · ⏳ planned. Phases are ordered by value to the
target user, not by technical convenience. We ship phase by phase; each phase is
independently useful.

---

## Phase 0 — Foundation ✅ (built)

The operational and document backbone.

- ✅ Masters: sites/warehouses, clients, vendors, materials, labour, equipment.
- ✅ Operations: material ledger + stock, attendance, advances, payroll,
  equipment hire, timeline/Gantt.
- ✅ Commercial: quotations, estimates, contracts, running bills + printable
  bill export.
- ✅ Procurement: purchase orders, vendor invoices (GST/TDS), PO↔invoice
  reconciliation.
- ✅ Civil billing spine: BOQ → Measurement Book → RA bills + RA abstract export.
- ✅ Site & quality: consumption reconciliation, DPR, cube/material tests, plant
  log.
- ✅ Finance foundation: GST/TDS maths, chart of accounts, double-entry journal,
  trial balance (repositioned as _advanced / for-the-CA_ — see Phase 7).
- ✅ Pure, testable cores: `finance.py`, `civil.py`, `bill_export.py`.

---

## Phase 1 — Money that matters ✅ (built)

The cash-first heart. This is what an owner-contractor opens the app for.

- ✅ **Payments & Receipts** — one screen to record money **in** (from clients)
  and **out** (to vendors/labour), by mode (Cash/Bank/UPI/Cheque), optionally
  against a site. (`payments` table, `tab_money.py`.)
- ✅ **Party balances** — per client, vendor, or labour: what was billed/invoiced,
  what was paid/received, and the **running balance** ("baaki"). The two-click
  answer to "who owes whom".
- ✅ **Cash / Day book** — dated cash in/out with a **running balance** and an
  optional opening balance and site filter. The digital bahi-khata.
- ✅ **Home dashboard** — a plain-language landing screen (`tab_home.py`): cash in
  hand, receivables, payables, active sites, this month's billing & collection.
- ✅ `money.py` pure helpers (signed cash, running/closing balance, party
  outstanding).

_Follow-ups deferred to later phases:_ record a payment **against** a specific
bill/invoice (link exists in schema, no UI yet); reconciled — not
cash-vs-billed-approximate — receivables/payables.

_Repositioning note:_ the double-entry Accounting tab stays but moves behind the
cash-first views; the contractor never needs the journal to run the business.

---

## Phase 2 — Get paid & submit 🚧 (in progress)

Contractors live and die by the **printed bill they hand over**.

- ✅ **GST tax invoice** for clients — CGST/SGST/IGST breakup, HSN/SAC, amount
  in words, printable (`tab_tax_invoice.py`, `bill_export.build_tax_invoice_html`).
- ✅ **Amount-in-words** (Indian lakh/crore) helper (`numwords.py`).
- ✅ **Party statement + cash book** print/HTML export
  (`bill_export.build_statement_html`).
- ✅ Save-to-folder + open-in-browser (print / Save-as-PDF) flow — offline,
  WhatsApp-attachable.
- ✅ Basic invoice **auto-numbering** (`INV-<serial>` when left blank) and a
  **Firm Details** settings panel (name/GSTIN/address) in the Tools tab.
- ✅ **Estimates** upgraded (ported from Construction-Billing-System): priced
  BOQ with contingency + GST → grand total, printable estimate document with
  amount in words (`tab_estimate.py`, `estimate.py`).
- ✅ Print/PDF for the remaining docs: quotation, PO (DocumentFrame "Print /
  Export"), and vendor invoice (with GST/TDS breakup) — all via
  `bill_export.build_statement_html` + `report_open.save_and_open_html`.
- ✅ Configurable invoice **number series** — prefix + width + financial-year
  reset (e.g. `INV/2026-27/001`), settings in Tools (`numbering.py`,
  `tab_tax_invoice._next_invoice_number`).
- ✅ **Company logo** on every printed document (`assets.py`, embedded as a
  data-URI letterhead by `bill_export`).
- 🚧 Further CBS features — branded proposal/contract documents are partial
  (firm letterhead + logo on the generic statement builder, but no dedicated
  proposal/contract template). **Specification library** and **Rate Books**
  are not built.
- ✅ Department-friendly **RA bill formats** — PWD-style abstract with tender
  quantities, upto-date amounts, memorandum of payments and signature block
  (`bill_export.build_ra_pwd_html`); **deviation statement** (tender vs
  executed qty per item, `civil.deviation_row`); **part-rate** on draft RA
  bill items with automatic re-roll of the payable figures (`tab_boq_ra.py`).

---

## Phase 3 — Labour reality ✅ (built)

How T2/T3 sites actually run: daily muster, weekly payout, thekedars.

- ✅ **Muster roll** — per-site daily grid, mark P/A/½/OT (individually or all),
  writes one attendance row per labourer per day (`tab_muster.py`).
- ✅ **Weekly wage payout** — computed from the muster, advances deducted,
  printable payout sheet, and one-click "Record as Payments" into the cash book.
- ✅ **Thekedar / labour-contractor ledger** — master + Work/Paid running
  balance, printable.
- ✅ Auto-recover advances (mark `advances.recovered`, FIFO, close when fully
  recovered) when a payout deducts them; "Record as Payments" is now idempotent
  (skips a labourer's week already recorded).
- ✅ Optional PF/ESI/labour-cess — a **Statutory** calculator sub-tab with
  editable rates/ceilings (`statutory.py`, `tab_statutory.py`). Deliberately
  opt-in: nothing is auto-deducted from a payout, since most T2/T3 labour is
  informal.

---

## Phase 4 — Trust & ease 🚧 (started early)

Adoption blockers for non-technical, single-PC users. Two essentials landed
early because they are pure trust wins:

- ✅ **Backup & restore** — one-click copy of the SQLite file to a chosen folder
  / USB, date-stamped; guarded restore that first makes a safety copy
  (`tab_tools.py`, Tools tab).
- ✅ **Fix the sharpest edge** — `CrudFrame` delete now catches
  `IntegrityError` and shows a plain-language dialog instead of a stack trace
  (AGENTS.md §4).
- ✅ **Vernacular UI** — English / Hindi / Hinglish string table with a Tools
  language toggle, persisted in `app_settings.language` (`i18n.py`). Scope is
  the navigation layer (section and tab labels) by design.
- 🚧 **Guided, low-typing entry** — today's-date defaults and remembered
  last-used values are in `CrudFrame` (`Field(default=TODAY)`,
  `Field(remember=True)`) but only wired into 4 tabs; FK fields are
  dropdown-first. **Missing: inline "add new" for masters** — you still have
  to leave a document screen to create a client.
- 🚧 Audit the remaining error paths so **no stack trace ever reaches the
  user** — the sharpest edge (delete) is fixed and ~15 handlers exist, but 8
  tab modules still have no exception handling at all.
- ✅ First-run **setup wizard** — firm details + first site + first client,
  runs once via `app_settings.setup_done` (`tab_wizard.py`). Sample-data
  seeding is not included.

---

## Phase 5 — Compliance made simple ✅ (built, bar e-invoice readiness)

Enough to keep the contractor and their CA happy, no more.

- ✅ **GST summary** — Output GST (sales) and Input GST (purchases) registers +
  a net-position (3B-style) summary, month-filtered and printable
  (`tab_gst.py`, `finance.gst_summary`).
- ✅ **Input vs output GST** position (output tax − input credit → payable /
  carry-forward).
- ✅ **TDS register** — TDS deducted on vendor invoices, month-filtered.
- ✅ **Running bills / RA bills in the outward GST view** — Approved/Paid
  `bills` and `ra_bills` taxed at a configurable works GST %, with a Source
  column so they are not double-counted against tax invoices
  (`tab_gst.outward`).
- ✅ **HSN-wise summary** as its own tab (`tab_gst.hsn_summary`). Covers tax
  invoices only — RA/running bills carry no HSN.
- ⏳ e-invoice / e-way-bill field readiness (nothing captured yet; most T2/T3
  contractors are below the e-invoicing threshold).

---

## Phase 6 — Insight ✅ (built)

Simple, honest numbers — not exec dashboards.

- ✅ **Site-wise profitability** — revenue (Approved/Paid bills + RA bills) vs
  cost (material issued + labour cash paid + equipment hire), profit & margin %
  (`tab_insight.py`, `money.profit_margin`).
- ✅ **Receivables / Payables** — per client/vendor outstanding at a glance.
- ✅ **Receivable / payable ageing** — 0–30 / 30–60 / 60–90 / 90+ buckets
  (`ageing.py`, two Insight tabs). _Caveat:_ payments are still not linked to
  specific bills, so it applies the lump receipts total oldest-first (a FIFO
  approximation, not reconciled ageing) — see the Phase 1 follow-up.
- ✅ **Material budget vs actual** — estimate/BOQ vs consumed
  (`analytics.material_budget`).
- ✅ Contract/BOQ **progress %** (`analytics.contract_progress`; deliberately
  unclamped so over-run shows above 100%).

---

## Phase 7 — Advanced (optional, opt-in) ⏳

Power features that must never complicate the core.

- 🚧 **Auto-posting to double-entry** — an **"Auto-Post Documents"** action
  posts balanced journal entries for tax invoices, vendor invoices, payments,
  **subcontractor bills** and **payroll** (`posting.py` rules +
  `journal_post.post_all`, idempotent). **Remaining: running/RA bills** — they
  need a retention-receivable account. ⚠️ Until that lands, a contractor who
  bills only via RA bills sees **no revenue** in the P&L below, so treat those
  statements as incomplete for RA-billed work.
- ✅ **P&L / balance sheet** on the resulting ledger, with retained-earnings
  fold-in and a balanced tie-out check (`reports.py`, in the Accounting tab).
- ✅ **Subcontractor / work-order billing** — sub bills with retention,
  works-contract TDS and other deductions → net payable, printable
  (`subcontract.py`, `tab_subcontract.py`).
- ⏳ **Multi-year / multi-firm** files, optional cloud backup.

---

## Project management (added on request)

The missing project layer, now in its own **Projects** section.

- ✅ **Projects** (client + site + budget + dates + status) and **Milestones**
  (target/actual dates, payment-stage amount, done/pending).
- ✅ Timeline tasks link to a project (`timeline_tasks.project_id`).
- ✅ **Project Overview** dashboard: budget vs cost-to-date vs billed, margin,
  budget-used %, milestone progress, open tasks (`tab_projects.py`, `projman.py`).
- ⏳ Hard project↔transaction links (costs are site-scoped today); per-project
  Gantt filter; critical-path / dependency scheduling.

## AI Assistant (added on request)

Ask your own data in plain language — retrieval-augmented **text-to-SQL** over
the SQLite DB, generated by a **local Ollama** model (stdlib `urllib`, so no pip
dependency and localhost-only).

- ✅ Read-only by construction (`validate_sql` + `PRAGMA query_only`); schema
  docs + few-shot examples as the retrieval grounding (`assistant.py`).
- ✅ Deterministic **quick answers** (cash/receivables/payables/month billed)
  that work with **no LLM** — the offline floor.
- ✅ Model/host configured in Tools; graceful "start Ollama" status when absent.
- ⏳ Optional embeddings for larger schemas; conversational follow-ups; charts
  from results.

## Enterprise hardening (added on request)

Security & robustness suited to a single-PC offline app (not corporate SSO/cloud):

- ✅ **Optional login** — off by default; an office enables sign-in with user
  accounts, roles (Admin/Operator/Viewer), **PBKDF2** password hashing, account
  **lockout**, and an **audit log** (`security.py`, `auth.py`, `session.py`,
  Tools > Users & Security / Audit Log).
- ✅ **DB robustness** — WAL journaling, `busy_timeout`, enforced foreign keys.
- ✅ **Operations** — indexes on hot foreign keys for speed at scale.
- 🚧 Per-tab write/delete gating for Viewers — `ui_guard.can_write()` is
  enforced in CrudFrame, DocumentFrame and the bespoke **financial** tabs (12
  in all). ⚠️ **Still ungated: the masters/operations tabs** — Projects,
  Masters, Vendor, Warehouse, Consumption, Site Reports, Equipment Hire,
  Timeline, Statutory, GST and Insight. A Viewer can currently write there,
  so the read-only role is not yet fully enforced.
- ⏳ At-rest encryption — would need a native dependency (out of scope).

## True remaining backlog (audited against the code, 2026-07-19)

Every item above was re-verified against `construction_app/`. What is
genuinely **not built**, ordered by value to a small Indian civil contractor:

1. **Auto-post running/RA bills to the ledger** — the one hole that makes a
   *shipped* feature wrong: the P&L/balance sheet omits revenue entirely for
   an RA-billed contractor. Fix before anything else.
2. **Per-tab write gating for the 11 masters/operations tabs** — a Viewer can
   write today, against an advertised read-only role. A correctness bug, not
   a feature.
3. **Payments linked to a specific bill/invoice** — the schema link exists but
   has no UI. Root dependency: it turns ageing from a FIFO approximation into
   real reconciled receivables and answers "which bill is this ₹2L against?".
4. **Rate books** — a reusable priced-item library; the biggest typing
   reduction available, and directly serves the minimal-typing principle.
5. **Inline "add new" for masters** — the missing half of guided entry; being
   forced to leave a bill screen to create a client is a classic drop-off.
6. **Error-path audit** — 8 tab modules still have zero exception handling.
7. **Specification library** — useful for department work; follows rate books.
8. **Multi-year / multi-firm files** — matters at year-end; workaround exists
   (separate DB copies).
9. **e-invoice / e-way-bill readiness** — capture fields when a user actually
   crosses the threshold.
10. **Per-project Gantt filter + hard project↔transaction links** — workable
    today while most contractors run one project per site.

Considered low value for this audience and candidates for **cutting** rather
than carrying as debt: critical-path scheduling, assistant embeddings /
conversational follow-ups / charts, cloud backup, at-rest encryption.

## Cross-cutting, always-on

- Keep **pure stdlib / tkinter / single-SQLite / no-pip**.
- Keep business maths in **pure, testable modules**.
- Every new document gets a **print/PDF** path.
- Every new screen respects **minimal-typing** and **plain language**.
- Update `AGENTS.md` (architecture) and this roadmap as phases land.
