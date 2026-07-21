# Report — SOP Gap Analysis & Required Modifications

**Construction OS vs. construction-management SOP best practices**
_Report only — no code changes. Compiled 2026-07-19 against `main` @ `a9e7afa`._
_Companion documents: `docs/RESEARCH-construction-management-sops.md` (the
research) and `docs/SOP-manual.md` (the ready-to-use SOPs)._

---

## 0. RESOLUTION UPDATE — 2026-07-21 (verified against `main` @ `ef6bbe7`)

**Status: substantially closed.** Since this report was written, a "Phase 8 —
SOP gap closure" (plus a "Phase 9" CPWD/CPWA departmental-forms pass) built out
essentially every gap listed below. The schema grew **45 → 79 tables**; the app
now has **43 tabs / 102 modules**. Verified on 2026-07-21:

- ✅ All app modules **compile** (`py_compile`), incl. the new `ollama_manager`.
- ✅ `init_db` applies the **79-table schema clean** on a fresh DB.
- ✅ **All 43 registered tabs build** headlessly (tk-stub) — **0 failures**.
- ✅ **425/425 unit tests pass** (`tests/test_core.py`, up from 58).

**Gap → now built (tab · table · commit):**

| Original gap (priority) | Now built |
|---|---|
| Variation / change-order register **(P0)** | **Variations** tab · `variations` · `478dc26` |
| Payment ↔ bill allocation → reconciled ageing **(P0)** | **Cash & Parties** allocation + Insight ageing · `payment_allocations`, `allocation.py` · `bf2ac70` |
| Cash-flow forecast **(P0)** | **Cash Flow** tab · `commitments` · `dfc7022` |
| Requisition → PO → GRN gate + 3-way match **(P0/P1)** | **Sourcing** + **Goods Receipt** tabs · `material_requisitions`, `goods_receipts`/`grn_items`, `quotes` · `2671dff`, `24dd625` |
| Retention register + release/DLP **(P1)** | **Retention** tab · `retention_releases` · `ee39138` |
| Cost-value reconciliation (CVR) **(P1)** | in **Look-ahead**/Insight · `4877d44` |
| ITP hold-points + NCR loop **(P1)** | **Quality** tab · `itp_items`, `inspections`, `ncrs` · `e5383b4` |
| Weekly look-ahead / PPC **(P1)** | **Look-ahead** tab · `4877d44` |
| Approval gates (workflow) **(P1)** | **Approvals** tab · `approvals` · `2002984` |
| KPI dashboard **(P1)** | **Key Numbers** tab · `89785a2` |
| RFI + drawing-revision register **(P2)** | in **Sourcing** · `rfis`, `drawings` · `24dd625` |
| HSE module **(P2)** | **Safety** tab · `incidents`, `work_permits`, `safety_inductions`, `toolbox_talks` · `ff01404` |
| Project closeout / snag list **(P2)** | **Closeout** tab · `snags` · `0e461b6` |
| Vendor 3-quote + rating **(P2)** | **Sourcing** tab · `quotes` · `24dd625` |
| Plant PM schedule + fuel log **(P2)** | **Plant** tab · `plant_services` · `149f23b` |
| Compliance calendar **(P2)** | **Compliance** tab · `compliance_filings` · `bfe0c89` |
| Bid/no-bid scorecard + estimate approval **(P2)** | **Bid / No Bid** tab · `bid_assessments` · `8ce254a` |
| Baseline-vs-actual programme + LD/EOT **(P2)** | Timeline + critical path · `37a0d23`, `5353d3d` |
| e-invoice / e-way readiness **(research §5)** | Tax Invoice fields · `einvoice.py` · `9ebbb31` |

**Also landed beyond the original scope:** CPWD/CPWA departmental formats
(Form 23 measurement book, Form 26 recovery, Form 21 muster, security-deposit
ledger, DAR rate analysis — the **Rate Analysis** tab), branded proposal/contract
letterheads, a TF-IDF assistant with conversational follow-ups, a full UI
redesign (rail/stage, light/dark, pictograms, stat-card dashboard), a Windows
installer, and a standalone Ollama Manager.

