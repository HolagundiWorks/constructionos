# Changelog — Construction OS

Notable changes, newest first. Dates are `YYYY-MM-DD`. This log records *what*
changed and *where* it lives; `docs/ROADMAP.md` tracks the phase status and
`AGENTS.md` §23 documents the architecture of the later modules.

---

## 2026-07-22 — WinUI: Excel-style ribbon, U3 money forms, startup-crash fix

- **Excel-style ribbon shell.** Replaced the top `NavigationView` with a
  `ToggleButton` section tab strip + an `AppBarButton` **command band**: picking a
  section (Masters, Billing, Money…) fills the band with that section's tabs as
  icon-over-label commands (Segoe MDL2 glyphs via `Helpers/RibbonIcons.cs`) rather
  than a dropdown. Both the strip and band scroll horizontally on narrow windows.
  `NavigationView` Top and `SelectorBar` were both dropped — they native-crash on
  this Windows App SDK build.
- **Fixed the intermittent startup crash (native heap corruption).** Traced under
  `cdb` to a re-entrant layout race: the shell navigated the `ContentFrame` to the
  first page *synchronously* inside the async menu-load continuation, racing the
  window's first layout → a heap-block overrun → `0xc000027b` fail-fast in
  `Microsoft.ui.xaml.dll` (no managed exception, so nothing logged). Fix: defer the
  first navigation via `DispatcherQueue.TryEnqueue(Low, …)`. Bisected 11/12 → 0/14;
  stress-tested **0/16** startups after the fix.
- **U3 money documents — create + list forms.** One generic `MoneyPage` (doc table
  = nav parameter) now serves **Payments, Tax Invoice, Vendor Invoices, Running
  Bills** through the shared `FieldForm` (FK pickers for Client/Vendor/Contract,
  gated follow-ups in an `InfoBar`); title/fields/rows all come from
  `GET /api/<doc>`. Verified live (Tax Invoice dialog renders the Client FK + 5
  inputs; posts via the backend engine).

---

## 2026-07-22 — WinUI shell: top ribbon nav (was left sidebar)

- **NavigationView is now a top ribbon** (`PaneDisplayMode="Top"`, was `Left`):
  the sections render as a horizontal bar, and WinUI **natively auto-collapses**
  items that don't fit into a "More" (») overflow flyout as the window narrows —
  the requested auto-collapse, with no custom chrome. Section parents open a
  dropdown of their tabs; the search palette + Settings gear sit in the bar.
  Stock control only; routing/selection unchanged. `dotnet build` 0 errors.
- **Title bar kept standard** (`ExtendsContentIntoTitleBar = false`): with a top
  ribbon, extending content into the title bar made the nav collide with the
  caption/close buttons — the OS title bar now sits cleanly above the ribbon.
- **Fixed: only "Home" showed in the ribbon.** `Nav_Loaded` probed
  `GET /api/health` **before** logging in, but that endpoint needs a session
  (401 without) — so the whole nav build hit its catch and fell back to a lone
  Home item. Now it calls `EnsureSessionAsync()` first and treats the (cosmetic,
  title-only) health probe as non-fatal, so the full always-on + section menu
  loads.

---

## 2026-07-22 — Switch the internalised AI from Ollama to Foundry Local

Replaced the built-in AI runtime with **Microsoft Foundry Local** (its
on-device, OpenAI-compatible daemon) — same product decision as before (one
hardcoded model, no picker, Start/Stop), a Windows-native runtime that
auto-selects the machine's CPU / GPU / NPU.

- **New `foundry_client.py`** (stdlib `urllib`) — chat completions via the
  OpenAI `/v1/chat/completions`; endpoint **discovered** from the CLI (the
  daemon picks a dynamic port). **New `foundry_service.py`** wraps the CLI:
  `server start/stop/status`, `model download/load/unload`, and `provision()`
  (download + load the one model on first Start). `_run` decodes CLI output as
  UTF-8 (the CLI emits ●/progress glyphs) so it never chokes on a Windows
  codepage.
- **Model:** `qwen2.5-coder-1.5b` — the Foundry Local catalogue's optimized ONNX
  build of the same Qwen2.5-Coder-1.5B the assistant always used.
- **Repointed** `assistant.py`, `tab_assistant.py`, `shell.py` (footer AI dot),
  the **AI Engine tab** (`tab_ollama.py` → `tab_aiengine.py`), and `main.py`.
  **Removed** `ollama_client.py`, `ollama_api.py`, `ollama_service.py`,
  `model_provision.py` and the bundled-GGUF/Modelfile provisioning (Foundry Local
  fetches its own optimized models).
- **Verified end-to-end on this machine:** installed Foundry Local 0.10.2,
  `foundry_service.endpoint()` correctly parsed the live daemon
  (`http://127.0.0.1:55263`), and `foundry_client.generate("…count rows in
  payments")` returned `SELECT COUNT(*) FROM payments;` in ~4 s on an RTX-4060.
  Tests: `TestFoundry` (default model, endpoint fallback, unreachable →
  `FoundryError`, service fails-soft without the CLI, model still hardcoded);
  GUI smoke builds the new AI Engine tab. Full suite **713 green**.

---

## 2026-07-22 — Real-display GUI render check: done (713 tests, 0 skipped)

- **Ran the tkinter GUI suite on a real display** (Windows 11 + Tk), which the
  head-less CI can't. The whole suite is **713 tests, 0 skipped, all green** —
  the 3 GUI smoke tests that skip on a display-less runner run and pass here:
  **every tab builds under both the light and dark themes** (all the merged
  tabs — EVM, Risk, Opportunity, Lessons, Process, Portfolio, Productivity — the
  first proof they render post-merge), the action dock resolves contextually, and
  the project-overview drill-down gathers on seeded data. Roadmap item flipped
  ⏳ → ✅.

---

## 2026-07-22 — WinUI: shared FieldForm (FK pickers) + receivable-ageing chart

Reconciled a parallel WinUI session (`cursor/winui-u4-u5-api-bind`) that had
independently built the same U3/U4/U5 work: adopted its two genuinely-better
pieces onto main and dropped the rest as redundant.

- **`Helpers/FieldForm.cs` — one metadata-driven form** for masters and money
  docs, understanding combo string options **and FK `{id,label}` options** (from
  the U0.7 `enrich_fields`). **FK fields are now a related-master `ComboBox`**
  (label shown, id submitted) instead of a typed id. `MastersPage` and
  `MoneyPage` were refactored onto it (killing the inline form duplication);
  MoneyPage also surfaces gated **follow-ups** in an `InfoBar` after a payment.
  FK enrichment verified live (`/api/labor` `site_id` → `[{id,label}]`).
- **Receivable-ageing chart** added to the Charts page (`/api/ageing`
  `labels`/`values`, CT-4) — U4's charts (KPIs, cash-flow, EVM, ageing) are now
  all built. `dotnet build` 0 errors.
- The redundant branch is deleted.

---

## 2026-07-22 — WinUI U4: cash-flow forecast chart (on cloud CT-4 shapes)

- **Cash-flow forecast on the Charts page.** A second stock LiveCharts chart binds
  `GET /api/cashflow`'s chart-ready arrays (cloud CT-4): projected **money in /
  out as columns** and the **running balance as a line** per forecast week. The
  Python engine still owns the lag maths; the client only plots `labels` +
  `series.{in,out,balance}`. Empty-state caption when there's nothing to project.
  With this, U4's charts (KPIs, cash-flow, EVM) are built — only the ageing
  series is left. `dotnet build` 0 errors.
