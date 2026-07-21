# Construction OS — Enterprise Project Management Solution

**Reference architecture and AI strategy for construction project management**

_Document type: Reference / Solution design (documentation only — no code changes)_
_Version: 1.0 · Last updated: 2026-07-21 · Prepared by: Human Centric Works_

---

## 0. How to read this document

This is a **reference document**, not a build order. It describes what an
enterprise-grade project management (PM) capability for Construction OS looks
like, and — the core of the ask — **where AI removes manual data entry,
eliminates repetitive work, computes KPIs, and analyses risk.**

A word on scope and honesty. Construction OS today is deliberately positioned
for the **solo / small civil contractor** running 1–5 sites offline on one PC
(see [`PRODUCT.md`](PRODUCT.md)). That product explicitly avoids
enterprise features — multi-branch, approval hierarchies, cloud, per-seat
pricing. This document does **not** overturn that; it describes the *target
architecture* for an enterprise tier that grows out of the same code, and it
labels every capability by maturity:

| Tag | Meaning |
|---|---|
| **Built** | Exists in the codebase today (module named). |
| **Extend** | A built module that needs enterprise-grade widening. |
| **Proposed** | New capability; design described, not yet built. |

Throughout, AI is treated as an **assistive, explainable layer over
deterministic maths** — never a black box that decides money. That principle
already governs the shipped advisory and assistant engines and is preserved
here.

---

## 1. Executive summary

