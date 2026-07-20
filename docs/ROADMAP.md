# Construction OS — Roadmap

_Last updated: 2026-07-19_

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
cash-vs-billed-approximate — receivables/payables. **This is now the highest-
value open item in the app:** the Phase 6 ageing report ships without it, so it
applies the lump receipts total oldest-first (a FIFO approximation). Until
payments are bill-linked, ageing buckets are indicative rather than reconciled.

_Repositioning note:_ the double-entry Accounting tab stays but moves behind the
cash-first views; the contractor never needs the journal to run the business.

---

## Phase 2 — Get paid & submit ✅ (built)

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
- ✅ Configurable invoice **number series** (prefix + financial-year reset) —
  `numbering.py` + Tools "Invoice Number Series"; tax-invoice auto-numbering
  honours it (e.g. `INV/2026-27/001`, restarting each April).
- ✅ **Rate Book / Specification library** — a schedule of standard priced items
  with specs (`rate_book`, Billing > Rate Book), reusable in estimates/BOQs.
- ✅ Department-friendly **RA bill formats** — PWD-style abstract with tender
  quantities, upto-date amounts, memorandum of payments and signature block
  (`bill_export.build_ra_pwd_html`); **part-rate** on draft RA bill items with
  automatic re-roll of the payable figures (`tab_boq_ra.py`); and a **deviation
  statement** (tender vs executed qty per item) both per-bill from the RA Bill
  frame (`civil.deviation_row`) and as a standalone contract-level tab
  (`civil.deviation`, BOQ / RA Bills > Deviation).
- ⏳ Branded proposal/contract documents.

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
- ✅ Optional PF/ESI/labour-cess (off the main flow — most are informal):
  `statutory.py` maths, optional PF/ESI No fields on the labour master, and a
  standalone "Statutory" calculator under Muster & Wages.

---

## Phase 4 — Trust & ease ✅ (built)

Adoption blockers for non-technical, single-PC users.

- ✅ **Backup & restore** — one-click copy of the SQLite file to a chosen folder
  / USB, date-stamped; guarded restore that first makes a safety copy
  (`tab_tools.py`, Tools tab).
- ✅ **Fix the sharpest edge** — `CrudFrame` delete now catches
  `IntegrityError` and shows a plain-language dialog instead of a stack trace
  (AGENTS.md §4).
- ✅ **Vernacular UI** — Hindi/Hinglish labels for the navigation layer via a
  string table (`i18n.py`) + language toggle in Tools; graceful English
  fallback for untranslated keys.
- ✅ **Guided, low-typing entry** — date fields default to today and Site (etc.)
  remembers the last selection, per table+column (`CrudFrame`/`Field` TODAY +
  remember).
- ✅ Audit the remaining error paths — an app-wide Tk `report_callback_exception`
  handler (`errors.py`) turns any uncaught callback error into a plain-language
  dialog, so **no stack trace ever reaches the user**.
- ✅ First-run **setup wizard** (`tab_wizard.py`) — firm details + first site +
  first client on a fresh book, shown once.

---

## Phase 5 — Compliance made simple ✅ (built)

Enough to keep the contractor and their CA happy, no more.

- ✅ **GST summary** — Output GST (sales) and Input GST (purchases) registers +
  a net-position (3B-style) summary, month-filtered and printable
  (`tab_gst.py`, `finance.gst_summary`).
- ✅ **Input vs output GST** position (output tax − input credit → payable /
  carry-forward).
- ✅ **TDS register** — TDS deducted on vendor invoices, month-filtered.
- ✅ **Running / RA bills in the outward GST view** — Output GST now spans tax
  invoices + RA + running bills (works-contract supply at a configurable
  Works GST %), with a Source column so RA-only billers are covered.
- ✅ **HSN-wise summary** (GSTR-1 style) of outward supplies by HSN/SAC.
- ⏳ e-invoice / e-way-bill field readiness (data captured now, integration
  later).

---

## Phase 6 — Insight ✅ (built)

Simple, honest numbers — not exec dashboards.

- ✅ **Site-wise profitability** — revenue (Approved/Paid bills + RA bills) vs
  cost (material issued + labour cash paid + equipment hire), profit & margin %
  (`tab_insight.py`, `money.profit_margin`).