**Remaining / worth a look:** a **submittals** register as a distinct log (RFIs
and drawing revisions exist; submittals do not); and the usual "does the
redesigned GUI actually render on a real display" check that a headless
environment can't perform. _(The earlier open item — RA/running bills posted with
a proper retention account — is now **done**: a **Retention Receivable (1400)**
account was added and `posting.ra_bill_lines` books the client-withheld retention
to it, so the P&L shows revenue and the balance sheet carries retention as an
asset.)_

The sections below are the **original 2026-07-19 analysis**, retained for history.

---

## 1. Purpose & method

This report compares **what Construction OS implements today** against the SOP
architecture and pain-point fixes established in the research report, and lists
the **modifications required** to close the gaps — prioritized for the target
user (a T2/T3 Indian civil contractor), not for a corporate EPC firm.

- **Status legend:** ✅ Built · 🟡 Partial · ❌ Missing
- **Priority:** **P0** (biggest cash/revenue leak, on-thesis) · **P1** (control
  & quality) · **P2** (completeness / lower urgency for T2/T3)
- **Effort:** **S** (small, a tab/table) · **M** (medium) · **L** (large)

This is a **planning report**. Nothing here has been coded.

---

## 2. Current implementation (baseline)

Construction OS today (60 Python modules, 45+ tables) covers a large part of the
SOP spine. Confirmed present:

- **Masters** — Sites, Clients, Vendors, Materials (std rate + HSN), Labour (+PF/
  ESI), Equipment, **Rate Book**.
- **Projects** — Projects + Milestones + overview dashboard.
- **Operations** — material ledger + stock, Muster & Wages (muster, weekly
  payout, thekedar ledger, statutory calculator), attendance/advances/payroll,
  equipment hire, consumption reconciliation, **Site Reports (DPR, cube tests,
  material tests, plant log)**, Timeline/Gantt.
- **Billing** — Quotations, Estimates (contingency/GST/grand total), Contracts,
  **BOQ → Measurement Book → RA bills**, deviation statement, PWD abstract,
  part-rate, Running Bills, GST Tax Invoice with configurable numbering.
- **Purchases** — Purchase Orders, Vendor Invoices (GST/TDS), **PO↔invoice
  reconciliation**, Subcontractors (work orders + sub bills with retention/TDS).
- **Money** — payments/receipts, party balances, cash book, **Insight**
  (profitability, contract/BOQ progress %, material budget vs actual,
  receivables/payables + **ageing**).
- **Accounts** — GST registers (output incl. RA/running bills, input, HSN
  summary), TDS register, chart of accounts, journal, trial balance, **P&L +
  balance sheet**, auto-posting (tax/vendor invoices, payments, sub bills,
  payroll, RA/running bills).
- **Platform** — offline single-file SQLite, multi-firm/multi-year company
  files, backup + synced-folder backup, optional login/roles/audit, first-run
  wizard, minimal-typing entry, Hindi/Hinglish UI, app-wide error handler, RAG
  assistant, a 58-case test suite.

**This is already a Level 1→3 system on the maturity ladder.** The gaps below are
the *control gates* and *document-control* pieces that turn record-keeping into
enforced process.

---

## 3. Coverage map (SOP domain → status → gap → required modification)

