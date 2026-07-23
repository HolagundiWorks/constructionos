# ACO — Roadmap

_Product: **ACO** (Accelerated Construction Operations; formerly Construction OS)._
_Last updated: 2026-07-23_

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
- **Internalised, one built-in model** (`qwen2.5-coder-1.5b`, Apache-2.0) that runs entirely on the machine — **no picker or catalogue**. The only control is **Start / Stop** on its own **AI Engine** rail row. The on-device runtime is **Microsoft Foundry Local** (its OpenAI-compatible local daemon, auto-selecting the machine's CPU / GPU / NPU), hidden behind the tab; first Start downloads + loads the one model. Verified end-to-end (`foundry_client.generate` → SQL in ~4 s on an RTX-4060 laptop).

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
- **Multi-year / multi-firm** company files — a registry of books with **carry-forward** (masters copied into a fresh year, empty ledger) and a **company-select login** (pick the book, then sign in — web + `/api/login`/`/api/companies`); one-click and synced-folder backup; guarded restore.
- **Windows installer** (PyInstaller + Inno Setup, per-user, no admin); **AGPL-3.0**.

---

## 🚧 In progress · ⏳ Next

> **Two platform tracks (owner-approved).** Beyond the shipped tkinter/browser
> product, development runs on two parallel tracks:
> - **Local — native WinUI 3 client** (`winui/`, `U` phases): the desktop UI
>   replatformed to **stock Fluent controls** over the Python domain (kept as a
>   localhost JSON API). Windows-only, C#/.NET — an owner-approved departure from
>   the stdlib/cross-platform rule **for the front-end only**.
> - **Cloud — headless services** (`C` / `CT` tasks): the shared JSON API,
>   purity, audit/event hooks, tests, docs. No display, no .NET, no ML weights.
>   Backlog in [`CLOUD-TASKS.md`](CLOUD-TASKS.md).

### Local track — WinUI 3 client (`winui/`)

Builds + **runs** on Windows (.NET 10 SDK + Windows App SDK 1.5, self-contained
unpackaged exe). Build output is redirected out of OneDrive; launch with
`winui/run.ps1`. Engineering notes: [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) §9,
Fluent rules: [`UI-PRINCIPLES-AND-GUIDELINES.md`](UI-PRINCIPLES-AND-GUIDELINES.md),
coding standard: `.github/instructions/winui3.instructions.md`.

| Phase | Deliverable | Status |
|---|---|---|
| **U0** | Backend JSON API (`webapi.py`) over the domain | ✅ shipped (u0.11) |
| **U1** | Shell from `/api/menu`; **Excel-style ribbon** (ToggleButton tab strip + AppBarButton icon band, no dropdowns); search palette | ✅ built + runs |
| **U2** | Masters — one generic register page: columnar tables + `FieldForm` CRUD with FK pickers | ✅ built + runs |
| **U3** | Money/Billing/Purchases — generic `MoneyPage` create+list (Payments, Tax/Vendor Invoices, Running Bills) | ✅ built + runs |
| **U4** | Dashboard (KPI cards + `InfoBar` advisories) + charts (KPI/cash-flow/ageing/EVM/portfolio, LiveCharts) | ✅ built + runs |
| **U5** | Controls (Risk/Opportunity/Lessons/Submittals), Process, search; **every catalog tab wired** to tables/forms/charts/reports (no placeholders left); **GST & TDS**, **Weekly Review**, **Accounting** (P&L / Balance Sheet / Journal) + **Look-ahead** (PPC) report pages | ✅ built + runs |
| **U6** | Packaging: backend **auto-launch ✅** + **PyInstaller sidecar ✅** (`ACO.Backend.exe`) + **signed MSIX ✅** (`build-msix.ps1`: assets → publish → `makeappx` → `signtool`, no VS) | ✅ built (dev-signed) |
| **U7** | Persona menus ✅, accessibility (`AutomationProperties`) ✅ mechanical, **parity pass ✅** (every catalog tab is a live page — Tools, Controls registers, EVM/Portfolio/Productivity all real, no placeholders); remaining: interactive a11y walkthrough, retire tkinter on Windows | 🚧 in progress |

**Shipped on the local track since the last update:**
- **ACO rebrand** (Radiant-Orange `#FF4F18` accent, brand strings in `branding.py`); **Light / Dark / follow-Windows** appearance (Settings → Appearance; default Light), alert colours kept semantic — the Fluent "Personal" theme choice from the UI deep-dive.
- **Excel-style ribbon** replacing the top `NavigationView` (both NavigationView-Top and `SelectorBar` native-crash on this SDK); decluttered top bar (utilities as a right-hand icon cluster, Fluent "<8 peers").
- **Generic columnar data tables** (`Ui.Table`) for masters, money docs and **~21 read-only registers**; a generic `DataTablePage`. **Every menu tab now resolves to a live, API-backed page** — the crude text-dump pages (Risk/Opportunity/Lessons/Submittals, EVM detail, Portfolio, Productivity) were replaced with real tables + headline cards, and no `InfoPage` placeholder is reachable from the menu.
- **Multi-company** in the client: a **company picker** in Settings (editable ComboBox from `/api/companies`) whose choice is sent on login (`AppSettings.Company` → `/api/login`), and the **active book shown in the window title** (`ACO — <book>`).
- **In-session company/connection switch** — Settings → Save re-logs in and rebuilds the shell in place (`App.MainWindow.ReloadShell()`), landing on Home.
- **Startup native crash** (`0xc000027b` heap corruption) cut to ~0–1/16 via a timer-deferred shell build.

**Local track — next:**
- ✅ **U6 packaging** — backend **auto-launch + PyInstaller sidecar** (`BackendLauncher` starts the bundled `ACO.Backend.exe`, built by `winui/build-sidecar.ps1`, when the port is free — verified end-to-end, no Python needed) **and a signed MSIX**: `winui/build-msix.ps1` generates the visual assets, publishes self-contained, bundles the sidecar, packs with `makeappx` and signs with `signtool` — no Visual Studio. Produces a ~77 MB `ACO_1.0.0.0_x64.msix` (dev-signed `CN=Human Centric Works`). **Remaining for release:** swap the self-signed dev cert for a real code-signing cert, and a test install/launch on a clean box.
- ✅ **Wired the richer data the cloud track adds** — CT-6 table metadata (`Ui.Table` honours the server's `columns`/`cols`: labelled, ordered, right-aligned, FK names), CT-7 **AccountingPage** (P&L / Balance Sheet / Journal), CT-9 **LookaheadPage** (PPC + weekly trend + misses).
- 🚧 **Accessibility** — page headings (`PageTitleStyle` → `HeadingLevel`), search + control names (incl. the new Accounting period box + Look-ahead per-week bars / stat cards via `AutomationProperties.Name`), decorative icons `Raw`; **contrast measured** — Radiant-Orange `#FF4F18` on white is 3.29:1 (WCAG AA for *large* text only, which is the only place it's used for text). Remaining is inherently interactive: a screen-reader walkthrough and a focus-visual/keyboard pass on a display.
- ✅ **Parity pass** — every `SECTIONS_CATALOG` tab now resolves to a real page (master / money doc / register / dedicated report). The last always-on gap, **Tools**, is wired: a `ToolsPage` over new `/api/firm` + `/api/modules` (firm letterhead identity + module on/off toggles, CSRF-gated). Still desktop/browser-only (not in the JSON API): backup/restore, invoice-number series, reference-data load, and language — a future Tools follow-up.
- ⏳ **Retire tkinter on Windows** — blocked until the desktop-only Tools bits above are exposed; a product call.
- ⏳ Residual intermittent startup crash — a WinUI-framework flakiness on this SDK; watch, consider a WindowsAppSDK bump. (Not fixed by churn: needs many interactive launches to verify, so left as a watch item rather than a blind SDK bump.)

### Cloud track — headless services

- ✅ **C0–C14 / API u0.11** — masters, money docs, EVM, cashflow, ageing, GST, review, chart shapes, the read-only register whitelist (`_API_TABLES`), event hooks, audit origin, signal feed, Tools settings (`/api/firm`, `/api/modules`).
- ✅ **Multi-company backend** — registry + carry-forward + company-select login (web + `/api/login` / `/api/companies`).
- ✅ **CT-6 … CT-10** (see [`CLOUD-TASKS.md`](CLOUD-TASKS.md)): rich register-table metadata + FK names (`web_tables.py`), `/api/pnl` + `/api/balance_sheet` (`reports_store.py`), `cols` headers on reports, `/api/lookahead` (`lookahead_store.py`), multi-company audit. All now consumed by the WinUI client (above).

### Cross-cutting (both tracks)
- ✅ **Enterprise PM backbone — fully surfaced** (EVM, risk, opportunity, forecast, KPIs, narration/review-pack) on desktop + browser + WinUI. See [`ENTERPRISE-PM-GAP-AND-ROADMAP.md`](ENTERPRISE-PM-GAP-AND-ROADMAP.md), [`EXECUTION-PART2.md`](EXECUTION-PART2.md).
- ✅ **Browser / LAN parity** — RA-bill statutory docs (Form 23 MB, Form 26 abstract), per-item measurement entry, compliance register, GST/TDS view.
- ✅ **Real-display GUI render check** — full tkinter suite green on a Windows box with a display (see [`CHANGELOG.md`](CHANGELOG.md)); headless CI skips the 3 GUI smokes (no Tk).
- ⏳ **L8** OCR/STT/VLM model sidecars over `sidecars/stub_server.py` (install weights locally).

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
