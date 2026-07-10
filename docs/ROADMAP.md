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

## Phase 1 — Money that matters 🚧 (in progress)

The cash-first heart. This is what an owner-contractor opens the app for.

- 🚧 **Payments & Receipts** — one screen to record money **in** (from clients)
  and **out** (to vendors/labour), by mode (Cash/Bank/UPI/Cheque), optionally
  against a bill/invoice/site. (`payments` table, `tab_money.py`.)
- 🚧 **Party ledger / balances** — per client, vendor, or labour contractor:
  what was billed/invoiced, what was paid/received, and the **running balance**
  ("baaki"). The two-click answer to "who owes whom".
- 🚧 **Cash / Day book** — dated cash in/out with a **running balance** and
  optional opening balance and site filter. The digital bahi-khata.
- 🚧 **Home dashboard** — a plain-language landing screen: cash in hand,
  receivables, payables, active sites, this month's billing & collection.
- 🚧 `money.py` pure helpers (signed cash, running balance, party outstanding).

_Repositioning note:_ the double-entry Accounting tab stays but moves behind the
cash-first views; the contractor never needs the journal to run the business.

---

## Phase 2 — Get paid & submit ⏳

Contractors live and die by the **printed bill they hand over**.

- ⏳ Print/PDF for **every** key document: RA bill (done), running bill (done),
  **tax invoice, quotation, estimate, PO, vendor invoice, party statement,
  cash book**.
- ⏳ **GST tax invoice** for clients (CGST/SGST/IGST breakup, HSN, invoice
  number series, amount in words).
- ⏳ Department-friendly **RA bill formats** (PWD-style abstract, deviation
  statement, part-rate handling).
- ⏳ **Share**: save-to-folder + "open to print / Save-as-PDF" flow that works
  offline; easy to attach on WhatsApp.
- ⏳ Amount-in-words (Indian numbering: lakh/crore) helper.

---

## Phase 3 — Labour reality ⏳

How T2/T3 sites actually run: daily muster, weekly payout, thekedars.

- ⏳ **Muster roll** — daily attendance grid per site, quick mark P/A/½/OT.
- ⏳ **Thekedar / labour-contractor ledger** — work given, advances, weekly
  settlement, running balance.
- ⏳ **Weekly wage payout** — generate from muster, adjust advances, print a
  payout sheet; ties into Payments (Phase 1).
- ⏳ Optional PF/ESI/labour-cess fields (off by default — most are informal).

---

## Phase 4 — Trust & ease ⏳

Adoption blockers for non-technical, single-PC users.

- ⏳ **Backup & restore** — one-click copy of the SQLite file to a chosen folder
  / USB, with date-stamped filenames; restore with confirmation.
- ⏳ **Vernacular UI** — Hindi/Hinglish labels via a simple string table;
  language toggle. Plain words over accounting jargon.
- ⏳ **Guided, low-typing entry** — defaults to today's date, remembers last
  site/party, dropdown-first, inline "add new" for masters.
- ⏳ **Fix the sharp edges** — friendly messages for FK-delete and other errors
  (AGENTS.md §4 gap); no stack traces ever reach the user.
- ⏳ First-run **sample data / setup wizard** (create first site + client).

---

## Phase 5 — Compliance made simple ⏳

Enough to keep the contractor and their CA happy, no more.

- ⏳ **GST summary** — GSTR-1-style outward sales and GSTR-3B-style worksheet
  from invoices/bills, exportable.
- ⏳ **TDS register** — TDS deducted (vendor payments) and TDS on receipts.
- ⏳ **Input vs output GST** position (from procurement vs sales).
- ⏳ e-invoice / e-way-bill field readiness (data captured now, integration later).

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