| SOP domain (research §) | Today | Status | Gap | Required modification | Pri |
|---|---|---|---|---|---|
| Estimating / rate library (§2.1) | Estimates + Rate Book | ✅ | No estimate **review/approval** step; no bid/no-bid checklist | Add an approval status + reviewer to estimates; a simple bid/no-bid scorecard | P2 |
| Pre-construction set-up (§2.2) | Contracts, Projects, budget, Gantt | 🟡 | No **baseline vs actual** programme; no procurement plan / mobilization checklist | Baseline schedule snapshot + slippage; a project set-up checklist | P2 |
| **Procurement chain (§2.3)** | PO, Vendor Invoice, reconciliation | 🟡 | No **requisition** and no **GRN** (goods receipt) gate; material IN is manual, not tied to a PO; no 3-quote / approved-vendor rule | **Requisition → PO → GRN → invoice** flow; GRN posts the material-ledger IN against the PO; capture 3 quotes; approved-vendor flag + rating | **P0/P1** |
| Material stores & reconciliation (§2.3) | Ledger + stock + consumption recon | ✅ | Issue is manual (no indent gate) | Optional issue-against-indent; low-stock flag | P2 |
| Subcontractor billing (§2.4) | Work orders + sub bills | ✅ | No sub-level variation | Fold into the variation register (below) | P1 |
| Site execution / production (§2.5) | DPR | 🟡 | No **weekly look-ahead / PPC**; no daily huddle log; no labour productivity vs norm | Light **Last Planner** look-ahead with Percent-Plan-Complete; productivity view | P1 |
| **Document control (§2.6)** | — | ❌ | No **variation/change-order**, **RFI**, **drawing revision**, or notice register | **Variation register linked to billing** (P0); RFI + drawing-revision log (P2, PMC work) | **P0**/P2 |
| Quality QA/QC (§2.7) | Cube/material test registers | 🟡 | No **ITP / hold-points**, no **NCR** loop | **ITP checklist** per activity with hold/witness points; NCR log with CAPA | P1 |
| HSE (§2.8) | — | ❌ | No induction / toolbox / permit / incident | Lightweight safety module (often informal for T2/T3) | P2 |
| Cost control & billing (§2.9) | RA bills, deviation, tax invoice, retention on bills | 🟡 | No **retention release / DLP** tracking; no **CVR** by cost head; no variation register | Retention register + release tracking; **cost-value reconciliation** per project by cost head; variation register (above) | **P0/P1** |
| **Financial & cash flow (§2.10)** | Cash book, ageing, GST/TDS | 🟡 | **Cash-flow forecast** missing; **payment↔bill linking** is schema-only (no UI) → ageing is approximate | **Payment-against-bill allocation UI** (schema exists) → reconciled ageing; **cash-flow forecast** (projected inflows vs outflows) | **P0** |
| Plant & equipment (§2.11) | Equipment hire | 🟡 | No preventive-maintenance schedule / fuel / idle log | PM schedule + fuel log (own plant) | P2 |
| Closeout (§2.12) | Milestones | ❌ | No **snag/punch list**, as-built/O&M, **lessons-learned** | Snag list; lessons-learned → rate-library feedback | P2 |
| Support / compliance (§2.13) | Backup, multi-firm, security, audit | 🟡 | No **compliance calendar** (GST/TDS/PF due dates) | Due-date reminders panel | P2 |
| KPIs & dashboards (research §8) | Home + Insight | 🟡 | No consolidated KPI view (PPC, DSO, CVR, % spend-under-PO, unbilled-variation) | A KPI dashboard reading existing data + the new registers | P1 |

---

## 4. Prioritized modification backlog

### P0 — the biggest cash/revenue leaks (do first)

1. **Variation / Change-Order register, linked to billing** _(§2.6/2.9, effort M)_
   - **Why:** Unbilled/undisputed variations are the single largest source of
     *unrecovered revenue* in contracting. Verbal "extra work" that is never
     priced and certified is money lost.
   - **What:** A register of variations per contract — description, quantity,
     rate, status (Raised → Approved → Billed), and a link into the RA/tax
     bill. A gate: *no extra item executed without an approved variation.*
   - **Data note:** new `variations` table; reuses BOQ/RA billing patterns.

2. **Payment ↔ bill/invoice allocation (reconciled ageing)** _(§2.10, effort S–M)_
   - **Why:** The schema already carries `payments.against_type/against_id` but
     **there is no UI**, so receivables/payables and ageing are *approximate*
     (billed-minus-received), not *reconciled* (which specific bills are open).
     The ROADMAP already flags this as the top open item.
   - **What:** When recording a receipt/payment, allocate it against one or more
     open bills/invoices; drive ageing and "who owes what" from real allocation.

3. **Cash-flow forecast** _(§2.10, effort M)_
   - **Why:** Construction fails on **liquidity, not profitability**. Contractors
     need to see a shortfall weeks ahead.
   - **What:** Projected **inflows** (certified/expected bills by expected date)
     vs **outflows** (vendor/sub payables, payroll, hire) on a weekly/monthly
     horizon, with a running projected balance.

4. **Requisition → PO → GRN gate** _(§2.3, effort M–L)_
   - **Why:** Procurement over phone/WhatsApp with no PO is the #1 leakage; and
     material-ledger IN today is hand-entered, disconnected from the PO.
   - **What:** A material **requisition** (site asks) → PO (approved) → **GRN**
     (gate at receipt; GRN writes the ledger IN and enables 3-way match PO↔GRN↔
     invoice). Optional 3-quote capture + approved-vendor flag.