Construction PM is a data-entry problem wearing a scheduling costume. The
schedule, the budget, the risk register and the KPI dashboard are only ever as
good as the field data feeding them — and that data arrives late, by hand, from
tired people at the end of a shift. Every downstream promise ("we can tell you
you're slipping") fails when the upstream capture fails.

The enterprise solution rests on three moves:

1. **Capture once, at the source, with as little typing as possible.** Voice,
   photo, document parsing, and reuse-last defaults replace forms.
2. **Let deterministic engines do the maths** — cost, quantities, CPM float,
   ageing, retention, tax — exactly as the shipped pure modules already do.
3. **Layer AI on top for the three jobs humans are slow and inconsistent at:**
   turning messy input into structured records, watching every KPI without
   fatigue, and reading weak early signals of risk.

The measurable goal: **cut manual data entry by the majority, surface every
material risk before it costs money, and make the weekly project review a
five-minute read instead of a two-day scramble.**

---

## 2. What "enterprise-grade" means here

Enterprise buyers evaluate PM tools against a predictable checklist. Mapping
Construction OS to it:

| Capability area | Enterprise expectation | Construction OS position |
|---|---|---|
| **Portfolio view** | Roll-up across many projects/sites | **Extend** — per-project drill-down built (`tab_projects.py`); portfolio roll-up proposed |
| **Scheduling** | CPM, baseline vs actual, float, EOT | **Built** — `cpm.py`, `programme.py`, `tab_timeline.py` (Gantt, critical path, LD/EOT) |
| **Cost control** | Budget vs actual, EVM, forecast-at-completion | **Extend** — budget vs cost, margin built (`projectcost.py`); EVM proposed |
| **Commercial / billing** | BOQ, RA bills, variations, retention | **Built** — `tab_boq_ra.py`, `variation.py`, `retention.py`, `mb.py` |
| **Procurement** | Requisition→PO→GRN 3-way match | **Built** — `procurement.py`, `sourcing.py`, `tab_grn.py` |
| **Quality & safety** | ITP, NCR, snags, incidents | **Built** — `quality.py`, `hse.py`, `closeout.py` |
| **KPI / analytics** | Live dashboards, drill-down, alerts | **Built + Extend** — `tab_kpi.py`, `tab_insight.py`, `advisory.py`; predictive proposed |
| **Risk management** | Register, scoring, early warning | **Extend** — advisory engine flags risk today; formal register + scoring proposed |
| **Access & audit** | Roles, approvals, audit trail | **Built** — `auth.py`, `security.py`, approvals (`approval.py`), audit log |
| **Access anywhere** | Web / mobile / LAN | **Built (LAN) / Extend** — `webapp.py` browser access; mobile field app proposed |
| **AI assistance** | NL query, automation, insight | **Built + Proposed** — local NL→SQL assistant (`assistant.py`); automation & prediction proposed |

The gap between "small-contractor tool" and "enterprise platform" is therefore
**not the domain logic** — that is unusually complete — but **scale-out
concerns**: multi-project roll-up, concurrency, mobile field capture, and the
AI automation layer this document centres on.

---

## 3. Solution architecture (reference)

### 3.1 Layered view

```
┌─────────────────────────────────────────────────────────────┐
│  EXPERIENCE      Desktop (tkinter) · Browser/LAN · Mobile*   │
├─────────────────────────────────────────────────────────────┤
│  AI ASSIST       Capture (voice/photo/doc→record)*           │
│  LAYER           Automation (rules + workflow)*              │
│                  NL query (text→SQL, read-only)  ·  Insight  │
├─────────────────────────────────────────────────────────────┤
│  INTELLIGENCE    KPI engine · Advisory (rules) · Risk engine*│
│  (deterministic) Analytics · CPM/float · Ageing · Retention  │
├─────────────────────────────────────────────────────────────┤
│  DOMAIN LOGIC    Pure, tkinter-free modules (testable core)  │
│                  finance · civil · money · programme · …     │
├─────────────────────────────────────────────────────────────┤
│  DATA            SQLite (single file) → portfolio store*     │
└─────────────────────────────────────────────────────────────┘
        * = Proposed / Extend for the enterprise tier
```

The load-bearing principle, inherited from the codebase: **all real maths lives
in the pure domain layer** (`finance.py`, `civil.py`, `programme.py`,
`analytics.py`, `retention.py`, …). AI never replaces that layer; it feeds it
clean data and explains its output. This keeps every rupee figure
deterministic, auditable, and unit-tested.

### 3.2 Data foundation

- **Today:** one SQLite file per firm/year, additive schema migrations
  (`db.py`). Excellent for a single site office.
- **Enterprise extension (Proposed):** a portfolio layer that federates many
  firm/site files into a read model for roll-up KPIs, while each project keeps
  its own authoritative file. This preserves the offline-first guarantee (a
  site keeps working with no network) and adds roll-up when connected.

### 3.3 The PM data spine

Every PM capability reads from the same spine that already exists:

- **Project umbrella** — client, site, budget, LD terms (`tab_projects.py`).
- **Schedule** — activities, dependencies, baseline, actuals, critical path
  (`cpm.py`, `programme.py`).
- **Cost** — budget vs committed vs actual, margin, retention exposure
  (`projectcost.py`, `retention.py`).
- **Commercial** — BOQ, measurements, RA bills, variations (`tab_boq_ra.py`).
- **Field** — DPR/site reports, muster, consumption, quality, safety.

AI's job is to **fill this spine faster and read it deeper** — nothing more
exotic.

---

## 4. The role of AI (core of this document)

AI in Construction OS is scoped to four jobs, in priority order. Each is
justified by the same test: *does it remove human toil or human error on a task
the deterministic engine cannot do alone?*

1. **Eliminate manual data entry** — turn messy real-world input into
   structured records. (§5)
2. **Automate repetitive tasks** — chain the rote follow-on work that a record
   triggers. (§6)
3. **Compute and narrate KPIs** — watch every number without fatigue and
   explain movement in plain language. (§7)
4. **Analyse risk** — read weak early signals and rank exposure before it
   costs money. (§8)

Guiding constraints for all four (non-negotiable, inherited from the shipped
design):

- **Explainable over clever.** Every AI output carries a *basis* — the count,
  sample, or source it rests on — exactly as `advisory.py` already does with its
  `confidence` + `basis` fields. No bare numbers.
- **Deterministic core, assistive edge.** AI proposes; the pure engines
  compute; a human approves anything that moves money or a legal date.
- **Read-only by default.** The NL assistant is engine-enforced `query_only`
  (`assistant.py`). Any *write* automation is a suggested draft a user
  confirms, never a silent mutation.
- **Local-first, private.** Field data need not leave the machine. The shipped
  assistant runs a **local Ollama model** offline; the enterprise tier keeps
  that option and treats cloud models as opt-in, per-firm.
- **Confidence-gated.** Low-confidence AI output is shown as a suggestion to
  review, never auto-committed. High-confidence, hard-fact output can drive
  alerts directly.

---

## 5. AI job 1 — Eliminating manual data entry

**The problem.** A site generates dozens of records a day — attendance,
measurements, material receipts, progress notes, safety observations. Today a
`munshi` types them from paper, hours later, with transcription errors. This is
the single largest source of both toil and bad data.

**The AI approach — capture at the source, structure automatically.**

| Input the field already produces | AI transformation | Structured record | Maturity |
|---|---|---|---|
| Spoken progress note ("laid 40 cubic metre slab, grid B, morning") | Speech-to-text → entity extraction | DPR line / measurement draft | Proposed |
| Photo of a delivery challan / vendor invoice | OCR + document parsing → field mapping | Goods receipt / vendor-invoice draft (3-way match) | Proposed |
| Photo of a hand-written muster sheet | OCR + name matching to labour master | Attendance grid draft | Proposed |
| Photo of site progress | Vision tagging (activity, location) | DPR photo log + progress hint | Proposed |
| BOQ / tender PDF from the department | Document parsing → line items + rates | BOQ import draft | Proposed |
| Free-text WhatsApp update | NL extraction → typed fields | Site-report / issue draft | Proposed |

**Design rules that keep this safe:**

- **Draft, don't commit.** AI always produces a *draft* record pre-filled into
  the existing entry form (`CrudFrame` / `DocumentFrame`). The user glances and
  saves. Every field is editable; nothing is written silently.
- **Confidence per field.** Each extracted field carries a confidence; low ones
  are highlighted for the human's eye. A challan quantity read at 60% confidence
  is flagged; a vendor name matched exactly is not.
- **Reuse the master data as ground truth.** Name/item matching resolves against
  the existing masters (labour, vendors, materials) so extraction snaps to real
  records instead of inventing strings.
- **Fall back gracefully.** If capture fails or is unavailable, the normal
  low-typing form (today-default, remember-last) still works. AI is an
  accelerator, never a dependency — matching the offline-first principle.

**Expected effect.** The bulk of routine field records shift from *type from
paper* to *speak/snap then confirm*. Fewer keystrokes, fewer transcription
errors, and — critically — data captured *at the moment of work* rather than
hours later, which is what makes the downstream KPIs and risk signals timely.

---

## 6. AI job 2 — Automating repetitive tasks

**The problem.** One real event triggers a chain of rote follow-on work. A
goods receipt should update stock, prompt the 3-way match, and flag the vendor
invoice. A completed activity should advance % complete, re-roll the schedule,
and update the look-ahead. Humans do this chaining manually and inconsistently.

**The AI approach — event-driven automation with a human gate on anything
consequential.**

| Trigger event | Automated follow-on | Human gate? | Maturity |
|---|---|---|---|
| Goods receipt saved | Update stock ledger; run 3-way match; flag invoice mismatch | Auto (deterministic) + AI narration of mismatch | Extend |
| RA bill approved | Post journal entry; update retention register; recompute receivables | Auto (idempotent posting, built) | Built |
| Activity marked complete | Advance % complete; recompute critical path & float; refresh look-ahead | Auto (CPM) + AI-drafted revised look-ahead | Extend |
| Statutory due date approaching | Assemble filing checklist; pre-fill register summary | Draft for review | Extend |
| Measurement entered | Draft the RA bill abstract line; suggest deviation flag | Draft for review | Extend |
| Recurring report due (weekly) | Generate the project review pack (KPIs + narrative + risk) | Draft for review | Proposed |
| Vendor payment due | Draft payment batch respecting TDS + ageing priority | Human approves batch | Proposed |
| Document (RFI/NCR/snag) ageing | Escalate, notify owner, draft chaser | Draft notification | Proposed |

**What AI adds over plain rules.** Much of this chaining is *deterministic* and
already partly built (idempotent journal posting is shipped). AI's specific
contribution is:

- **Drafting the human-facing artefact** — the review narrative, the chaser
  message, the filing summary — from the structured numbers.
- **Deciding what's worth surfacing** — ranking which of a hundred possible
  follow-ups actually need attention, the same ranking discipline the advisory
  engine uses today.
- **Natural-language triggers** — "close out all snags on the Ward-7 site and
  draft the handover pack" resolved to the concrete steps.

**Non-negotiable:** anything that moves money, files with a department, or
changes a contractual date is **always a draft a human approves.** Automation
removes the *assembly* toil, not the *accountability*.

---

## 7. AI job 3 — KPIs (measurement and narration)

### 7.1 What exists

The KPI and insight layer is **built and strong**:

- **KPI board** (`tab_kpi.py`) — cash, receivables (with a past-90-day note),
  payables, net position, billed/collected this month, retention.
- **Insight** (`tab_insight.py`) — site profitability, budget vs actual,
  ageing (0-30/30-60/60-90/90+), contract/BOQ progress %, material budget vs
  actual.
- **Analytics core** (`analytics.py`) — physical progress (measured/BOQ value)
  and material budget variance, as pure functions.
- **Advisory engine** (`advisory.py`) — ranks *what to do* with an explicit
  confidence and basis for every call.

### 7.2 The enterprise KPI framework

A recommended standard KPI set for construction PM, mapped to where the number
already lives:

| Dimension | KPI | Source | Maturity |
|---|---|---|---|
| **Schedule** | Schedule Performance (planned vs actual %) | `programme.py` baseline vs actual | Built |
| | Programme slip (days) + LD exposure | `tab_timeline.py`, LD/EOT | Built |
| | PPC — Plan Percent Complete (look-ahead reliability) | `planning.py` | Built |
| | Critical-path float trend | `cpm.py` | Extend (trend) |
| **Cost** | Budget vs actual, margin % | `projectcost.py` | Built |
| | Cost Performance / earned value (SPI, CPI) | `earnedvalue.py` | **Built (maths)** — surfacing pending |
| | Forecast cost at completion (EAC) | `earnedvalue.py` (+ trend) | **Built (maths)** — trend/surfacing pending |
| | Material budget variance | `analytics.py` | Built |
| **Cash** | Receivables, ageing, DSO | `ageing.py`, `tab_insight.py` | Built |
| | Cash-flow forecast | `cashflow.py` | Built |
| | Retention locked / due | `retention.py` | Built |
| **Commercial** | Contract progress %, variation value | `analytics.py`, `variation.py` | Built |
| **Quality** | Open NCRs, snag closure rate, ITP pass | `quality.py` | Built |
| **Safety** | Incident rate, open observations | `hse.py` | Built |
| **Productivity** | Output per crew/day, plant utilisation | muster, `plant.py` | Extend |

**Earned Value Management (EVM)** — SPI, CPI, and
forecast-at-completion. The inputs already exist (baseline value, measured
value via `analytics.contract_progress`, actual cost via `projectcost`), so EVM
was a **pure-module addition** — now **built** as `earnedvalue.py` with unit
tests, consistent with the architecture; only its surfacing in a KPI/Insight tab
remains. No AI required for the maths.

### 7.3 Where AI improves KPIs

The maths stays deterministic. AI improves the **experience and reach** of
KPIs:

- **Narration.** Turn the KPI board into a plain-language weekly briefing:
  *"Margin on Ward-7 dropped 4 points this week — driven by steel overspend
  against norm; receivables past 90 days rose to ₹6.2 L on two client bills."*
  This is generation over numbers the engine already computed, with the source
  numbers cited.
- **Anomaly flagging (fatigue-free watch).** AI watches *every* KPI on *every*
  project and surfaces only the meaningful moves — the job humans do badly at
  scale. It extends the advisory engine from one firm's snapshot to a portfolio.
- **Natural-language query (Built).** "Which sites are over budget on cement?"
  answered by the read-only NL→SQL assistant (`assistant.py`) — no dashboard
  navigation.
- **Forecasting (Proposed).** Trend-based projection of completion date and cost
  at completion, always shown as a *range with confidence*, never a false-precise
  single number.

**Guardrail:** every AI KPI statement is traceable to the deterministic figure
behind it. A narrated insight is a *sentence over a number*, and the number is
one click away. This is the shipped `basis`/`confidence` discipline applied to
narration.

---

## 8. AI job 4 — Risk analysis

### 8.1 What exists

Risk detection today is **implicit in the advisory engine** (`advisory.py`): it
already flags cash below payables, invoices aged past 90 days, vendor invoices
without a goods receipt, programme slip with LD exposure, and thin plan
reliability — each with a severity (`act`/`watch`/`info`/`good`) and a
confidence. This is a working early-warning system for a single firm.

### 8.2 The enterprise risk framework (Proposed / Extend)

Formalise risk into a first-class, project-spanning capability:

**A. Structured risk register (Extend).** A register per project with:
category (schedule / cost / commercial / quality / safety / statutory /
external), description, likelihood, impact, owner, mitigation, and status —
scored on a standard likelihood × impact matrix. Deterministic scoring; the
register is normal structured data.

**B. Automatic risk detection (Extend of `advisory.py`).** Promote the advisory
rules into a named risk taxonomy and add project-level rules:

| Risk signal (rule-derived, explainable) | Read from |
|---|---|
| Critical-path activity slipping → completion + LD risk | `cpm.py`, `programme.py` |
| Burn rate outpacing progress → cost overrun (CPI < 1) | EVM (Proposed) |
| Cash forecast turning negative in horizon | `cashflow.py` |
| Receivables ageing past 90 days concentration | `ageing.py` |
| Material consumption exceeding norm → wastage/leakage | `analytics.py`, `civil.reconcile_consumption` |
| Vendor invoice without goods receipt → payment-control risk | 3-way match |
| Statutory filing approaching/overdue → penalty risk | `compliance.py`, `statutory.py` |
| Look-ahead reliability (PPC) low → planning risk | `planning.py` |
| Open high-severity NCR / safety incident trend | `quality.py`, `hse.py` |

Each detected risk lands in the register with its **basis** (the count/sample
it rests on) and a suggested mitigation draft — never a bare red flag.

**C. AI's specific contribution to risk.** Beyond rules, AI reads what rules
miss:

- **Early, weak signals.** Correlating soft indicators — a run of low-confidence
  measurements, repeated small schedule slips on one crew, rising RFI age — into
  a "this project is drifting" flag *before* any single threshold trips.
- **Predictive risk (Proposed).** Trend projection: likelihood a milestone is
  missed given current float-burn; likely cost at completion given burn vs
  progress. Always a *range with confidence and basis*, feeding the register as
  a **suggestion a human accepts or dismisses.**
- **Narrative risk summary.** A plain-language "top 5 risks across the
  portfolio, ranked by exposure (₹ / days), with why and what to do" — the
  advisory engine's ranking discipline, portfolio-wide.
- **Cross-project learning (Proposed, privacy-gated).** With consent, patterns
  that preceded overruns on past projects inform early warnings on new ones.
  Strictly opt-in; local-first; never silently sharing one firm's data.

### 8.3 Risk governance guardrails

- **Explainable only.** No risk flag without a stated basis. A contractor must
  be able to ask "why am I seeing this?" and get the rule and the numbers —
  the shipped advisory contract.
- **AI suggests, human owns.** AI can *detect* and *rank* risk; a person owns
  the mitigation and the accept/dismiss decision. The register records who
  decided what, when (audit log).
- **Confidence-honest.** A predicted risk off thin history is labelled `Low`
  confidence and shown as such — the tool never over-claims certainty on a
  forecast.

---

## 9. Non-functional & governance considerations

For an enterprise deployment, the following must hold (status noted):

- **Security & access** — roles (Admin/Operator/Viewer), versioned PBKDF2
  hashing (600k iterations), account lockout, audit log. **Built** (`auth.py`,
  `security.py`). Enterprise extend: SSO, finer-grained project roles.
- **Approvals** — approval queue for consequential actions. **Built**
  (`approval.py`, `tab_approvals.py`). Extend: multi-step hierarchies.
- **Auditability** — every AI-drafted record and every risk decision is logged
  with who confirmed it. **Built (audit log)**; extend to tag AI-origin records.
- **Data residency & privacy** — field data stays local by default; the
  assistant runs a **local** model offline. Cloud AI is opt-in per firm. This
  is a differentiator, not a limitation.
- **Reliability** — offline-first: a site keeps operating with no network;
  roll-up syncs when connected. Preserves the founding guarantee.
- **Explainability & compliance** — because every money figure is
  deterministic and every AI output is traceable, the system is auditable for
  statutory and contractual scrutiny — essential where AI touches billing.

---

## 10. Phased delivery (reference sequence)

A pragmatic order that delivers value early and keeps the deterministic core
first:

| Phase | Theme | Headline deliverables | Depends on |
|---|---|---|---|
| **E0** | Foundation | EVM pure module (SPI/CPI/EAC); formal risk register schema | Existing analytics/cost |
| **E1** | Capture | Photo→GRN/invoice OCR; voice→DPR; draft-and-confirm flow | Masters as ground truth |
| **E2** | KPI reach | Portfolio roll-up read model; KPI narration; portfolio advisory | E0, data federation |
| **E3** | Risk | Risk detection taxonomy over rules; risk narrative; mitigation drafts | E0, advisory engine |
| **E4** | Automation | Event-driven follow-on drafting; recurring review pack generation | E1–E3 |
| **E5** | Prediction | Trend forecasts (completion, EAC); early-warning correlation | E2, E3 history |
| **E6** | Field mobile | Mobile capture app feeding E1 pipeline | E1, web layer |

Each phase keeps the two hard rules where the core is concerned: **new business
maths goes in a pure, testable module**, and **AI stays assistive and
explainable**.

---

## 11. Success metrics for the solution itself

How to know the AI investment paid off (targets, to be baselined):

- **Data-entry reduction** — % of field records created via capture (voice /
  photo / parse) vs manual typing; keystrokes per record.
- **Timeliness** — median lag between work happening and its record existing
  (capture-at-source should collapse this from hours to minutes).
- **Risk lead time** — average days a material risk is flagged *before* it
  costs money or a date.
- **KPI adoption** — weekly review time (target: minutes, from days); % of
  reviews using the AI-generated pack.
- **Accuracy** — AI-drafted records accepted without edit vs corrected; false-
  positive rate on risk flags (kept low so the flags stay trusted).
- **Trust** — every AI output has a visible basis (target: 100%; a design
  invariant, not a KPI to trend).

---

## 12. Summary

Construction OS already owns the hard part of enterprise construction PM: a
complete, deterministic, unit-tested domain core covering schedule (CPM/LD/EOT),
cost, commercial billing, procurement, quality, safety, finance, and a
rule-based KPI + advisory layer. The enterprise opportunity is not to rebuild
that — it is to **scale it out** (portfolio, mobile, concurrency) and to **wrap
it in an explainable AI layer** that does the four things people are slow and
inconsistent at:

1. **Capture** — turn voice, photos, and documents into structured records so
   people stop typing from paper.
2. **Automate** — chain the rote follow-on work, drafting the human-facing
   artefacts, gating anything consequential behind human approval.
3. **Measure** — watch every KPI on every project without fatigue and narrate
   what moved and why, over numbers the engine computed.
4. **Foresee** — read weak early signals and rank risk by exposure before it
   costs money.

The through-line is discipline: **deterministic maths underneath, explainable
AI on top, a human on anything that moves money or a date.** That is what makes
this enterprise-grade rather than merely automated — and it is the same
discipline the shipped advisory and assistant engines already embody.

---

_This document is a reference/design artefact. It changes no code and commits
no roadmap; capabilities are labelled Built / Extend / Proposed so readers can
distinguish what exists from what is envisioned. For product scope and
principles see [`PRODUCT.md`](PRODUCT.md); for delivered features see
[`ROADMAP.md`](ROADMAP.md); for architecture and conventions see
[`../AGENTS.md`](../AGENTS.md)._
