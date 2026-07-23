# ACO — Research (single report)

**Date:** 2026-07-23 · **One document** replacing separate competitive, Fluent UI,
SOP-practice, and CPWD primary-source research files.  
**Status of work:** [`ROADMAP.md`](ROADMAP.md) only.  
**Product box:** [`PRODUCT.md`](PRODUCT.md) · Brand: [`BRAND.md`](BRAND.md) ·
Fluent checklist: [`UI-PRINCIPLES-AND-GUIDELINES.md`](UI-PRINCIPLES-AND-GUIDELINES.md)

---

## 1. Market box

| Attribute | ACO |
|---|---|
| Buyer | T2/T3 Indian civil contractor, ~₹20L–₹5Cr, 1–5 sites |
| Mental model | Cash in / out / “kitna baaki” |
| Deployment | Offline-first, one SQLite file |
| Differentiator | BOQ → MB → RA → CPWA forms + GST/TDS + cash book, no SaaS tax |
| Non-fit | Large EPC, multi-branch enterprise, cloud-only |

White space: *PWD-ready billing + kitna-baaki on your PC*, with EVM/PPC/risk
available without enterprise ceremony.

---

## 2. Competitive landscape (condensed)

### India

| Segment | Tools | Lesson |
|---|---|---|
| Micro | **Tally** + Excel | Stay cash-first; **export for the CA**; don’t force ledger-first |
| Small ERP | Odoo / ERPNext | Win on **zero implementation theatre** + native civil forms |
| Mid civil | CONWORX, BuildNext, Xpedeon, ProjectsNext-class | Offline + RA; steal **Tally-bridge** story, not RFID/VR |
| Enterprise | Ramco, biCanvas, SAP | **Anti-pattern** for T2 — complexity kills adoption |

Buyers repeatedly need: measurement-true RA, GST without a second sheet, material
reconciliation, offline site sync, retention/advances, something the munshi opens
daily. Field stack today is often **Excel (qty) + Tally (books)** — collapse the
split without becoming Tally.

### Global (lessons only)

Procore / Buildertrend: price creep, export lock-in, implementation burden,
accounting glue breaks trust. JobTread: clarity without enterprise bloat.  
**Reject:** SaaS per-seat mandatory cloud, AI autopilot on payments.

### Lean / LPS (forums)

PPC = commitments kept ÷ made — **binary Done** (no partial credit); **reason
codes** on misses (materials, predecessor, labour, weather, over-commit, …).
CPM ≠ weekly commitments. Target culture ~80%+ PPC; don’t game the metric.

---

## 3. CPWD / CPWA + SOP spine (what to encode)

Canonical Indian chain: **MB → RA bill → retention/SD recovery → final bill**.

| Finding | Product implication |
|---|---|
| MB is the legal basis for payment (Form 23); CMB ok for works ≥ ₹15L | MB-format print is a **deliverable**, not a nicety |
| Form 26 Memorandum of Payments (taxes / SD / other → cheque) | Keep Form 26 recoveries exact |
| Muster Form 21 (+ 21A unpaid wages) | Two-part muster + payout discipline |
| Retention: ~5% PG + ~2.5%/bill (state variance) | Configurable SD ledger + release |
| DAR rate analysis: material+labour+sundries → +1% water → +15% CPOH | Rate-analysis builder (shipped skeleton) |
| LPS weekly plan + PPC | Look-ahead page: binary Done + reasons |
| RA quality gates (tests / MAS with bills) | Link QC registers → bill-ready |

**Caveats:** DAR rates age; cite **governing contract** for payment timelines;
state PWDs vary — CPWD as defaults.

**SOP adoption rule:** short, plain language, embedded in the tool, enforced by
gates — not binders. India T2 reality: WhatsApp + Excel + owner’s head; digitise
the **cash + MB/RA + muster** loops first.

Operational checklists: [`SOP-manual.md`](SOP-manual.md).

---

## 4. Fluent / WinUI appearance (condensed)

Microsoft hub: [Design Windows apps](https://learn.microsoft.com/en-us/windows/apps/design/).  
Principles: Effortless · Calm · Personal · Familiar · Complete+Coherent.

| Topic | Policy |
|---|---|
| Accent | Radiant Orange `#FF4F18` = CTA/selection only (3.29:1 → large text/fills) |
| Severity | System Critical/Caution/Success — never brand orange |
| Theme | **Light / Dark / System** (shipped — Fluent *Personal*) |
| Materials | Prefer Mica when crash-safe; else honest theme brushes; Acrylic flyouts; Smoke dialogs |
| Type | Segoe UI Variable + type ramp; sentence case |
| Geometry | Fluent radii on WinUI; do **not** clone tkinter 0-radius / Urbanist |
| Shell | Owner Excel-style ribbon OK if ≤8 peers, clear labels, no pogo-stick |
| Writing | Warm, helpful, crisp; you/we; errors with next step |

Dual-skin: share **accent + voice**; native chrome per shell.

Implementation checklist: [`UI-PRINCIPLES-AND-GUIDELINES.md`](UI-PRINCIPLES-AND-GUIDELINES.md).

---

## 5. Implications → ROADMAP (do not duplicate status here)

Priorities live only in [`ROADMAP.md`](ROADMAP.md) §2:

- **P0** WinUI civil/labour honesty: BOQ/MB/RA, subcontractors, AI Engine, GRN match, muster payout  
- **P1** Gantt, Tools depth, a11y walkthrough, release signing  
- **P2** Mica revisit, breadcrumbs, empty/loading coherence  
- **P3** CA export pack, PPC reason depth, risk accept-from-detect  
- **P4** L8 weights, takeoff on WinUI, retire tkinter (product call)

---

## 6. Sources (non-exhaustive)

- Construction Estimator India / Tech4LYF — India ERP comparisons 2025–26  
- ProjectsNext / CONWORX / BuildNext positioning; Procore vs Buildertrend 2026 reviews  
- LCI Last Planner Standard Work; LookAheadWall PPC notes  
- CPWD Works Manual; CPWA Book of Forms; DAR / Analysis of Rates  
- [Microsoft Learn — Windows apps design](https://learn.microsoft.com/en-us/windows/apps/design/)  
- Quora / practitioner threads — Excel + Tally billing stack  

---

*Single research report. Do not re-split into parallel audit/roadmap docs.*