### P1 — control & quality

5. **Retention register + release/DLP tracking** _(§2.9, effort S–M)_ — total
   retention withheld (client-side receivable, sub-side payable), release on
   milestone / defect-liability-period expiry, with reminders.
6. **Cost-Value Reconciliation (CVR) per project** _(§2.9, effort M)_ — cost
   incurred vs value earned by cost head (material/labour/plant/subcontract),
   period over period, to catch a loss-making job early. (Extends Insight.)
7. **ITP / QA hold-point checklists + NCR log** _(§2.7, effort M)_ — per-activity
   inspection checklists with hold/witness points (pre-pour, pre-cover) and a
   non-conformance log with corrective/preventive action.
8. **Weekly look-ahead / PPC** _(§2.5, effort M)_ — a light Last-Planner view:
   weekly commitments, constraint flags, and **Percent Plan Complete** as a
   reliability KPI.
9. **Approval gates (workflow, not just status text)** _(best practice #3, effort
   M, cross-cutting)_ — estimate review, PO approval, bill certification as real
   gates with an approver and timestamp (leverages the existing roles).
10. **KPI dashboard** _(§8, effort S–M)_ — PPC, DSO/ageing, CVR, % spend-under-PO,
    unbilled-variation value, first-time-pass inspection %.

### P2 — completeness (lower urgency for T2/T3)

11. **RFI + drawing-revision register** _(§2.6)_ — mainly for firms doing PMC /
    departmental work; latest-revision-on-site discipline.
12. **HSE module** _(§2.8)_ — induction, toolbox talks, permit-to-work, incident/
    near-miss log (often informal at this scale).
13. **Project closeout** _(§2.12)_ — snag/punch list, lessons-learned feeding the
    rate library, final account.
14. **Vendor management depth** _(§2.3)_ — 3-quote comparison, approved-vendor
    list, performance rating.
15. **Plant PM schedule + fuel log** _(§2.11)_; **compliance calendar** _(§2.13)_;
    **bid/no-bid scorecard** + **estimate approval** _(§2.1)_; **baseline-vs-actual
    programme** _(§2.2)_.

---

## 5. Cross-cutting recommendation: turn *documents* into *gates*

The research's strongest single lesson is **"gate, don't hope."** Construction OS
already stores most records; the highest-leverage change is to make the SOP step
**unskippable**:

- No payment without a GRN (procurement).
- No extra work without an approved variation (revenue protection).
- No pour without a QC hold-point sign-off (quality).
- No sub work without a work order (already enforced ✅).

These are small UI/state additions on top of existing data, and they convert the
app from a *ledger* into a *process*.

---

## 6. Explicit non-goals for the T2/T3 audience

To protect the founding thesis (offline, single-PC, minimal-typing, no-pip),
**do not** build: BIM/model coordination, IoT/drones/sensors, predictive/AI
analytics beyond the local assistant, heavy multi-user cloud sync, or
corporate-style multi-level approval chains. These are Level-4 features that add
cost and friction without helping a solo contractor bill, get paid, and stay in
control.

---

## 7. Suggested sequencing

1. **Wave 1 (revenue & cash):** Variation register → Payment-to-bill allocation →
   Cash-flow forecast. _(Directly attacks the top three money leaks; mostly reuses
   existing patterns/tables.)_
2. **Wave 2 (procurement control):** Requisition → GRN gate + retention register.
3. **Wave 3 (quality & planning):** ITP/NCR + weekly look-ahead/PPC + KPI
   dashboard.
4. **Wave 4 (completeness):** RFI/drawings, HSE, closeout, vendor depth, plant PM,
   compliance calendar.

Each wave is independently shippable and independently useful — matching the
phase-by-phase discipline already in the ROADMAP.

---

## 8. Summary

Construction OS covers the **operational, commercial, billing, money, and
accounting** spine well for its audience. The material gaps are concentrated in
**document-control gates** (variations above all), **reconciled cash/receivables**
(payment-to-bill linking + cash-flow forecast), and the **procurement receipt
gate** (GRN). Closing the P0 set would remove the three largest sources of lost
revenue and liquidity surprise for a small contractor — with modest effort,
because the data model is largely already in place.

See `docs/SOP-manual.md` for the operating procedures these features should
enforce.