- ✅ **Receivables / Payables** — per client/vendor outstanding at a glance.
- ✅ **Receivable / payable ageing** — 0–30 / 30–60 / 60–90 / 90+ buckets;
  bills FIFO-settled by receipts/payments then aged by date (`ageing.py`).
- ✅ **Material budget vs actual** (value) — theoretical consumption (norm ×
  work done) vs actual issued, valued at the material's standard rate
  (`analytics.material_budget`).
- ✅ Contract/BOQ **progress %** (measured value ÷ BOQ value,
  `analytics.contract_progress`).

---

## Phase 7 — Advanced (optional, opt-in) ✅ (built)

Power features that must never complicate the core.

- ✅ **Auto-posting to double-entry** — a **"Auto-Post Documents"** action posts
  balanced journal entries for tax invoices, vendor invoices, payments, **paid
  payroll**, **subcontractor bills**, and **running / RA bills** (`posting.py`
  rules + `journal_post.post_all`, idempotent). Client-withheld retention posts
  to a **Retention Receivable** asset (code 1400), created automatically on
  databases that predate it; running bills post only their incremental value
  (`work_done_value − previous_billed`). RA/running bills carry no tax columns,
  so the ledger holds the work value **excluding GST** — works-contract GST is
  presented in the GST view at a configurable rate.
- ✅ **P&L and Balance Sheet** built on the posted ledger (`reports.py`,
  Accounting > Profit & Loss / Balance Sheet), with a tie-out check.
- ✅ **Subcontractor / work-order billing** — work orders (+ items) and sub
  running bills with retention & works-contract TDS (`subcontract.py`,
  `tab_subcontract.py`); posts Dr Subcontractor Charges / Cr Retention + TDS +
  Payable.
- ✅ **Multi-year / multi-firm files** — a **Company Files** panel in Tools
  lists every data file, switches between them, registers an existing one, or
  creates a new one. **New Financial Year** carries the masters forward (sites,
  clients, vendors, materials, labour, equipment, thekedars, consumption norms,
  rate book, chart of accounts including custom heads, and firm settings) while
  bills, payments and the ledger start empty (`company.py`). The registry is a
  small JSON beside the code — it cannot live inside a company file, or you
  could never find the others. Switching asks for a restart, like Restore does.
- ✅ **Optional cloud backup** — remember your cloud drive's local folder
  (Google Drive / OneDrive / Dropbox) and back up to it in one click; the sync
  client does the upload. No network code, credentials, or new dependency.

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
- ✅ Schema/examples cover the newer modules (subcontractors, work orders, rate
  book, BOQ) and results render a monospace **bar chart** for (label, number)
  answers (`assistant.text_bar_chart`).
- ⏳ Optional embeddings for larger schemas; conversational follow-ups.

## Enterprise hardening (added on request)

Security & robustness suited to a single-PC offline app (not corporate SSO/cloud):

- ✅ **Optional login** — off by default; an office enables sign-in with user
  accounts, roles (Admin/Operator/Viewer), **PBKDF2** password hashing, account
  **lockout**, and an **audit log** (`security.py`, `auth.py`, `session.py`,
  Tools > Users & Security / Audit Log).
- ✅ **DB robustness** — WAL journaling, `busy_timeout`, enforced foreign keys.
- ✅ **Operations** — indexes on hot foreign keys for speed at scale.
- ✅ Per-tab write/delete gating for Viewers — `ui_guard.can_write()` is
  enforced in CrudFrame and DocumentFrame (so every master/operations tab
  built on them inherits it), in the bespoke financial tabs, and now in the
  settings and cash-opening saves that were genuinely exposed.
  _Correction:_ an earlier audit here claimed eleven masters/operations tabs
  were ungated. That was a false positive from grepping each module for
  `can_write` — those tabs are CrudFrame-based and were always covered. An
  AST scan of the real write paths found **seven** genuinely unguarded
  button actions: the six settings saves in Tools (firm details, invoice
  series, language, AI config, modules, backup folder) and the cash-book
  opening balance — a Viewer could change any of them. Also fixed: viewing
  an inspection persisted its derived result, so a read-only account caused
  a write. A source-level test now fails if a new unguarded write appears,
  with a justified exemption list for derived-value helpers.
