# Contractor-OS — Roadmap

_Last updated: 2026-07-10_

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
- ⏳ Print/PDF for the remaining docs: quotation, estimate, PO, vendor invoice.
- ⏳ Configurable invoice **number series** (prefix + financial-year reset).
- ⏳ Department-friendly **RA bill formats** (PWD-style abstract, deviation
  statement, part-rate handling).

---

## Phase 3 — Labour reality 🚧 (mostly built)

How T2/T3 sites actually run: daily muster, weekly payout, thekedars.

- ✅ **Muster roll** — per-site daily grid, mark P/A/½/OT (individually or all),
  writes one attendance row per labourer per day (`tab_muster.py`).
- ✅ **Weekly wage payout** — computed from the muster, advances deducted,
  printable payout sheet, and one-click "Record as Payments" into the cash book.
- ✅ **Thekedar / labour-contractor ledger** — master + Work/Paid running
  balance, printable.
- ⏳ Auto-recover advances (mark `advances.recovered`) when a payout deducts
  them, and de-dupe re-runs of "Record as Payments".
- ⏳ Optional PF/ESI/labour-cess fields (off by default — most are informal).

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
- ⏳ **Vernacular UI** — Hindi/Hinglish labels via a simple string table;
  language toggle. Plain words over accounting jargon.
- ⏳ **Guided, low-typing entry** — defaults to today's date, remembers last
  site/party, dropdown-first, inline "add new" for masters.
- ⏳ Audit the remaining error paths so **no stack trace ever reaches the user**.
- ⏳ First-run **sample data / setup wizard** (create first site + client).

---

## Phase 5 — Compliance made simple 🚧 (mostly built)

Enough to keep the contractor and their CA happy, no more.

- ✅ **GST summary** — Output GST (sales) and Input GST (purchases) registers +
  a net-position (3B-style) summary, month-filtered and printable
  (`tab_gst.py`, `finance.gst_summary`).
- ✅ **Input vs output GST** position (output tax − input credit → payable /
  carry-forward).
- ✅ **TDS register** — TDS deducted on vendor invoices, month-filtered.
- ⏳ Bring **running bills / RA bills** into the outward GST view (currently
  only tax invoices count as outward supply).
- ⏳ e-invoice / e-way-bill field readiness (data captured now, integration
  later); HSN-wise summary.

---

## Phase 6 — Insight ⏳

Simple, honest numbers — not exec dashboards.

- ⏳ **Site-wise profitability** — billed vs (material + labour + hire + other).
- ⏳ **Material budget vs actual** — estimate/BOQ vs consumed (builds on Phase-0
  consumption reconciliation).
- ⏳ **Receivable / payable ageing** — 0–30 / 30–60 / 60–90 / 90+ buckets.
- ⏳ Contract/BOQ **progress %** (measured value ÷ BOQ value).

---

## Phase 7 — Advanced (optional, opt-in) ⏳

Power features that must never complicate the core.

- ⏳ **Auto-posting to double-entry** — bills, vendor invoices, payroll, and
  payments post balanced journal entries automatically (Dr/Cr), so the trial
  balance and a P&L / balance sheet come for free for the CA.
- ⏳ **Subcontractor / work-order billing** — back-to-back BOQ, sub RA bills,
  retention & TDS on works contract.
- ⏳ **Multi-year / multi-firm** files, optional cloud backup.

---

## Cross-cutting, always-on

- Keep **pure stdlib / tkinter / single-SQLite / no-pip**.
- Keep business maths in **pure, testable modules**.
- Every new document gets a **print/PDF** path.
- Every new screen respects **minimal-typing** and **plain language**.
- Update `AGENTS.md` (architecture) and this roadmap as phases land.
