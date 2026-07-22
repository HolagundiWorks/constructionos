# ACO — UI Replatform to WinUI 3 (Native Windows)

**Migration architecture, component mapping, and phased plan for moving the UI
from the tkinter "HCW UX" shell to native WinUI 3 — stock Fluent components only,
no custom controls**

_Document type: Migration architecture & implementation spec_
_Version: 1.1 · Last updated: 2026-07-22 · Prepared by: Human Centric Works_
_Product: **ACO** (Accelerated Construction Operations; formerly Construction OS)._
_Decision: native WinUI 3 desktop (Windows-only, C#/.NET) — authorised departure
from the stdlib/cross-platform constraints. Read with
[`APP-ARCHITECTURE.md`](APP-ARCHITECTURE.md),
[`AI-MODELS-AND-DEPLOYMENT.md`](AI-MODELS-AND-DEPLOYMENT.md), and
[`PRODUCT.md`](PRODUCT.md) (brand: ACO + Radiant Orange logo mark)._

---

## 0. Decision & explicit constraint change

The chosen path is a **native WinUI 3 (Windows App SDK) desktop application in
C#/XAML**, using **only stock Fluent controls, elements, toolset, data
visualization, styling, icons and pictograms — no custom items**. This is a
deliberate, owner-approved replatform that **breaks founding constraints** the
rest of the product held (documented so the trade is explicit, not accidental):

| Founding constraint | Under WinUI 3 |
|---|---|
| Pure Python **stdlib, no pip** | **Broken** — front-end is C#/.NET + Windows App SDK + NuGet packages |
| **tkinter** GUI | **Replaced** — XAML / WinUI 3 |
| **Cross-platform** (Win/Linux/Mac) | **Broken** — WinUI 3 is **Windows 10/11 only** |
| **Double-click-a-folder / USB** | **Replaced** — MSIX package + Windows App SDK runtime |
| Single SQLite file, offline | **Kept** |
| The **pure domain core + ~642 tests** | **Kept** (reused as a backend — §1) |

The single most important design decision below (§1) is what makes this a
**replatform of the *UI*** rather than a **rewrite of the *whole app***.

---

## 1. Target architecture — reuse the domain, replace only the UI

**Do not reimplement the ~93 pure Python business modules (finance, civil, EVM,
risk, scheduling, …) and their ~642 tests in C#.** Keep them. Run the existing
Python core as a **local backend service** that the WinUI 3 client calls over
**localhost HTTP** — the same "server does the compute, thin client renders"
topology already documented for the LAN/AI layers.

```
 ┌─────────────────────────────────────────────────────────────┐
 │  WinUI 3 client  (C#/.NET, Windows App SDK)  — this replatform│
 │    NavigationView · DataGrid · Fluent controls · Segoe icons  │
 │    charts (WinUI Community Toolkit / LiveCharts2)             │
 │            │  HTTP + JSON  (localhost only)                    │
 ├────────────┼──────────────────────────────────────────────────┤
 │  Python backend service  (existing, ~unchanged)               │
 │    NEW: JSON API (webapi.py) over the SAME domain + db         │
 │    reuses finance/civil/risk/earnedvalue/… (~642 tests kept)   │
 │    auth/roles/audit reused; SQLite single file                │
 └─────────────────────────────────────────────────────────────┘
```

**Why this architecture:**

- The app **already ships a stdlib HTTP backend** (`webserver.py`, `webapp.py`,
  `web_main.py`) serving the same domain + DB. It renders HTML today; it needs a
  **JSON API** added — a small, stdlib, **headless-testable** change (§3). The
  hard part (the business logic) is done and tested.
- The WinUI 3 client becomes a **pure presentation layer**: it renders Fluent
  controls and calls JSON endpoints. No business maths lives in C#, so nothing
  trusted moves to an untested reimplementation.
- The Python backend is **bundled as a sidecar** (PyInstaller, as the installer
  already does) that the WinUI 3 app launches on start and talks to on
  `127.0.0.1` — never exposed to the network.

**Alternative rejected:** rewriting the domain in C# would duplicate 60 modules
and ~642 tests, double the maintenance, and risk silent money-maths divergence —
for no user-visible gain. The client/service split is the correct decomposition.

---

## 2. What is buildable/verifiable here vs. Windows-only

This environment is Linux with **no .NET / Windows App SDK**, so:

- **Buildable & unit-testable now (Python):** the **JSON API** (`webapi.py`) over
  the domain — §3. This is the backend the WinUI 3 client consumes; it can be
  written and tested headless here, and it de-risks the whole client by fixing
  the contract first.
- **Designable & scaffoldable now, but Windows-only to compile/run:** the WinUI 3
  C# solution (§4–§7). This spec defines its structure, the full component
  mapping, styling, icons, and packaging so a Windows dev (or a Windows CI
  runner) can build it; it cannot be compiled or screenshotted from Linux.

So the honest sequencing (§9) is **API-first**: lock the contract in tested
Python, then the C# client renders against it.

---

## 3. Backend JSON API (`webapi.py`) — new, Python, testable here

Add JSON endpoints beside the existing HTML routes, reusing the same
`webapp.handle(Request) → Response` pattern (socket-free, unit-tested):

- **Read:** `GET /api/dashboard`, `/api/kpi`, `/api/{register}` (sites, clients,
  risks, opportunities, …), `/api/project/{id}/evm`, `/api/workflow` (from the
  built `workflow.py`), `/api/menu?persona=…` (from the built `menu.py`).
- **Write:** `POST/PUT/DELETE /api/{register}` gated by role (`ui_guard`),
  CSRF/session reused, every write audited (as the web layer already does).
- **Contract:** stdlib `json`; each endpoint delegates to a **pure domain
  module** and serialises the result — no logic in the transport. Because
  `webapp.handle` is `Request→Response`, the whole API is testable **without a
  socket** (like `tests/test_web.py`).

This is the U0 workstream (§9) and the one deliverable I can build and prove in
this environment.

---

## 4. WinUI 3 client — solution structure

A standard Windows App SDK / WinUI 3 solution (C#, .NET 8, MSIX):

```
ConstructionOS.WinUI/               # WinUI 3 app (Windows App SDK)
├── App.xaml / App.xaml.cs          # app bootstrap, theme resources, backend launch
├── MainWindow.xaml                 # the shell: NavigationView (rail) + Frame (stage)
├── Views/                          # one Page per section/tab (mirrors SECTIONS_CATALOG)
│   ├── HomePage.xaml               # dashboard (KPIs, advisories)
│   ├── Masters/…  Billing/…  Money/…  Controls/…   (Risk/Opportunity/Lessons)
│   └── ProcessPage.xaml            # the "what's next" workflow view (workflow.py)
├── ViewModels/                     # MVVM (CommunityToolkit.Mvvm) — bind to API DTOs
├── Services/ApiClient.cs           # HttpClient + CSRF; Put/Delete; ApiException
├── Services/AppSettings.cs         # %LOCALAPPDATA%\Construction OS\winui-settings.json
├── Helpers/                        # JsonRows, PageLoad, NavRoute
├── Models/                         # DTOs matching the JSON contract (as needed)
├── Assets/                         # MSIX assets only (no custom iconography — §6)
└── ConstructionOS.WinUI.csproj     # Windows App SDK + CommunityToolkit refs
```

- **Pattern:** MVVM with the **Windows Community Toolkit MVVM** — the standard,
  Microsoft-backed toolkit (no custom framework). Pages today bind via code-
  behind helpers (`PageLoad` / `JsonRows`); ViewModels grow as forms harden.
- **Navigation:** the rail is a **`NavigationView`** whose items are generated
  from the backend `/api/menu?persona=…` (driven by the built `menu.py` personas
  + grouping), routed through **`NavRoute`**, and the stage is a **`Frame`**.
  Settings gear opens connection settings. This reuses the E7.1 model directly.

---

## 5. Component & element mapping — stock WinUI 3 only ("no custom items")

Every current UX element maps to a **stock** WinUI 3 / Windows App SDK / WinUI
Community Toolkit control. Nothing is hand-drawn.

| Current (tkinter / HCW UX) | WinUI 3 stock control |
|---|---|
| Rail + Stage (`shell.RailStage`) | **`NavigationView`** (left pane) + **`Frame`** |
| Section tabs (nested Notebook) | `NavigationView` menu items / **`TabView`** for tabbed sections |
| Pictogram per rail row (emoji) | **`FontIcon`/`SymbolIcon`** — Segoe Fluent Icons (§6) |
| `CrudFrame` list + form | **`DataGrid`** (CommunityToolkit) for the list + **`Expander`/`ContentDialog`** form |
| `DocumentFrame` header + line items | Header **form controls** + **`DataGrid`** for line items |
| Master pickers (`*_options`) | **`ComboBox`** / **`AutoSuggestBox`** |
| Text / number / date fields | **`TextBox`**, **`NumberBox`**, **`DatePicker`**, **`CalendarDatePicker`** |
| Toggles (modules, security) | **`ToggleSwitch`**, **`CheckBox`**, **`RadioButtons`** |
| Home KPI band | **`ItemsRepeater`** of KPI **cards** (`Border`+`Grid` styled) + **`InfoBadge`** |
| Advisories (severity/confidence) | **`InfoBar`** (severity variants) / **`Expander`** list |
| Plain-language error dialog (`errors.py`) | **`ContentDialog`** / **`InfoBar`** (no stack trace) |
| Command actions (Save, Print…) | **`CommandBar`** + **`AppBarButton`** |
| Approvals / status | **`InfoBadge`**, **`ProgressRing`**, status **`Border`** chips |
| Global search / command palette (N4) | **`AutoSuggestBox`** in the title bar |
| Light/dark toggle | WinUI **theme resources** + **Mica** backdrop; `ElementTheme` toggle |
| Gantt / Timeline (`tab_timeline` canvas) | **DataGrid + charts** (see §5.1) or Community Toolkit controls |
| Reports/print (`bill_export` HTML) | Keep HTML export; preview in **`WebView2`** |
| Workflow "what's next" (E7.2) | **`Stepper`/`BreadcrumbBar`** + `InfoBar` for the next step |

### 5.1 Data visualization (charts)

WinUI 3 has **no first-party chart control**, so — to stay "stock, not custom" —
use a **standard, widely-adopted charting toolkit** rather than hand-drawing on a
`Canvas` (as the current Gantt/insight views do):

- **WinUI Community Toolkit** controls where they fit, and **LiveCharts2** (MIT,
  the de-facto WinUI/.NET charting library) for KPI trends, EVM (SPI/CPI),
  cash-flow, ageing, PPC, and the programme/Gantt visual.
- These render the numbers computed by the **Python domain** (EVM, ageing,
  forecast, drift) — the client never computes them.

This is the one area to flag explicitly: "all data-viz from WinUI 3" is satisfied
by the **WinUI Community Toolkit / LiveCharts2** ecosystem, since the base
framework ships no chart control. No bespoke chart code.

---

## 6. Icons & pictograms — Segoe Fluent Icons (stock)

Replace the emoji pictograms (`🏠 🗂 🏗 🛠 🧾 🛒 💰 📊 ⚙`) with **Segoe Fluent
Icons** glyphs via `FontIcon` (the standard Windows 11 icon font) — no custom
SVGs. Proposed rail mapping:

| Section | Segoe Fluent Icon (glyph name) |
|---|---|
| Home | `Home` |
| Assistant | `Chat` / `Robot` |
| Masters | `Library` / `Contact` |
| Project Management | `Manufacturing` / `Building` |
| Operations | `Repair` (wrench) |
| Billing | `Document` / `Receipt` |
| Purchases | `Shop` / `Cart` |
| Money | `Money` / `Wallet` |
| Accounts | `Chart` / `Financial` |
| Controls (registers) | `Shield` / `Flag` |
| Tools | `Settings` |

All from the **Segoe Fluent Icons** set; the exact code points are chosen from
the official Windows glyph list at build time.

---

## 7. Packaging & runtime

- **WinUI 3 client:** Windows App SDK (self-contained or framework-dependent),
  **MSIX** package, signed; targets Windows 10 1809+/Windows 11.
- **Python backend sidecar:** frozen with **PyInstaller** (the installer already
  does this for the AI model bundle), shipped inside the MSIX; the WinUI 3 app
  launches it on `127.0.0.1:<port>` at startup and stops it on exit. The SQLite
  file stays in `%LOCALAPPDATA%\Construction OS` exactly as `paths.py` already
  places it.
- **No network exposure:** the backend binds localhost only; the client is the
  sole consumer.

---

## 8. What this keeps vs. gives up

**Keeps:** the entire pure domain core and its ~642 tests; the SQLite single-file
data model; auth/roles/audit; the EVM/risk/opportunity/lessons/workflow/menu
logic just built; offline operation.

**Gives up:** cross-platform (Windows-only now); the no-pip/stdlib front-end; the
zero-install "double-click a folder / USB" story (now an MSIX install + Windows
App SDK runtime). The existing **tkinter UI** (`shell`, `theme`, `tokens`,
`widgets`, `crud_frame`, all 47 `tab_*`) is **retired on Windows** — keep it in
the tree for non-Windows use or delete per a later call.

---

## 9. Phased plan (UI Replatform track — "U" phases)

| Phase | Deliverable | Where verifiable |
|---|---|---|
| **U0** | **Backend JSON API** (`webapi.py`) over the domain + DTO contract; tests | **✅ Done — u0.1** |
| **U1** | WinUI 3 solution + shell: `MainWindow` `NavigationView` from `/api/menu`, theme (Mica, light/dark), Segoe Fluent Icons | **✅ Built + runs** — shell over `/api/menu`, Settings gear, offline fallback, `NavRoute` |
| **U2** | Masters + generic **ListView** CRUD page bound to the API (replaces `CrudFrame`) | **✅ Built** — `Views/MastersPage.*`, one metadata-driven page (list + add/edit/delete) for every master, on the shared **`FieldForm`** helper with **FK pickers** (a related-master `ComboBox` from the API's `{id,label}` options, not a typed id) |
| **U3** | Money/Billing/Purchases pages; forms with stock inputs; `CommandBar` | **🚧 Partial** — **Payments: "New payment" form** via the shared **`FieldForm`** (`CommandBar` + `ContentDialog`; `POST` → 201, posts to the ledger — verified end-to-end; surfaces gated follow-ups in an `InfoBar`); Capture + Import pages built; the same helper extends to invoices/bills next |
| **U4** | Dashboard (KPI cards, `InfoBar` advisories) + **charts** (EVM/cash/ageing) | **✅ built** — Home **KPI cards** + **`InfoBar` advisories**; Charts page: money-KPI columns **+ cash-flow forecast** (in/out + balance) **+ receivable ageing** (`/api/cashflow`, `/api/ageing` — cloud CT-4); **EVM** per-project CPI/SPI chart (`/api/evm`) |
| **U5** | **Controls** section — Risk/Opportunity/Lessons register pages (over the built stores) + **Process view** (workflow.py) + search (`AutoSuggestBox`) | **✅ built** — Risks/Opportunities/Lessons/Submittals/Portfolio + Process pages; **`AutoSuggestBox` command palette** in the NavigationView search slot (type → `GET /api/search` tab hits → pick → routes via the shared `NavigateTo`) |
| **U6** | Packaging: PyInstaller backend sidecar inside **MSIX**; launch/停 lifecycle; signing | Windows — notes in [`winui/PACKAGING.md`](../winui/PACKAGING.md) |
| **U7** | Parity pass, persona menus (menu.py), accessibility, retire tkinter on Windows | Windows |

**Build status:** U0 is built and proven headless (the tested Python API). The
`cursor/complete-remaining-roadmap-32b0` branch (finished **cloud track U0.2–U0.6**
+ **hardened WinUI client** — `ApiClient`/`AppSettings`/`NavRoute`/`PageLoad`,
Settings gear, Capture/Import/Productivity pages) is **merged to main**; Python
**706 tests green**. The U1–U5 WinUI client now **compiles *and runs*** on the
Windows dev box (.NET 10 SDK + Windows App SDK 1.5): `dotnet build -c Debug
-p:Platform=x64` is **0 errors**, and
the self-contained exe (`-r win-x64 --self-contained -p:WindowsAppSDKSelfContained=true`,
which bundles the .NET 8 + WindowsAppSDK runtimes so nothing extra need be
installed) launches a **responsive "Construction OS" window** that logs into the
Python backend and builds its rail from `/api/menu`.

Getting there took four real fixes to the scaffold, all committed:
1. **`app.manifest`** had a malformed `<manifest>` root — a Win32 manifest's root
   must be `<assembly>`, or activation fails at start ("side-by-side
   configuration is incorrect").
2. **DataGrid → stock `ListView`.** The scaffold referenced
   `CommunityToolkit.WinUI.UI.Controls.DataGrid` 7.1.2, which is the **UWP/WinUI-2**
   build and was never ported to WinUI 3; it crashes at startup with a
   `themeresources.xaml` `XamlParseException`. Every register page now uses the
   stock WinUI `ListView` (which also honours the "stock controls only" rule).
3. **`<UseRidGraph>true</UseRidGraph>`** so WindowsAppSDK's native win-x64 assets
   deploy (clears `NETSDK1206`).
4. **`<WindowsPackageType>None</WindowsPackageType>`** so it runs unpackaged via
   the bootstrapper (U6 will add a separate MSIX packaging project rather than
   flip this back).

Run it: start the backend (`cd construction_app && python web_main.py --host
127.0.0.1 --port 8080`), then launch the built `ConstructionOS.WinUI.exe` (or F5
in VS 2022). Note: launching it from an automation/CI shell that then exits tears
the window down — start it from an interactive session (double-click / VS / your
own terminal) to keep it open.

---

## 10. Testing strategy

- **Backend (Python, here):** unit-test every `/api/*` endpoint via
  `webapp.handle` (socket-free), asserting the JSON contract and role-gating —
  extending `tests/test_web.py`.
- **Client (Windows):** MVVM ViewModels unit-tested (xUnit) against a mocked
  `ApiClient`; WinUI UI tests via **WinAppDriver**; the domain stays covered by
  the existing ~642 Python tests. No business logic is tested twice because none
  is duplicated.

---

## 11. Local development — getting started (Windows)

For picking this up on a Windows dev box:

**Prerequisites**
- **Windows 11** (or Windows 10 1809+).
- **Visual Studio 2022** with the **".NET Desktop Development"** workload and the
  **Windows App SDK / WinUI** components (or `winget install Microsoft.DotNet.SDK.8`
  + the Windows App SDK).
- **.NET 8 SDK**; **Windows App SDK 1.5+**.
- **Python 3.8+** (already required) to run the backend during development.

**First run (API-first, matches §9)**
1. **Run the Python backend** (unchanged app, dev mode):
   `cd construction_app && python web_main.py --host 127.0.0.1 --port 8080`
   — and, once U0 lands, the JSON API is served under `/api/*` on the same port.
2. **Verify the backend contract** headless before touching C#:
   `python -m unittest discover -s tests` (the API tests extend `test_web.py`).
3. **Scaffold the WinUI 3 client** (new solution, outside `construction_app/`):
   `dotnet new winui3 -n ConstructionOS.WinUI` (or File → New → **Blank App,
   Packaged (WinUI 3 in Desktop)** in VS 2022), then add
   `CommunityToolkit.Mvvm`, `CommunityToolkit.WinUI.UI.Controls.DataGrid`, and a
   charting package (`LiveChartsCore.SkiaSharpView.WinUI`) via NuGet.
4. Point `Services/ApiClient.cs` at `http://127.0.0.1:8080/api` and build the
   `MainWindow` `NavigationView` from `GET /api/menu?persona=…` (§4).

**Repo layout suggestion:** keep the WinUI 3 solution in a sibling folder (e.g.
`winui/ConstructionOS.WinUI/`) so the Python package (`construction_app/`) and its
tests stay clean; the two are wired only by the localhost JSON contract.

**Order of work:** U0 (Python API + tests) → U1 (shell) → U2 (DataGrid CRUD) →
U3 (money/billing) → U4 (dashboard + charts) → U5 (Controls + Process view) →
U6 (MSIX + backend sidecar) → U7 (parity, personas, retire tkinter on Windows).

## 12. Summary

Moving to **native WinUI 3** is a Windows-only, C#/.NET replatform of the **UI
only** — made safe by **keeping the tested Python domain as a localhost backend
service** and building the WinUI 3 app as a pure Fluent presentation layer over a
JSON API. Every UX element maps to a **stock** WinUI 3 / Windows App SDK / WinUI
Community Toolkit control (`NavigationView`, `DataGrid`, `InfoBar`, `NumberBox`,
`ContentDialog`, `CommandBar`, `AutoSuggestBox`, **Segoe Fluent Icons**,
**LiveCharts2** for data-viz) — **no custom items**. The plan is **API-first**:
U0 (the JSON API) is built and tested in Python now; U1–U7 (the WinUI 3 client)
are fully specified here for a Windows build environment. The cost is explicit and
owner-approved: Windows-only, MSIX + Windows App SDK, and the retirement of the
cross-platform stdlib/tkinter front-end — in exchange for a fully native, stock
Fluent Windows application over the unchanged, still-tested business core.

---

_Migration architecture & implementation spec. U0 (backend API) is buildable and
testable in the current environment; the WinUI 3 client (U1–U7) is specified for a
Windows/.NET build. Read with [`APP-ARCHITECTURE.md`](APP-ARCHITECTURE.md) (the
layers reused as the backend) and [`ENTERPRISE-PM-GAP-AND-ROADMAP.md`](ENTERPRISE-PM-GAP-AND-ROADMAP.md)._
