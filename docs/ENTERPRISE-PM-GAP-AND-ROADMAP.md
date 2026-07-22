# Construction OS — Enterprise PM: Gap Identification & Implementation Roadmap

**From today's solo-contractor product to the enterprise PM + AI target**

_Document type: Gap analysis + Implementation roadmap (documentation only — no code changes)_
_Version: 1.1 · Last updated: 2026-07-22 · Prepared by: Human Centric Works_
_Companion to [`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md) (the target
architecture & AI strategy) and [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md).
Baseline: `main` — ~152 Python modules (~93 tkinter-free), 85 tables, 61 indexes,
~642 headless-runnable tests (GUI smoke skips / errors without `tkinter`)._

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
| Portfolio roll-up across projects/firms | ✅ | Federated `portfolio_store` + Money › Portfolio + WinUI + `/api/portfolio` advisories | — | Maintain | — |
| Earned Value Management (SPI/CPI/EAC) | ✅ | Maths (`earnedvalue.py`) + DB bridge (`evm.py`) + desktop tab + browser `/evm` | — | Maintain; keep bridge tkinter-free (see §5A C0) | — |
| Formal risk register + scoring | ✅ | Scoring (`risk.py`) + store (`risk_store.py`) + **Controls › Risk Register** + detection (`risk_detect.py`) | — | Maintain | — |
| Concurrency / multi-user at scale | 🟡 | WAL + busy_timeout + LAN web; notes in `docs/CONCURRENCY.md` | Contention under many concurrent field users | Conflict handling / redesign only with owner decision | P1 · L · Platform |
| Mobile field capture | 🟡 | Browser `/m/capture` + `/api/capture/*` (E6-lite); no native app | Field data can sync via LAN; native app still open | Native mobile optional | P1 · L · Platform |
| AI-origin tagging in audit | ✅ | `audit_log.origin` + default `manual`; AI paths tagged; `?origin=` filter | — | Maintain | — |
| Enterprise identity (SSO, project roles) | ❌ | Roles Admin/Operator/Viewer built; no SSO or per-project scoping | Larger orgs need finer access; solo users need none | Optional SSO + per-project role scoping (opt-in) | P2 · M · Platform |

### 3.2 AI Job 1 — Eliminate manual data entry (capture)

| Target | Status | Gap | Impact | Required work | Pri · Effort · Type |
|---|---|---|---|---|---|
| Photo → GRN / vendor-invoice draft (OCR) | 🟡 | `capture` + `sidecar_bridge` soft-fail; no weights in-repo | Largest source of typing + transcription error | Install OCR sidecar weights locally (L8) | P1 · L · AI |
| Voice → DPR / measurement draft | 🟡 | Same bridge (`stt` kind); no weights | Field notes captured hours late at a desk | Install STT weights locally (L8) | P1 · M · AI |
| Photo of muster → attendance draft | 🟡 | `labor_match` + `muster_draft` + API; no OCR weights | Repetitive daily typing; name errors | Pair with OCR sidecar (L8) | P2 · M · AI |
| BOQ / tender PDF → import draft | 🟡 | `boq_import` CSV/TSV/plain + API; PDF still open | Slow tender onboarding | PDF/VLM sidecar later | P2 · M · AI |
| Free-text (WhatsApp) → structured record | 🟡 | `text_extract` + capture confirm targets | Updates live in chat, never in the system | Optional model extractor over same drafts | P2 · M · AI |

**Cross-cutting design (must hold for all capture):** AI produces a *draft* into
the existing `CrudFrame`/`DocumentFrame`; every field editable; per-field
confidence; matches resolve against masters as ground truth; graceful fallback
to the normal low-typing form when capture is unavailable (offline-first stays
true).

### 3.3 AI Job 2 — Automate repetitive tasks

| Target | Status | Gap | Impact | Required work | Pri · Effort · Type |
|---|---|---|---|---|---|
| Event-driven follow-on chaining | ✅ | `followups` + `event_hooks`; GRN/MB/VO/payment/capture/filings/RA/NCR/muster wired | — | Maintain | — |
| Recurring project-review pack generation | ✅ | `review_pack` + `review_assemble` + Weekly Review tab + `/review` | — | Maintain | — |
| Mismatch / exception narration | ✅ | `procurement.narrate_*` + `finance.narrate_reconcile` + `/api/match` `/api/reconcile` | — | Maintain | — |
| NL-triggered workflows | 🟡 | `nl_intent` + `POST /api/intent` (keyword → gated drafts) | Richer NL still model-side | Optional model classifier over the same drafts | P2 · M · AI |

**Guardrail:** anything that moves money, files with a department, or changes a
contractual date is **always a draft a human approves** — automation removes
assembly toil, never accountability.

### 3.4 AI Job 3 — KPI measurement & narration

| Target | Status | Gap | Impact | Required work | Pri · Effort · Type |
|---|---|---|---|---|---|
| Deterministic KPI set (schedule/cost/cash/quality) | ✅ | Broadly complete | — | Maintain | — |
| EVM KPIs (SPI, CPI, EAC) | ✅ | Surfaced in Project Management › Earned Value + browser `/evm` | — | Maintain | — |
| Portfolio KPI roll-up | ✅ | `earnedvalue.portfolio` + Weekly Review + Money › Portfolio | — | Maintain | — |
| KPI narration (plain-language briefing) | ✅ | `narrative.kpi_briefing` assembled into Weekly Review (`review_assemble`) | — | Maintain; optional LLM re-voice later | — |
| Portfolio anomaly watch | ✅ | `advisory.for_portfolio` on `/api/portfolio` | — | Maintain | — |
| Forecasting (completion date, cost) | ✅ | `forecast.py` + `/api/forecast` (+ schedule SPI path) | — | Maintain | — |
| Productivity KPIs (crew/day, plant util.) | ✅ | `productivity` + `productivity_store` + Key Numbers + `/api/productivity` | — | Maintain | — |

**Guardrail:** every AI KPI statement traces to the deterministic figure behind
it — the shipped `basis`/`confidence` discipline applied to narration.

### 3.5 AI Job 4 — Risk analysis

| Target | Status | Gap | Impact | Required work | Pri · Effort · Type |
|---|---|---|---|---|---|
| Risk register + likelihood×impact scoring | ✅ | Scoring + store + **Risks** tab + AI detection | — | Maintain | — |
| Rule-based risk detection taxonomy | ✅ | `risk_detect.py` (11 rules + mitigation drafts) | Detection not yet auto-wired from every save event | Optional: event hook → draft into register (E4) | P1 · M · Core |
| Risk narrative (top-N by exposure) | ✅ | `narrative.risk_briefing` in Weekly Review | — | Maintain | — |
| Predictive / early-weak-signal risk | ❌ | Threshold rules only | Drift caught late, after a threshold trips | Correlate soft signals; trend projection (range+basis) | P2 · L · AI |
| Cross-project learning | 🟡 | `pattern_learn` → AI lesson drafts (opt-in apply) | Past overruns don't auto-inform new jobs | Human still applies; richer learning later | P2 · L · AI |

**Guardrail:** no risk flag without a stated basis; AI *detects & ranks*, a human
*owns* the mitigation and the accept/dismiss decision (logged).

### 3.6 Navigation, menu structure & operational-workflow gaps

The application's menu is a two-level Rail → Stage hierarchy driven by
`modules.SECTIONS_CATALOG`, organised **by function** (Masters / Operations /
Billing / …), not by workflow. See
[`APP-ARCHITECTURE.md`](APP-ARCHITECTURE.md) §5 for the full hierarchy and the
operational-flow mapping. The gaps:

| # | Target | Status | Gap | Impact | Required work | Pri · Effort · Type |
|---|---|---|---|---|---|---|
| **N1** | Menu home for the new registers | ✅ | Controls section + Lessons Learned tab shipped | — | Maintain | — |
| **N2** | Guided operational workflow | ✅ | Process rail over `workflow` + `workflow_state` | — | Maintain | — |
| **N3** | Role/persona-scoped menu | ✅ | Tools › Persona + `menu.resolve` in rail | — | Maintain | — |
| **N4** | Global search / command palette / breadcrumbs | ✅ | Process search + `record_search` + `GET /api/search` (tabs + records) | Record jump opens section/tab (not row deep-link) | Optional record deep-link | P2 · S · UI |
| **N5** | Sub-section grouping (3rd level) | ✅ | `menu.GROUPS` rendered as nested notebooks in `_section` | — | Maintain | — |
| **N6** | Workflow-menu alignment | ✅ | Resolved by Process view (overlay, not a re-org) | — | Maintain | — |

**Guardrail:** the menu *model* — the role→section map, the workflow step graph,
the catalog grouping — is **pure config/data and unit-testable headless**; only
the on-screen rendering is display-dependent. This is the same build/verify
boundary as the rest of the roadmap: the model can be built and tested now, the
rail/overlay rendering follows on a display.

### 3.7 UI replatform to WinUI 3 (owner-approved, separate track)

An owner decision moves the desktop UI from the tkinter "HCW UX" shell to
**native WinUI 3** (Windows-only, C#/.NET, stock Fluent components only). This is
a **separate "U" track**, not part of the E-phases, because it is a *front-end
replatform* rather than a capability gap — and it **deliberately breaks** the
stdlib / cross-platform / no-pip constraints (accepted). Full spec:
[`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md).

| # | Target | Status | Approach | Verifiable |
|---|---|---|---|---|
| **U0** | Backend JSON API over the domain (`webapi.py`) | ✅ | Reuse the tested Python core as a localhost service; JSON endpoints under `/api/*` (stdlib, testable) | **Here (Python)** |
| **U1–U7** | WinUI 3 C# client (NavigationView, DataGrid, Fluent, Segoe icons, charts) | 🟡 | U1–U5 page scaffolds + packaging notes in `winui/`; build/MSIX on Windows | Windows/.NET only |

**Key decision (already made):** reuse the domain as a backend, **do not** rewrite
the ~642-tested business modules in C#. The client renders; the Python core still
computes. **U0 is the only piece buildable/verifiable in this environment**, and
is the correct API-first first step.

---

## 4. Gap prioritisation (the short list)

Reading across §3, the highest-leverage gaps — those that either **unblock other
work** or **deliver the most value per unit effort**:

**P0 — foundational (do first; everything else leans on these):**

1. **Headless purity / cost roll-up extraction (cloud C0)** — unblock the suite
   in display-free environments and keep the EVM bridge honest. _(S · Core)_
2. **Backend JSON API U0 (cloud C1/C2)** — the contract for WinUI 3 and mobile.
   _(M · Platform)_
3. **Portfolio UX over the federated read model** — roll-up maths exists;
   needs a durable shell + API. _(M · Core/UI)_

**P1 — high value (the visible payoff):**

4. **E7 Controls / Lessons Learned / Process / persona rail (local L1–L3)** —
   finish discoverability over built stores. _(M · UI)_
5. **Capture pipeline** (photo→GRN/invoice, voice→DPR) — biggest cut to manual
   entry; models are local-track. _(L · AI)_
6. **Event auto-wire** detect/followups into drafts (C5 + L4). _(M · AI/Core)_
7. **WinUI 3 client U1–U7 (local L5–L7)** after U0. _(L · Platform)_

**P2 — completeness:** predictive register feed (C4), NL-triggered workflows,
mobile field app (L9), cross-project learning, SSO/project roles, muster OCR,
BOQ import.

---

## 5. Implementation roadmap

The phases below map 1:1 to the E0–E6 sequence in
[`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md) §10, expanded here with
deliverables, dependencies, and acceptance criteria. Each phase is
**independently shippable and independently useful** — matching the phase
discipline already in [`ROADMAP.md`](ROADMAP.md).

**Implementation status at a glance** (verified against `main`, 2026-07-22). The
**deterministic backbone of E0–E5 and the E7 models are built.** Most enterprise
registers now also have a **desktop + browser surface**. Cloud C0–C6 (purity,
JSON API, audit origin, signal feed, event hooks, lessons API) is **built**.
What remains is mostly **local**: WinUI 3 client, residual GUI, ML/mobile.

| Phase | Built (module / surface) | Remaining | Track |
|---|---|---|---|
| **E0** | `earnedvalue` + `evm` + **Earned Value tab** + `/evm`; `risk` + `risk_store` + **Risks tab**; detection; **AI-origin audit** | — | Cloud done |
| **E1** | `capture.py` + `sidecar_bridge.py` (soft-fail OCR/STT/VLM) | Model **weights** + live sidecar processes | Local (models) |
| **E2** | `narrative`, `review_pack`, `portfolio_store`, `review_assemble` + **Weekly Review** + **Portfolio** + `/review` + `/api/narrative` | — | Cloud done |
| **E3** | `risk_detect`, `narrative.risk_briefing`, Risks tab; event detect hook | More save-path auto-wire (optional) | Local (handlers) |
| **E4** | `review_pack`, `followups`, `event_hooks` + GRN/measurement/variation/payment wiring | Remaining save handlers | Local (GUI) |
| **E5** | `forecast`, `drift`, `signal_feed` → AI risk drafts | Tab surfacing of suggestions | Local (tab) |
| **E6** | Browser `/m/capture` + `/api/capture/*` (E6-lite) | Native mobile app (optional) | Local (optional) |
| **E7** | `menu.py`, `workflow.py`, Controls, Lessons Learned, persona, Process, search, N5 groups | Display smoke (L0) | Cloud models+UI shipped · L0 local |
| **U** | `webapi.py` `/api/*` (**U0.4**) + WinUI page scaffolds | U2–U7 bind/run/MSIX on Windows | **U0.4** · scaffolds Local |

**What this environment can still produce:** pure Python domain, SQLite stores,
stdlib JSON API, unit tests, docs — **not** display smoke tests, .NET/WinUI, or
ML model weights.

### 5A. Cloud development track (headless Python agent)

**Environment:** Linux cloud agent — **no display, no .NET, no ML models**.
Stdlib only, tkinter-free domain, verified with:

```bash
python -m unittest discover -s tests          # headless suite
cd construction_app && python -m compileall -q .
```

GUI/`tab_*` imports that pull `tkinter` will **error on import** here — that is
an environment limit, not a logic failure. Never claim a UI was tested without a
display.

| Area | Modules / deliverables | Status |
|---|---|---|
| Deterministic PM core (E0–E5) | `earnedvalue`, `risk`, `risk_store`, `risk_detect`, `opportunity`(+store), `lessons`/`lessons_register`(+store), `forecast`, `drift`, `narrative`, `review_pack`, `portfolio_store`, `capture` | ✅ built + tested |
| Navigation/workflow models (E7.1/E7.2) | `menu.py` (personas + grouping), `workflow.py` (flow graph) | ✅ built + tested |
| Execution KPIs (Part 2) | `productivity`, `hse.trir` | ✅ built + tested |
| **Backend JSON API (U0)** | `webapi.py` — masters, docs, registers, capture floors, patterns | ✅ **u0.4** |
| WinUI U1 scaffold | `winui/ConstructionOS.WinUI/` (NavigationView + ApiClient + pages) | ✅ scaffolded (Windows to build) |
| AI-origin audit (C3) | `audit_log.origin` + `auth.audit(..., origin=)` | ✅ built + tested |
| Prediction → register (C4) | `signal_feed.py` | ✅ built + tested |
| Event hooks (C5) | `event_hooks.py` over `followups` + `risk_detect` | ✅ built + tested |
| Lessons API (C6) | `/api/lessons` + store | ✅ built + tested |
| Headless purity (C0) | `project_rollup.py` | ✅ built + tested |
| Sidecar bridge (E1 floor) | `sidecar_bridge.py` + `/api/sidecar/*` | ✅ soft-fail (no weights) |
| NL intent floor | `nl_intent.py` + `POST /api/intent` | ✅ gated drafts only |
| Concurrency notes | `docs/CONCURRENCY.md` | ✅ documented (no redesign) |
| Tests & docs | `tests/test_core.py`, `tests/test_web.py`, all `docs/*` | ✅ ongoing |

#### Already done on this track

| Area | Deliverables |
|---|---|
| Deterministic PM core (E0–E5) | `earnedvalue`, `evm` (bridge), `risk`(+store/detect), `opportunity`(+store), `lessons_register`(+store), `forecast`, `drift`, `narrative`, `review_pack`, `review_assemble`, `portfolio_store`, `capture`, `followups`, `productivity` |
| Navigation/workflow models (E7.1/E7.2) | `menu.py` (personas + grouping), `workflow.py` (flow graph) — drift-guarded tests |
| Web/LAN surfaces for new PM | `/evm`, `/review`, Risk/Opportunity/EVM browser pages (stdlib HTML) |
| Docs | Architecture, WinUI migration, AI models, this roadmap |

#### Ordered action plan — cloud (C0–C6 ✅ done)

| # | Action | Status |
|---|---|---|
| **C0** | Headless purity — `project_rollup.py` | ✅ |
| **C1/C2** | U0 JSON API (`webapi.py`) + tests | ✅ |
| **C3** | AI-origin audit tagging | ✅ |
| **C4** | Forecast/drift → register drafts (`signal_feed`) | ✅ |
| **C5** | Event hooks (`event_hooks`) | ✅ |
| **C6** | Lessons API `/api/lessons` | ✅ |
| **C7** | Docs/counts hygiene after each merge | ongoing |
| **C8** | U0.1 API widen + WinUI U1 scaffold | ✅ |
| **C9** | U0.2 (search records, match/reconcile/ageing/filings, portfolio advisories) | ✅ |
| **C10** | U0.3 (NL intent, sidecar bridge API, narrative, Productivity tab) | ✅ |
| **C11** | U0.4 (text/muster/BOQ capture floors, pattern learn, more events) | ✅ |

**Cloud non-goals:** compiling WinUI on Linux, MSIX signing, tkinter smoke screenshots, shipping OCR/STT weights, mobile app UI.

### 5B. Local development track (Windows + display + .NET)

**Environment:** Windows 11 (or 10 1809+) with a display, Visual Studio 2022 /
Windows App SDK, Python 3.8+. This is where **GUI**, **WinUI 3**, and **model
sidecars** are built and verified.

#### Already done on this track (shipped on `main`)

| Surface | Where |
|---|---|
| Earned Value tab + browser | Project Management › Earned Value; `/evm` |
| Risk Register tab | **Controls › Risk Register** |
| Opportunity Register tab | **Controls › Opportunity Register** |
| Lessons Learned register | **Controls › Lessons Learned** (`tab_lessons_learned`) |
| Submittals | **Controls › Submittals** (also Purchases › Sourcing) |
| Process view + search | Always-on **Process** rail |
| Weekly Review tab + browser | Money › Review; `/review` |
| Field capture (E6-lite) | Browser `/m/capture` + `/api/capture/*` |
| Productivity | Operations › Productivity (`tab_productivity`) |
| Rate Realisation (`tab_lessons`) | distinct from Lessons *Learned* register |

#### Ordered action plan — local next

| # | Action | Depends on | Verified by | Pri |
|---|---|---|---|---|
| **L0** | Run full suite **with tkinter** + `tests/test_smoke_tabs.py` light+dark after pulls | — | Discover green locally | P0 |
| **L1** | **E7.3 Controls section** + Lessons Learned tab | — | ✅ catalog + tabs shipped (smoke on display) | P1 |
| **L2** | **E7.3 persona rail** via `menu.resolve` | E7.1 | ✅ Tools › Persona + rail filter | P1 |
| **L3** | **E7.4 Process view + search** | E7.2 | ✅ Process rail + `workflow_state` | P1 |
| **L4** | **E4 GUI event wiring** (GRN + payment API follow-ups) | C5 | ✅ drafts surfaced, not auto-posted | P1 |
| **L5** | **U1 WinUI shell** — build/run on Windows against `web_main.py` | **U0** | VS 2022 build (env-blocked in cloud) | P0 |
| **L6** | **U2–U5 WinUI pages** | U1 | ✅ page scaffolds in `winui/`; bind/run on Windows | P1 |
| **L7** | **U6–U7 packaging + parity** | U2–U5 | `winui/PACKAGING.md` scaffold; signed MSIX on Windows | P1 |
| **L8** | **E1 model sidecars** — OCR / STT / VLM weights | capture | `sidecars/` stubs; install weights locally | P2 |
| **L9** | **E6 mobile capture** | U0 | ✅ `/m/capture` + API; native app optional later | P2 |

**Local setup (WinUI)** — see [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) §11.

### Contract between tracks

```
 Cloud (Python)                         Local (Windows)
 ─────────────                         ───────────────
 C0 purity / stores ──┐
 C1–C2 JSON API (U0) ─┼── localhost /api/* ──► L5–L7 WinUI client
 C3–C6 domain hooks ──┘                      L1–L4 tkinter residual
                                             L8 models · L9 mobile
```

**Rule:** build **U0 (C1/C2) before** WinUI pages (L5+). The client is pure
presentation; the Python core still computes. Do not reimplement finance/civil/
EVM/risk maths in C#.

### Phase E0 — Foundation _(P0 · deterministic core first)_

**Goal:** lay the deterministic groundwork that every later phase reads from.

- **E0.1 EVM module ✅ (built)** — `earnedvalue.py`: PV, EV, AC → SPI, CPI, SV,
  CV, EAC (three methods), ETC, VAC, TCPI, percent-complete/spent, and a
  value-weighted `portfolio` roll-up. Pure, tkinter/DB-free, unit-tested
  (`TestEarnedValue`). DB bridge `evm.py` + **desktop tab + browser `/evm`**
  shipped. _Remaining (cloud C0): keep the cost roll-up import tkinter-free._
- **E0.2 Risk scoring ✅ + register ✅ + tab ✅** —
  `risk.py` / `risk_store.py` / **Project Management › Risks**. Detection via
  `risk_detect.py`. _Remaining: optional Controls-section home (local L1)._
- **E0.3 AI-origin audit tagging ✅** — `audit_log.origin` (`manual`/`ai`) via
  `auth.audit(..., origin=)` (default manual); capture and signal-feed tag AI
  drafts. Risks still carry their own `source` column.

**Depends on:** existing analytics/cost/programme (present).
**Acceptance:** EVM figures reconcile in tests ✅; risk scoring/store ✅; tab
shipped ✅; no new pip dependency ✅. _Audit origin tagging shipped (C3)._

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
portfolio advisory (pooled `advisory` counts) ✅. **Weekly Review** tab +
`/review` surface the pack (`review_assemble`). _Remaining:_ optional dedicated
multi-file portfolio shell (local); JSON exposure via U0 (cloud C1).

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
register-ready (`risk_store.add(..., source='ai')`). **Risks tab shipped.**
_Remaining:_ auto-wire detect on events (cloud C5 + local L4).

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

### Phase E7 — Navigation & Workflow _(P1 · make it usable and discoverable)_

**Goal:** turn the built capability into a coherent, role-aware, workflow-guided
application — give the new registers a menu home and present work as a flow, not
a flat 47-tab grid. Addresses the §3.6 gaps (N1–N6). Reference:
[`APP-ARCHITECTURE.md`](APP-ARCHITECTURE.md) §5.

- **E7.1 Menu model ✅ (built)** — `menu.py` (target `config/menu.py`): personas
  (Owner / Commercial-QS / Site Engineer / Accountant / Storekeeper) → visible
  sections via `visible_sections`/`resolve` (composes with the module
  feature-flags), a backward-compatible **grouping** overlay (`GROUPS` /
  `groups_for` / `flatten` — a 3rd hierarchy level for crowded sections), and the
  proposed **Controls** section for the Part 2 registers. 8 unit tests
  (`TestMenuModel`), including a drift-guard that flattens the grouping against
  the live `SECTIONS_CATALOG`. (N3, N5)
- **E7.2 Workflow graph ✅ (built)** — `workflow.py`: the four operational flows
  (bid→contract, contract→cash, procure→pay, plan→execute) as ordered
  **step → section → tab** graphs; `next_step`/`progress`/`all_progress` compute
  the "what's next" and completion from a state dict. 6 unit tests
  (`TestWorkflow`), including `unknown_locations() == []` — a drift-guard that
  every step points at a real menu location. (N2, N6)
- **E7.3 "Controls" section + register tabs ✅** — Controls home for Risk /
  Opportunity / Lessons Learned / Submittals; persona rail via `menu.resolve`.
- **E7.4 Process view + search ✅** — Process rail over `workflow` +
  `workflow_state`; tab + record search (`menu.search_tabs`, `record_search`);
  N5 nested groups. Display smoke remains **L0** local.

**Depends on:** E0–E5 stores/logic (built); `modules.SECTIONS_CATALOG`,
`shell.RailStage`, `advisory`, `followups` (built).
**Acceptance:** the menu model and workflow graph are unit-tested headless
(role→sections resolves correctly; a flow's next-incomplete step is computed from
state); the Part 2 registers are reachable from a menu; a persona sees a menu
scoped to their job. _Rendering (rail filtering, Process overlay, search UI) is
display-dependent and verified on a display, per the standing boundary._
**Built:** E7.1–E7.4 models and desktop surfaces (Controls, Lessons Learned,
persona, Process, search, N5 groups). _Remaining:_ L0 display smoke verification.

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

**Suggested waves** (each independently shippable), tagged by track:

- **Wave A (foundation):** E0 — ✅ mostly done; residual **C0** (headless purity),
  **C3** (audit tagging).
- **Wave B (visible value):** E1 ‖ E2 ‖ E3 — engine ✅; surfaces mostly ✅;
  residual capture models (**L8**), event auto-wire (**C5**/**L4**).
