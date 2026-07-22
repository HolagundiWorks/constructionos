# Construction OS — Enterprise PM: Gap Identification & Implementation Roadmap

**From today's solo-contractor product to the enterprise PM + AI target**

_Document type: Gap analysis + Implementation roadmap (documentation only — no code changes)_
_Version: 1.0 · Last updated: 2026-07-21 · Prepared by: Human Centric Works_
_Companion to [`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md) (the target
architecture & AI strategy). Baseline: `main` — 60 Python modules, 45+ tables._

---

## 1. Purpose & method

This document does two things:

1. **Gap identification** — a concrete, honest inventory of the distance between
   **what Construction OS is today** and the **enterprise PM + AI target** set out
   in [`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md).
2. **Implementation roadmap** — a phased, dependency-ordered plan to close those
   gaps, with per-phase deliverables, acceptance criteria, and the architectural
   rules each phase must respect.

It is a **planning document only.** Nothing here has been coded, and it commits
no team to a date. It reuses the conventions of the existing
[`REPORT-sop-gap-analysis.md`](REPORT-sop-gap-analysis.md) so the two read as a
set.

**Legends used throughout:**

- **Status:** ✅ Built · 🟡 Partial (Extend) · ❌ Missing (Proposed)
- **Priority:** **P0** (foundational / blocks other work) · **P1** (high value) ·
  **P2** (completeness / lower urgency)
- **Effort:** **S** (a module + tab) · **M** (medium) · **L** (large / multi-part)
- **Type:** **Core** (deterministic maths, must be a pure testable module) ·
  **AI** (assistive/explainable layer) · **Platform** (scale-out / infrastructure)

**The framing tension (stated up front, as in the solution doc).** The shipped
product is *deliberately* scoped to the solo T2/T3 contractor and *explicitly not*
enterprise (see [`PRODUCT.md`](PRODUCT.md) §2, and the non-goals in the SOP
report §6). This roadmap describes an **enterprise tier that grows from the same
code**; it does **not** propose degrading the offline, single-PC, minimal-typing
core that solo users depend on. Every gap below is labelled so a reader can tell
"missing for enterprise" from "intentionally out of scope for solo."

---

## 2. Baseline — what already exists (do not rebuild)

The domain core is unusually complete. Confirmed present and strong:

- **Schedule** — CPM, critical path, baseline vs actual, float, LD/EOT
  (`cpm.py`, `programme.py`, `tab_timeline.py`).
- **Cost** — budget vs cost, margin, per-project drill-down (`projectcost.py`,
  `tab_projects.py`); material budget variance (`analytics.py`).
- **Commercial / billing** — BOQ → Measurement Book → RA bills, deviation,
  variations, retention (`tab_boq_ra.py`, `mb.py`, `variation.py`,
  `retention.py`).
- **Procurement** — Requisition → PO → GRN 3-way match (`procurement.py`,
  `tab_grn.py`, `sourcing.py`).
- **Quality / safety / closeout** — ITP hold-points, NCR, snags, HSE
  (`quality.py`, `hse.py`, `closeout.py`).
- **Money & finance** — cash book, payment↔bill allocation, ageing, cash-flow
  forecast, GST/TDS, double-entry auto-posting (`allocation.py`, `ageing.py`,
  `cashflow.py`, `finance.py`, `journal_post.py`).
- **KPI & advisory** — KPI board, Insight, rule-based advisory with
  confidence + basis (`tab_kpi.py`, `tab_insight.py`, `advisory.py`).
- **AI assistant** — local, offline, read-only NL→SQL with TF-IDF retrieval
  (`assistant.py`).
- **Platform** — offline single-file SQLite, multi-firm/multi-year, roles +
  audit + approvals, browser/LAN access, first-run wizard, error handler, test
  suite (`db.py`, `auth.py`, `approval.py`, `webapp.py`).