- Follows the **cloud CT-1…CT-5 merge** (pure `gst.py`, `/api/gst`,
  `/api/measurements` CRUD, chart shapes, a master-API audit-commit fix) — merged
  reconciled with the WinUI work; **713 tests green**.

---

## 2026-07-22 — WinUI U3: record a payment from the client

- **MoneyPage is now write-capable.** A `CommandBar` **New payment** button opens
  a stock `ContentDialog` **built from the API's field metadata** (`GET
  /api/payments` → kind/options/default/required), rendered with stock inputs
  (`ComboBox` / `NumberBox` / `TextBox`), then `POST /api/payments` — which the
  Python engine computes and **posts to the ledger** via `journal_post.post_all`.
  Create-only (a payment is a record of fact). No maths in C#.
- **Verified end-to-end**, not just compiled: restarted the backend on current
  code, `POST /api/payments` returned **201** with the created row (id, amount,
  direction…) and the list reflected it. `dotnet build` 0 errors. The same
  metadata-driven form pattern extends to tax/vendor invoices and bills next.

---

## 2026-07-22 — WinUI U5: command-palette search in the shell

- **Global tab search.** A stock `AutoSuggestBox` in the `NavigationView` search
  slot: typing queries `GET /api/search`, shows the matched tabs, and picking one
  navigates to it. The rail selection and the search palette now share **one**
  `NavigateTo(tag)` (master tabs → generic `MastersPage`; everything else via
  `NavRoute`), so both route identically. Search is best-effort — a backend
  hiccup clears suggestions, never crashes the shell. `dotnet build` 0 errors.

---

## 2026-07-22 — WinUI U4: Earned Value page — per-project CPI/SPI chart

- **EVM page plots real performance.** `Views/EvmPage.*` now reads
  `GET /api/evm` (`{rows, portfolio}`) and draws a stock LiveCharts **grouped
  column chart** — cost (CPI) and schedule (SPI) per project, with a portfolio
  summary line (projects · CPI · SPI · over-cost · behind · "1.0 = on plan") and
  the full per-project detail below. Null indices (AC/PV not booked yet) render
  as gaps via `double?` values, not fake zeros. Fixes the old page, which read
  the wrong keys (`projects`/`items`) and always showed nothing. No EVM maths in
  C#. `dotnet build` 0 errors.
## 2026-07-22 — Cloud CT-1…CT-5: pure GST, measurements API, chart shapes

Headless backlog from `docs/CLOUD-TASKS.md` (no WinUI / display):

- **CT-1.** New pure `construction_app/gst.py` (`outward` / `inward` /
  `hsn_summary` / `tds_register`). `tab_gst` and browser `/gst` import it —
  no lazy Tk for the LAN view.
- **CT-2.** `GET /api/gst?month=YYYY-MM` →
  `{month, outward, hsn, inward, tds}`.
- **CT-3.** `measurements` on the JSON masters CRUD; blank dims stay NULL;
  quantity via shared `web_masters.derive` → `civil.measurement_quantity`;
  list filter `?contract_id=`.
- **CT-4.** Parallel `labels`/`values` (cashflow also `series`) on
  `/api/cashflow`, `/api/ageing`, `/api/evm` alongside existing detail.
- **CT-5.** Audit coverage for measurement writes + empty-DB read sweep in
  `TestWebApi`. Master CRUD now commits **after** `auth.audit` (was before —
  audit rows were dropped on close).
- API version **u0.8**. Docs: `docs/API.md`, this entry; `CLOUD-TASKS` marked done.
- Suite: **713** tests OK (5 skipped, no display).

---

## 2026-07-22 — WinUI U4: Home dashboard — KPI stat cards + InfoBar advisories

- **Home page is a real dashboard now.** `Views/HomePage.*` renders the money
  snapshot from `GET /api/kpi` as a horizontally-scrolling band of **stock KPI
  stat cards** (cash / receivable / payable / net position / billed / collected
  this month, `Border` + Fluent card brushes), and the `/api/dashboard`
  advisories as stock **`InfoBar`s** severity-mapped (act→Error, watch→Warning,
  good→Success) — replacing the flat text list. No maths in C#; every figure
  comes from the API. `dotnet build` 0 errors.
- Also added **`docs/CLOUD-TASKS.md`** — the headless "C"-track backlog for the
  cloud agent (pure `gst.py`, `/api/gst`, `/api/measurements`, chart-ready
  API shapes, audit sweep), each with acceptance tests + the stdlib/tkinter-free
  rules; WinUI / MSIX / ML weights explicitly out of its scope.

---

## 2026-07-22 — Cloud U0.7: WinUI API thickenings

Continue headless API work that unblocks local U3–U5 without .NET:

- **FK options.** `web_masters.enrich_fields` resolves `fk_sql` →
  `options:[{id,label}]` on master/doc list payloads.
- **Contracts master** + browser create; `GET/POST /api/contracts`.
- **BOQ.** `GET /api/boq_items?contract_id=`; BOQ import confirm covered in tests.
- **Running bills.** `GET /api/bills/previous?contract_id=`.
- **Cashflow.** `cashflow_assemble` + `GET /api/cashflow` (plottable buckets).
- **Ageing.** Plottable `buckets` array on `GET /api/ageing`.
- **Allocations.** `GET/POST /api/allocations` over `allocation.py`.
- **PO create.** `POST /api/purchase_orders` with items → derived total.
- **Search.** Record hits carry `nav`/`tag` for WinUI AutoSuggest.
- API version **u0.7**; WinUI `MasterTables` includes Contracts.
- Suite: **708** tests OK (5 skipped).
## 2026-07-22 — Browser / LAN parity complete: measurement entry, compliance, GST

- **Per-item measurement entry in the browser** (the last desktop-only gap). A
  writable `measurements` register (Billing group) with the BOQ item + contract
  pickers, dimensions, and MB reference. **`quantity` is derived on save**
  (`Nos×L×B×D` via `civil.measurement_quantity`) — and a new `dim` field kind
  keeps a blank dimension **NULL** (factor 1, "not applicable"), so a
  running-metre item measured as Nos×L doesn't get zeroed by a `0` breadth.
- **Compliance-filings register writable in the browser** (Accounts group). The
  obligation is picked by friendly name and **stored as its stable
  `compliance.OBLIGATIONS` key**, so browser-entered filings line up with the
  desktop calendar.
- **GST & TDS view in the browser** (`/gst`, read-only). Outward supplies
  (GSTR-1), HSN/SAC summary, inward ITC and the TDS register for a month —
  computed by the desktop's *own* `tab_gst.outward/inward/hsn_summary/
  tds_register`, lazy-imported so the two surfaces report identical figures.
  A computed report, so it stays view-only by design.
- **Mechanism:** `web_masters` gains a small `derive(table, values)` hook (fills
  computed columns like the measurement quantity before insert/update); the
  webapp create/edit routes apply it. Registers placed in the nav
  (measurements→Billing, compliance→Accounts) + a `/gst` rail link.
- **Tests.** Browser measurement create asserts the derived quantity **and** that
  a blank breadth stays NULL; compliance create asserts the obligation-key
  mapping; the `/gst` view renders with its rail link. Full suite **709 green**.

---

## 2026-07-22 — WinUI U4: ChartsPage plots a real LiveCharts series

- **First real chart.** `Views/ChartsPage.*` now binds a stock LiveCharts
  `ColumnSeries` to the money snapshot from `GET /api/kpi` (cash, receivable,
  payable, net position, billed / collected this month) with a labelled X axis —
  replacing the previous key-dump placeholder. No maths in C#: the API computes
  every figure; the page only renders what it returns, and shows a plain "nothing
  recorded yet" line when the bars are all zero.
- **Native dependency verified.** LiveCharts renders through SkiaSharp's native
  `libSkiaSharp.dll`; confirmed it (and the LiveChartsCore / SkiaSharp assemblies)
  deploys into the self-contained `win-x64` output, so the Charts tab renders on a
  clean machine rather than crashing on a missing native lib. `dotnet build` 0
  errors. Remaining U4: EVM/ageing series + the KPI stat cards.

---

## 2026-07-22 — Roadmap honesty pass (post WinUI harden + local run)

- Reconciled [`ENTERPRISE-PM-GAP-AND-ROADMAP.md`](ENTERPRISE-PM-GAP-AND-ROADMAP.md)
  v1.2: counts (176 modules / 113 tkinter-free / 705+ tests), §4 priority short
  list, glance/waves/summary “Next” columns, E0–E4 leftover notes, L8 stub
  server. Aligned with local proof that **U1/U2 build and run** (ListView).
  [`ROADMAP.md`](ROADMAP.md) / [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) §9.

---

## 2026-07-22 — WinUI client compiles (U1–U5) + branch merge

- **Merged** `cursor/complete-remaining-roadmap-32b0` into main (Controls/Process/
  persona desktop tabs, `portfolio_store` + `workflow_state`, `productivity_store`,
  AI sidecar scaffolds, and the WinUI U3–U5 pages) — reconciled with main's U0
  audit fix and U2 masters CRUD. Conflicts in `MainWindow.xaml.cs` (routing unions
  the master tabs + the new pages), `README.md` and the changelog were resolved as
  unions. Merged Python tree: **671 tests green**.
- **The WinUI client builds.** `dotnet build -p:Platform=x64` (.NET 10 SDK +
  Windows App SDK) compiles the whole solution — shell, `MastersPage`,
  Money/EVM/Charts, Controls (Opportunities/Lessons/Submittals) + Process pages,
  `ApiClient` — with **0 errors** (one benign `NETSDK1206` RID warning). First real
  verification of the previously-uncompilable scaffold. *Compile* proof, not yet a
  *run* proof (launching against the backend + screenshots is next).
- **`.gitignore`** now excludes .NET build output (`bin/`, `obj/`, `.vs/`, MSIX).

---

## 2026-07-22 — WinUI client runs (fixes: manifest, DataGrid→ListView, packaging)

Got the merged WinUI U1–U5 client to actually **launch and render** a responsive
"Construction OS" window against the Python backend (was: compile-only). Four
scaffold fixes, all found by launching and reading the crash/event logs:

- **`app.manifest` root was `<manifest>` not `<assembly>`** → activation failed at
  process start ("side-by-side configuration is incorrect"). Fixed to a valid
  Win32 manifest (+ PerMonitorV2 DPI, long-path aware).
- **CommunityToolkit DataGrid (7.1.2) is UWP/WinUI-2** and crashes WinUI 3 at
  startup (`Cannot locate …themeresources.xaml`); it was never ported to WinUI 3.
  Replaced it across **all** register pages (Risks, Opportunities, Lessons,
  Submittals, Money, EVM, Portfolio, and the U2 Masters CRUD) with the **stock
  WinUI `ListView`** + a small `Ui.Lines` helper — which also satisfies the
  roadmap's "stock controls only" rule. Masters keeps add/edit/delete via the
  `CommandBar` with selection mapped back to the record by index.
- **`<UseRidGraph>true</UseRidGraph>`** so WindowsAppSDK's native win-x64 assets
  deploy (clears `NETSDK1206`), and **`<WindowsPackageType>None</WindowsPackageType>`**
  so it runs unpackaged via the bootstrapper.
- **`App.xaml.cs`** gains a dev crash-logger (UI/CLR/task unhandled exceptions →
  `%TEMP%\cos_winui_crash.log`) that made the above diagnosable without a debugger.

Verified: `dotnet build -p:Platform=x64` → 0 errors; the self-contained exe
(bundles .NET 8 + WindowsAppSDK) shows a responsive window (`Responding=True`,
title "Construction OS") that logs in and loads the persona menu. See
[`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) §9 for the run recipe. Python side
unchanged.

