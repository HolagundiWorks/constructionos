# Construction OS — UI Replatform to WinUI 3 (Native Windows)

**Migration architecture, component mapping, and phased plan for moving the UI
from the tkinter "HCW UX" shell to native WinUI 3 — stock Fluent components only,
no custom controls**

_Document type: Migration architecture & implementation spec_
_Version: 1.0 · Last updated: 2026-07-22 · Prepared by: Human Centric Works_
_Decision: native WinUI 3 desktop (Windows-only, C#/.NET) — authorised departure
from the stdlib/cross-platform constraints. Read with
[`APP-ARCHITECTURE.md`](APP-ARCHITECTURE.md) and
[`AI-MODELS-AND-DEPLOYMENT.md`](AI-MODELS-AND-DEPLOYMENT.md)._

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
| The **pure domain core + 619 tests** | **Kept** (reused as a backend — §1) |

The single most important design decision below (§1) is what makes this a
**replatform of the *UI*** rather than a **rewrite of the *whole app***.

---

## 1. Target architecture — reuse the domain, replace only the UI

**Do not reimplement the ~60 pure Python business modules (finance, civil, EVM,
risk, scheduling, …) and their 619 tests in C#.** Keep them. Run the existing
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
 │    reuses finance/civil/risk/earnedvalue/… (619 tests kept)   │
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
and 619 tests, double the maintenance, and risk silent money-maths divergence —
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
├── Services/ApiClient.cs           # typed HttpClient over the localhost JSON API
├── Models/                         # DTOs matching the JSON contract
├── Assets/                         # MSIX assets only (no custom iconography — §6)
└── ConstructionOS.WinUI.csproj     # Windows App SDK + CommunityToolkit refs
```

- **Pattern:** MVVM with the **Windows Community Toolkit MVVM** — the standard,
  Microsoft-backed toolkit (no custom framework).
- **Navigation:** the rail is a **`NavigationView`** whose items are generated
  from the backend `/api/menu?persona=…` (driven by the built `menu.py` personas
  + grouping), and the stage is a **`Frame`** that navigates to the section's
  `Page`. This reuses the E7.1 model directly.

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

**Keeps:** the entire pure domain core and its 619 tests; the SQLite single-file
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
| **U0** | **Backend JSON API** (`webapi.py`) over the domain + DTO contract; tests | **Here (Python, headless)** |
| **U1** | WinUI 3 solution + shell: `MainWindow` `NavigationView` from `/api/menu`, theme (Mica, light/dark), Segoe Fluent Icons | Windows |
| **U2** | Masters + generic **DataGrid** CRUD page bound to the API (replaces `CrudFrame`) | Windows |
| **U3** | Money/Billing/Purchases pages; forms with stock inputs; `CommandBar` | Windows |
| **U4** | Dashboard (KPI cards, `InfoBar` advisories) + **charts** (EVM/cash/ageing) | Windows |
| **U5** | **Controls** section — Risk/Opportunity/Lessons register pages (over the built stores) + **Process view** (workflow.py) + search (`AutoSuggestBox`) | Windows |
| **U6** | Packaging: PyInstaller backend sidecar inside **MSIX**; launch/停 lifecycle; signing | Windows |
| **U7** | Parity pass, persona menus (menu.py), accessibility, retire tkinter on Windows | Windows |

**U0 is the only phase this Linux/no-.NET environment can build and prove** — and
it's the right first step regardless, because it fixes the client/service
contract in tested Python before any C# is written.

---

## 10. Testing strategy

- **Backend (Python, here):** unit-test every `/api/*` endpoint via
  `webapp.handle` (socket-free), asserting the JSON contract and role-gating —
  extending `tests/test_web.py`.
- **Client (Windows):** MVVM ViewModels unit-tested (xUnit) against a mocked
  `ApiClient`; WinUI UI tests via **WinAppDriver**; the domain stays covered by
  the existing 619 Python tests. No business logic is tested twice because none
  is duplicated.

---

## 11. Summary

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
