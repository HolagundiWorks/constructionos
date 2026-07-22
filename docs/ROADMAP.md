# Construction OS — Roadmap

_Last updated: 2026-07-22_

**Audience:** small civil contractors in tier-2 / tier-3 Indian cities (see
`PRODUCT.md`). Every item is judged by one question: _does this help a solo
contractor bill, get paid, pay, and stay in control — offline, on their own PC,
with minimal typing?_

**Legend:** ✅ shipped · 🚧 in progress · ⏳ planned · ✖ deliberate non-goal

> This file tracks **status and direction**. The blow-by-blow of *what changed
> and where* lives in [`CHANGELOG.md`](CHANGELOG.md); the design decisions and
> caveats behind each area live in that area's spec/report under `docs/` and in
> `AGENTS.md`. Grouped by capability, not by build order.

---

## ✅ Shipped

### Money & billing
- Masters: sites/warehouses, clients, vendors, materials, labour, equipment, thekedars.
- Payments & receipts (Cash/Bank/UPI/Cheque), party balances ("baaki"), cash/day book.
- Payment ↔ bill/invoice allocation with **reconciled ageing**; **cash-flow forecast** (lagged, flags the first week the balance goes negative).
- Estimates (priced BOQ → contingency → GST → grand total), quotations, contracts, running bills, RA bills.
- GST tax invoice (CGST/SGST/IGST, HSN/SAC, amount-in-words); configurable invoice number series (FY reset); e-invoice / e-way-bill field readiness.
- Rate Book + **Rate Analysis** (CPWD DAR skeleton); **Rate Realisation** (achieved purchase rate → standard); CPWD reference library (items, material rates, consumption norms).
- Branded letterhead + bank block on all outward documents; **print / PDF for every document**.

### Labour
- Muster roll, weekly wage payout, thekedar ledger, advance auto-recovery, optional PF/ESI/labour-cess.

### Procurement & SOP gates ("gate, don't hope")
- Requisition → PO → **GRN gate** (accepted qty becomes stock) + **3-way match** (over-invoiced headline).
- **Variation / change-order** register; single-step **approval gate** (records who/when + audit).
- **Retention** register + **security-deposit ledger** (5% PG + 2.5%/bill), DLP / release tracking.
- Vendor depth (quote comparison, approved-vendor flag, 3-factor rating).

### Quality · planning · HSE · closeout
- ITP hold-points + **NCR** log; weekly look-ahead + **PPC**; **CVR** (cost-value reconciliation).
- **HSE** register (permits, incidents, LTIFR, near-miss ratio); **closeout** snag list + handover readiness.
- **Plant** PM + fuel analysis; **RFI / drawing-revision / submittal** registers.
- **KPI dashboard** with good / watch / act verdicts.

### Statutory forms (CPWD)
- Measurement Book (**Form 23 / CMB**), RA memorandum of payments (**Form 26** recoveries), Muster Roll (**Form 21 / 21A**).
- **Statutory compliance calendar** (GST/TDS/PF/ESI/cess/IT) — dates only, no penalty figures.

### Finance
- Idempotent **double-entry auto-posting** (invoices, payments, payroll, sub/running/RA bills); **P&L + Balance Sheet**; GST/TDS registers; HSN summary.

### Project management
- Projects + milestones, per-project **overview** (budget vs cost vs billed, margin), project ↔ transaction links.
- **Critical-path / dependency scheduling** (CPM) and an **MS-Project-grade scheduler** (working calendar, typed deps FS/SS/FF/SF + lag, WBS); **baseline-vs-actual** with LD / EOT exposure; per-project Gantt.
- **Risk register** (Project Management › Risks) — likelihood × impact → score / band / expected exposure (derive-on-save via `risk.py`/`risk_store.py`), owner, response, mitigation, and **Auto-detect** that raises risks from the current figures (`risk_detect`) each with a drafted response.
- **Earned Value** (Project Management › Earned Value, and browser `/evm`) — per-project **SPI / CPI / EAC / VAC / TCPI** with a value-weighted portfolio roll-up, worst-first. BAC = contract value / budget, AC = project cost roll-up, EV = billed value, PV = time-scheduled from the project window (`earnedvalue.py` maths, `evm.py` assembly; the two proxies are footnoted on screen, not hidden).
- **Opportunity register** (Project Management › Opportunities) — the upside twin of the risk register: likelihood × impact → band, probability-weighted **expected upside**, urgency-driven priority (`opportunity.py`/`opportunity_store.py`, same derive-on-save discipline), best-first with the strongest washed green.
- **Weekly Review** (Money › Review, and browser `/review`) — the whole weekly review assembled in one call: plain-language narrative, money at a glance, portfolio EVM, advisories, and the risk & opportunity summaries (`review_pack.py` assembly over `advisory`/`risk_detect`/`narrative`/`earnedvalue`). A draft to read — it books, files and pays nothing.
- **Bid / no-bid** scorecard (ledger-evidenced, vetoes override the score).

