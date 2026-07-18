# Contractor-OS — Product Document

_Last updated: 2026-07-10_

## 1. One line

A dead-simple, offline, single-PC business app that a **small civil
contractor in a tier-2 / tier-3 Indian city** can run themselves — to bill
their work, know who owes them money, pay their labour and suppliers, and hand
a clean printed bill to the client — without an accountant, an internet
connection, or a monthly subscription.

## 2. Who this is for (and who it is NOT for)

### Primary user — the owner-contractor ("thekedar / contractor sahab")
- Runs 1–5 sites at a time: residential buildings, shops, small commercial,
  road/drain/culvert work, PWD / municipal / panchayat contracts.
- Turnover roughly ₹20 lakh – ₹5 crore a year. A handful of staff.
- Works from a **Windows laptop or desktop** in a small office or from home.
  Often the only computer in the business.
- Comfortable on a smartphone (WhatsApp, UPI, YouTube) but **not** with
  accounting software. Thinks in **cash in / cash out** and **"kitna len-den
  baaki hai"** (how much is outstanding), not debits and credits.
- Frequently prefers **Hindi / regional language** or Hinglish over formal
  English.
- Keeps records in a diary (bahi-khata), a notebook, and WhatsApp. Loses
  track of small vendor and labour payments.

### Secondary user — the "munshi" / site clerk / accountant-cousin
- Does data entry: attendance, measurements, material receipts, payments.
- Low-to-medium computer skill. Needs big, obvious buttons and few fields.

### NOT our user (explicit non-goals)
- **Not corporates / large builders / EPC firms.** No multi-branch, no
  role-based access control, no approval hierarchies, no ERP integrations, no
  SAP/Tally-grade double-entry-first accounting as the primary experience.
- **Not accountants** as the primary user. A CA may _use_ the exports, but the
  contractor must be able to run the whole thing alone.
- **Not a cloud SaaS.** No login servers, no per-seat pricing assumptions, no
  "your data lives on our servers." Their data is one file on their PC.

## 3. What they actually struggle with (jobs to be done)

1. **"Make me a bill I can submit."** A clean, printed running/tax bill for the
   client or department — measurement-based for civil work, GST where needed.
   Today: hand-written or a cousin makes it in Excel; errors, delays, disputes.
2. **"Who owes me and whom do I owe?"** Party-wise outstanding for clients,
   suppliers, and labour contractors. Today: scattered across diary + WhatsApp.
3. **"Where did the cash go?"** A day book / cash book across sites — advances,
   petty cash, material payments, labour payouts. Today: memory + loose slips.
4. **"Pay the labour this week."** Muster roll → weekly wage → advances
   adjusted, often through a thekedar (labour contractor). Today: manual.
5. **"Did the material get used or wasted?"** Cement/steel bought vs consumed.
   Today: gut feeling, occasional shock.
6. **"Don't let me lose my data."** One PC, no backups. A crash = the business
   memory gone. Today: terrifyingly fragile.
7. **"Handle GST without a headache."** Correct GST on bills and a simple
   summary at return time. Today: depends entirely on the CA.

## 4. Design principles (the non-negotiables)

1. **Offline-first, single file.** The whole business is one SQLite file next to
   the app. No internet required to do anything core. Sync/cloud is optional and
   later, never a dependency.
2. **Windows-first.** The typical machine is Windows. Ship/run so a
   double-click works; document a one-file launch. (Codebase stays pure-stdlib
   Python + tkinter precisely so it runs anywhere with zero install pain.)
3. **Print-first.** Contractors submit **paper**. Every important document (RA
   bill, tax invoice, party statement, cash book) must produce a clean
   printout / PDF (via browser HTML export today; see the roadmap).
4. **Minimal typing.** Pick from lists, reuse last values, sensible defaults,
   dates default to today. Every extra field is a tax on adoption.
5. **Cash-first, not ledger-first.** Lead with cash book and party balances.
   Double-entry accounting exists under the hood / for the CA, but the
   contractor never has to see a journal to run their business.
6. **Vernacular-ready.** Design for Hindi/regional labels and Hinglish. Avoid
   jargon ("Net Payable" over "Accounts Receivable"; "Baaki" over "Outstanding"
   in localized builds).
7. **Trust & data safety.** Backups must be one click. Nothing silently
   destructive. The user's data is sacred and local. Security stays **opt-in**: a solo contractor keeps zero-friction, no-login access; an office with staff can switch on local sign-in with roles and an audit trail (never a cloud account or a dependency).
8. **Forgiving.** Non-technical users mistype. Fail softly with plain-language
   messages, never a stack trace. (Note the known FK-delete gap in AGENTS.md —
   this principle says fix it.)
9. **Free/cheap to run.** No dependency that implies a subscription. The
   business model, if any, is a one-time or optional-support model — never a
   gate on the contractor's own data.

## 5. Why not just Tally / Busy / Excel / a SaaS?

- **Tally / Busy**: accountant-first, double-entry mental model, steep for an
  owner-contractor, and **not civil-billing aware** (no BOQ / Measurement Book /
  RA bill). Great for the CA, wrong for the site.
- **Excel / diary**: what they use now — error-prone, no measurement math, no
  party balances that update themselves, easy to lose.
- **Construction SaaS**: built for corporates/enterprise, English-only,
  subscription, internet-dependent, feature-heavy. Overkill and unaffordable in
  spirit for a T2/T3 solo contractor.

Contractor-OS sits in the gap: **civil-billing-native, contractor-operable,
offline, printable, and cheap.**

## 6. Product pillars (maps to the codebase)

| Pillar | What it means for the T2/T3 contractor | Status |
|---|---|---|
| Site operations | Sites, materials, labour, equipment, stock, attendance | Built |
| Civil billing | BOQ → Measurement Book → RA bill, printable abstract | Built |
| Commercial | Quotations, estimates, contracts, running bills | Built |
| Procurement | Purchase orders, vendor invoices (GST/TDS), reconciliation | Built |
| Site & quality | Consumption reconciliation, DPR, cube/material tests, plant log | Built |
| **Money that matters** | **Cash book, party balances, payments & receipts** | **Roadmap P1** |
| Get paid & submit | Print/PDF everywhere, GST tax invoice, share | Roadmap P2 |
| Labour reality | Muster roll, thekedar ledger, weekly payout | Roadmap P3 |
| Trust & ease | Backup/restore, vernacular UI, guided entry | Roadmap P4 |
| Compliance made simple | GST summary, TDS register | Roadmap P5 |
| Insight | Site profitability, budget vs actual, ageing | Roadmap P6 |
| Advanced (optional) | Auto-posted double-entry, subcontractor billing | Roadmap P7 |

## 7. What "done well" looks like (success signals)

- A contractor generates and prints an RA bill or tax invoice **without help**
  in under 10 minutes.
- They can answer **"how much is X party baaki?"** in two clicks.
- They can see **cash in hand** and this month's collections on opening the app.
- They take a **backup** without being told how twice.
- Nothing they click ever shows a stack trace.

## 8. Guardrails for contributors (and AI agents)

- Keep the founding constraints: **pure stdlib Python, tkinter, single SQLite
  file, no pip dependencies.** They are what make "runs on any T2/T3 contractor's
  PC with zero install" true. Don't trade them for polish.
- Prefer **fewer fields and clearer words** over feature completeness.
- Keep business maths in the **pure modules** (`finance.py`, `civil.py`,
  `money.py`, `bill_export.py`) so it's testable without a GUI.
- Read `AGENTS.md` for architecture and conventions before writing code.
- When in doubt, optimize for the **solo contractor doing it alone at night**,
  not the accountant and not the enterprise.
