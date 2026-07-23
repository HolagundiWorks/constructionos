# Optimisation & precision programme — make ACO as powerful and precise as possible

**Date:** 2026-07-23  
**Audience:** Product owner + engineering (cloud + local)  
**Companion reports:** [`COMPLETENESS-AUDIT.md`](COMPLETENESS-AUDIT.md), [`RESEARCH-COMPETITIVE-CASE-STUDY.md`](RESEARCH-COMPETITIVE-CASE-STUDY.md)  
**Scope:** Reports and prioritised programme only — no code in this document.

---

## 1. Precision doctrine (non-negotiable)

Before adding features, lock these rules into every new surface (API + WinUI + docs):

| Rule | Meaning | Failure mode today |
|------|---------|-------------------|
| **Explainable over clever** | Money/schedule/risk return `None` when undefined — never fake 0/∞ | WinUI placeholders can show empty grids that look like “zero work” |
| **AI proposes; human approves** | Nothing that moves money/date writes without confirm | Capture is the right pattern; Assistant must not auto-write |
| **One source of truth** | Pure module → store → API → client; no second maths in C# | Risk of WinUI re-implementing GST |
| **Honest confidence** | Advisory High/Low must stay visible | Flat “AI said so” destroys trust |
| **Indian cash-first** | Kitna baaki before trial balance | Don’t lead CA screens to T2 users |
| **Document honesty** | Claims must match `main` SHA | ROADMAP “parity ✅” currently overclaims |

**Precision metric proposal (track quarterly):**

1. **Maths integrity:** % of money endpoints that return `null` for undefined (not 0).  
2. **Workflow coverage:** % of SECTIONS_CATALOG labels with a *purpose-built* WinUI page (not DataTable).  
3. **Doc drift:** count of stale claims in AGENTS/PRODUCT/ROADMAP (target 0).  
4. **Test floor:** unittest count + compileall green on every cloud PR.  
5. **Forum pain coverage:** % of top-10 India contractor pains addressed (Excel MB, GST, cash, PPC, retention).

---

## 2. Optimisation pillars

```
P0  Correctness & honesty     — stop lying to the user (nav, docs, empty states)
P1  Cash & civil spine        — the India T2 “can’t live without” loops
P2  Execution intelligence    — PPC, risk, opportunity, narrative, lookahead depth
P3  CA / compliance bridge    — GST/TDS export, FY, retention aging
P4  Performance & ops         — SQLite, API batching, offline, packaging
P5  Moat features             — takeoff, local RAG, portfolio, multi-company polish
```

---

## 3. P0 — Correctness & honesty (do first)

### 3.1 WinUI route honesty

| Symptom | Fix |
|---------|-----|
| Assistant / AI Engine → Capture | Wire `AssistantPage` / engine status page; Capture stays Capture |
| BOQ / RA → Import | `BoqRaPage` or dedicated BOQ + RA pages |
| Subcontractors → Thekedars | `SubcontractorsPage` over work_orders / sub_bills |
| Cash Flow → Payments | Dedicated cashflow forecast page |
| Empty stage for missing route | Always land on a page with title + “not wired” if stub |

**Acceptance:** Opening every rail label shows a title matching the catalog label.

### 3.2 Documentation honesty

| File | Action |
|------|--------|
| `ROADMAP.md` | Soften U5/U7 “parity ✅”; redefine “live page” vs “workflow parity” |
| `AGENTS.md` §0 / §25 | Refresh module / table / test counts (or link to regen commands) |
| `PRODUCT.md` | Roles exist when security on; WinUI primary UI direction |
| `CLOUD-TASKS.md` CT-9 Why | Remove “placeholder” language — LookaheadPage + API exist |
| `COMPLETENESS-AUDIT.md` | Keep updated each major merge |

### 3.3 Empty-state precision

Every list page must distinguish:

- **No data yet** (honest empty — CTA to add)  
- **API error** (retry)  
- **Endpoint missing** (show gap, not blank)  
- **Permission denied** (role)

Fake zeros on KPI cards when data is missing are **bugs**.

---

## 4. P1 — Cash & civil spine (power for India T2)

These loops are where Excel+Tally still win. Beat them, and ACO becomes default.

### 4.1 Measurement Book → RA → retention → receipt

| Gap | Optimisation |
|-----|----------------|
| WinUI BOQ/RA miswired | Purpose-built MB entry (Nos×L×B×D), live qty, RA snapshot |
| RA previous_qty Draft double-count | Surface rule in UI (“Approve before next Draft”) |
| Retention release timing | RetentionPage + calendar reminders (followups) |
| Receipt allocation | AllocatePage already exists — link from party balance |

**Precision:** `civil.measurement_quantity` blank-dim=1 must be visible in UI (“blank = 1”).