**Conclusion:** the gap to "enterprise PM + AI" is **not domain logic** — it is
(a) a small set of deterministic *analytics* additions, (b) *scale-out* platform
work, and (c) the *AI automation & prediction* layer. Sections 3–5 enumerate
exactly those.

---

## 3. Gap identification

Gaps are grouped by the four AI jobs from the solution doc, plus the platform
foundation they all sit on. Each row: the target, today's status, the specific
gap, its impact, and the required work.

### 3.1 Foundation & platform gaps

| Target | Status | Gap | Impact | Required work | Pri · Effort · Type |
|---|---|---|---|---|---|
| Portfolio roll-up across projects/firms | 🟡 | Per-project drill-down exists; no cross-project read model | No single view of a portfolio of sites; every KPI is per-file | Federated read model over firm/year files (offline-safe) | P0 · L · Platform |
| Earned Value Management (SPI/CPI/EAC) | 🟡 | Pure maths now built (`earnedvalue.py` + tests); not yet surfaced in a tab | Forecast-at-completion computable; cost KPIs still point-in-time in the UI | Surface `earnedvalue` in Insight/KPI; feed portfolio roll-up | P0 · M · Core |
| Formal risk register + scoring | 🟡 | Scoring (`risk.py`) + persistence (`risks` table, `risk_store.py`) now built + tested; only the tab is pending | Risks can be stored, scored, owned, and audited; not yet on screen | A tkinter tab over `risk_store` | P0 · S · Core |
| Concurrency / multi-user at scale | 🟡 | WAL + busy_timeout + LAN web; single-file assumptions remain | Contention under many concurrent field users | Concurrency review; roll-up store; conflict handling | P1 · L · Platform |
| Mobile field capture | 🟡 | Browser/LAN read + some entry; no mobile-optimised capture | Field data still typed later at a desk — the root cause of stale data | Mobile capture app feeding the capture pipeline (§3.2) | P1 · L · Platform |
| AI-origin tagging in audit | 🟡 | Audit log exists; doesn't distinguish AI-drafted records | Can't audit "what did the AI touch and who confirmed it" | Tag AI-origin + confirming user on records | P1 · S · Platform |
| Enterprise identity (SSO, project roles) | ❌ | Roles Admin/Operator/Viewer built; no SSO or per-project scoping | Larger orgs need finer access; solo users need none | Optional SSO + per-project role scoping (opt-in) | P2 · M · Platform |

### 3.2 AI Job 1 — Eliminate manual data entry (capture)

| Target | Status | Gap | Impact | Required work | Pri · Effort · Type |
|---|---|---|---|---|---|
| Photo → GRN / vendor-invoice draft (OCR) | ❌ | Manual entry only | Largest source of typing + transcription error | OCR + doc-parse → draft record, confidence per field | P1 · L · AI |
| Voice → DPR / measurement draft | ❌ | Manual entry only | Field notes captured hours late at a desk | Speech-to-text → entity extraction → draft | P1 · M · AI |
| Photo of muster → attendance draft | ❌ | Manual grid entry | Repetitive daily typing; name errors | OCR + match to labour master → draft grid | P2 · M · AI |
| BOQ / tender PDF → import draft | ❌ | Manual BOQ entry | Slow, error-prone tender onboarding | Document parse → line items + rates → draft | P2 · M · AI |
| Free-text (WhatsApp) → structured record | ❌ | Manual re-keying | Updates live in chat, never in the system | NL extraction → typed draft (site report / issue) | P2 · M · AI |

**Cross-cutting design (must hold for all capture):** AI produces a *draft* into
the existing `CrudFrame`/`DocumentFrame`; every field editable; per-field
confidence; matches resolve against masters as ground truth; graceful fallback
to the normal low-typing form when capture is unavailable (offline-first stays
true).

### 3.3 AI Job 2 — Automate repetitive tasks