- ⏳ At-rest encryption — would need a native dependency (out of scope).

## Phase 8 — SOP gap closure: turn records into gates 🚧

Driven by `docs/REPORT-sop-gap-analysis.md`, which compared the app against
construction-management SOP practice (`docs/RESEARCH-construction-management-sops.md`).
Phases 0–7 built the **ledger**; this phase makes the process **unskippable**.

The report's core finding: _"gate, don't hope."_ Most records already exist —
the leverage is in making the SOP step impossible to skip.

- No payment without a **GRN** (procurement).
- No extra work without an **approved variation** (revenue protection).
- No pour without a **QC hold-point** sign-off (quality).
- No sub work without a work order (already enforced ✅).

### Wave 1 — revenue & cash (P0, the three biggest leaks) ✅ complete

- ✅ **Variation / change-order register** — Billing > Variations. Per contract:
  description, reason, letter/email reference (the paper trail that makes a
  claim defensible), qty × rate, status Raised → Approved → Billed → Rejected,
  approver, and which bill recovered it. Amount is derived and `VO-n` is
  auto-numbered per contract from the highest serial, so deleting one cannot
  reissue a number. The **Position** view headlines *approved but not yet
  billed* — work the client has agreed to pay for that nobody has asked for —
  and shows the revised contract value; rejected claims never inflate a total
  (`variation.py`, `tab_variations.py`).
- ✅ **Payment ↔ bill/invoice allocation** — Money > Payments > *Allocate to
  Bills* splits a receipt across the documents it settles (`allocation.py`,
  `tab_allocate.py`, new `payment_allocations` table). Ageing now uses those
  allocations, falling back to oldest-first only for receipts still
  unallocated — so a part-migrated ledger keeps adding up and allocating
  nothing reproduces the old numbers exactly. This matters: a client paying
  the newest bill while disputing an old one looked, under FIFO, like a client
  with no aged debt. The allocation dialog and the ageing view share one
  document query so they can never disagree.
  _Note:_ receivables now include **tax invoices** as well as bills/RA bills.
  That closes a blind spot (a contractor billing only by tax invoice
  previously showed zero receivables), but if you raise both an RA bill and a
  tax invoice for the same work, that work will count twice — the same
  double-count caveat the GST view already carries.
- ✅ **Cash-flow forecast** — Money > Cash Flow (`cashflow.py`,
  `tab_cashflow.py`). Weekly or monthly buckets from cash in hand: open client
  bills as inflows, open vendor and subcontractor payables plus the weekly wage
  bill as outflows, both sides **lagged** by editable day counts because being
  paid on the due date is not how the trade works. It names **the first period
  the running balance goes negative** and tints those rows. Open positions come
  from the same allocation-aware query as the ageing view, and an overdue bill
  lands today rather than dropping out of the forecast; anything past the
  horizon folds into the last bucket so totals still reconcile.

### Wave 2 — procurement control (P0/P1) ✅ complete

- ✅ **Requisition → PO → GRN gate** — Purchases > Goods Receipt
  (`procurement.py`, `tab_grn.py`). A **requisition** records the site's
  written request; a **GRN** receives against a purchase order and, when
  *Posted*, writes the **accepted** quantity into the material ledger —
  rejected material never becomes stock, and ledger rows carry the GRN number
  so any stock entry traces back to its delivery. Posting is one-way and
  guarded: a posted GRN refuses to post or be edited again, because
  re-posting would double the stock. "Copy Items From PO" pulls in what is
  still outstanding across earlier receipts.
  The **3-Way Match** view compares ordered ↔ received ↔ invoiced per PO and
  headlines **over-invoiced** — value billed with no receipt behind it, the
  payment about to leave for goods that never arrived. Differences are judged
  against an editable tolerance, because deliveries never tally exactly and a
  report that cries wolf gets ignored.
