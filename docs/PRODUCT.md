# ACO — Product Document

_Last updated: 2026-07-22_

**ACO** = **Accelerated Construction Operations**  
(formerly Construction OS; same product, new name and orange logo mark)

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
- **Not corporates / large builders / EPC firms.** No multi-branch corporate
  hierarchy as the primary design, no mandatory approval chains, no
  SAP/Tally-grade double-entry-first accounting as the primary experience.
  *(Opt-in Admin/Operator/Viewer roles exist when security is turned on in
  Tools — they are for a small office, not enterprise IAM.)*
- **Not accountants** as the primary user. A CA may _use_ the exports, but the
  contractor must be able to run the whole thing alone.
- **Not a cloud SaaS.** No login servers, no per-seat pricing assumptions, no
  "your data lives on our servers." Their data is one file on their PC
  (optional LAN/browser on the same book is fine).

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

Product non-negotiables below. For the **WinUI 3 / Fluent** visual and
interaction rules (Windows 11 principles, stock controls, type ramp, writing
tone, PR checklist), see
[`UI-PRINCIPLES-AND-GUIDELINES.md`](UI-PRINCIPLES-AND-GUIDELINES.md) and
[`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md).

1. **Offline-first, single file.** The whole business is one SQLite file next to
   the app. No internet required to do anything core. Sync/cloud is optional and
   later, never a dependency.
2. **Windows-first.** The typical machine is Windows. Ship/run so a
   double-click works; document a one-file launch.
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
   destructive. The user's data is sacred and local. Security stays **opt-in**.
8. **Brand: ACO / Radiant Orange.** Product name **ACO** (Accelerated
   Construction Operations). Keep the existing logo **mark** (geometry) and
   fill it with Radiant Orange (`#FF4F18`, same as the UI accent in
   `tokens.py`). Do not invent a new mark without owner approval.

## 5. Branding constants

Source of truth: `construction_app/branding.py`

| Constant | Value |
|---|---|
| `APP_NAME` | `ACO` |
| `APP_FULL_NAME` / `TAGLINE` | `Accelerated Construction Operations` |
| `WINDOW_TITLE` | `ACO — Accelerated Construction Operations` |
| `BRAND_ORANGE_HEX` | `#FF4F18` |
| Data folder (installed) | `%LOCALAPPDATA%\ACO` (legacy `Construction OS` still opened if present) |

## 6. Positioning

ACO sits in the gap: **civil-billing-native, contractor-operable,
offline**, between Excel/WhatsApp chaos and heavyweight ERP suites the T2/T3
owner will never run alone.