### AI
- **Assistant** — read-only text-to-SQL over your own data (TF-IDF retrieval, conversational follow-ups, deterministic quick answers that work with no LLM).
- **Internalised, one built-in model** (`qwen2.5-coder:1.5b`, Apache-2.0) that runs entirely on the machine — **no downloader, catalogue, or picker**. The only control is **Start / Stop** on its own **AI Engine** rail row (the local Ollama runtime is bundled + hidden; the model is registered offline at first start).

### Takeoff
- Bluebeam-style **on-drawing quantity takeoff** — calibrate scale, then length / area / volume / count, live quantities, **Send to Estimate**; PDF → PNG via poppler / Ghostscript when present.

### Browser / LAN access
- Built-in **stdlib web server** — use the app in a browser at `http://<host>:<port>`, **no client install**, sharing the same SQLite file (see [`LAN.md`](LAN.md)).
- **Login-gated** (reuses the desktop accounts / roles / PBKDF2 / audit; Viewers read-only). All read views, plus **write** for the Masters + on-site logs (snags/NCRs), **estimates** (with print), and **all postable money documents** (payments, tax/vendor invoices, running & RA bills) — posting through the desktop's own engine.
- **RA-bill statutory documents in the browser** — an RA bill's record view lists its measured items and prints the **Measurement Book (Form 23 / CMB)** and the **PWD-style RA abstract (Form 26)** from the same pure builders the desktop uses (shared `mb_report.py`, so the two surfaces render the identical document).
- **Portfolio dashboards in the browser** — **Earned Value** (`/evm`) and the assembled **Weekly Review** (`/review`), read-only, from the same assemblers as the desktop.

### Platform
- **One HCW-UI design system** across desktop + web from a pure `tokens.py` (guard-tested so the two can't drift).
- **Optional login** (Admin / Operator / Viewer, lockout, audit log), per-tab write-gating for Viewers; WAL + enforced foreign keys + hot-path indexes.
- **Multi-year / multi-firm** company files; one-click and synced-folder (cloud) backup; guarded restore.
- **Windows installer** (PyInstaller + Inno Setup, per-user, no admin); **AGPL-3.0**.

---

## 🚧 In progress · ⏳ Next

- ✅ **Enterprise PM backbone — fully surfaced.** Deterministic EVM, risk, forecast, opportunity, execution KPIs and narration / review-pack: the pure modules landed and every one now has a screen — **lessons-learned**, **submittals**, the **risk register**, **Earned Value**, the **opportunity register** and the assembled **Weekly Review** (desktop + browser). Design and provenance tracked in [`ENTERPRISE-PM-GAP-AND-ROADMAP.md`](ENTERPRISE-PM-GAP-AND-ROADMAP.md) and [`EXECUTION-PART2.md`](EXECUTION-PART2.md).
- ⏳ **Browser / LAN — remaining parity.** RA-bill statutory documents are now viewable and printable in the browser (measured items, Form 23 MB, Form 26 abstract — above); the one piece still desktop-only is **per-item measurement *entry*** (the on-drawing / dimension grid). The **GST / compliance** registers also stay desktop / view-only for now; everything else is browser-editable.
- ⏳ **Real-display GUI render check.** A validation task, not a code gap: the headless CI has no Tk, so the two GUI smoke tests run only on a machine with a display (or Xvfb). The 600+ pure-logic tests pass headlessly.

---

## ✖ Non-goals (protecting the founding thesis)

- **At-rest encryption** — real crypto needs a native / pip dependency, which breaks the stdlib-only rule; weak stdlib "encryption" would promise a protection it can't deliver. The honest answer is OS-level protection (BitLocker / an encrypted volume) around the single data file, which the multi-firm file model already suits.
- **BIM, IoT / drones, predictive analytics beyond the local assistant, heavy multi-user cloud sync, corporate multi-level approval chains** — Level-4 features that add cost and friction without helping a solo contractor bill, get paid, and stay in control.

---

## Cross-cutting principles (always-on)

- Pure **stdlib / tkinter / single SQLite / no pip** — the whole product depends on it.
- Business maths lives in **pure, testable modules**; every new document gets a **print / PDF** path; every screen respects **minimal typing** and **plain language**.
- **Honesty by construction:** don't fabricate what can't be produced offline (e-invoice QR), don't compute penalty figures, don't guess an attribution — say "not enough data" rather than show a confident wrong number.
- Anything printed **as a rule** cites the governing contract; anything state-variable ships as a **configurable default**, not a constant.
- Keep `AGENTS.md` (architecture) and this roadmap current as work lands.
