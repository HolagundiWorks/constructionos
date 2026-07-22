# Construction OS — Part 2: Construction (Execution)

**Risk & opportunity management, KPIs, and continuous improvement during
delivery — mapped to the system**

_Document type: Reference / Solution design (documentation only — describes code)_
_Version: 1.0 · Last updated: 2026-07-21 · Prepared by: Human Centric Works_
_Companion to [`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md) and
[`ENTERPRISE-PM-GAP-AND-ROADMAP.md`](ENTERPRISE-PM-GAP-AND-ROADMAP.md)._

---

## 0. Objective

Deliver the project **safely, on time, within budget, and to the required
quality** while **proactively managing risks and capturing opportunities**
throughout execution.

This document records the Part 2 (execution) framework and — the point that
makes it more than a slide — maps every element to where it now lives in the
codebase. Much of the execution spine was already built (schedule, cost, quality,
safety, procurement); this pass added the **risk & opportunity management engine**
and the **execution KPIs** the framework calls for, as pure, unit-tested modules.
Maturity tags: **Built** · **Extend** · **Proposed**.

---

## 1. Opportunities & risks by area

The framework's area-by-area view, with where each side is served today:

| Area | Opportunities | Risks | In the system |
|---|---|---|---|
| **Site management** | Lean construction, site logistics, productivity | Poor coordination, congestion, access | `productivity.py` (KPIs); look-ahead/PPC (`planning.py`); DPR (`tab_site_reports.py`) |
| **Safety** | Safety culture, hazard ID, digital tools | Accidents, violations, unsafe practice | `hse.py` (permits, incidents, **LTIFR + TRIR**, near-miss ratio) |
| **Quality** | First-time-right, standard inspections, prefab | Rework, defects, non-conformance | `quality.py` (ITP hold-points, NCR); `productivity.material_waste` |
| **Schedule** | Sequencing, parallelism, recovery planning | Delays, weather, subcontractor slippage | `cpm.py`, `programme.py`, `forecast.schedule_forecast` |
| **Cost control** | Reduce waste, resource/equipment use | Overruns, price escalation, low productivity | `earnedvalue.py` (EVM), `projectcost.py`, `productivity.py` |
| **Resources** | Labour/equipment allocation, multi-skilling | Shortages, breakdowns, low productivity | `muster`, `plant.py`, `productivity.equipment_utilisation` |
| **Procurement** | Alt suppliers, local sourcing, JIT | Supply disruption, late delivery, shortages | `procurement.py`, `sourcing.py`, GRN 3-way match |
| **Contract admin** | Early resolution, collaborative change | Claims, variations, disputes | `variation.py` (register), retention (`retention.py`) |
| **Stakeholder** | Communication, community engagement | Client/community/utility conflicts | risk register (category `external`) |
| **Commissioning & handover** | Early planning, digital handover | Delayed testing, incomplete docs, punch-list | `closeout.py` (snags/handover readiness) |

Each area's *risks* and *opportunities* now have a **first-class register** to
live in (below), scored the same way so they rank against each other.

---

## 2. Key deliverables → where they come from

| Deliverable | Source in the system | Maturity |
|---|---|---|
| **Updated Risk Register** | `risks` table + `risk_store.py`; auto-detection via `risk_detect.py`; **Project Management › Risks** tab | **Built** |
| **Opportunity Register** | `opportunities` table + `opportunity_store.py`; **Project Management › Opportunities** tab | **Built** |
| Monthly Progress Reports | `review_pack.build` + `review_assemble`; **Money › Review** + `/review` | **Built** |
| Cost Performance Report | `earnedvalue.py` + `evm.py`; **Project Management › Earned Value** + `/evm` | **Built** |
| Schedule Updates | `programme.py`, `cpm.py`, `forecast.schedule_forecast` | **Built** |
| Safety Performance Report | `hse.summarise` (LTIFR, TRIR, near-miss, permits) | **Built** |
| QA/QC Reports | `quality.py` (ITP, NCR) | **Built** |
| Change Management Log | `variation.py` register | **Built** |
| Procurement Status Report | `procurement.py`, `sourcing.py`, GRN match | **Built** |
| Commissioning Plan / Handover Docs | `closeout.py` | **Extend** |
| **Lessons Learned Register** | `lessons_learned` table + `lessons_store.py` (§6) | **Built (data); dedicated tab still pending** (Rate Realisation is a different feature) |

The two headline execution artefacts — the **Risk Register** and the
**Opportunity Register** — are the new capability this pass delivers.

---

## 3. Risk & opportunity management process (implemented)

The framework's six steps, and how the modules realise each:

### 3.1 Identify
Regular site risk reviews capture new risks/opportunities and review changes in
scope/schedule/site conditions.
- **Manual:** `risk_store.add(...)` / `opportunity_store.add(...)`.
- **Automatic (AI, E3):** `risk_detect.detect(snapshot)` reads the same metrics
  snapshot the dashboard assembles and raises scored, register-ready risks
  (`source='ai'`) with a **basis** on every flag — so identification never
  depends solely on someone remembering.

### 3.2 Assess
Evaluate **probability, impact, urgency**; calculate an overall score.
- `risk.assess(likelihood, impact, value, urgency=…)` — the 5×5 matrix gives the
  **score** (likelihood × impact); **urgency** (1–5) is the *when*, and drives a
  **priority** = score × urgency that sequences equally-scored items. An
  **expected exposure** = probability-weighted value sizes it in rupees/days.
- `opportunity.assess(...)` mirrors this for the upside (**expected value**).

### 3.3 Prioritize
Classify as **Critical / High / Medium / Low**.
- `risk.band(score)` / `opportunity.band(score)` map the 1–25 score to those four
  bands (1–4 Low · 5–9 Medium · 10–15 High · 16–25 Critical), so a severe top-row
  item is never merely "Low".

### 3.4 Response planning
- **Risk responses** — Avoid / Reduce / Transfer / Accept (`risk.RESPONSES`,
  validated by `risk.valid_response`).
- **Opportunity responses** — Exploit / Enhance / Share / Accept
  (`opportunity.RESPONSES`). Stored on the row; an unrecognised value is dropped,
  not persisted.

### 3.5 Assign ownership
Each item carries an **owner, action plan, target completion date, status**.
- Columns on both tables: `owner`, `action_plan`, `target_date`, `status`
  (risks: Open/Mitigating/Closed/Accepted; opportunities:
  Open/Pursuing/Realized/Declined), plus `decided_by`/`decided_date` stamped by
  `set_status(...)` — the audit trail of who decided what, when.

### 3.6 Monitor & review
Review at daily / weekly / monthly cadence; track open, closed, emerging risks,
opportunity realisation and mitigation effectiveness.
- `risk_store.summary(...)` / `opportunity_store.summary(...)` give counts by
  band, total expected exposure/value, and the top-N — the standing review view.
- **Mitigation effectiveness** is explicit: `risk.assess(..., residual_*)`
  returns the post-mitigation band and a `mitigation_benefit` (score points the
  control buys), so a review can show a mitigation actually moved the needle.
- `review_pack.build(...)` assembles the whole monthly review (KPIs +
  advisories + risks + opportunities + narrative) as one draft.

**Guardrail:** detection and scoring are AI/rule-assisted, but a **human owns the
response and the accept/dismiss** — nothing auto-closes a risk or auto-commits a
response. Every flag carries its basis (the "why am I seeing this?").

---

## 4. Key Performance Indicators (implemented)

| Group | KPI | Function | Maturity |
|---|---|---|---|
| **Safety** | TRIR | `hse.trir` (recordable × 200,000 / hours) | **Built** |
| | LTIFR | `hse.ltifr` | **Built** |
| | Near-miss reporting | `hse.summarise` `near_miss_ratio` | **Built** |
| **Schedule** | SPI | `earnedvalue.spi` | **Built** |
| | Planned vs actual | `programme.py` baseline vs actual | **Built** |
| | Critical-path status | `cpm.py` | **Built** |
| | Forecast duration/slip | `forecast.schedule_forecast` | **Built** |
| **Cost** | CPI | `earnedvalue.cpi` | **Built** |
| | Budget vs actual | `projectcost.py` | **Built** |
| | Forecast at completion (FAC/EAC) | `earnedvalue` `eac` (three methods) | **Built** |
| **Quality** | NCRs | `quality.py` | **Built** |
| | Rework % | `productivity.material_waste` (rework twin) / `quality` | **Extend** |
| | Inspection pass rate | `quality.py` (ITP) | **Extend** |
| **Productivity** | Labour productivity | `productivity.labour_productivity` (+ `performance_factor`) | **Built** |
| | Equipment utilisation | `productivity.equipment_utilisation` | **Built** |
| | Material waste | `productivity.material_waste` | **Built** |
| **Commercial** | Change orders | `variation.py` | **Built** |
| | Claims status | `variation.py` (status) | **Extend** |
| | Payment milestones | `milestones` / cash-flow | **Built** |

Every KPI is a **deterministic pure function** returning an honest `None` where
the denominator is missing (a rate with no hours is *no answer*, not a small
one). An LLM narrates them (`narrative.py`); it never computes them.

---

## 5. What this pass added (new, tested)

All pure/DB-only, tkinter-free, no pip, unit-tested headless:

- **`risk.py`** (extended) — `urgency` → `priority`; risk **response taxonomy**
  (Avoid/Reduce/Transfer/Accept) with validation; ranking now urgency-weighted.
- **`opportunity.py`** (new) — the upside twin: same matrix, `expected_value`,
  Exploit/Enhance/Share/Accept, ranking + register summary.
- **`opportunities` table + `opportunity_store.py`** (new) — register
  persistence mirroring `risk_store` (derive-on-save, project-delete cascade).
- **`risks` table** (extended) — `urgency`, `priority`, `response`,
  `action_plan`, `target_date` (additive migration for older files).
- **`hse.py`** (extended) — **TRIR**.
- **`productivity.py`** (new) — labour productivity + performance factor,
  equipment utilisation (capped at 100), material waste %.
- **`review_pack.py`** (extended) — optional opportunity summary in the pack.
- **`lessons_register.py` + `lessons_learned` table + `lessons_store.py`** (new) — the
  Lessons Learned register (§6): outcome/root-cause/recommendation with a
  feed-forward queue, capture straight from a risk/opportunity, project-delete
  cascade.
- **Tests** — 25 new unit tests (risk urgency/response, opportunity + store,
  risk-store urgency, productivity, TRIR, review-pack opportunities, lessons +
  store). Full suite passes bar the pre-existing missing-`tkinter` GUI theme test.

**Remaining (display-dependent, deliberately deferred):** the tkinter tabs for
the risk and opportunity registers, and surfacing the KPIs on screen — these need
a display to verify and so are left as clean next steps, consistent with the rest
of the roadmap.

---

## 6. Continuous improvement

Capture lessons learned during execution, review mitigation effectiveness,
document opportunity realisations, and feed insight into future projects.

- **Mitigation effectiveness** — already measurable (`mitigation_benefit`, §3.6).
- **Opportunity realisation** — tracked by opportunity `status`
  (Pursuing → Realized) and `expected_value` vs actual.
- **Lessons Learned Register (Built)** — `lessons_learned` table +
  `lessons_register.py` (taxonomy + roll-up) + `lessons_store.py` (persistence). A lesson
  records the **outcome** (positive/negative/neutral), a **root cause** and — the
  part that matters — a **recommendation** to feed forward, with a **status**
  whose `Applied` state means the insight was actually carried into future
  planning. Lessons can be captured **straight from a risk that materialised or
  an opportunity realised** (`lessons_store.from_risk` / `from_opportunity`,
  linking `source_id`), so the register fills itself from what the project
  already recorded. `feed_forward()` returns the live queue — recommendations
  not yet applied — that closes the loop into the next project's planning (an
  updated rate, a tuned detection rule, a changed checklist). Pure roll-up and
  DB persistence are unit-tested; only the tkinter tab remains, and — being
  display-dependent — is deferred like the other register tabs.

---

## 7. Summary

Part 2's execution framework is now backed by a real engine, not just a process
diagram. The **risk and opportunity registers** share one scoring machine
(probability × impact, urgency-driven priority, banded, with response
taxonomies), persist with an audit trail, and can be **auto-populated** from the
live metrics snapshot with an explainable basis. The **execution KPIs** —
safety (TRIR/LTIFR), schedule (SPI/forecast), cost (CPI/FAC), and productivity
(labour/plant/waste) — are deterministic pure functions, ready to surface and to
narrate. The discipline is unchanged from the rest of the product: **deterministic
maths underneath, explainable AI on top, a human on every response and every
decision.**

---

_Reference/design document. The maths and persistence described here are built
and unit-tested; the on-screen tabs remain the display-dependent next step. Read
alongside [`ENTERPRISE-PM-GAP-AND-ROADMAP.md`](ENTERPRISE-PM-GAP-AND-ROADMAP.md)
and [`ROADMAP.md`](ROADMAP.md). Architecture: [`../AGENTS.md`](../AGENTS.md)._
