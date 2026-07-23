# SOP Manual — Construction Management Firm

**Ready-to-use standard operating procedures for a small/mid civil contractor.**
_Report deliverable — no code. Written to be adopted as-is by a T2/T3 firm, and
to describe the process Construction OS supports (or should enforce). Companion
research: [`RESEARCH.md`](RESEARCH.md) §3. Status: [`ROADMAP.md`](ROADMAP.md)._

Each SOP is one page: **Purpose · Scope · Roles · Procedure · Hold points (gates)
· Records · App screen**. "App screen" notes where the step lives in Construction
OS today, or **[gap]** where the gap-analysis report proposes a new module.

Legend for the gate marker 🚦 = a hold point where work/payment must not proceed
without the sign-off named.

---

## SOP-01 — Estimating & Tendering

- **Purpose:** Win profitable work with accurate, reviewed estimates.
- **Scope:** Every tender/quotation before submission.
- **Roles:** Estimator (prepares), Owner/PM (reviews & approves), Admin (submits).
- **Procedure:**
  1. Run bid/no-bid check (client creditworthiness, scope fit, distance, margin,
     competition). Proceed only if it passes.
  2. Take off quantities from drawings/BOQ; price each item from the **Rate Book**
     (schedule of rates); update rates for current steel/cement/fuel prices.
  3. Add contingency % and overhead + profit; roll up to the grand total (with
     GST) and amount-in-words.
  4. 🚦 **Second-person review** of quantities and rates before submission.
  5. Submit against a document checklist (EMD, signatures, deadline).
- **Records:** Estimate, rate basis, review sign-off, tender submission proof.
- **App screen:** Billing → Estimates, Billing → Rate Book. _[gap: bid/no-bid
  scorecard; estimate approval step.]_

---

## SOP-02 — Project Set-up (pre-construction)

- **Purpose:** Convert a won bid into a controlled project with a baseline.
- **Scope:** Every awarded contract before site mobilization.
- **Roles:** PM (owns), Estimator (hands over), Accounts (sets budget).
- **Procedure:**
  1. Create the **Contract** (value, retention %, dates, penalty/LD terms) and
     the **Project** (client + site + budget + milestones).
  2. Convert the estimate into a **cost-control budget** by cost head
     (material / labour / plant / subcontract / overhead).
  3. Build the **baseline programme** (WBS, milestones, critical activities) in
     the timeline.
  4. Prepare a **procurement plan** for long-lead items tied to the programme.
  5. Complete the **mobilization checklist** (utilities, storage, safety signage,
     statutory registrations).
- **Records:** Contract, budget baseline, baseline programme, procurement plan.
- **App screen:** Billing → Contracts; Projects; Operations → Timeline. _[gap:
  baseline-vs-actual; procurement plan; mobilization checklist.]_

---

## SOP-03 — Procurement (Requisition → PO → GRN → Invoice → Payment)

- **Purpose:** No material bought or paid for outside a tracked, approved chain.
- **Scope:** All material and hired-service purchases above a set value.
- **Roles:** Site (requisitions), Purchase (raises PO), Store (receives/GRN),
  Accounts (matches & pays), Owner/PM (approves).
- **Procedure:**
  1. Site raises a **material requisition** (item, qty, needed-by).
  2. Purchase obtains **3 quotes** above the threshold, selects an **approved
     vendor**, and raises a **Purchase Order**. 🚦 **PO approved** before sending.
  3. On delivery, Store checks quantity + quality at the gate and records a
     **GRN against the PO**; the GRN writes the material-ledger **IN**.
  4. Book the **Vendor Invoice** (GST/TDS) and run the **3-way match**
     (PO ↔ GRN ↔ Invoice); flag any variance.
  5. 🚦 **No payment without a matched GRN.** Pay per terms; record against the
     invoice.
- **Records:** Requisition, quotes, PO, GRN, vendor invoice, reconciliation,
  payment.
- **App screen:** Purchases → Purchase Orders, Vendor Invoices (+reconciliation);
  Operations → Warehouse. _[gap: requisition, GRN gate, 3-quote, approved-vendor
  — see gap report P0/P1.]_

---

## SOP-04 — Material Stores & Reconciliation