| Target | Status | Gap | Impact | Required work | Pri · Effort · Type |
|---|---|---|---|---|---|
| Event-driven follow-on chaining | 🟡 | Some deterministic chaining built (idempotent posting) | Rote follow-ups done manually + inconsistently | Event hooks + drafted follow-on artefacts, human-gated | P1 · M · AI/Core |
| Recurring project-review pack generation | ❌ | Reviews assembled by hand | Weekly review is a multi-day scramble | Auto-generate KPI + narrative + risk pack (draft) | P1 · M · AI |
| Mismatch / exception narration | 🟡 | 3-way match flags exist; no narration | Users read raw flags, miss the "why" | Narrate exceptions from structured numbers | P2 · S · AI |
| NL-triggered workflows | ❌ | NL assistant is read-only | Can't say "close snags + draft handover" | Map NL intent → concrete gated steps | P2 · M · AI |

**Guardrail:** anything that moves money, files with a department, or changes a
contractual date is **always a draft a human approves** — automation removes
assembly toil, never accountability.

### 3.4 AI Job 3 — KPI measurement & narration

| Target | Status | Gap | Impact | Required work | Pri · Effort · Type |
|---|---|---|---|---|---|
| Deterministic KPI set (schedule/cost/cash/quality) | ✅ | Broadly complete | — | Maintain | — |
| EVM KPIs (SPI, CPI, EAC) | 🟡 | Maths built (`earnedvalue.py`); not surfaced | Predictive cost view computable, not yet on screen | Surface `earnedvalue` (shared with §3.1) | P0 · M · Core |
| Portfolio KPI roll-up | 🟡 | Per-project only | No portfolio health at a glance | Roll-up over federated read model | P0 · M · Core |
| KPI narration (plain-language briefing) | ❌ | Numbers shown, not narrated | Users must interpret raw boards | Generate sentences over computed numbers, cite source | P1 · M · AI |
| Portfolio anomaly watch | 🟡 | Advisory is single-firm | Meaningful moves missed across many sites | Extend advisory to portfolio; surface only material moves | P1 · M · AI |
| Forecasting (completion date, cost) | ❌ | Point-in-time only | No forward view | Trend projection as range + confidence | P2 · M · AI |
| Productivity KPIs (crew/day, plant util.) | 🟡 | Muster + plant data exist | Underused signal | Derive from muster/`plant.py` | P2 · S · Core |

**Guardrail:** every AI KPI statement traces to the deterministic figure behind
it — the shipped `basis`/`confidence` discipline applied to narration.

### 3.5 AI Job 4 — Risk analysis

| Target | Status | Gap | Impact | Required work | Pri · Effort · Type |
|---|---|---|---|---|---|
| Risk register + likelihood×impact scoring | 🟡 | Scoring (`risk.py`) + persistence (`risks`, `risk_store.py`) built + tested; tab pending | Risks storable/scored/owned/audited; not yet on screen | A tab over `risk_store` (shared with §3.1) | P0 · S · Core |
| Rule-based risk detection taxonomy | 🟡 | Advisory rules exist, unnamed as risks | No consistent risk vocabulary | Promote advisory rules into a named risk taxonomy | P1 · M · Core |
| Risk narrative (top-N by exposure) | ❌ | No narrative | Hard to see the portfolio's top risks | Ranked plain-language risk summary | P1 · S · AI |
| Predictive / early-weak-signal risk | ❌ | Threshold rules only | Drift caught late, after a threshold trips | Correlate soft signals; trend projection (range+basis) | P2 · L · AI |
| Cross-project learning | ❌ | None | Past overruns don't inform new jobs | Opt-in, local-first pattern learning | P2 · L · AI |

**Guardrail:** no risk flag without a stated basis; AI *detects & ranks*, a human
*owns* the mitigation and the accept/dismiss decision (logged).

---

## 4. Gap prioritisation (the short list)

Reading across §3, the highest-leverage gaps — those that either **unblock other
work** or **deliver the most value per unit effort**:

**P0 — foundational (do first; everything else leans on these):**

1. **EVM pure module** (`earnedvalue.py`) — unblocks predictive cost KPIs *and*
   cost-overrun risk detection. Pure maths, inputs already exist. _(M · Core)_
2. **Risk register + scoring schema** — the container every risk capability
   writes into. _(M · Core)_
3. **Portfolio federated read model** — unblocks all portfolio roll-up KPIs and
   portfolio-wide advisory/risk, without breaking offline-first. _(L · Platform)_

**P1 — high value (the visible payoff):**

4. **Capture pipeline** (photo→GRN/invoice, voice→DPR) — the biggest cut to
   manual entry and the fix for stale data. _(L · AI)_
5. **KPI narration + portfolio advisory** — turns boards into a five-minute read.
   _(M · AI)_
6. **Risk detection taxonomy + narrative** — the early-warning payoff. _(M · AI)_
7. **Recurring review-pack generation** — automates the weekly scramble. _(M · AI)_

**P2 — completeness:** predictive forecasting, NL-triggered workflows, mobile
field app, cross-project learning, SSO/project roles, muster OCR, BOQ import.

---

## 5. Implementation roadmap

The phases below map 1:1 to the E0–E6 sequence in
[`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md) §10, expanded here with
deliverables, dependencies, and acceptance criteria. Each phase is
**independently shippable and independently useful** — matching the phase
discipline already in [`ROADMAP.md`](ROADMAP.md).

**Implementation status at a glance** (what has been built as verifiable,
headless-tested modules vs. what remains). The **deterministic backbone of E0–E5
is built** — every piece that could be written and unit-tested without a display,
a model, or a pip dependency:

| Phase | Built (module) | Remaining |
|---|---|---|
| **E0** | `earnedvalue.py`, `risk.py`, `risk_store.py` + `risks` table | risk tab (GUI); wider audit tagging |
| **E1** | `capture.py` (draft-and-confirm framework) | the OCR/voice/vision **models** (external sidecars) + tabs |
| **E2** | `narrative.py`; `review_pack.py` roll-up; `portfolio_store.py` (federated read model) | tabs |
| **E3** | `risk_detect.py` (11 rules + mitigation drafts), `narrative.risk_briefing` | risk tab |
| **E4** | `review_pack.py` (pack + portfolio); `followups.py` (event → follow-on logic) | GUI event wiring |
| **E5** | `forecast.py` (trend + schedule); `drift.py` (weak-signal correlation) | feed forecasts into the register (tab) |
| **E6** | — | mobile capture app (separate front-end) |

**The deterministic roadmap is complete.** Every piece that can be written and
unit-tested without a display, a model, or a pip dependency is built (591-test
suite). The irreducible residual is exactly three things this environment cannot
produce or verify — and none is application logic:

1. **tkinter tabs** — the on-screen registers and KPI/EVM surfacing. Need a
   display to smoke-test (this container has no `tkinter`). The data, scoring,
   and roll-ups behind every tab are done.
2. **The ML models themselves** — OCR / speech-to-text / VLM for capture, and
   the LLM that re-voices narration. These are **external local sidecars** by
   design (see [`AI-MODELS-AND-DEPLOYMENT.md`](AI-MODELS-AND-DEPLOYMENT.md)), not
   code in this repo; `capture.py` is the deterministic scaffold they feed.
3. **The E6 mobile app** — a separate front-end project.

The full-run's single error is the pre-existing missing-`tkinter` GUI theme test,
unrelated to this work.

### Phase E0 — Foundation _(P0 · deterministic core first)_

**Goal:** lay the deterministic groundwork that every later phase reads from.

- **E0.1 EVM module ✅ (built)** — `earnedvalue.py`: PV, EV, AC → SPI, CPI, SV,
  CV, EAC (three methods), ETC, VAC, TCPI, percent-complete/spent, and a
  value-weighted `portfolio` roll-up. Pure, tkinter/DB-free, 8 unit tests in
  `tests/test_core.py` (`TestEarnedValue`). Inputs map to `programme` (baseline
  → PV), `analytics.contract_progress` (measured value → EV), `projectcost`
  (total cost → AC). _Remaining: surface it in Insight/KPI (E2)._
- **E0.2 Risk scoring ✅ + register persistence ✅ (built) / tab ⏳** —
  `risk.py`: 5×5 likelihood×impact scoring, bands (Low/Medium/High/Critical),
  probability-weighted expected exposure, residual-after-mitigation, ranking and
  a register summary (pure, 8 unit tests, `TestRisk`). `risks` table added to
  `db.py` (additive, cascades on project delete) and `risk_store.py` — a
  conn-taking, tkinter-free persistence layer that derives score/band/exposure
  on every save through `risk.py` (so stored values can't drift) and re-assesses
  from raw levels in `summary` (so a hand-edited row still rolls up honestly).
  7 DB-backed unit tests against a temporary SQLite database (`TestRiskStore`).
  _Remaining: a tkinter tab over the store — deferred because it needs a display
  to verify._
- **E0.3 AI-origin audit tagging ⏳** — the `risks` table already carries a
  `source` (`manual`/`ai`) and `decided_by`/`decided_date`; extending the app-wide
  audit log to tag AI-drafted origin on other records is not yet started.

**Depends on:** existing analytics/cost/programme (present).
**Acceptance:** EVM figures reconcile against a worked example in tests ✅; risk
scoring/exposure/ranking unit-tested ✅; the register persists, derives on save,
and cascades on project delete, all against a real temp database ✅; no new pip
dependency ✅; full suite passes (the one environment error is the pre-existing
missing-`tkinter` GUI theme test, unrelated to this work). _The risk tab and
wider audit tagging remain open._

### Phase E1 — Capture _(P1 · cut manual entry)_

**Goal:** turn field input (photo, voice, document) into draft records.

- **E1.1 Draft-and-confirm framework** — a shared path that takes an extracted
  field set, pre-fills the existing entry form, marks per-field confidence, and
  requires human save. Reusable across all capture types.
- **E1.2 Photo → GRN / vendor-invoice** — OCR + document parse → draft feeding
  the built 3-way match.
- **E1.3 Voice → DPR / measurement** — speech-to-text → entity extraction →
  draft site report / measurement line.

**Depends on:** E0.3 (audit tagging); masters as ground truth (present). Requires
an AI capability decision (local model vs opt-in cloud) — see §6.
**Acceptance:** a delivery challan photo produces a GRN draft with >0 fields
correctly pre-filled and every field editable; capture failure falls back to the
normal form with no error; nothing is written without a human save; local/offline
path works or degrades cleanly.
**Built:** E1.1 the draft-and-confirm framework (`capture.py` — stages a model's
extracted fields as an editable draft with per-field confidence, flags the
low-confidence ones for review, folds in human overrides at full confidence, and
only then yields a record to save; nothing is ever written on its own) ✅.
_Remaining:_ E1.2/E1.3 the actual OCR / speech-to-text / VLM extractors — these
are **external local model sidecars** (see
[`AI-MODELS-AND-DEPLOYMENT.md`](AI-MODELS-AND-DEPLOYMENT.md)), not code in this
repo; `capture.py` is the deterministic scaffold they feed, and it is built and
tested independently of any model.

### Phase E2 — KPI reach _(P0/P1 · portfolio + narration)_

**Goal:** see the whole portfolio and read it in plain language.

- **E2.1 Portfolio read model** — federated, offline-safe roll-up across
  firm/year files; each project keeps its authoritative file.
- **E2.2 Portfolio KPI roll-up** — schedule/cost/cash/quality KPIs (incl. EVM
  from E0.1) aggregated across projects.
- **E2.3 KPI narration** — plain-language weekly briefing generated over the
  computed numbers, each statement citing its source figure.
- **E2.4 Portfolio advisory** — extend `advisory.py` from one snapshot to the
  portfolio; surface only material moves.

**Depends on:** E0.1 (EVM), E0.2 (register for risk-linked KPIs).
**Acceptance:** a portfolio of ≥2 projects rolls up correctly and matches the sum
of per-project figures; every narrated sentence links to a deterministic number;
a site with no network still shows its own KPIs.
**Built:** E2.1 federated read model (`portfolio_store.py` — opens each firm/year
file **read-only** and pools projects, risk exposure, opportunity upside and
lessons across them; each file stays authoritative, preserving offline-first) ✅;
E2.2 roll-up (`earnedvalue.portfolio`, value-weighted; pooled via
`review_pack.portfolio`) ✅; E2.3 narration (`narrative.kpi_briefing`) ✅; E2.4
portfolio advisory (pooled `advisory` counts) ✅. _Remaining:_ the tab (display).

### Phase E3 — Risk _(P1 · early warning)_

**Goal:** make risk a first-class, explainable, portfolio-spanning capability.

- **E3.1 Risk detection taxonomy** — promote the advisory rules into a named risk
  taxonomy; add project-level rules (critical-path slip, CPI<1 from E0.1, cash
  forecast negative, ageing concentration, consumption over norm, filing due,
  low PPC, open high-severity NCR/incident). Each writes to the register with its
  basis.
- **E3.2 Risk narrative** — ranked "top-N risks by exposure (₹/days), why, and
  what to do" across the portfolio.
- **E3.3 Mitigation drafts** — a suggested mitigation per detected risk (draft,
  human-owned).

**Depends on:** E0.1, E0.2, E2.1.
**Acceptance:** each detected risk lands in the register with a stated basis and
severity/confidence; a user can answer "why am I seeing this?" from the rule +
numbers; AI never auto-closes or auto-accepts a risk.
**Built:** E3.1 detection taxonomy (`risk_detect.py` — 11 snapshot rules across
schedule/cost/commercial/quality/statutory/external, each scored via
`risk.assess`, `source='ai'`, ranked, with a basis) ✅; E3.2 risk narrative
(`narrative.risk_briefing`, top-N by exposure) ✅; E3.3 mitigation drafts
(`risk_detect.suggest_mitigation` / `with_mitigations` — a suggested response +
first action per category, a draft the owner edits) ✅. Detected risks are
register-ready (`risk_store.add(..., source='ai')`). _Remaining:_ the risk tab.

### Phase E4 — Automation _(P1 · remove rote assembly)_

**Goal:** chain the follow-on work a record triggers; automate the review pack.

- **E4.1 Event-driven follow-on** — on key events (GRN saved, activity complete,
  filing approaching), draft the follow-on artefacts (revised look-ahead, filing
  checklist, chaser), human-gated for anything consequential.
- **E4.2 Recurring review-pack generation** — assemble the weekly project/portfolio
  review (KPIs + narrative + risk) as a reviewable draft.

**Depends on:** E1 (capture), E2 (KPIs/narration), E3 (risk).
**Acceptance:** the weekly pack generates from live data with no manual assembly;
every money/date-moving action remains a draft requiring approval; automations
are logged with AI-origin (E0.3).
**Built:** E4.2 review-pack generation (`review_pack.build` assembles KPIs +
advisories + risks + narrative + optional EVM/forecast/opportunities into one
draft dict; `review_pack.portfolio` across projects) ✅; E4.1 event → follow-on
**decision logic** (`followups.py` — maps each event to its rote follow-ups, every
consequential one flagged `gated` so it stays a human-approved draft) ✅.
_Remaining:_ the GUI wiring that fires an event from a save handler.

### Phase E5 — Prediction _(P2 · forward view)_

**Goal:** project forward, honestly.

- **E5.1 Trend forecasts** — completion date and cost-at-completion from
  float-burn and EVM trend, always a range with confidence + basis.
- **E5.2 Early-weak-signal correlation** — combine soft indicators (low-confidence
  measurement runs, repeated small slips, rising RFI age) into a "drifting"
  flag before any single threshold trips.

**Depends on:** E2 (roll-up), E3 (risk register + history).
**Acceptance:** every forecast shows a range and its basis, never a false-precise
point; a forecast feeds the register as a suggestion a human accepts/dismisses;
confidence is labelled honestly (thin history → Low).
**Built:** E5.1 trend forecasts (`forecast.py` — least-squares trend with a
low/value/high band and sample-driven confidence; `schedule_forecast` for
duration/slip; cost EAC in `earnedvalue`) ✅; E5.2 weak-signal correlation
(`drift.py` — pools falling PPC, repeated small slips, rising RFI age and
low-confidence measurements into one low-confidence "drifting" flag, each signal
named with its basis; raised only when ≥2 weak signals agree) ✅. _Remaining:_
feeding a forecast/drift flag into the register as a suggestion (tab).

### Phase E6 — Field mobile _(P2 · capture at the source)_

**Goal:** put capture in the field worker's hand.

- **E6.1 Mobile capture app** — a lightweight mobile front-end feeding the E1
  capture pipeline (voice/photo/quick forms), syncing to the project file.

**Depends on:** E1 (capture pipeline), existing web layer (`webapp.py`).
**Acceptance:** a field user captures attendance/progress/photos on a phone;
records sync to the authoritative file; offline capture queues and reconciles on
reconnect.

---

## 6. Cross-cutting decisions the roadmap forces

Two decisions gate the AI phases and should be settled before E1 starts. These
are genuine forks, not defaults — flagged for an owner to decide:

1. **AI runtime & the no-pip / offline rule.** The shipped assistant runs a
   *local Ollama* model with stdlib-only glue. Capture (OCR, speech-to-text) and
   generation at enterprise quality may exceed what a small local model does
   well. Options: (a) keep strictly local/offline (smaller models, lower
   accuracy, no dependency); (b) opt-in cloud AI per firm (higher accuracy,
   introduces a network dependency and data-egress considerations); (c) a hybrid
   — local floor, cloud opt-in. This choice ripples through every AI phase and
   through privacy/residency guarantees. **Recommend (c): hybrid, local-first,
   cloud opt-in per firm** — preserves the offline guarantee as the floor.

2. **Where portfolio data lives.** Federated read model over local files
   (offline-safe, more engineering) vs a central store (simpler roll-up, breaks
   offline-first). **Recommend the federated read model** to protect the founding
   guarantee that a site keeps working with no network.

Both decisions are documented as recommendations only; neither is made here.

---

## 7. Sequencing & dependencies

```
E0 Foundation ──┬──> E2 KPI reach ──┐
 (EVM, risk     │                   ├──> E4 Automation ──┐
  register,     ├──> E3 Risk ───────┘                    ├──> (mature platform)
  audit tag)    │                                        │
                └──> E1 Capture ────────────────> E6 Mobile
                                                         │
                     E5 Prediction <──(needs E2 + E3 history)
```

- **E0 is the gate** — EVM and the risk register unblock KPI, risk, and
  prediction. Do it first.
- **E1 (Capture) and E2/E3 (KPI/Risk) can run in parallel** after E0 — they share
  no code path.
- **E4 needs E1–E3**; **E5 needs E2–E3 plus accumulated history**; **E6 needs E1.**

**Suggested waves** (each independently shippable):

- **Wave A (foundation):** E0.
- **Wave B (visible value, parallel tracks):** E1 capture ‖ E2 KPI reach ‖ E3 risk.
- **Wave C (leverage):** E4 automation.
- **Wave D (frontier):** E5 prediction, E6 mobile.

---

## 8. Roadmap risks (and mitigations)

Honest risks to *this plan itself*:

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| AI accuracy on capture too low to trust → users revert to typing | Medium | High | Draft-and-confirm keeps a human in the loop; per-field confidence; ship where accuracy is provable (invoices/challans) before muster OCR |
| No-pip / offline constraint clashes with AI quality | Medium | High | Settle §6.1 first; hybrid local-floor + cloud opt-in; label capability honestly |
| Portfolio roll-up erodes offline-first | Medium | High | Federated read model, not central store (§6.2); each project file stays authoritative |
| Scope creep past the solo-user thesis | Medium | Medium | Every enterprise feature opt-in and off by default; solo experience unchanged |
| False-positive risk flags erode trust | Medium | Medium | Basis on every flag; tune thresholds; track false-positive rate as a metric |
| Deterministic maths buried in AI/GUI | Low | High | Enforce: new maths → pure testable module (E0 sets the pattern); source-level test guards |

---

## 9. Non-goals (protect the founding thesis)

Consistent with [`PRODUCT.md`](PRODUCT.md) §2 and the SOP report §6, the
enterprise tier does **not**:

- Force any solo user onto cloud, login, or a network dependency (all enterprise
  features are opt-in, off by default).
- Replace the deterministic core with AI — AI stays assistive and explainable.
- Add pip/native dependencies to the *core*; any AI runtime dependency is
  isolated, opt-in, and never required for the offline floor.
- Auto-commit anything that moves money, files with a department, or changes a
  contractual date — those stay human-approved drafts.
- Pursue BIM/IoT/drones or heavy corporate approval chains beyond what a real
  enterprise construction buyer needs from *this* tool.

---

## 10. Exit criteria & success metrics

The roadmap is "done" for a phase when its acceptance criteria (§5) pass **and**
these hold:

- **Determinism preserved** — every money/schedule figure is computed by a pure,
  unit-tested module; a source-level test guards it.
- **Explainability preserved** — 100% of AI outputs carry a visible basis
  (design invariant, not a trend).
- **Offline floor preserved** — a disconnected site runs its own project
  unchanged.

Outcome metrics to baseline and track (from the solution doc §11):

- Manual data-entry reduction (% records via capture; keystrokes/record).
- Timeliness (median lag: work happening → record existing).
- Risk lead time (days a risk is flagged before it costs money/date).
- KPI review time (target: minutes, from days).
- AI accuracy (drafts accepted without edit; risk false-positive rate).

---

## 11. Summary

The distance from today's Construction OS to an enterprise PM + AI platform is
**short on domain logic and concentrated in three places**: a couple of
deterministic analytics additions (**EVM**, a **risk register**), **scale-out
platform** work (portfolio roll-up, mobile, concurrency), and the **AI layer**
(capture, automation, narration, risk prediction).

The plan closes them in dependency order: **E0 lays the deterministic foundation**
(EVM + risk register + audit tagging); **E1–E3 deliver the visible payoff in
parallel** (capture cuts manual entry, KPI reach makes reviews a five-minute
read, risk gives early warning); **E4 automates the rote assembly**; **E5–E6 add
the frontier** (prediction, mobile). Throughout, the discipline is the one the
shipped code already embodies: **deterministic maths underneath, explainable AI
on top, a human on anything that moves money or a date, and the offline solo
experience never degraded.**

---

_Planning document only — changes no code, commits no dates. Read alongside
[`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md) (the target & AI
strategy), [`REPORT-sop-gap-analysis.md`](REPORT-sop-gap-analysis.md) (the SOP
gap set), [`PRODUCT.md`](PRODUCT.md) (scope & principles), and
[`ROADMAP.md`](ROADMAP.md) (delivered features). Architecture and conventions:
[`../AGENTS.md`](../AGENTS.md)._
