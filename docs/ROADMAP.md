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
- ✅ **Branded proposal / contract documents** (`firm.py`, shared
  `bill_export.letterhead_html` / `bank_block_html`). Only the GST tax invoice
  ever carried the firm's identity; every other document — quotations,
  contracts, purchase orders, work orders — showed a bare company name. Now a
  shared letterhead (logo, name, address, GSTIN, phone, email) sits on all of
  them, and any document that asks for money carries a **bank block** to pay
  into. Firm details gained phone, email and bank fields, entered once in
  Tools.

  Two deliberate small rules. A letterhead line with no value is **dropped,
  not printed blank** — an empty "GSTIN:" on an unregistered firm reads as a
  mistake. And the bank block needs **both account and IFSC** or it renders
  nothing, because a half-filled payment instruction is worse than none:
  someone will try to use it.

  The change is backward-compatible by construction. `build_statement_html`
  gained an optional `firm` argument; the ~20 internal reports that pass none
  render exactly as before (bare name, no letterhead, no bank block), so only
  the outward-facing documents were opted in. The settings panel and the
  letterhead reader are both driven from `firm.FIELDS`, with a test asserting
  they cannot list different things.

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
- ✅ **e-invoice / e-way-bill field readiness** (`einvoice.py`, fields on the
  tax invoice + the printed invoice). Above a turnover threshold, or for goods
  moving beyond a value, e-invoicing and e-way bills are mandatory — but
  *generating* them needs a live call to the government portal, which an
  offline app cannot make. What it can do is hold the fields the portal gives
  back (IRN, acknowledgement, e-way-bill number, transporter, vehicle), check
  they are the right *shape*, and print them where a compliant invoice must
  show them.

  Two things it deliberately does **not** do. It does not decide whether
  e-invoicing or an e-way bill is *required* — that turns on turnover and on
  whether the supply is goods or a service, and a works contract is a service
  (SAC) that often needs no e-way bill at all. Nagging a service-only firm
  trains it to ignore the app; telling a goods supplier it is fine when it is
  not is a fine waiting to happen. So the checks are about shape (IRN is 64
  hex, e-way is 12 digits, vehicle looks like a plate) and the readiness report
  is about what is *present*, never what is *owed* — with a test asserting the
  module contains no notion of "required", "mandatory", "threshold" or
  "penalty".

  And it does not fabricate the QR code: a real e-invoice QR encodes the
  portal's signed payload, which cannot be reproduced offline, so the invoice
  prints the IRN rather than a QR that would not verify. The e-invoice / e-way
  panel appears on the printed invoice only when the fields are actually filled
  in.

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

- ✅ **RFI + drawing-revision register** — Purchases > Sourcing
  (`tab_sourcing.py`). RFIs record the question and the date it was asked: an
  unanswered RFI is a delay with someone else's name on it, which matters when
  the delay is eventually priced. The drawing register tracks revisions and
  which copy is on site — building to a superseded drawing is rework nobody
  planned for.
- ✅ **HSE register** — Operations > Safety (`hse.py`, `tab_hse.py`). Permits
  to work, incidents (including near misses), toolbox talks and inductions,
  plus a Position summary. Deliberately small: safety paperwork that takes
  long gets abandoned, and an abandoned register is worse than none because it
  looks like a record. A permit is marked **valid or expired** — an expired
  permit is not a lesser permit, it is no permit — with a 2-day expiry warning
  so it can be renewed before work stops. **LTIFR** is reported per 200,000
  hours but returns *n/a* below 10,000 hours worked, because one injury in a
  fortnight produces a rate that looks catastrophic and means nothing. The
  **near-miss ratio** is shown for a non-obvious reason: a site reporting no
  near misses is almost never a safe site, it is one where nobody writes them
  down.