- **Purpose:** Control stock; expose the 5–15% wastage/pilferage.
- **Scope:** All site materials.
- **Roles:** Store keeper (records), PM (reviews reconciliation).
- **Procedure:**
  1. Receive only against a **GRN** (SOP-03); update stock.
  2. Issue material **against an indent** for a specific activity; record ledger
     **OUT**.
  3. Maintain a **consumption norm** per activity (e.g. bags/cum).
  4. Periodically run **theoretical (norm × work done) vs actual issued**
     reconciliation; investigate variances beyond tolerance.
  5. Do a periodic **physical stock** count vs system stock.
- **Records:** Ledger (IN/OUT), stock summary, consumption reconciliation.
- **App screen:** Operations → Warehouse; Operations → Consumption; Money →
  Insight (Material Budget).

---

## SOP-05 — Subcontractor / Petty-Contractor Engagement & Billing

- **Purpose:** No sub work without a written order; correct retention & TDS.
- **Scope:** All subcontractors/thekedars.
- **Roles:** PM (engages), Site (measures), Accounts (bills & pays).
- **Procedure:**
  1. Issue a **Work Order** (scope, rate, retention %, TDS %). 🚦 No sub work
     starts without it.
  2. Measure work done; raise a **sub running bill** (previous value auto-fills;
     retention + TDS deducted → net payable).
  3. 🚦 **Certify** before payment; price any extra item as a **variation**
     (SOP-07) first.
  4. Track retention withheld and its release.
- **Records:** Work order, sub bills, retention register, payments.
- **App screen:** Purchases → Subcontractors (Work Orders + Sub Bills). _[gap:
  sub-level variation; retention release.]_

---

## SOP-06 — Daily Site Reporting & Weekly Look-Ahead

- **Purpose:** Keep field and office on one record; plan reliably.
- **Scope:** Every active site, every day/week.
- **Roles:** Site engineer (reports), PM (plans), foremen/leads (commit).
- **Procedure:**
  1. File the **Daily Progress Report (DPR)** — manpower, plant, work done,
     material received, weather, hindrances.
  2. Hold a 10-minute **daily huddle** (yesterday plan vs actual, today, blockers).
  3. Weekly **look-ahead (Last Planner)**: the people doing the work commit to
     next week's tasks; **remove constraints (material, access, unresolved RFI)
     before committing**.
  4. Track **Percent Plan Complete (PPC)** = tasks done ÷ tasks committed as the
     reliability KPI.
- **Records:** DPR, weekly plan, PPC trend.
- **App screen:** Operations → Site Reports (DPR). _[gap: weekly look-ahead / PPC;
  huddle log — see gap report P1.]_

---

## SOP-07 — Variation / Change-Order Control  *(highest-value gate)*

- **Purpose:** Never do extra work that isn't priced, approved, and billed.
- **Scope:** Any change to scope, quantity, rate, or time.
- **Roles:** Site (identifies), PM (prices), Client/PM (approves), Accounts
  (bills).
- **Procedure:**
  1. Log the variation (description, item, quantity, rate, reason).
  2. 🚦 **Get written approval before executing** the extra work.
  3. Track status: **Raised → Approved → Executed → Billed**.
  4. Include approved variations in the next RA/tax bill; keep the register
     billing-linked so nothing is forgotten.
  5. Issue written **notice** for any time impact (EOT) to preserve rights.
- **Records:** Variation register, client approval, linked bill.
- **App screen:** **[gap — new module, gap report P0]**. Today variations are not
  tracked; this is the single biggest unrecovered-revenue risk.

---

## SOP-08 — Progress Measurement & Client Billing (MB → RA → Invoice → Collect)

- **Purpose:** Bill measured work promptly and completely; get paid.
- **Scope:** Every contract billing cycle.
- **Roles:** Site (measures), PM (certifies), Accounts (invoices & collects).
- **Procedure:**
  1. Record measurements in the **Measurement Book** (Nos × L × B × D) against
     BOQ items.
  2. Generate the **RA bill** (cumulative − previous = this bill; retention &
     deductions applied); include approved **variations** (SOP-07) and a
     **deviation statement** for over/under-run.
  3. 🚦 **Certify** the bill; raise the **GST tax invoice** (CGST/SGST/IGST,
     HSN/SAC, amount-in-words) with the correct **number series**.
  4. Send (print / WhatsApp-able PDF); **follow up on receivables by ageing**;
     record receipts **against the specific bill**.
  5. Track **retention** and release it on milestone / defect-liability expiry.
- **Records:** MB, RA bill, deviation statement, tax invoice, receipts, retention
  register.
