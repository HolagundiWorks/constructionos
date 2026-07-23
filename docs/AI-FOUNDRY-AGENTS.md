# ACO — Azure AI Foundry multi-agent plan

_Product: ACO (Accelerated Construction Operations)._  
_Status: Phase A (local orchestration) **in progress** · Azure cloud Agents **planned**._  
_Related: [`AI-MODELS-AND-DEPLOYMENT.md`](AI-MODELS-AND-DEPLOYMENT.md),
[`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md), [`ROADMAP.md`](ROADMAP.md)._

## 1. Principle

The **ERP stays the system of record**. Azure AI Foundry (and today’s
**Foundry Local**) is the **AI operating platform**: orchestration, model
runtime, prompts, evaluation, and guardrails — not a second ledger.

| Layer | Owns |
|---|---|
| SQLite + pure Python domain | Projects, BOQ, estimates, POs, bills, risks, maths |
| Agent runtime (`agents_*`) | Route → tools → draft proposals with basis |
| Foundry Local (today) | On-device LLM for NL→SQL + optional narrative |
| Azure AI Foundry Agents (later, opt-in) | Cloud multi-agent hosting, Entra, eval, monitoring |

**Non-negotiable:** AI **proposes**; a human **approves** anything that moves
money or a date. Agents return drafts / gated follow-ups — they never silent-write.

## 2. Target architecture

```
Users (Estimator / PM / Site / Owner)
                │
         Construction ERP (WinUI / tk / LAN)
                │
         JSON API  /api/agents/*
                │
         Agent runtime (stdlib) ── tool calls ──► pure domain modules
                │
         Provider adapter
           ├─ Foundry Local (default, offline)
           └─ Azure AI Foundry Agents (opt-in, future)
```

Specialized agents collaborate via **workflows** (ordered handoffs), not one
mega-chatbot.

## 3. Agent roster (ACO)

| Id | Audience | Primary tools (domain) |
|---|---|---|
| `estimation` | Estimator | estimates, rate_book, lessons, historical costs |
| `boq` | Estimator / QS | boq_items, measurements, deviation, duplicates |
| `drawing` | QS / Engineer | takeoff drafts, pdf text, sidecar VLM (stub) |
| `procurement` | Buyer | POs, GRN match, quotes, vendors, demand |
| `planning` | PM | timeline/CPM, lookahead/PPC, LD exposure |
| `finance` | Owner / CA | cashflow, ageing, P&L, GST, retention |
| `document` | PM / Admin | RFIs, submittals, contracts, narrative search |
| `site` | Site engineer | muster, DPR, inspections, NCR, snags |
| `safety` | HSE | permits, incidents, LTIFR |
| `executive` | Owner | portfolio KPIs, top risks, advisories |

The existing single **Assistant** tab remains the general NL→SQL path;
persona agents sit **beside** it and reuse the same read-only / draft rules.

## 4. Phased delivery

### Phase A — Local orchestration (this cloud track) ✅ implement now

Stdlib domain + API, no Azure subscription required:

1. **Catalog** — `agents_catalog.py` (ids, audience, tools, example prompts).
2. **Tools** — `agent_tools.py` wrappers over existing pure modules (read-only
   or draft-returning).
3. **Knowledge** — `knowledge_base.py` curated snippets (schema + SOP/product)
   for TF-IDF retrieve (same style as `assistant.SCHEMA_DOCS`).
4. **Runtime** — `agent_runtime.py`: route question → agent → run tools →
   assemble answer; optional Foundry Local summarize when engine is up.
5. **Workflows** — `agent_workflows.py`: multi-agent recipes
   (`variation_impact`, `procurement_30d`, `executive_brief`).
6. **API** — `GET /api/agents`, `GET /api/agents/{id}`,
   `POST /api/agents/ask`, `POST /api/agents/workflow`.
7. **Tests + docs** — unit tests; ROADMAP / CHANGELOG / API.md.

### Phase B — WinUI surfaces (local Windows)

- Persona picker on Assistant / new Agents page.
- Workflow runner UI (show each agent’s step + gated actions).
- AI Engine page Start/Stop remains Foundry Local.

### Phase C — Azure AI Foundry cloud (opt-in per firm)

When a firm opts in (Entra + Foundry project):

1. Provider adapter implementing the same
   `generate(system, prompt) → text` contract as `foundry_client`.
2. Register ACO tools as Foundry Agent tools that call **localhost ERP API**
   (never bypass draft/confirm).
3. Evaluation harness (golden questions per agent) stored under `tests/`.
4. Monitoring: log prompt/response sizes + latency into `audit_log`
   (`origin='ai'`), never plaintext secrets.

Cloud Agents **do not** replace SQLite maths; they only orchestrate and narrate.

### Phase D — Vision / drawing agent depth

Depends on L8 VLM weights + takeoff polish (ROADMAP P4). Until then the
`drawing` agent returns honest “sidecar not ready” + PDF text extract drafts.

## 5. Multi-agent example: variation impact

Workflow id `variation_impact`:

1. `drawing` — note design-change scope (text/PDF draft).
2. `boq` — quantity / missing-item check on affected BOQ lines.
3. `estimation` — price delta vs rate book / lessons.
4. `planning` — schedule / LD exposure hint.
5. `procurement` — material demand / vendor risk hint.
6. `finance` — cash-flow / margin impact hint.
7. `executive` — one-page summary + **gated** “create variation draft”
   follow-up (human confirms).

Each step records `agent`, `basis`, `confidence`, `gated`.

## 6. Why this fits ACO

- **Offline-first:** Phase A works with Foundry Local off (deterministic tools
  + quick answers).
- **Stdlib:** no pip; cloud Foundry stays an HTTP adapter.
- **Honesty:** `None` / empty when undefined; soft-fail when engine off.
- **Indian contractor UX:** plain language; cash-first executive answers.

## 7. Out of scope (non-goals)

- Auto-posting journals or approving bills from an agent.
- Embedding models / vector DB in the stdlib core (TF-IDF retrieve stays).
- Replacing WinUI with a chat-only UI.
- Mandatory cloud AI for every install.