- ✅ **Closeout: snag list + handover readiness** — Operations > Closeout
  (`closeout.py`, `tab_closeout.py`). The punch list per site, then a
  readiness view: what proportion is verified, what is overdue, which trades
  are holding it up, and a plain answer to *can this be handed over?*
  **Verified counts, Fixed does not** — Fixed is the contractor's claim,
  Verified is the client agreeing, and only the second one ends the argument.
  A Blocker stops handover on its own; a Fixed-but-unverified snag does not,
  since waiting on the client's walk-round is scheduling rather than a defect.
  This matters beyond tidiness: handover starts the DLP clock, and the DLP is
  what releases retention — a drifting punch list is retention left
  uncollected. _(Lessons-learned feeding the rate library remains.)_
- ✅ **Vendor depth** — Purchases > Sourcing (`sourcing.py`). Quotes recorded
  against a requisition and compared, showing the **saving against the highest
  quote** (what justifies bothering) and the spread. The cheapest is a
  *recommendation with reasoning*, not a silent auto-pick: where it cannot
  meet the required date the next one that can is recommended instead, because
  late material costs more in idle labour than the price difference. Plus an
  approved-vendor flag and a three-factor rating (quality / delivery / price)
  — three because a ten-factor scorecard for eleven suppliers is a form nobody
  fills in twice. Unrated vendors sort last rather than being assumed poor.
- ✅ **Statutory compliance calendar** (`compliance.py`, new Compliance tab
  under Accounts, feeding two KPIs). Every other deadline in this app is money
  the contractor is *owed*; these are the ones where being late costs them
  directly — late fees per day, interest on unpaid tax, and a late GSTR-1 that
  holds up the customer's input credit. Nobody sends a reminder, and a firm
  without a full-time accountant finds out from a notice.

  Generates a financial year's filings from a rule table for whichever regimes
  the firm ticks — GST (monthly / QRMP / composition), TDS, PF, ESI, BOCW cess,
  income tax. **Nothing ticked yields nothing, not everything:** showing a sole
  proprietor their ESI obligations trains them to ignore the calendar.

  The rules encode the exceptions people actually get wrong: **March TDS is due
  30 April, not 7 April**, and the **Q4 26Q return is 31 May, not 30 April**.
  Due days clamp into short months rather than rolling forward, since rolling
  forward moves a deadline.

  Rebuilding is **idempotent and non-destructive** — `INSERT OR IGNORE` against
  a unique (obligation, period) index. The instinct on seeing a wrong date is
  to press rebuild, and losing a year of filing history to that would be
  unforgivable. Due dates are stored per row, not recomputed on read, so a date
  the department extends by notification can be corrected in place and stays
  corrected.

  **No penalty or late-fee figure is computed, and a test enforces that.**
  Those rates change often and vary by return, turnover and whether the return
  is nil. Days late plus the firm's accountant beats a confident wrong number.
  The calendar likewise says plainly that these are standard dates and a
  notification overrides them.
- ✅ **Plant preventive maintenance + fuel analysis** (`plant.py`, new Plant tab
  under Operations, feeding two KPIs). The daily plant log already captured
  hours, diesel and downtime — nothing ever computed anything from them. The
  daily entry stays in Site Reports where the site team already works; this tab
  is what the log is *for*.

  **Fuel: each machine is judged against its own median litres per hour.** Not
  a fleet average, not a manufacturer figure. A JCB and a needle vibrator have
  nothing to say to each other, and a spec sheet describes a new machine in a
  laboratory — on a fleet average the JCB is flagged every day and the vibrator
  never. The median rather than the mean because the outliers are exactly what
  is being hunted and a mean quietly absorbs them. Nothing is reported until a
  machine has enough history to have a norm; crying wolf early is how a signal
  gets ignored. Diesel issued against a machine that logged **no hours** is a
  separate, cleaner signal, reported on its own.

  **Nothing is called theft.** Unusual consumption has innocent explanations —
  a machine idling on standby, a tank filled the evening before — so the view
  names days, machines and the baseline it judged them against, and leaves the
  conclusion to the person who knows. Accusing a named operator on arithmetic
  alone would be both wrong and, on a small site, unforgivable.

  **Service falls due on hours run or elapsed days, whichever comes first** — a
  mixer idle through the monsoon still needs its oil changed, and one that ran
  flat out for a fortnight needs it early. A machine with no interval set reads
  *not scheduled*, never OK: the app does not know it is fine. A log whose date
  will not parse is **counted** toward hours since service rather than skipped,
  because the two failure directions are not equal — counting services a
  machine early, skipping leaves a seizure to happen.

  Logs now link to the equipment master, since 'JCB', 'jcb' and 'JCB 3DX' are
  one machine to everyone except a `GROUP BY`; the free-text field stays for
  logs that predate the link, and grouping falls back to the name.