---

## 2026-07-22 — WinUI U2 scaffold: generic masters DataGrid CRUD

- **One metadata-driven CRUD page for every master.** `Views/MastersPage.*`
  (WinUI, scaffold) is navigated to with a table name; it calls `GET /api/{table}`
  and builds both the `DataGrid` columns and the add/edit `ContentDialog` **from
  the API's field metadata** (`fields`: key/label/kind/options/default/required),
  then writes via `POST`/`PUT`/`DELETE /api/{table}` with the CSRF header. One
  page replaces the tkinter `CrudFrame` for all ten masters — no per-master XAML.
  Stock Fluent controls only (`DataGrid`, `CommandBar`/`AppBarButton` with Segoe
  Fluent glyphs, `NumberBox`/`ComboBox`/`TextBox`, `ContentDialog`, `InfoBar`).
- **`ApiClient` gained `PutJsonAsync` / `DeleteAsync`** (shared CSRF body writer)
  and an `ApiException` that surfaces the API's `{"error"}` text — so a Viewer's
  403 or a validation 400 shows in the page's `InfoBar` rather than crashing.
- **Shell wiring:** `MainWindow` routes any master tab (section-agnostic, by tab
  label) to `MastersPage` via a `MasterTables` map.
- **Windows-only:** this is C#/XAML scaffold — it compiles under VS 2022 +
  Windows App SDK, not in the headless environment. The Python side is unchanged;
  the domain + API stay covered by the 663-test suite. Known refinement: FK fields
  are entered by id (a related-master picker is next). Spec:
  [`docs/WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md) §9 (U2).

---

## 2026-07-22 — U0 hardening: JSON-API writes now audit reliably

- **Fixed: API write audits were silently dropped.** `PUT`/`DELETE /api/risks`
  and every `POST`/`PUT`/`DELETE /api/opportunities` wrote an `audit_log` row but
  never committed it — the register store committed the *change* first, so the
  later `auth.audit(...)` insert sat in an uncommitted transaction and was rolled
  back on connection close. The audit trail (a governance guarantee the contract
  promises: "every write audited") was missing those actions. Added the missing
  `conn.commit()` to the five affected handlers in `webapi.py`.
- **Regression test.** `TestWebApi.test_api_writes_are_audited` drives
  create/update/delete for a risk and an opportunity through the API and asserts
  all six `api_*` rows appear in `GET /api/audit`. Swept every read endpoint
  (health, dashboard, menu, workflow, evm, review, portfolio, all masters + docs)
  — all 200. Full suite 663 green.

## 2026-07-22 — Harden local WinUI + sidecar soft-fail stubs

- **WinUI ApiClient.** Timeouts, Put/Delete, health probe, CSRF on writes,
  `ApiException` with status/body, session reset; `AppSettings` persisted under
  `%LOCALAPPDATA%\Construction OS\winui-settings.json`.
- **Shell.** Typed `NavRoute`, Settings gear page (URL/user/persona/timeout +
  Test health), menu persona from settings, offline fallback messaging.
- **Pages.** Shared `JsonRows` / `PageLoad`; status lines and pretty JSON on
  Home/Process/registers/Money/EVM/Portfolio/Productivity/Charts/Capture/Import.
- **Sidecars.** Stdlib `sidecars/stub_server.py` (loopback `/health` + `/extract`)
  and `health_check.py`; unit tests for stub extract + live probe.
- **Docs.** `winui/README.md`, `PACKAGING.md`, roadmap L5–L7 notes. (Later local
  work proved compile + run — see entries above.)

---

## 2026-07-22 — Finish cloud track: U0.6 GRN confirm, vendor invoice, PDF text

- **GRN confirm.** `POST /api/grn/confirm` writes Draft GRN + lines (no stock
  post) and returns `GRN_SAVED` follow-ups.
- **Vendor invoice floor.** `vendor_invoice_draft` + `/api/vendor_invoice/draft|confirm`
  with `finance.invoice_totals`.
- **PDF text.** `pdf_text.py` + `POST /api/pdf/extract` via local `pdftotext`
  (soft-fail).
- **Events.** `SNAG_RAISED`, `RUNNING_BILL_APPROVED` + API/GUI wiring
  (snag confirm, bills create, Blocker snag save, running-bill approve).
- **Cloud track closed** for deterministic floors; remaining work is local
  (display smoke, WinUI build/MSIX, model weights, SSO).

---

## 2026-07-22 — Continue: U0.5 GRN draft, signal suggest, mobile modes

- **GRN draft floor.** `material_match` + `grn_draft` + `POST /api/grn/draft`
  (challan paste → matched lines; no stock post).
- **Measurement extract.** `text_extract` target `measurement` (Nos×L×B×D).
- **Live signal suggest.** `signal_suggest` + `POST /api/signals/suggest` (PPC/RFI
  soft signals → drift → preview drafts; opt-in apply). Process tab shows preview.
- **Mobile capture modes.** `/m/capture` — work done / paste note / muster names
  with Preview→Confirm.
- **WinUI** `ImportPage` scaffold for GRN/BOQ/text/signals.
- **API u0.5.** Predictive weak-signal row marked partial (drift+suggest built).

---

## 2026-07-22 — Continue: U0.4 capture floors, pattern learn, more events

- **Text extract.** `text_extract.py` + `POST /api/text/extract` — WhatsApp/site
  notes → DPR / work-done / NCR / snag drafts; confirm targets expanded.
- **Muster match.** `labor_match` + `muster_draft` + `/api/muster/draft|confirm`
  (difflib name match → attendance).
- **BOQ import.** `boq_import.py` + `/api/boq/import/draft|confirm` (CSV/TSV/plain).
- **Pattern learn.** `pattern_learn.py` + `POST /api/patterns/learn` (opt-in AI
  lesson drafts from recurring negatives / high risks).
- **Signals preview.** `POST /api/signals/preview` (no write).
- **Events.** `RA_BILL_APPROVED`, `NCR_RAISED`, `ATTENDANCE_SAVED` + GUI wiring
  on RA status, Critical NCR save, muster save, inspection→NCR raise.
- **API u0.4.**

---

## 2026-07-22 — Continue: U0.3 intent/sidecar/narrative, Productivity, concurrency notes

- **NL intent floor.** `nl_intent.py` maps free text → gated `followups` /
  `workflow` drafts; `POST /api/intent` (nothing auto-runs).
- **Sidecar bridge.** `sidecar_bridge.py` soft-fails OCR/STT/VLM localhost
  probes; `GET /api/sidecar/status`, `POST /api/sidecar/extract` → `capture`
  drafts. Stub READMEs updated with HTTP contract.
- **Narrative API.** `GET /api/narrative?kind=kpi|risk` over `narrative.py`.
- **Productivity tab.** Operations › Productivity over `productivity_store`;
  WinUI `ProductivityPage` + `CapturePage` scaffolds.
- **Payment event wiring.** Cash & Parties payment create surfaces gated
  `PAYMENT_DUE` follow-ups (same pattern as GRN).
- **API u0.3.** Health/contract version bump.
- **Concurrency notes.** `docs/CONCURRENCY.md` — honest single-file limits, no
  redesign.
- Gap glance / E0.3 / E7.3–E7.4 hygiene (already-shipped items marked built).

---

## 2026-07-22 — Continue: N4 records, U0.2 API, portfolio advisory, audit default

- **N4 record search.** `record_search.py` + Process palette + `GET /api/search`
  returns tabs **and** records (`/t/{table}/{id}` hrefs).
- **U0.2 API.** `purchase_orders` / `goods_receipts` lists, `/api/match` (with
  narration), `/api/reconcile`, `/api/ageing`, `/api/filings/feed`; health
  version `u0.2`.
- **Audit default.** `auth.audit` defaults to `origin=manual`; manual filter
  includes legacy NULL rows.
- **Events.** Capture confirm raises `ACTIVITY_COMPLETE` follow-ups;
  `compliance_feed` drafts `FILING_DUE` from overdue/due-soon filings.
- **Portfolio advisories.** `advisory.for_portfolio` on `/api/portfolio`.
- **PO↔invoice narration.** `finance.narrate_reconcile`.
- **Drift guard.** Headless test: `BUILDERS` / `MODULE_ICONS` cover every
  catalog label (no `import main`).
- Gap table hygiene for portfolio / audit / narration / productivity / N4.

---

## 2026-07-22 — Continue: N5 groups, portfolio, productivity, match narration

- **N5 grouping.** Billing/Operations section notebooks render `menu.GROUPS` as
  nested group tabs; Process deep-link walks nested notebooks.
- **More event wiring.** Measurement save and variation Approve surface gated
  `event_hooks` drafts (same pattern as GRN).
- **Portfolio shell.** Money › Portfolio tab + WinUI `PortfolioPage` over
  `portfolio_store` (federated paths optional).
- **Productivity bridge.** `productivity_store` feeds Key Numbers +
  `GET /api/productivity` from muster/plant/work-done (pure ratios unchanged).
- **3-way match narration.** `procurement.narrate_match` / `narrate_summary`
  on the Goods Receipt match view.
- **Nav status.** N1–N3/N5/N6 marked built in the gap table; N4 partial (tab
  search only).

---

## 2026-07-22 — Remaining roadmap: Controls / Process / persona / WinUI / field

- **L1 Controls section.** `modules.SECTIONS_CATALOG` gains **Controls** (Risk
  Register, Opportunity Register, Lessons Learned, Submittals); Risks /
  Opportunities leave Project Management. Labels align with `menu.CONTROLS_SECTION`.
- **L2 Lessons Learned tab.** New `tab_lessons_learned.py` over `lessons_store`
  (distinct from Rate Realisation `tab_lessons.py`).
- **L3 Persona rail.** Tools › Persona persists `app_settings.persona`;
  `main.py` builds the rail via `menu.resolve`.
- **L4 Process + search.** Always-on Process rail (`tab_process.py`) over
  `workflow` + new `workflow_state.infer`; command search via `menu.search_tabs`.
- **L4 event wiring.** GRN add/post surfaces `event_hooks` drafts (no auto-post);
  payment create API returns gated follow-ups.
- **L6–L7 WinUI scaffolds.** Opportunities / Lessons / Submittals / Money / EVM /
  Charts pages + `winui/PACKAGING.md` (MSIX notes). Still Windows-only to build.
- **L8 sidecar stubs.** `sidecars/{ocr,stt,vlm}/` READMEs — no weights in-repo.
- **L9 field capture (E6-lite).** `/m/capture` mobile web form +
  `POST /api/capture/draft|confirm` over `capture.py`.
- **Tests.** 667 headless OK (5 skipped without tkinter). GUI smoke still needs
  a local display (L0).

---

## 2026-07-22 — Roadmap continue: U0.1 API widen + WinUI U1 scaffold

- **API u0.1.** Money docs create (`payments`, invoices, bills), submittals CRUD,
  `GET /api/portfolio`, `POST /api/forecast` + `/api/drift`,
  `GET /api/contract` catalogue. Spec: [`docs/API.md`](API.md).
- **WinUI U1 scaffold** under `winui/ConstructionOS.WinUI/` — NavigationView
  shell, ApiClient (cookie+CSRF), Home / Risks / Process pages. Compiles only on
  Windows (VS 2022 + Windows App SDK); see `winui/README.md`.
- **Tests.** Web suite green; full headless suite OK.

---

## 2026-07-22 — Cloud track: C3–C6 (audit origin, signal feed, events, lessons API)

- **C3 AI-origin audit.** `audit_log.origin` (`manual`/`ai`) + `auth.audit(..., origin=)`;
  `capture.origin_of` for confirmed capture drafts.
- **C4 signal feed.** `signal_feed.py` turns drift / schedule forecast / rising
  cost trends into AI risk drafts (`source='ai'`), with dedupe + audit.
- **C5 event hooks.** `event_hooks.react` composes `followups` + optional
  `risk_detect`; gated flags preserved.
- **C6 lessons API.** `/api/lessons` CRUD; also `/api/events`, `/api/signals/feed`,
  `/api/audit?origin=ai`.
- **Tests.** 661 headless OK (5 skipped).

---

## 2026-07-22 — Cloud track: C0 purity + U0 JSON API

- **C0 headless purity.** Cost/revenue DB bridge moved to tkinter-free
  `project_rollup.py`; `evm` / dashboard / KPI no longer import `tab_projects`.
  `lessons.apply_rates` extracted; display-only theme tests skip without tkinter.
- **U0 JSON API (`webapi.py`).** Session-gated `/api/*` over the domain: health,
  me, login, dashboard/KPI, menu, workflow, EVM, review, risks, opportunities,
  and masters CRUD. CSRF via `X-CSRF-Token` / body; Viewers read-only.
  `webserver` accepts JSON bodies and PUT/DELETE.
- **Tests.** `TestWebApi` in `test_web.py`; full headless suite 648 OK (5 skipped).

---

## 2026-07-22 — Cloud vs local roadmap split (actionable)

- **Roadmap §5A / §5B expanded** into ordered action plans for the two
  development environments (cloud headless Python vs local Windows/.NET/display).
  Companion status tables refreshed for shipped EVM / Risk / Opportunity / Weekly
  Review surfaces; Lessons Learned register tab still called out as pending.
- **Cloud actions** C0–C6 delivered (see entries above); **local next**: residual
  E7 UI (Controls, Lessons Learned tab, Process view, persona rail), then WinUI
  **U1–U7** against the JSON API.
- Agent memory (`CLAUDE.md`, `AGENTS.md` headline counts) and
  `EXECUTION-PART2.md` maturity tags aligned with the tree.

---

## 2026-07-22 — RA-bill statutory documents in the browser (Form 23 + Form 26)

- **Measurement Book and RA abstract, printable from the browser.** An RA bill's
  record view now lists its **measured items** and offers two print links:
  **Measurement Book (Form 23 / CMB)** for the whole contract, and the
  **PWD-style RA abstract (Form 26)** for that bill. Each opens as a standalone
  printable page (browser Print / Save-as-PDF), generated by the *same* pure
  `bill_export` builders the desktop uses.
- **`mb_report.py` — one assembler for both surfaces.** The SQL that turns
  measurements / RA items into the rows those builders need now lives in a single
  DB bridge (`mb_report.py`), and **both the desktop tab and the browser route
  call it** — the measurement book a contractor prints from the laptop and the
  one a client opens over the LAN can no longer drift apart. The desktop
  `export_mb` / `export_pwd` were refactored onto it (dropping their duplicated
  queries).
- **What's still desktop-only:** per-item measurement *entry* (the dimension
  grid). Viewing and printing the statutory documents is now at parity.
- **Tests.** `mb_report` (Form-23 markers + the measured entry; the PWD abstract;
  a missing bill → `None`) in `test_core`; the `/t/ra_bills/<id>/mb` and `/ra`
  routes plus the record-view items table in `test_web`. Also hardened the
  pre-existing `test_viewer_cannot_apply` so the Viewer read-only **dialog can't
  block a head-less run** (a leaked Tk root made its modal hang intermittently).
  Full suite 628 green.

---

## 2026-07-22 — Opportunity register + Weekly Review — Enterprise-PM UI complete

- **Opportunity register** (Project Management › Opportunities). The upside twin
  of the risk register, over the existing pure `opportunity.py` /
  `opportunity_store.py`: likelihood × impact → band, probability-weighted
  **expected upside**, urgency-driven priority — all **computed live and never
  typed**, derive-on-save so a stored band can't drift. Best-first, with the
  strongest opportunities washed green (pursue) rather than red. Writes gated for
  Viewers; sortable columns.
- **Weekly Review** (Money › Review, and browser `/review`). The whole weekly
  review assembled in one call by the pure `review_pack.build`, bridged to the
  live database by the new `review_assemble.py`: a plain-language narrative
  (`narrative.py`), money at a glance, the portfolio EVM, advisories, and the
  risk & opportunity summaries. It states on screen that it is **a draft to
  read, not a decision — nothing here books, files or pays**. Desktop tab and
  the browser page render one identical pack (shared assembler), so the two
  surfaces can never disagree.
- **Enterprise-PM backbone is now fully surfaced** — every pure module (EVM,
  risk, opportunity, forecast, narrative, review-pack, lessons, submittals) has
  a screen.
- **Tests.** `review_assemble.assemble` (KPIs + EVM + opportunities present; EVM
  honestly absent when no project is measured) in `test_core`; the `/review`
  route + rail link in `test_web`; both new tabs build in the GUI smoke test.
  Full suite 623 green.

---

## 2026-07-22 — Earned Value (SPI / CPI / EAC) — desktop tab + browser view

- **Earned Value surfaced.** A new read-only **Project Management › Earned
  Value** tab (and a matching browser page at `/evm`) shows, per project, the two
  performance indices **SPI** and **CPI**, percent complete, the forecast
  **EAC / VAC**, and a plain health verdict — over a **value-weighted portfolio**
  roll-up (a big overrunning job can't hide behind small tidy ones), sorted
  worst cost-performance first.
- **`evm.py` — the honest DB bridge.** The maths stays in the pure, already-tested
  `earnedvalue.py`; `evm.py` only decides where the four base numbers come from:
  **BAC** = contract value (fallback budget), **AC** = the project cost roll-up's
  `total_cost`, **EV** = the roll-up's billed `revenue`, **PV** = `BAC ×` the
  elapsed fraction of the project's start→end window. Both proxies (EV tracks
  *billed* not raw progress; PV is time-scheduled, not a baseline S-curve) are
  **footnoted on screen**, not hidden. Undefined indices render as `—`, never
  faked. DB-only and head-less-safe (the cost roll-up is imported lazily, as
  `dashboard`/`tab_kpi` already do), so desktop and browser share one definition.
- **Tests.** `evm.planned_pct` (elapsed-fraction clamping, `None` on missing/
  degenerate dates) and the assembly wiring (BAC fallback, PV derivation, the
  "skip projects with no value to measure" rule) are unit-tested with the cost
  roll-up mocked; the `/evm` route and its rail link are covered in `test_web`.

---

## 2026-07-22 — Browser / LAN access: printable estimate

- **Print / Save-as-PDF an estimate from the browser.** The estimate record view
  gains a *Print / Save as PDF* link that serves the fully-formatted document
  (letterhead, priced items, subtotal → contingency → GST → grand total, amount
  in words), generated by the *same* pure `bill_export.build_estimate_html` the
  desktop uses — so the browser and desktop produce the identical document. It
  opens as a standalone page (not the app chrome) that the browser prints or
  saves to PDF. Login-gated like every other route.

---

## 2026-07-22 — Tables: sortable columns; browser lists scroll, not page

- **Sortable columns everywhere.** Click a column header to sort (numeric-aware
  — ₹/commas stripped so amounts sort as numbers), toggling ascending/descending
  with an ▲/▼ arrow. Desktop: a reusable `widgets.make_sortable` wired into
  `CrudFrame` (so every master/operations register gets it) and the Risk tab,
  and the chosen order **sticks across a data refresh**. Web: header links carry
  `?sort=&dir=`, whitelisted to the shown columns (identifiers never come from
  the raw query, so it stays injection-safe).
- **Browser register lists scroll instead of paging.** The old Prev/Next pager
  is gone; the table sits in a fixed-height scroll box with a **sticky header**,
  loading up to 500 rows. If there are more, the count line says *"showing first
  500 of N — search to narrow"* rather than silently truncating.

---

## 2026-07-22 — Shell: status footer, rail refresh, no floating dock

- **Status footer** — a full-width taskbar at the bottom of the window with a
  live **AI-engine light**: green ● *AI engine: running* / red ● *off*, polled
  off the UI thread (a ~1 s probe never freezes the window) and recoloured on a
  theme flip.
- **Refresh moved into the rail** — a single, predictable **⟳ Refresh** at the
  rail foot (reuses the active tab's refresh); replaces the old floating dock's
  refresh.
- **Removed the floating action dock** (bottom-right New · Refresh · Save
  overlay) and its now-dead `FloatingDock` widget — the per-tab buttons already
  cover add/save, so nothing is lost.

---

## 2026-07-22 — Risk Register (Enterprise PM: E0.2 / E3 surfaced)

- **The risk register is now on screen** — Project Management › Risks
  (`tab_risk.py`), over the already-built `risk_store` / `risk.py` scoring. A
  worst-first list (likelihood × impact → score / band / expected exposure),
  a form whose **score/band/exposure are computed live, never typed**
  (derive-on-save, so a stored band can't disagree with the maths), owner /
  response / mitigation / status, and per-project + status filters.
- **Auto-detect** raises risks from the current figures — it reads the same
  dashboard snapshot the advisories use (`risk_detect`, 11 rules), skips ones
  already on the register, and adds the rest each with a **drafted response**
  the owner can edit. Verified against the sample book: 10 risks detected
  (receivables ageing, thin cash, critical NCR, programme slip…), stored
  worst-first with a portfolio exposure roll-up. Writes gated for Viewers.

---

## 2026-07-22 — Internalise the AI: one built-in model, Start/Stop only

- **The AI is now internal.** The app ships **one hardcoded model**
  (`qwen2.5-coder:1.5b`) and the whole downloader/manager surface is gone — no
  model catalogue, no pull, no "install Ollama", no model picker. `assistant`
  always uses the built-in model (any stale `assistant_model` setting is
  ignored; a test enforces it).
- **AI Engine is now just Start / Stop** (`tab_ollama.py` rewritten): a status
  line plus Start / Stop, and first Start registers the bundled model offline.
  The local runtime is still Ollama, but bundled and never shown.
- Removed the `ollama_catalog` module and the redundant "AI Assistant" settings
  panel in Tools (model/host fields, Test/Start buttons). 612 tests pass.

---

## 2026-07-22 — Browser / LAN access: RA bills + more registers

- **RA bills in the browser** — record a running-account bill's value and the
  CPWA **Form-26 recoveries** (security deposit, income-tax TDS, labour cess),
  reusing the desktop's pure `civil.ra_bill_totals` so both compute identical
  retention/TDS/cess/net, then posts via `journal_post.post_all`. The detailed
  Measurement Book (per-item measurements, part-rates, printed Form 23/26) stays
  on the desktop. Verified: SD 2.5% / TDS 2% / cess 1% on ₹1,00,000 → 2500 /
  2000 / 1000, net 94,500, cumulative 1,50,000, and a balanced `RABill` entry.
- **More editable registers in the browser** (same drift-guarded `web_masters`
  path): Projects, Milestones, the Rate Book, Thekedars, and the on-site logs —
  **Snags** (punch list) and **NCRs** — whose *Raised* date defaults to today
  (a shared `@today` resolver). The schema-drift test now covers all fourteen.

---

## 2026-07-22 — Browser / LAN access: money documents that post (Stage 3b)

- **Record money in the browser** — payments, tax invoices, vendor invoices and
  running bills. Each writes the document with the *same* derived amounts the
  desktop computes (GST, TDS, net payable, retention, incremental bill value),
  then posts through the shared, idempotent `journal_post.post_all`, so the
  double entry is produced by `posting.py`'s rules and never re-implemented.
- Create + view only (records of fact). Posting is state-gated — a **Draft** bill
  saves without posting; every posted entry balances (verified: payment 5000,
  tax invoice 118000 incl. +18% GST, vendor invoice 59000 / net 58000, running
  bill 150000 with retention 7500 / net 142500). Gated on role + session CSRF;
  a posting hiccup is swallowed so it never loses the saved document.
- `web_docs.py` (tkinter-free specs + `compute()` per document); `webapp.py`
  `_doc_create` route + `_can_create`; `webserver.py` keeps blank POST values.
  This completes the browser money-entry parity except the measurement-book RA
  workflow, which stays on the desktop.

---

## 2026-07-21 — Rate Realisation: the lessons-learned loop

- **Feed what things actually cost back into the rate library.** A new **Rate
  Realisation** view (Billing › Rate Book, second sub-tab) puts each material's
  **achieved** purchase rate next to its **standard/reference** rate. The
  achieved rate is *quantity-weighted* from the goods-received ledger — a
  500-bag order at ₹402 outweighs a 5-bag top-up at ₹450 — so it reflects what
  the job really paid, not a plain average.
- **One click closes the loop.** "Apply Achieved → Standard" (per-selection or
  all-drifted) rewrites `materials.rate`, which flows into estimates, rate
  analysis and the material budget — so the next estimate is priced on reality.
  Scope is a single finished site (a job's lessons at closeout) or all sites (a
  periodic refresh).
- **Honest by construction.** Nothing auto-applies; the number of purchases
  behind each achieved rate is shown so a one-off spike can't silently reset a
  good standard, a material with no purchase history is skipped (no-data, not a
  zero), and a **Viewer cannot apply**. Pure maths in `lessons.py`
  (`weighted_rate`, `realise`), UI in `tab_lessons.py`; 7 new tests (weighted
  average, over/under/no-data classification, and the admin-applies /
  viewer-blocked write-back).

---

## 2026-07-21 — Submittals register (document control)

- **The last document-control gap is closed.** A **submittal** — the
  pre-execution approval of a proposed material / make / shop drawing ("approve
  what I intend to use") — is now a register in **Purchases › Sourcing ›
  Submittals**, beside RFIs and drawing revisions. Deliberately a *separate*
  table from `rfis`: an RFI is a question about the documents, a submittal is a
  proposal for approval, and conflating them is a known cause of scope-creep
  confusion.
- Status lifecycle: Submitted → Approved / Approved as noted / Revise & resubmit
  / Rejected. A resubmittal is a new row whose `supersedes_id` cites the prior
  (traceability, informational — no self-FK, so a blank never breaks an insert).
- `submittals.py` (pure): `is_open` / `is_approved` / `is_overdue` — only an
  undecided submittal is open, and only an open one past its required-by date is
  overdue (a decided one is out of the reviewer's court). `dashboard.collect`
  counts open submittals and flags overdue ones with an **advisory** that goes
  `act` when any is overdue (else `watch`), mirroring the RFI advisory.
- Ships behind the existing Sourcing module toggle; mostly relevant to PMC /
  departmental work. Verified: schema applies clean, Sourcing tab builds
  headlessly, 7 new unit tests (pure lifecycle + a DB-backed dashboard count)
  pass, full suite green apart from the pre-existing real-display GUI smoke test.

---

## 2026-07-21 — Browser / LAN access: Estimates (Stage 3a)

- **Prepare a priced estimate in the browser** — header + line items, with
  add/remove line rows. The roll-up (subtotal → contingency → taxable → GST →
  grand total) reuses the *same* pure `estimate.estimate_totals` as the desktop,
  and the grand total is stored on save. Estimates never touch the ledger, so
  this stays clear of the double-entry engine (reserved for bills / RA bills).
- `webserver.py`/`webapp.py`: repeated form fields (`li_qty`, `li_rate`, …) are
  now kept as aligned per-row lists (`form_multi`, `keep_blank_values`), so a
  blank cell can't shift a column. Write routes generalised beyond the flat
  Masters (`_is_writable`, `_guard_write`); create/edit gated on role + session
  CSRF; edit replaces line items transactionally (no duplicates); web edits
  audit-logged. A tiny inline script adds/removes rows (no framework).
- The estimate record view shows the line items and the computed totals.

---

## 2026-07-21 — One HCW-UI design system for desktop + web (strict rule)

- **`tokens.py`** — a pure, tkinter-free single source of truth ported verbatim
  from the kit's authoritative `hcwux/src/tokens.ts`: Fog-Gray canvas, Pure-White
  cards, Coal-Black ink, the one Radiant-Orange accent (fills/active only; links
  are slate), and the shape law — square surfaces (0 radius), 4px buttons, 8px
  dialogs, 3px tab/nav alert rule. Both skins read from it.
- **Desktop** (`theme.py`) now sources its palettes from `tokens.py` (no value
  change — it already matched), and **24 tabs** had ad-hoc hex text colours
  (`#555`, `#8a5a00`, `#2e7d32` …) replaced with `theme.palette()[role]`, so
  every text colour flips correctly in dark mode.
- **Web** (`webrender.py`) CSS is now **generated from the same tokens** and
  corrected to the kit's shape: square cards/inputs/tables (was rounded), 4px
  buttons, 8px dialog cards, and a white **instrument rail** (was a dark
  sidebar) whose active row wears the 3px accent inset rule.
- Guardrails: tests lock the tokens to the kit's values, assert the web CSS
  carries the token values (can't drift from the desktop), and forbid any new
  ad-hoc `foreground='#…'` literal from re-entering the app.

---

## 2026-07-21 — Browser / LAN access: Masters data entry (Stage 2)

- **Add / edit / delete the Masters in the browser** — sites, clients, vendors,
  materials, labour, equipment. First write surface on the way to full parity
  (Billing → Money next).
- `web_masters.py`: a **tkinter-free** spec mirroring the desktop CRUD field-for-
  field (so the headless server needs no Tk import), plus value coercion matching
  `CrudFrame._collect_values` (number→float, fk→id, combo whitelist). A
  `tests/test_web.py` guard checks every field is a real column and every fk
  query runs — the web spec can't silently drift from the schema.
- `webapp.py` write routes: `/t/<m>/new`, `/t/<m>/<id>/edit`, `/t/<m>/<id>/delete`,
  gated on `can_write(role)` (Viewer → 403) with a **per-session CSRF token** on
  every form; delete catches `IntegrityError` (won't orphan linked rows) and web
  edits hit the same audit log (`web_create`/`web_update`/`web_delete`).
- `webrender.py`: form controls (text/number/combo/fk/textarea), error list, and
  a POST-only delete button.

---

## 2026-07-21 — Browser / LAN access

- **Use the app in a browser, no client install.** A built-in web server
  (`http.server`, still pure standard library — no web framework, no pip) serves
  Construction OS over the office LAN at `http://<host>:<port>`. It shares the
  **same SQLite file** and business logic as the desktop; `db.get_conn`'s
  per-request WAL connections make concurrent browser readers safe.
- **Login required, roles reused.** The web layer always authenticates against
  the desktop `auth` accounts (PBKDF2, lockout, audit log); the first visit
  bootstraps the admin. Viewers are read-only. The `users` table (hashes) and
  app config are never browsable; CSRF-guarded login, `HttpOnly`/`SameSite=Lax`
  cookies.
- **This turn:** the foundation + all **read views** (dashboard KPIs/advisories/
  bottlenecks/decisions, and every register with search, pagination and a record
  view). Write flows are staged next (Masters → Billing → Money) toward full
  read/write parity.
- Files: `webserver.py` (server + start/stop lifecycle), `webapp.py`
  (`handle(request)→response`, socket-free/testable), `webrender.py` (HCW-styled,
  theme-aware, responsive HTML), `netinfo.py` (LAN URLs), `web_main.py` (headless
  `--host/--port`). Launcher in **Tools › Web / LAN access**. See `docs/LAN.md`.

---

## 2026-07-21 — Takeoff + inbuilt offline AI

- **Bluebeam-style quantity takeoff.** Measure straight off a scaled drawing:
  calibrate the scale once, then run a polyline for length, a polygon for area
  (× depth for volume), or click-count. Live quantities, totals by unit,
  save/load, and **Send to Estimate**. Pure engine `takeoff.py` (shoelace area,
  polyline length, scale-from-calibration); `pdf_render.py` renders a PDF page to
  PNG via an external poppler/Ghostscript when present (tkinter shows PNG, not
  PDF); `tab_takeoff.py` is the Canvas markup UI under **Billing**;
  `takeoffs`/`takeoff_items` tables.
- **Inbuilt offline AI model.** The assistant's default is now
  **`qwen2.5-coder:1.5b`** — tuned for its NL→SQL, ~1 GB, Apache-2.0. The
  installer can bundle it (run `installer\fetch_payload.ps1` first): Ollama
  installs silently and the model GGUF is laid beside the app, registered offline
  by a one-time in-app `ollama create` (`model_provision.py`, wired into
  **Assistant › AI Engine**). Result: the assistant runs with no internet, out of
  the box. Lean builds without the payload still pull a model on first use.

---

## 2026-07-21 — v1.0.0: intelligent dashboard, HCW UI, production hardening

The 1.0 release. Everything below stays pure standard library (tkinter +
sqlite3), no pip.

- **UI — HCW rail + stage.** Replaced the top tab-bar with a left rail (identity,
  pictogram nav, settings at the foot) and a work stage, on the HolagundiWorks
  design kit. Added a **light / dark** toggle — including a dark-mode logo, the
  black artwork lifted to near-white by a stdlib PNG tinter
  (`tools/logo_tint.py`) — pill-switch module toggles, sub-tab pictograms, and a
  theme-wide semantic colour system (`theme.wash`) so status rows read right in
  both schemes.
- **Intelligent home dashboard.** KPI band + a rule-based **advisory** engine
  (`advisory.py`) that ranks actions with an honest **confidence**, a
  **bottlenecks** scoreboard and a **decisions-pending** queue, all from
  `dashboard.collect`. On-device and explainable; no model required.
- **Project Management** as its own section (Projects + Timeline + Look-ahead),
  with a per-project **drill-down** (cost/margin, programme slip + LD, retention,
  open snags / RFIs / NCRs). Operations slimmed to daily execution.
- **CPWD reference library** (`refdata.py`) — standard civil items, current
  material rates and consumption norms (the material split for concrete,
  masonry, plastering …); a **rate-book picker** wires those into Estimates and
  BOQ. **Load Sample Data** (`sampledata.py`) seeds a realistic demo book.
- **Security hardening.** Versioned PBKDF2 password hashes (600k iterations,
  transparently upgraded on login; legacy hashes still verify), a
  password ≠ username guard, and an audit confirming no SQL-injection surface
  (all interpolation is hardcoded identifiers; the LLM's SQL is `query_only`).
- **Licensing & docs.** Released under **AGPL-3.0** (`LICENSE`); rewrote the
  README for GitHub; added `docs/TEST_PLAN.md`.
- **Tests.** A real suite now: `tests/test_core.py` (pure maths + posting +
  security) and `tests/test_smoke_tabs.py` (builds every tab on the sample book,
  both themes). 454 tests.

## 2026-07-19 — Backlog completion (autopilot pass)

Completed the remaining planned (⏳) items across every roadmap phase. All new
business maths lives in pure, `python -c`-testable modules; all 31 tabs build
clean. Founding constraints unchanged (Python stdlib only, tkinter, single
SQLite file, no pip).

### Phase 2 — Get paid & submit (now ✅)
- **Print / Export on every document** — `report_open.save_and_open_html`
  helper; DocumentFrame "Print / Export" (quotations, POs) and a vendor-invoice
  export with GST/TDS breakup.
- **Configurable invoice number series** — `numbering.py` (Indian financial
  year, prefix + FY-reset formatting, next-serial by scanning numbers in use);
  tax-invoice auto-numbering honours it (e.g. `INV/2026-27/001`). Config in
  Tools → Invoice Number Series.
- **Rate Book / Specification library** — `rate_book` table + master under
  Billing (schedule of standard priced items with specs).
- **PWD deviation statement** — `civil.deviation` + a Deviation view in
  BOQ / RA Bills (tendered vs executed → excess/saving).

### Phase 3 — Labour (now ✅)
- **Optional PF / ESI / labour-cess** — `statutory.py` (EPF, ESI split, BOCW
  cess); optional `pf_no`/`esi_no` on the labour master; a standalone
  "Statutory" calculator under Muster & Wages. Nothing auto-deducts.

### Phase 4 — Trust & ease (now ✅)
- **First-run setup wizard** (`tab_wizard.py`) — firm details + first site +
  first client, shown once on a fresh book.
- **Guided low-typing entry** — `CrudFrame`/`Field` `default=TODAY` and
  `remember=True`: dates prefill today, Site (etc.) remembers the last choice
  per table+column. Applied across the ops tabs.
- **Vernacular UI** (`i18n.py`) — Hindi/Hinglish navigation labels with English
  fallback; language toggle in Tools.
- **App-wide error safety net** (`errors.py`) — a Tk `report_callback_exception`
  handler turns any uncaught callback error into a plain-language dialog (full
  traceback still logged). No stack trace ever reaches the user.

### Phase 5 — Compliance (now ✅)
- **RA / running bills in Output GST** — outward GST now spans tax invoices +
  RA + running bills (works-contract supply at a configurable Works GST %), with
  a Source column so RA-only billers are covered.
- **HSN-wise summary** — GSTR-1-style HSN/SAC taxable + CGST/SGST/IGST.

### Phase 6 — Insight (now ✅)
- **Receivable / payable ageing** (`ageing.py`) — FIFO-settle dated bills by
  receipts/payments, bucket the remainder 0-30/30-60/60-90/90+.
- **Contract / BOQ progress %** and **material budget vs actual** (value)
  (`analytics.py`).

### Phase 7 — Advanced (✅)
- **P&L + Balance Sheet** on the posted ledger (`reports.py`) in Accounting.
- **Payroll & subcontractor auto-posting** — `posting.payroll_lines`,
  `posting.sub_bill_lines`, and new `journal_post` loops (idempotent).
- **Subcontractor / work-order billing** — `subcontract.py`, tables
  `work_orders` (+items) and `sub_bills`, and `tab_subcontract.py` (work orders +
  sub running bills with retention & works-contract TDS).

### Assistant
- Schema docs + few-shot examples extended to the new modules (subcontractors,
  work orders, rate book, BOQ); results render a monospace **bar chart** for
  (label, number) answers (`assistant.text_bar_chart`).

### Schema additions
- Tables: `work_orders`, `work_order_items`, `sub_bills`, `rate_book`.
- Columns: `materials.rate`, `labor.pf_no`, `labor.esi_no` (idempotent
  migrations in `db._ADD_COLUMNS`).
- `app_settings` config keys: `works_gst_pct`, `invoice_prefix` /
  `invoice_width` / `invoice_fy_reset`, `language`, `setup_done`, and
  `last:<table>:<column>` remember-last values.

### New modules (all pure unless noted)
`report_open.py` (DB/tk helper), `numbering.py`, `ageing.py`, `analytics.py`,
`reports.py`, `subcontract.py`, `statutory.py`, `i18n.py`, `errors.py` (tk),
`tab_subcontract.py`, `tab_statutory.py`, `tab_wizard.py`.