- **App screen:** Billing → BOQ / RA Bills, Tax Invoice; Money → Cash & Parties,
  Insight (ageing). _[gap: payment-against-bill allocation; retention release —
  gap report P0/P1.]_

---

## SOP-09 — Quality (ITP + NCR)

- **Purpose:** Build right the first time; make quality checks unskippable.
- **Scope:** All quality-critical activities.
- **Roles:** QC engineer (inspects), PM (approves hold points), lab (tests).
- **Procedure:**
  1. For each activity, define an **Inspection & Test Plan (ITP)**: checks,
     acceptance criteria (spec/code), frequency, and **Hold/Witness Points**
     (pre-pour, pre-cover, pressure test).
  2. 🚦 At a **Hold Point**, work must not proceed until QC signs off.
  3. Record test results (cube/material) in the register with traceability.
  4. Raise a **Non-Conformance Report (NCR)** for defects; log root cause and
     **corrective + preventive action**; close the loop.
- **Records:** ITP, inspection checklists, test certificates, NCR log.
- **App screen:** Operations → Site Reports (cube/material tests). _[gap: ITP
  hold-point checklists; NCR loop — gap report P1.]_

---

## SOP-10 — Cash Flow & Receivables/Payables

- **Purpose:** Never be surprised by a liquidity shortfall.
- **Scope:** Firm-wide, weekly/monthly.
- **Roles:** Accounts (forecasts), Owner (decides), PM (informs).
- **Procedure:**
  1. Maintain the **cash book** (all in/out, by mode) and party balances.
  2. Review **receivables/payables ageing** (0–30/30–60/60–90/90+); follow up
     the oldest first.
  3. Build a **cash-flow forecast**: expected certified **inflows** by date vs
     committed **outflows** (vendors, subs, payroll, hire) → running projected
     balance.
  4. 🚦 Act on any projected shortfall **before** it hits (accelerate billing,
     stagger vendor payments, match terms to receipts).
  5. File GST/TDS/PF on time (compliance calendar).
- **Records:** Cash book, ageing, cash-flow forecast, GST/TDS registers.
- **App screen:** Money → Cash & Parties, Insight (ageing); Accounts → GST & TDS.
  _[gap: cash-flow forecast; compliance calendar — gap report P0/P2.]_

---

## SOP-11 — Health & Safety (brief)

- **Purpose:** Prevent incidents; meet statutory duty (BOCW/OSHA-equivalent).
- **Scope:** All site personnel.
- **Roles:** Safety officer/PM (owns), all workers (comply).
- **Procedure:** Induction + PPE on entry; weekly **toolbox talks**;
  **permit-to-work** for high-risk tasks (height, excavation, hot work, confined
  space); log **incidents/near-misses** and investigate; periodic safety audit.
- **Records:** Induction register, toolbox-talk log, permits, incident reports.
- **App screen:** **[gap — lightweight HSE module, gap report P2]**.

---

## SOP-12 — Project Closeout & Lessons Learned

- **Purpose:** Finish clean; feed learning back into the firm.
- **Scope:** Every project at completion.
- **Roles:** PM (owns), QC (snags), Accounts (final account), Estimator (rates).
- **Procedure:**
  1. Close the **snag/punch list**; obtain client sign-off.
  2. Hand over **as-built drawings, O&M manuals, warranties**.
  3. Settle the **final account**; release **retention** at defect-liability
     expiry.
  4. Hold a **lessons-learned** review; **update the Rate Book** with actual
     achieved rates and update SOPs.
- **Records:** Snag list, handover docs, final account, lessons-learned note.
- **App screen:** Projects → Milestones; Billing → Rate Book. _[gap: snag list;
  lessons-learned capture — gap report P2.]_

---

## Adoption notes

- Keep each SOP to **one page, plain language, action verbs**; add a photo/diagram
  where it prevents error.
- **Embed the SOP in the app** so the hold points (🚦) are enforced by a
  checklist/gate, not by memory — this is the difference between an SOP that works
  and one that sits in a binder.
- **Start with the P0 gates** (SOP-07 variations, SOP-08 payment allocation,
  SOP-10 cash-flow, SOP-03 GRN) — they close the largest money leaks.
- Review adoption with the KPIs in the research report §8 (PPC, DSO, CVR, %
  spend-under-PO, unbilled-variation value, first-time-pass inspection %).