- ✅ **Baseline-vs-actual programme, with LD exposure and EOT support**
  (`programme.py`, new Baseline vs Actual view in Timeline, feeding a KPI).
  The timeline let dates be edited in place, so the original plan vanished the
  first time anything moved. That is the expensive gap: when a job finishes
  late the contractor must prove *what* slipped and *whose fault it was*, and
  "we remember it was the drawings" is not evidence.

  Freezing the baseline turns the timeline into two money numbers.
  **Liquidated damages exposure** — a percentage of contract value per week
  capped at a percentage of the whole, part weeks counting as whole weeks, cap
  applied last. Terms are per project, because they differ by contract.
  **Extension of time** — delay attributed to the employer (late drawings,
  access, a variation, exceptional weather) is normally excusable, and the view
  shows what exposure would fall to if the claim succeeded.

  **Claimable days take the largest excusable slip, never the sum.** Three
  tasks each a fortnight late because the same drawings were late is a
  fortnight of delay, not six weeks. Summing them is the commonest way an EOT
  claim is inflated to the point of being rejected whole.

  Three honesty constraints, all load-bearing. The LD figure is an **exposure
  estimate on the terms entered**, never a statement of what will be charged —
  contracts differ and departments remit. Days are **claimable, not granted**:
  only the employer grants an extension. And **re-baselining destroys the
  evidence**, so the confirmation quotes the real figures — "this erases 30
  days of recorded delay and 30 days currently supporting a claim" — rather
  than a generic caution nobody reads.

  A late task with no cause recorded is called out separately: those are days
  that cannot be claimed for, and the reason is far easier to establish now
  than at the final account.
- ✅ **Bid / no-bid scorecard** (`bidding.py`, new tab under Billing).
  I argued against building this, on the grounds that a scorecard which only
  weighs the estimator's own guesses is astrology with arithmetic. That
  objection shaped the design rather than being ignored.

  **Evidence comes from the firm's own ledger**, not from the person filling
  the form: whether this client has actually paid past bills, how much of our
  money (receivable plus retention) is already sitting with them, and how full
  the order book is against a stated annual capacity. None of that is opinion,
  and the payment record is the largest risk in this trade — a profitable job
  for a client who pays at 180 days can still close the business.

  **Judgement factors are anchored.** Each of the six describes what 1 and 5
  concretely mean, because a bare 1-5 scale invites everyone to pick 3 and
  produces a confident-looking 60 that means nothing. Unscored factors are
  excluded and the weights renormalised, so a half-filled card reads as "what
  we know so far" rather than being punished as though the blanks were bad.

  **Vetoes override the score, and that is the whole point.** A weighted
  average lets five comfortable scores drown out one fatal factor. No cash to
  carry it, a client already months overdue, work we cannot actually do — those
  are not worth 10% each, they end the conversation. The end-to-end run shows
  it working: the *same* judgement score of 78.8 returns BID for a client who
  pays and DO NOT BID for one sitting on ₹4.2 lakh at 125 days.

  Vetoes are written as sentences citing the figure, because "score 42" is not
  something anyone can argue with while "this client owes you 4,20,000 more
  than 60 days old" is. The verdict says outright that it is advice.

  The assessment records **what was actually decided and how it turned out**,
  so the weights above can eventually be checked against the firm's own history
  instead of being trusted forever.

**Explicit non-goals** (protecting the founding thesis): BIM, IoT/drones,
predictive analytics beyond the local assistant, heavy multi-user cloud sync,
corporate multi-level approval chains. These are Level-4 features that add cost
and friction without helping a solo contractor bill, get paid, and stay in
control.

---

## Phase 9 — statutory forms: what the department actually asks for 🚧