### 4.2 Muster → wages → payments

| Gap | Optimisation |
|-----|----------------|
| Muster is DataTable | Grid UX like tkinter muster (site+date → all Active labour) |
| Weekly payout double-run | Explicit “already paid this week?” guard + audit |
| Advance recovery | Surface open advance on payout screen |

### 4.3 PO → GRN → three-way match → vendor invoice → payment

| Gap | Optimisation |
|-----|----------------|
| GRN DataTable | Match UI with variance colours |
| Vendor invoice tax derived | Never editable net_payable — always `finance.invoice_totals` |
| Reconciliation | Show Matched / Over / Under with eps |

### 4.4 Cash book & kitna baaki

| Gap | Optimisation |
|-----|----------------|
| Party balances | One-tap “outstanding” with ageing buckets |
| Cash book | Opening from settings + running balance |
| Hindi/Hinglish | Labels for cash views (already in i18n — use them) |

---

## 5. P2 — Execution intelligence (enterprise PM without enterprise bloat)

From Lean Construction / LPS research and our own `planning.py` / `risk_*` / `narrative.py`:

### 5.1 Weekly work plan (make PPC real)

**Today:** LookaheadPage + `/api/lookahead` exists.  
**Optimise toward LPS:**

1. **Binary Done** checkbox (not % complete for PPC tasks).  
2. **Reason codes** on miss (7–10 standard reasons).  
3. **PPC trend** sparkline (last 6–8 weeks) — already partially in planning maths.  
4. **Make-ready checklist** (constraints) before a task can enter the week.  
5. **Commitment owner** (name) on each weekly line.

Do **not** replace CPM — keep Gantt for contract programme; WWP for execution.

### 5.2 Risk / opportunity precision

| Optimisation | Detail |
|--------------|--------|
| Detection → register | One-click “accept detection as risk” |
| Score transparency | Show likelihood × impact formula |
| Residual vs inherent | Two scores when mitigation logged |
| Opportunity twin | Same UX as risk (don’t bury) |

### 5.3 Narrative & advisory

| Optimisation | Detail |
|--------------|--------|
| Confidence badges | Always visible on Home |
| Citation | “Based on RA Bill #… / SPI …” |
| No silent AI | Assistant answers cite SQL or “quick answer” |

### 5.4 EVM / forecast honesty

| Rule | Detail |
|------|--------|
| SPI/CPI | `None` when BAC or EV undefined |
| EAC | Show formula used |
| Forecast bands | Optimistic / likely / pessimistic — label assumptions |

---

## 6. P3 — CA & compliance bridge (trust + handoff)

Forum pattern: contractors keep Tally for the CA. ACO should **export cleanly**, not replace Tally overnight.

| Deliverable | Why |
|-------------|-----|
| Trial balance / P&L / BS export (CSV + HTML) | CA import or attach |
| GST period summary + HSN | GSTR prep |
| TDS register export | 26Q prep |
| Journal export by FY (Apr–Mar) | Audit |
| Retention schedule | DL period |
| Party outstanding aging | Debtors/creditors |

**API:** reports_store already has PnL/BS — extend export formats and GST/TDS bundles.

**Precision:** FY boundaries via `numbering.financial_year` only — never calendar year for Indian tax screens.

---

## 7. P4 — Performance, API, packaging

### 7.1 SQLite & concurrency

| Topic | Guidance |
|-------|----------|
| WAL | Keep; document checkpoint on backup |
| busy_timeout | Keep 5000; consider higher for LAN+desktop |
| Short connections | Never hold `db_getter` conn across UI awaits |
| Indexes | Audit slow queries when portfolio grows |

### 7.2 JSON API optimisation

| Topic | Guidance |
|-------|----------|
| Pagination | Large tables (ledger, attendance) |
| Field selection | `?fields=` for mobile later |
| ETags / If-None-Match | Cut WinUI refresh cost |
| Batch read | Dashboard: one `/api/home` vs N calls |
| Idempotent writes | Client-generated keys for payments |

### 7.3 WinUI performance

| Topic | Guidance |
|-------|----------|
| Virtualising lists | Large TreeView substitutes |
| Lazy rail | Already pattern — keep |
| Don’t poll Ollama on UI thread | Background + status footer |

### 7.4 Packaging / ops

| Topic | Guidance |
|-------|----------|
| MSIX + API sidecar | Document port conflicts |
| Sample book | Always one-click for demos |
| Backup/restore | Include -wal/-shm discipline |

---

## 8. P5 — Moat features (after spine is precise)

Only after P0–P1:

1. **Takeoff** — canvas accuracy, calibration UX, link to BOQ.  
2. **Local RAG assistant** — SCHEMA_DOCS freshness CI check; few-shot EXAMPLES for MB/RA/GST.  
3. **Portfolio** — multi-company already started; firm-year rollup clarity.  
4. **Drawing AI** — optional sidecar; never block core ERP.  
5. **Offline field pack** — sync queue with conflict rules (hard; design before code).

---

## 9. API gap backlog (from audit) — optimisation order

| Priority | Area | Suggested endpoints / work |
|----------|------|----------------------------|
| P0 | Nav honesty | N/A (client) |
| P1 | MB / measurements | CRUD + qty compute |
| P1 | RA generate | Snapshot endpoint (wrap civil/mb) |
| P1 | Muster save | Batch attendance upsert |
| P1 | GRN match | Match summary endpoint |
| P1 | Wages / payout | Pure wages already — expose |
| P2 | PPC reasons | Extend lookahead_store |
| P2 | Risk accept-from-detect | store helper |
| P3 | GST/TDS export | reports_store |
| P3 | Ageing API | wrap ageing.py |
| P3 | Cashflow API | wrap cashflow.py |
| P4 | Home aggregate | `/api/home` |
| P5 | Takeoff persist | existing pure — wire |

---

## 10. Testing & precision gates (cloud)

Every cloud PR that touches maths:

```bash
python -m unittest discover -s tests
cd construction_app && python -m compileall -q .
```

Add targeted cases for:

- `None` vs `0` on EVM/SPI when undefined  
- RA previous_qty excludes Draft  
- GST split CGST/SGST vs IGST  
- Measurement blank dim = 1  
- Wage overtime fraction  
- SQL injection still blocked in assistant validate_sql  

**Doc gate (lightweight):** script or checklist that AGENTS headline counts match `wc`/`unittest` output before release notes.

---

## 11. Local (Windows) optimisation queue

| # | Task | Depends on |
|---|------|------------|
| 1 | Fix NavRoute miswires (P0) | None |
| 2 | BoqRaPage + MusterPage + GrnMatchPage | API P1 |
| 3 | CashFlowPage + AgeingPage | API P3 |
| 4 | Soften empty states / error banners | None |
| 5 | Smoke: every catalog label opens matching title | 1 |
| 6 | MSIX + localhost API handshake doc | Packaging |

---

## 12. Competitive response map (what to copy / reject)

| From competitors / forums | Copy? | How |
|---------------------------|-------|-----|
| Procore photos + drawings | Selectively | Attach to NCR/snag — not full DMS |
| Buildertrend client portal | Later | Simple share link for RA PDF |
| JobTread pricing clarity | Yes | Transparent ACO edition pricing when commercial |
| LPS PPC binary + reasons | Yes | Lookahead depth |
| Tally depth | Bridge | Export, don’t clone |
| Primavera | No | Keep CPM stdlib |
| AI autopilot payments | **Never** | Capture + approve only |
| Per-seat SaaS tax | Reject | Keep offline SQLite economics |

---

## 13. 90-day programme sketch (effort, not calendar promises)

Phased by dependency — duration depends on staffing (cloud agent vs local Windows):

### Phase A — Honesty
- Doc claim cleanup  
- WinUI nav fixes  
- Empty-state taxonomy  

### Phase B — Civil + labour spine on WinUI
- MB/RA/Muster/GRN purpose-built pages  
- Matching API endpoints  

### Phase C — Money precision
- Ageing + cashflow pages  
- GST/TDS export pack  
- Allocation UX polish  

### Phase D — Execution intelligence
- PPC reasons + trend  
- Risk accept flow  
- Home aggregate API  

### Phase E — Moat
- Takeoff  
- Assistant SCHEMA CI  
- Portfolio polish  

---

## 14. What “as powerful and precise as possible” means for ACO

**Powerful** = the contractor can run the firm without Excel for MB/RA/muster/PO/GRN/cash and without a second app for weekly planning.

**Precise** = every number is deterministic, Indian-tax correct, undefined when unknown, role-guarded when security is on, and every UI label matches a real backend capability.

**Not the goal** = matching Procore’s module count or SAP’s GL depth. That path destroys the T2 wedge and the stdlib/offline moat.

---

## 15. Immediate next actions (owner checklist)

1. Accept these three reports as the planning baseline.  
2. Decide: **WinUI-first** remaining work vs keep tkinter as fallback for P1 loops.  
3. Prioritise Phase A + B (honesty + civil/labour).  
4. Assign cloud vs local split per [`ENTERPRISE-PM-GAP-AND-ROADMAP.md`](ENTERPRISE-PM-GAP-AND-ROADMAP.md) §5A/§5B.  
5. Re-run completeness audit after each phase; update scorecard SHA.

---

*End of optimisation programme.*