- **Wave C (leverage):** E4 automation — logic ✅ (`followups`); GUI wiring **L4**.
- **Wave D (frontier):** E5 prediction (**C4** + tab), E6 mobile (**L9**).
- **Wave E (usability):** E7 — models ✅; Controls/Process/search **L1–L3**.
- **Wave U (replatform):** **C1/C2 (U0 API)** → **L5–L7 (WinUI U1–U7)**.

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
**short on domain logic** — EVM, risk, opportunity, forecast, drift, narrative,
review-pack, menu/workflow models are **built and mostly surfaced**. What remains
is concentrated in three places: (1) the **JSON API + WinUI 3 replatform** (U0
cloud → U1–U7 local), (2) **navigation/usability** leftovers (Controls, Lessons
Learned tab, Process view, persona rail), and (3) the **AI capture / mobile**
frontier (model sidecars + field app).

Work is split deliberately:

| Track | Owns | Next |
|---|---|---|
| **Cloud (§5A)** | Pure domain, stores, stdlib JSON API, headless tests, docs | **C0** purity fix → **C1/C2 U0 API** |
| **Local (§5B)** | tkinter residual UI, WinUI 3 client, ML sidecars, mobile | **L0** smoke → **L1–L3** E7 UI; after U0 → **L5–L7** WinUI |

Throughout, the discipline stays: **deterministic maths underneath, explainable
AI on top, a human on anything that moves money or a date, and the offline solo
experience never degraded.**

---

_Planning document only — changes no code, commits no dates. Read alongside
[`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md) (the target & AI
strategy), [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) (UI replatform),
[`REPORT-sop-gap-analysis.md`](REPORT-sop-gap-analysis.md) (the SOP gap set),
[`PRODUCT.md`](PRODUCT.md) (scope & principles), and [`ROADMAP.md`](ROADMAP.md)
(delivered features). Architecture and conventions: [`../AGENTS.md`](../AGENTS.md)._