Driven by `docs/RESEARCH-sop-primary-sources.md`, the primary-source research
run (CPWD Works Manual, CPWA Code Book of Forms, CPWD Analysis of Rates). Where
Phase 8 asked _"is the process gated?"_, this phase asks a narrower and more
literal question: **when a contractor submits to a PWD division, does the paper
this app produces match the form the department is expecting?**

That distinction matters because the two failure modes are different. A missing
gate costs money slowly, through leakage. A bill on the wrong format is simply
returned, and payment waits another cycle.

- ✅ **Measurement Book in Form 23 layout** (`mb.py`, `bill_export.build_mb_html`).
  Entries group into pages by MB reference — in entry order, not sorted, because
  MB references are free text ('12', '12A', 'Vol II p.7') and sorting them
  lexically would reorder the book. Each page closes with its total and the
  dated "Measured by me" certificate; the document ends with an abstract of
  measured-against-tendered quantity per BOQ item.

  For works of ₹15 lakh and above it titles itself a **Computerised Measurement
  Book** and cites Works Manual Para 7.12, which is the provision that makes a
  contractor-prepared MB acceptable for departmental submission. Below that
  threshold it deliberately does *not* claim CMB status — printing that on a
  work which does not qualify would misrepresent the document — and says so.

  The **record check** is the part with money attached. Para 7.5 forbids blank,
  void and duplicated entries, so `mb.integrity_issues` flags a measurement
  repeated on the same page (same item, same location, same dimensions) as an
  error, alongside zero/negative quantities and missing dates. A duplicate is
  otherwise invisible: it flows through the RA bill as a real quantity and is
  billed twice. The count surfaces in the tab while entering, not only on the
  printout, because the point is to catch it before certification.
- ✅ **RA bill Memorandum of Payments in Form 26 shape** — the single "other
  recoveries" lump is now the statutory recovery block: **(i) Taxes** (income
  tax TDS, labour cess) **(ii) Security deposit (iii) Other**, each itemised
  with its rate, subtotalled, and reconciling to the net payable by cheque.
  The per-bill security deposit now defaults to CPWD's **2.5%** rather than a
  generic 5%, editable because state PWDs differ.

  All three percentages are charged on the value of work done *in this bill*,
  never the cumulative value — earlier bills already recovered against their
  own. This matters at the part-rate path: re-pricing an item drops the bill
  value, so the tax lines are re-rolled with it. Leaving them stale would
  unbalance the ledger posting and print a memorandum whose recoveries do not
  sum to the deduction.

  On the accounting side the recoveries deliberately do **not** all go one
  way. Retention and TDS are **assets** (1400 Retention Receivable, new 1500
  TDS Receivable) because both come back — retention on release, TDS as credit
  against our own tax. Only cess and other recoveries are expensed. Posting
  TDS as a cost would understate both profit and what the client still owes.
  Note 1500 TDS *Receivable* is the mirror of the existing 2200 TDS *Payable*:
  same word, opposite side of the balance sheet.
- ✅ **Muster Roll Form 21** (`muster.py`, two builders in `bill_export`).
  There was no muster print at all — attendance went in and only a payout
  summary came out.

  **Part I** is the nominal roll: name *and father's name* (common names are
  everywhere on site and this is a payment record), a day-by-day attendance
  grid, rate, days, gross, advance recovered, net — and the payee **signature /
  thumb-impression column**, which is the reason the form exists. It prints
  blank on purpose: it is signed on paper at the moment of payment, and a
  pre-filled acknowledgement would be worthless as evidence. For cash-paid
  informal labour the signed muster is often the only proof a payment happened,
  which matters to the contractor under a labour inspection.

  The grid distinguishes **not marked (`-`) from marked absent (`A`)**. On a
  document somebody signs, those are different claims, and silently converting
  one to the other would be a small forgery.

  The roll lists **everyone on the books**, including a worker with zero days;
  the payout list deliberately does not. Who was engaged and who gets paid are
  different questions, and dropping the zero-day worker from the roll would
  hide someone who should have been marked.

  **Form 21A (Register of Unpaid Wages)** is *derived* — anyone who earned but
  has no recorded payment for the period — so it cannot drift out of step with
  what was actually disbursed. Zero-earners are excluded: an absence is not a
  liability, and listing it would bury the real unpaid amounts.

  **Part II is an honest approximation and is documented as one.** The
  statutory form reconciles work done *by that labour* against the measurement
  book. This app does not record which worker executed which BOQ item, so it
  compares the period's wage bill against the value of work measured in the
  same period. That answers the question the form exists to ask — is the wage
  bill proportionate to what got built — without pretending to a per-worker
  attribution the data cannot support. A period with wages but no measurement
  is flagged rather than divided by zero: that is a measurement gap, not a
  100% labour ratio.
