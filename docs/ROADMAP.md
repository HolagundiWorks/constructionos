# ACO — Roadmap

_Product: **ACO** (Accelerated Construction Operations)._  
_Last updated: 2026-07-23 · Baseline: API **u0.12**_

**This is the single status document.** What changed and where →
[`CHANGELOG.md`](CHANGELOG.md). Engineering / product specs are listed in §5 —
they are **not** status boards.

**Audience test:** does this help a solo T2/T3 Indian contractor bill, get paid,
pay labour, and stay in control — offline, on their PC, with minimal typing?
(`PRODUCT.md`)

**Legend:** ✅ done · 🚧 in progress · ⏳ planned · ✖ non-goal

---

## Snapshot

| Layer | Status |
|---|---|
| Desktop ERP (tkinter) + pure domain + SQLite | ✅ Complete product |
| Browser / LAN (stdlib) | ✅ Read + money/masters write |
| JSON API (`webapi.py`) | ✅ **u0.12** (C0–C14, CT-1…CT-10 closed) |
| WinUI 3 client | 🚧 **Nav-complete**; workflow depth in progress |
| MSIX packaging | ✅ Dev-signed; ⏳ release cert + clean-box proof |
| OCR / STT / VLM sidecars (L8) | ⏳ Stub only (weights local) |

---

## 1. Completed

### 1.1 Product (desktop + domain)

Full ERP surface for the audience — money, civil billing, labour, procurement,
quality/HSE, PM, AI assistant, takeoff, multi-company books. Detail lives in
[`CHANGELOG.md`](CHANGELOG.md) and `AGENTS.md`.

| Area | Done |
|---|---|
| **Money** | Payments/receipts, baaki, cash book, allocation, ageing, cash-flow forecast |
| **Billing** | Estimates, quotations, contracts, running bills, RA, GST tax invoice, CPWA Forms 21/23/26 |
| **Labour** | Muster, weekly payout, thekedar ledger, advances, optional PF/ESI/cess |
| **Procurement** | Requisition → PO → GRN + 3-way match, variations, retention, vendor rating |
| **Quality / HSE / plant / closeout** | ITP/NCR, PPC look-ahead, HSE, plant PM, snags, RFI/submittals |
| **Finance** | Auto-posting journal, P&L, balance sheet, GST/TDS registers |
| **Project management** | CPM/Gantt, EVM, risk, opportunity, weekly review, bid/no-bid |
| **AI** | Read-only assistant (Foundry Local / quick answers); draft-and-confirm capture floors |
| **Takeoff** | On-drawing quantities → estimate |
| **Platform** | Opt-in roles, audit, WAL SQLite, multi-firm registry, Windows installer, AGPL-3.0 |

### 1.2 Browser / LAN

✅ Same SQLite book over HTTP — login/roles, masters + money writes, RA Form 23/26,
EVM + weekly review, measurement entry, GST/TDS, compliance. See [`LAN.md`](LAN.md).

### 1.3 Cloud / API track (headless) — **closed**

| Track | Delivered |
|---|---|
| **C0–C14 / U0.x** | Domain purity, `/api/*` through Tools settings, events, signals, capture floors |
| **CT-1…CT-10** | Pure GST, measurements API, chart shapes, rich tables, P&L/BS, lookahead, company audit |
| **u0.12** | `/api/assistant/quick`, `POST /api/assistant`, `/api/parties` |

### 1.4 WinUI track — phases done

| Phase | Deliverable | Status |
|---|---|---|
| **U0** | JSON API for the client | ✅ u0.12 |
| **U1** | Ribbon shell + search (stock controls) | ✅ |
| **U2** | Masters CRUD (`FieldForm`, FK pickers) | ✅ |
| **U3** | Money docs create+list | ✅ |
| **U4** | Home KPIs + charts (LiveCharts) | ✅ |
| **U5** | Controls + GST + Review + Accounting + Look-ahead; **nav-complete** | ✅ |
| **U6** | Backend auto-launch + PyInstaller sidecar + **dev-signed MSIX** | ✅ |
| **U7** (partial) | Persona menus, mechanical a11y, Tools page | ✅ so far |

**Also done on WinUI:** dedicated **AssistantPage**, **CashFlowPage**,
**PartiesPage** (baaki + ageing); empty/error honesty; ₹ formatting; precision
test gates. Blow-by-blow → changelog.

---

## 2. Pending

### 2.1 P0 — WinUI workflow honesty (local)