- ✅ **Retention register + release / DLP tracking** — Money > Retention
  (`retention.py`, `tab_retention.py`). Retention never appears on an invoice,
  so it is the easiest money to forget. The register totals what **clients owe
  us** and what **we hold from subcontractors**, records part or full
  releases, and flags what is **past its defect-liability date and still
  unreleased** (with how many days overdue), plus a 60-day look-ahead so the
  claim can be raised before the date. The release date is completion + DLP in
  calendar months — clamped for short months — and a document with no
  completion date is shown as held *with that reason* rather than given an
  invented date.

### Wave 3 — quality & planning (P1) ✅ complete

- ✅ **ITP hold-points + NCR log** — Operations > Quality (`quality.py`,
  `tab_quality.py`). An ITP checklist per activity/stage marks each check
  **Hold** (work stops until signed off), **Witness** (engineer invited, does
  not block) or **Record**. An inspection loads that checklist and answers the
  only question that matters on site — **"may the work proceed?"** — which is
  not the same as "did anything fail": an *unanswered* Hold point blocks, since
  unrecorded is exactly how an inspection gets skipped. The inspection's result
  is derived from its lines, never typed, so it cannot contradict the evidence.
  A failed check raises a pre-filled **NCR** with root cause, corrective and
  preventive action; the log headlines how long the oldest open one has sat.
- ✅ **Weekly look-ahead + Percent Plan Complete** — Operations > Look-ahead
  (`planning.py`, `tab_planning.py`). Record what the site *promises* for the
  week, then score it. PPC is **binary** — a part-finished task is a miss,
  because counting it as progress is how a programme slips while every line
  looks busy. The score says the plan was unreliable; the **ranked reasons for
  misses** say why, and that is the half that changes anything.
- ✅ **Cost-Value Reconciliation** — cost incurred vs value earned per head
  (material issued, labour paid, plant hire, subcontract) against approved
  billing, worst head first. Value is apportioned across heads by their share
  of cost — the standard CVR simplification, stated on screen rather than
  implied to be measured.
- ✅ **Approval gates** — Money > Approvals (`approval.py`, `tab_approvals.py`).
  One queue for everything sitting in draft: estimates, purchase orders,
  running and RA bills, subcontractor bills and variations, with their value.
  Approving advances the document's own status **and** writes an approval row
  recording who and when, plus an audit entry — a status anyone can change was
  never evidence, and that pairing is the whole point. Rejecting records the
  decision and leaves the document in place, because a rejected bill is sent
  back, not deleted. Deliberately a **single step, not a chain** — multi-level
  approval is an explicit non-goal for a contractor who is also the approver.
- ✅ **KPI dashboard** — Money > Key Numbers (`tab_kpi.py`). Unbilled
  variations, invoiced-without-a-receipt, % spend under PO, receivables and
  the 90+ slab, retention due for release, PPC and its biggest cause of
  misses, first-time-pass % and open NCRs — each with a **verdict** (good /
  watch / act) so the screen is read rather than interpreted, and a headline
  count of what needs an action today. Where there is no data a KPI says so
  instead of showing a confident zero, because "0%" and "nothing recorded
  yet" mean very different things.

### Wave 4 — completeness (P2, lower urgency at this scale)

- ⏳ RFI + drawing-revision register (mainly PMC/departmental work).
- ⏳ HSE module (induction, toolbox, permit, incident) — often informal here.
- ⏳ Closeout: snag list, lessons-learned feeding the rate library.
- ⏳ Vendor depth (3 quotes, approved-vendor list, rating); plant PM + fuel log;
  compliance calendar; bid/no-bid scorecard; baseline-vs-actual programme.

**Explicit non-goals** (protecting the founding thesis): BIM, IoT/drones,
predictive analytics beyond the local assistant, heavy multi-user cloud sync,
corporate multi-level approval chains. These are Level-4 features that add cost
and friction without helping a solo contractor bill, get paid, and stay in
control.

---

## Cross-cutting, always-on

- Keep **pure stdlib / tkinter / single-SQLite / no-pip**.
- Keep business maths in **pure, testable modules**.
- Every new document gets a **print/PDF** path.
- Every new screen respects **minimal-typing** and **plain language**.
- Update `AGENTS.md` (architecture) and this roadmap as phases land.