- ✅ **Security-deposit ledger** (extends `retention.py`; new Security Deposit
  view beside the retention register). A CPWD contract secures performance
  **twice**, and the two are separate money with separate release rules:
  a 5% performance guarantee furnished before work starts (Para 21.1), and
  2.5% deducted from the gross of every running and final bill (Para 21.2).
  Keeping them apart on screen is the point — the guarantee is the one people
  forget exists long after the job closed.

  The accrual shows each bill's deduction *and* the running total, because the
  question a contractor actually asks — "how much of mine is sitting with them
  now" — is not answered by any single bill. Where a bill records what was
  really withheld, that beats the nominal percentage: a part rate or a
  departmental adjustment makes the two differ, and the register should show
  what happened, not what the formula says.

  Once the accrued deposit reaches **₹5 lakh** it may be swapped for a bank
  guarantee, which the view flags — it converts dead cash into working capital
  and nobody sends a reminder. Eligibility is tested against what is still
  *held*, not what accrued, so a release correctly drops you back below the
  threshold.

  Rate, guarantee and threshold are all editable defaults rather than
  constants, because state PWDs differ sharply — Arunachal deducts 10% a bill
  against CPWD's 2.5%.
- ✅ **Rate analysis on the DAR skeleton** (`rateanalysis.py`, new Rate
  Analysis tab beside the Rate Book). Builds a per-unit rate from its inputs
  the way the CPWD Analysis of Rates does — material + labour + machinery +
  sundries → +1% water → +15% CPOH (7.5 profit + 7.5 overhead) → divided by
  the analysis quantity — so an item never priced before can be costed from
  first principles and defended when the department questions the figure.

  **Water and scaffolding are per-item toggles, and water defaults to off.**
  The DAR applies water charges to items that consume water and scaffolding to
  items needing access; charging 1% water on a steel-supply item is simply
  wrong, and defaulting it on would make every dry rate 1% high in a way
  nobody would ever notice.

  **The analysis quantity is explicit and the division happens once.** The DAR
  analyses a convenient block — 10 cum of concrete, 100 sqm of plaster —
  because labour constants are quoted that way. Analysing per unit and
  rounding at each step compounds error, so the division is the last operation.
  A missing quantity yields *no rate* rather than zero: an incomplete analysis
  is a normal in-progress state, and zero would read as a real, free rate.

  **The module ships no rate data at all** — deliberately, and there is a test
  asserting it. The DAR's published rates are 2014-dated (Delhi materials
  Mar–Apr 2014, labour at the 01.04.2014 minimum wage). Bundling them would
  hand contractors a decade-old schedule wearing the authority of a government
  document. Rates come from the firm's own material and labour masters, so the
  analysis reflects what they actually pay. The derived rate can be pushed
  into the Rate Book — updating the existing entry rather than duplicating it
  — because otherwise the number dies on the screen that produced it.

**Standing caveat for this phase:** CPWD is the dominant template, not a
universal standard, and the GCC 2019 supersedes some Works Manual terms
(notably payment timelines). Anything this app *prints as a rule* must cite the
governing contract, and anything state-variable ships as a configurable default
rather than a constant.

---

## Cross-cutting, always-on

- Keep **pure stdlib / tkinter / single-SQLite / no-pip**.
- Keep business maths in **pure, testable modules**.
- Every new document gets a **print/PDF** path.
- Every new screen respects **minimal-typing** and **plain language**.
- Update `AGENTS.md` (architecture) and this roadmap as phases land.