| Item | Why pending |
|---|---|
| **BOQ / RA / Measurement Book** page | Still Import-style — need MB → RA → print |
| **Subcontractors** (work orders + sub bills) | Still masters `thekedars` — need WO API + page |
| **AI Engine** page | Still CapturePage — Foundry Start/Stop surface |
| **Goods Receipt / three-way match** UX | Import/table proxies — match + confirm |
| **Muster → payout** grid | DataTable — site+date Active labour workflow |

### 2.2 P1 — WinUI depth & Tools

| Item | Why pending |
|---|---|
| Timeline **Gantt / CPM** view | Table of tasks only |
| Key Numbers **vs** Insight split | Both → ChartsPage |
| Tools: backup/restore, invoice series, refdata, language, security | Firm + modules only in API/WinUI |
| Interactive **a11y** walkthrough + keyboard/focus pass | Mechanical names done |
| Release **code-signing cert** + clean-box MSIX install proof | Dev-signed only |
| Residual startup crash watch / SDK bump | Intermittent framework flake |

### 2.3 P2 — Fluent appearance & theme

| Item | Why pending |
|---|---|
| **Light / Dark / System** theme setting | Forced Light today |
| Safe **Mica** (or documented deferral) | Removed for crash risk |
| Accent-only CTAs; shared empty/loading recipe | Partial |
| Breadcrumb on deep civil paths (Contract → BOQ → MB → RA) | Not wired |

### 2.4 P3 — Precision / money / CA bridge

| Item | Why pending |
|---|---|
| GST/TDS **export pack** (CA handoff) | Registers exist; export bundle thin |
| PPC **binary Done + reason codes** depth on LookaheadPage | API/page exist; deepen LPS honesty |
| Risk **accept-from-detect** one-click | Detection exists |
| Home aggregate `/api/home` (fewer round-trips) | Optional perf |

### 2.5 P4 — Moat / later

| Item | Why pending |
|---|---|
| **L8** OCR/STT/VLM weights over `sidecars/stub_server.py` | Local Windows + models |
| Takeoff polish on WinUI | Desktop takeoff ships; WinUI thin |
| **Retire tkinter on Windows** | Product call after Tools + civil spine parity |
| Native mobile field app | Browser `/m/*` modes only |

---

## 3. Non-goals

- At-rest encryption in-app (use BitLocker / encrypted volume).
- BIM, IoT/drones, heavy multi-user cloud sync, corporate multi-level approvals.
- Replacing Tally overnight (export/bridge instead).
- Custom WinUI chrome / non-Fluent control kits.
- SaaS per-seat mandatory cloud.

---

## 4. Principles (always on)

- Domain: **stdlib Python, single SQLite, no pip**; maths in pure modules + tests.
- WinUI: **stock Fluent only**; orange accent sparingly; AI proposes, human approves money/dates.
- Honesty: `None` when undefined — never fake 0/∞; empty ≠ error ≠ missing endpoint.
- Status updates land in **this file**; narratives of *what shipped* land in
  **CHANGELOG**.

---

## 5. Spec index (not status)

| Doc | Role |
|---|---|
| [`CHANGELOG.md`](CHANGELOG.md) | What changed (append-only history) |
| [`PRODUCT.md`](PRODUCT.md) | Who we build for |
| [`BRAND.md`](BRAND.md) | Visual identity |
| [`API.md`](API.md) | JSON API contract |
| [`APP-ARCHITECTURE.md`](APP-ARCHITECTURE.md) | Structure, menu, workflow |
| [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) | WinUI engineering notes |
| [`UI-PRINCIPLES-AND-GUIDELINES.md`](UI-PRINCIPLES-AND-GUIDELINES.md) | Fluent checklist |
| [`ENTERPRISE-PM-SOLUTION.md`](ENTERPRISE-PM-SOLUTION.md) | Enterprise PM / AI solution design |
| [`EXECUTION-PART2.md`](EXECUTION-PART2.md) | Risk / opportunity / KPI execution |
| [`LAN.md`](LAN.md) | Browser / LAN server |
| [`SOP-manual.md`](SOP-manual.md) | Contractor SOPs |
| [`TEST_PLAN.md`](TEST_PLAN.md) | Test layers |
| [`RESEARCH-UI-FLUENT-DEEP-DIVE.md`](RESEARCH-UI-FLUENT-DEEP-DIVE.md) | Fluent colour / appearance / workflow research |
| [`RESEARCH-COMPETITIVE-CASE-STUDY.md`](RESEARCH-COMPETITIVE-CASE-STUDY.md) | Competitor & forum research |
| [`RESEARCH-construction-management-sops.md`](RESEARCH-construction-management-sops.md) | SOP practice research |
| [`RESEARCH-sop-primary-sources.md`](RESEARCH-sop-primary-sources.md) | CPWD/CPWA primary sources |
