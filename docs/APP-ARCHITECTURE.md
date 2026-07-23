# Construction OS — Application Architecture, Structure & Configuration

**An enterprise-grade structure for the app: where each module belongs, how the
app is wired and configured, what is implemented today, and what should change**

_Document type: Architecture research & target design (documentation only)_
_Version: 1.0 · Last updated: 2026-07-22 · Prepared by: Human Centric Works_
_Baseline: `main` — 143 Python modules in `construction_app/`._
_Read with [`../AGENTS.md`](../AGENTS.md) (conventions) and
[`ROADMAP.md`](ROADMAP.md) (status)._

---

## 0. How to read this document

This is a **research + target-design** document. It (1) maps the codebase as it
is today, (2) proposes an enterprise-grade structure — which module belongs
where — with a concrete per-module mapping, (3) documents the app's workflow and
configuration, and (4) states plainly **what is already implemented** vs **what
needs to change**, with a low-risk migration path.

One honesty note governs everything below. The current **flat layout is a
deliberate choice**, not an accident: pure-stdlib Python in one folder is what
makes "runs anywhere Python runs, by double-clicking one folder / one USB stick /
one PyInstaller bundle" true (see [`PRODUCT.md`](PRODUCT.md), `paths.py`). So
"enterprise-grade structure" here does **not** mean "adopt a heavyweight
framework". It means **explicit layers, enforced dependency direction, and
consolidated configuration** — the organisation an enterprise team needs — while
preserving the offline, no-pip, single-artifact virtues that are the product's
moat. Every recommendation is weighed against that.

Maturity tags: **Implemented** · **Partial** · **Change** (proposed).

---

## 1. Executive summary

- **The domain core is already excellent and genuinely enterprise-grade in
  quality:** ~60 pure, tkinter-free, DB-free business modules with a 605-test
  suite, a clean separation between *maths* (pure) and *screens* (tkinter tabs),
  a single-source-of-truth module catalog, opt-in security with roles + audit, a
  stdlib web/LAN server, and a local-AI sidecar. These are the hard parts, and
  they are done well.
- **The structure around that core is not enterprise-grade:** all 143 modules
  live in **one flat directory**. Layering exists only by *convention* (a
  docstring says "No tkinter/DB"), not by *structure* — nothing prevents a domain
  module importing the UI, and the recent `lessons.py` vs `lessons_register.py`
  filename collision is exactly the failure mode a flat namespace invites.
  Configuration is spread across three mechanisms. `main.py` hard-wires ~70 tab
  imports.
- **The change is organisational, not a rewrite:** group the existing modules
  into **layered packages** (`domain`, `data`, `services`, `ui`, `config`, `app`),
  **enforce the dependency direction** with a test (the AST import test already
  proves the concept), and **consolidate configuration**. Phased and
  import-compatible, this loses none of the offline/no-pip virtues.

---

## 2. Current architecture (as-is)

### 2.1 The de-facto layers (already present, by convention)

Despite the flat directory, the code already falls into clean layers — they are
just not *expressed* as packages. Counting the 143 modules:

| De-facto layer | What it is | Count (approx) | Examples |
|---|---|---|---|
| **Domain (pure)** | Business maths — no tkinter, no DB | ~60 | `finance`, `civil`, `programme`, `cpm`, `risk`, `earnedvalue`, `advisory`, `analytics`, `forecast` |
| **Data / persistence** | Schema, connections, stores | ~8 | `db`, `risk_store`, `opportunity_store`, `lessons_store`, `portfolio_store`, `journal_post`, `sampledata` |
| **UI (tkinter)** | Screens + GUI infrastructure | ~55 | 47× `tab_*`, `shell`, `theme`, `tokens`, `widgets`, `crud_frame`, `ui_guard`, `errors` |
| **Web service** | Stdlib LAN server | 6 | `webapp`, `webserver`, `webrender`, `web_masters`, `web_main`, `netinfo` |
| **AI service** | Local-model sidecar client | 6 | `assistant`, `ollama_api/client/catalog/service`, `model_provision` |
| **Reporting** | HTML/PDF document builders | ~4 | `bill_export`, `pdf_render`, `report_open`, `einvoice` |
| **Security** | Auth, hashing, session, approvals | 4 | `auth`, `security`, `session`, `approval` |
| **Config / bootstrap** | Entry, paths, catalog, firm/i18n | ~10 | `main`, `web_main`, `paths`, `company`, `firm`, `modules`, `i18n`, `branding`, `assets` |
| **Shared utils** | Cross-cutting primitives | ~4 | `isodate`, `numwords`, `numbering`, `money` |

**The load-bearing virtue:** the domain layer is *pure* and *testable headless*.
`tests/test_core.py` exercises it end-to-end (including DB stores against a temp
SQLite file). This is the single most valuable architectural property the app
has, and any restructure must preserve it absolutely.

### 2.2 What is genuinely enterprise-grade already (**Implemented**)

- **Maths/UI separation.** Business logic lives in pure modules; `tab_*` are a
  thin GUI over them. The `CrudFrame` / `DocumentFrame` abstractions
  (`crud_frame.py`, `tab_documents.py`) mean most screens are declarative.
- **Single source of truth for navigation.** `modules.SECTIONS_CATALOG` drives
  both the UI layout and the feature-toggle panel — a real **feature-flag
  system** (`module:<label>` in `app_settings`).
- **Testability.** 605 tests, pure-first, DB stores tested against temp files.
- **Security posture.** Opt-in login, roles (Admin/Operator/Viewer), versioned
  PBKDF2, lockout, audit log; per-tab write-gating via `ui_guard.can_write()`.
- **Deployment story.** `paths.py` cleanly separates read-only bundle
  (`resource_base()`) from writable per-user data (`data_dir()`), frozen vs
  source — so the same code runs from a USB stick or an installed `.exe`.
- **Two front-ends, one core.** Desktop (tkinter) and web (`http.server`) both
  sit over the *same* pure modules and DB — no logic duplicated.
- **Multi-tenant data.** `company.py` — a firm/year file registry with
  carry-forward of masters. This is real multi-book support.

### 2.3 What is not enterprise-grade (**Change**)

| # | Issue | Why it matters | Evidence |
|---|---|---|---|
| C1 | **Flat 143-file namespace** | No module boundaries; hard to navigate, easy to collide | `lessons.py` vs `lessons_register.py` collision (just happened on merge) |
| C2 | **Layering by convention, not structure** | Nothing *prevents* a domain module importing tkinter or a store; the rule is a docstring | Only a partial guard exists (the AST import test checks *imports are declared*, not *layer direction*) |
| C3 | **Config scattered across 3 mechanisms** | No single place to see/override configuration; hard to reason about per-tenant/env | `app_settings` (DB) + JSON company registry + `paths.py`/env (`LOCALAPPDATA`, `OLLAMA_MODELS`) |
| C4 | **`main.py` hard-wires ~70 tab imports** | Adding a tab edits a monolith; wiring and catalog can drift | `main.py` top: 40+ `from tab_* import build_*` lines |
| C5 | **Schema is one growing string; no migration ledger** | `db.SCHEMA` + an ad-hoc `_ADD_COLUMNS` list; no versioned migrations or rollback | `db.py` `SCHEMA` (1000+ lines) + `_ADD_COLUMNS` |
| C6 | **No enforced module ownership / naming** | 47 `tab_*` + 60 domain modules with no package to signal ownership or bounded context | flat `construction_app/` |
| C7 | **Reporting/AI/web mixed into the flat root** | Service layers aren't isolated; a web-only or AI-only change touches the common root | `webapp.py`, `assistant.py` sit beside `finance.py` |

None of these is a defect in *behaviour* — the app works and is well-tested. They
are **structure and governance** gaps that slow an enterprise team and invite the
collision/ drift failure modes above.

---

## 3. Target enterprise structure (which module goes where)

### 3.1 The layered package tree

Group the existing modules into **six layers as packages**, with a strict
**dependency direction** (arrows point to what a layer may import):

```
app  ──►  ui  ──►  services  ──►  domain  ──►  data
  │        │           │            ▲           ▲
  └────────┴───────────┴────────────┴───────────┘
                    all may import  config  and  shared
```

- **`domain` never imports `ui`, `services`, or `app`.** It may import `data`
  (stores) and `shared`. This is the rule that keeps the core pure and testable.
- **`ui` and `services` (web, ai) are peers** over the domain — the two
  front-ends and the sidecars, none depending on the other.
- **`config` and `shared` are leaves** everyone may use.

```
construction_app/                # (kept as the package root to preserve tooling)
├── app/                         # entry points + composition only
│   ├── main.py                  # desktop bootstrap (login → shell → notebook)
│   ├── web_main.py              # headless web entry
│   └── registry.py              # NEW: tab/section registration (extracted from main.py)
│
├── config/                      # ALL configuration in one place
│   ├── paths.py                 # frozen/source + data_dir/resource_base
│   ├── settings.py              # NEW: typed accessors over app_settings (DB)
│   ├── company.py               # firm/year file registry + carry-forward
│   ├── firm.py                  # firm details
│   ├── modules.py               # feature-flag catalog (SECTIONS_CATALOG)
│   ├── i18n.py                  # vernacular strings
│   ├── branding.py  assets.py   # brand identity + logos
│   └── resources/               # committed binary brand assets
│
├── shared/                      # cross-cutting primitives (leaf)
│   ├── isodate.py  money.py  numwords.py  numbering.py
│
├── data/                        # persistence
│   ├── db.py                    # connection (WAL/FK/timeout) + init
│   ├── schema.sql / schema.py   # CHANGE: schema extracted from db.py
│   ├── migrations.py            # CHANGE: versioned additive migrations (from _ADD_COLUMNS)
│   ├── sampledata.py
│   └── stores/                  # DB-access modules (take a conn)
│       ├── risk_store.py  opportunity_store.py  lessons_store.py
│       ├── portfolio_store.py  journal_post.py
│
├── domain/                      # PURE business logic (no tkinter, no DB imports of ui)
│   ├── finance/                 # finance, posting, reports, ageing, cashflow, statutory
│   ├── commercial/              # estimate, bidding, variation, subcontract, procurement,
│   │                            #   sourcing, projectcost, projman, submittals
│   ├── civil/                   # civil, mb, takeoff, rateanalysis, refdata, analytics
│   ├── schedule/                # programme, cpm, scheduler, planning
│   ├── risk/                    # risk, risk_detect, opportunity, forecast, drift,
│   │                            #   advisory, review_pack, narrative, dashboard
│   ├── execution/               # productivity, hse, quality, closeout, plant, muster,
│   │                            #   wages, consumption*, lessons, lessons_register
│   └── earnedvalue.py           # (or under a `controls/` bounded context)
│
├── services/                    # cross-cutting services over the domain
│   ├── web/                     # webapp, webserver, webrender, web_masters, netinfo
│   ├── ai/                      # assistant, ollama_api/client/catalog/service, model_provision
│   ├── reporting/               # bill_export, pdf_render, report_open, einvoice
│   └── security/                # auth, security, session, approval
│
└── ui/                          # tkinter presentation
    ├── shell.py theme.py tokens.py widgets.py crud_frame.py ui_guard.py errors.py
    └── tabs/                    # all 47 tab_*.py, grouped by section to mirror the catalog
        ├── masters/  project/  operations/  billing/  purchases/  money/  accounts/  tools/
```

### 3.2 Per-module mapping (the "where does it go" table)

Every current module → its target home (abbreviated; the full set follows the
same rules):

| Current module(s) | → Target |
|---|---|
| `main`, `web_main` | `app/` |
| `paths`, `company`, `firm`, `modules`, `i18n`, `branding`, `assets`, `resources/` | `config/` |
| `isodate`, `money`, `numwords`, `numbering` | `shared/` |
| `db` | `data/` (+ extract `schema` and `migrations`) |
| `risk_store`, `opportunity_store`, `lessons_store`, `portfolio_store`, `journal_post`, `sampledata` | `data/stores/` |
| `finance`, `posting`, `reports`, `ageing`, `cashflow`, `statutory` | `domain/finance/` |
| `estimate`, `bidding`, `variation`, `subcontract`, `procurement`, `sourcing`, `projectcost`, `projman`, `submittals` | `domain/commercial/` |
| `civil`, `mb`, `takeoff`, `rateanalysis`, `refdata`, `analytics` | `domain/civil/` |
| `programme`, `cpm`, `scheduler`, `planning` | `domain/schedule/` |
| `risk`, `risk_detect`, `opportunity`, `forecast`, `drift`, `advisory`, `review_pack`, `narrative`, `dashboard`, `earnedvalue` | `domain/risk/` (controls) |
| `productivity`, `hse`, `quality`, `closeout`, `plant`, `muster`, `wages`, `lessons`, `lessons_register` | `domain/execution/` |
| `webapp`, `webserver`, `webrender`, `web_masters`, `netinfo` | `services/web/` |
| `assistant`, `ollama_*`, `model_provision` | `services/ai/` |
| `bill_export`, `pdf_render`, `report_open`, `einvoice` | `services/reporting/` |
| `auth`, `security`, `session`, `approval` | `services/security/` |
| `shell`, `theme`, `tokens`, `widgets`, `crud_frame`, `ui_guard`, `errors` | `ui/` |
| all `tab_*` | `ui/tabs/<section>/` |

_\*`consumption` maths lives in `civil.reconcile_consumption`; the tab goes to
`ui/tabs/operations/`._

### 3.3 The one rule that makes it enterprise-grade

> **Dependency direction is enforced by a test, not trusted to discipline.**

Extend the existing AST import test (`tests/test_core.py` already parses every
module's imports) into a **layering test**: assert that no `domain/**` module
imports `tkinter`, `ui.*`, `services.*`, or `app.*`; that `data/**` imports
neither `ui` nor `services`; and that `config`/`shared` import nothing above
them. This converts the current docstring convention ("No tkinter/DB") into a
**mechanically enforced boundary** — the thing that separates an enterprise
architecture from a tidy one.

---

## 4. Application workflow (how it runs today)

### 4.1 Desktop boot & request flow (**Implemented**)

```
python main.py
   │
   ├─ paths.data_dir()            # locate the writable book (source vs installed)
   ├─ db.init_db()               # SCHEMA + additive migrations + CoA seed + indexes
   ├─ auth / tab_login            # optional login gate (if security enabled)
   ├─ tab_wizard.maybe_run_setup  # first-run firm/site/client
   ├─ shell.RailStage             # left rail → sections (from modules.SECTIONS_CATALOG)
   └─ ttk.Notebook per section    # main.py wires each label → a build_*_tab(parent, db_getter)

   User action in a tab
      → tab_* (GUI)  reads/writes via  db.get_conn()  (short-lived, WAL, FK on)
      → delegates maths to a pure domain module (finance/civil/risk/…)
      → renders result; write-gated by ui_guard.can_write() for the role
```

**Key properties:** connections are **short-lived** (opened/closed per
operation), so switching the active firm file (`company.py` sets `db.DB_PATH`)
just changes what the next operation opens. Any uncaught GUI error is caught by
`errors.py` and shown as a plain dialog — never a stack trace.

### 4.2 Web / LAN flow (**Implemented**)

```
python web_main.py                 # or Tools › Web/LAN access
   → webserver.serve(host, port)   # ThreadingHTTPServer (stdlib), 0.0.0.0
   → webapp.handle(Request)→Response  # routing, sessions, login gate (socket-free, unit-tested)
   → same pure domain modules + db.get_conn()   # NO logic duplicated
   → webrender.py                  # theme-aware HTML (stdlib escaping)
```

Login is always required on the web; roles + PBKDF2 + audit are reused from the
desktop. Serves the **same** SQLite file. This is the model for the enterprise
"server does the compute, browsers are thin clients" topology (see
[`AI-MODELS-AND-DEPLOYMENT.md`](AI-MODELS-AND-DEPLOYMENT.md)).

### 4.3 AI flow (**Implemented**)

```
tab_assistant (or web)  → assistant.answer(question)
   → retrieval (TF-IDF over schema docs) + validate_sql + PRAGMA query_only
   → ollama_client.generate()  → LOCAL Ollama sidecar (localhost, urllib, no pip)
   → deterministic quick_answers()  as the offline floor when no model is present
```

AI is **read-only by construction** and **local-first** — the pattern the
enterprise capture/narration layers extend.

### 4.4 The workflow gap (**Change**)

`main.py` is both the **composition root** (correct) and a **hard-coded wiring
table** of ~70 imports (the smell). Extract a `app/registry.py` where each tab
**registers itself** against a catalog label, so `main.py` iterates
`modules.SECTIONS_CATALOG` and asks the registry for a builder — the catalog and
the wiring can no longer drift, and adding a tab no longer edits a monolith.

---

## 5. Menu structure, navigation hierarchy & operational workflow

This section documents the **menu hierarchy** (what the user sees and clicks),
the **operational workflow** (how work actually flows across those menus), and
the gap between the two — the enterprise navigation questions.

### 5.1 Current menu hierarchy (**Implemented**)

The app uses one spatial model (`shell.RailStage`): a fixed **left Rail** of
top-level entries, each opening a **Stage** that holds a Notebook of that
section's tabs. It is a **two-level hierarchy**, driven by
`modules.SECTIONS_CATALOG` (the single source of truth), with `Home`,
`Assistant`, and `Tools` always-on at the ends:

```
Rail (top level)                Stage (tabs within the section)
─────────────────────────────────────────────────────────────────────────────
🏠 Home            (always on)  intelligent dashboard (KPIs, advisories, bottlenecks)
💬 Assistant       (always on)  Ask-your-data · AI Engine
🗂  Masters                     Sites · Clients · Vendors · Materials · Labour · Equipment
🏗  Project Management          Projects · Timeline (Gantt/CPM) · Look-ahead (PPC)
🛠  Operations                  Warehouse · Muster & Wages · Labour Ops · Equipment Hire ·
                                Plant · Consumption · Site Reports · Quality · Safety · Closeout
🧾 Billing                      Rate Book · Rate Analysis · Takeoff · Bid/No-Bid · Quotations ·
                                Estimates · Contracts · BOQ/RA Bills · Variations · Running Bills · Tax Invoice
🛒 Purchases                    Sourcing · Purchase Orders · Goods Receipt · Vendor Invoices · Subcontractors
💰 Money                        Key Numbers · Approvals · Cash & Parties · Cash Flow · Retention · Insight
📊 Accounts                     GST & TDS · Compliance · Accounting
⚙  Tools           (always on)  Backup & Settings · Company Files · Modules · Users & Security · Audit Log
```

**Properties:** sections are built **lazily** (on first open, so startup is
instant); every section and its tabs can be **toggled off** per firm
(`module:<label>` feature flags — a `Viewer` sees the same menu as an `Admin`,
minus the write buttons); the rail uses a **pictogram per row** so a section is
found by shape before the word. The menu is organised **by function**
(Masters / Operations / Billing / …), not by workflow.

### 5.2 Operational workflow — how work flows across the menus (**Implemented** logic; **not surfaced as guided flows**)

The business processes are end-to-end sequences that **cross several
functional sections** — the menu does not signpost the order, the user must know
it. The core operational flows, with the menu each step lives in:

| Workflow | Step sequence (→) and where it lives |
|---|---|
| **Bid → Contract** (pre-construction) | Sourcing *(Purchases)* → Rate Analysis / Takeoff *(Billing)* → Estimate *(Billing)* → Bid/No-Bid *(Billing)* → Quotation *(Billing)* → **Contract** *(Billing)* |
| **Contract → Cash** (commercial) | Contract → BOQ *(Billing)* → Measurement Book / Takeoff *(Billing)* → RA / Running Bill *(Billing)* → Variations *(Billing)* → Tax Invoice *(Billing)* → Receipt + allocation *(Money)* → Retention release *(Money)* |
| **Procure → Pay** (supply) | Requisition / Sourcing *(Purchases)* → Purchase Order *(Purchases)* → **Goods Receipt / 3-way match** *(Purchases)* → Vendor Invoice *(Purchases)* → Payment *(Money)* |
| **Plan → Execute** (delivery) | Project *(Project Mgmt)* → Timeline/CPM/baseline *(Project Mgmt)* → Look-ahead/PPC *(Project Mgmt)* → DPR / Site Reports *(Operations)* → Consumption reconcile *(Operations)* → Quality ITP/NCR *(Operations)* → Safety *(Operations)* → Closeout / snags *(Operations)* |
| **Labour cycle** | Muster *(Operations)* → Weekly payout *(Operations)* → Advances *(Operations)* → Payroll *(Operations)* → Payment *(Money)* |
| **Record → Report** (finance) | auto-posting *(engine)* → Journal → Trial Balance → P&L / Balance Sheet *(Accounts)* ; GST & TDS registers, Compliance calendar *(Accounts)* |
| **Risk & Opportunity** (Part 2) | Identify/detect → Assess → Prioritize → Respond → Monitor — **logic built (`risk*`, `opportunity*`), but no menu home yet** |
| **Continuous improvement** | Closeout → Lessons / Rate Realisation → feed the Rate Book *(Billing)* |

The **guardrail engine already knows the flow**: `advisory.py` ranks "what to do
next", and `followups.py` maps an event to its rote next steps (both built). The
menu simply doesn't yet *present* work as a guided flow.

### 5.3 Menu & workflow gaps (**Change**)

| # | Gap | Impact |
|---|---|---|
| **N1** | **New registers have no menu home** — Risk, Opportunity, Lessons-learned registers exist as data+logic (Part 2) but are unreachable in the UI | The Part 2 deliverables can't be used by an operator |
| **N2** | **Menu is functional, not workflow-guided** — no "what's next" / process view threading bid→contract→bill→collect | A new user can't discover the operating sequence; steps are hunted across sections |
| **N3** | **No role/persona-scoped menu** — every enabled section shows for every role (Viewer = Admin menu minus buttons) | A site clerk, a QS, and an accountant see one undifferentiated 47-tab surface |
| **N4** | **No global search / command palette / breadcrumbs** — with 47+ tabs, findability is by memory | Slow navigation; no deep-linking to a record |
| **N5** | **Crowded sections don't sub-group** — Billing already holds 11 tabs; new registers will worsen it | The two-level hierarchy doesn't scale as capability grows |
| **N6** | **Workflow-menu mismatch** — steps of one process sit in different sections (Sourcing in Purchases, Bid/No-Bid in Billing; measurement in Billing, DPR in Operations) | The functional grouping fights the operational flow |

### 5.4 Target enterprise menu & workflow model (**Change**)

- **A "Controls" (or "Risk & Governance") section** — a menu home for the Part 2
  registers: **Risk Register · Opportunity Register · Lessons Learned ·
  Submittals**, so the built logic becomes reachable (closes **N1**).
- **Role/persona-scoped menus** — extend the feature-flag model with a
  **role → visible-sections** map (Owner, QS/Commercial, Site Engineer,
  Accountant, Storekeeper), so each persona lands on a menu shaped to their job
  (**N3**). Keep it data-driven (a `config/menu.py` mapping), unit-testable.
- **A guided-workflow layer over the functional menu** — a "Process / What's
  next" view that threads the §5.2 flows as ordered steps with completion state,
  built on the **already-present** `advisory.py` (ranking) and `followups.py`
  (next-step logic). The functional menu stays; the workflow view is an overlay
  that *sequences* it (**N2**, **N6**). The step→section→tab graph is a
  deterministic, testable model (`workflow.py`).
- **Global search / command palette** — one keystroke to jump to any tab or
  record; the web layer already routes by URL, so deep-links/breadcrumbs align
  the two front-ends (**N4**).
- **Sub-section grouping** — allow a section's catalog entry to hold *grouped*
  tabs (e.g. Billing → *Pre-construction* / *Contract billing* / *Invoicing*), so
  the hierarchy can deepen from two levels to three where a section is crowded
  (**N5**). This is a `SECTIONS_CATALOG` schema extension, backward-compatible.

The menu **model** (role map, workflow graph, catalog grouping) is pure config +
data and **unit-testable headless**; only the on-screen rendering is
display-dependent — the same build/verify boundary as the rest of the roadmap.

## 6. Application configuration (where settings live)

### 6.1 Current configuration surface (**Implemented**, but scattered — **C3**)

| Mechanism | Holds | Where |
|---|---|---|
| **`app_settings` table** (DB) | `company_name`, `language`, `ui_theme`, `works_gst_pct`, `cash_opening`, `setup_done`, **`module:<label>`** (feature flags), **`compliance:<type>`** | inside each firm's SQLite file |
| **Company registry** (JSON) | list of firm/year files (name + path) | JSON beside the code (`company.py`) — must live outside any one book |
| **`paths.py` + env** | writable vs bundle dirs; `LOCALAPPDATA` (Windows), `OLLAMA_MODELS` | filesystem/env |
| **`firm.py`** | firm details (name, GSTIN, address, bank) | `app_settings` |

This is coherent but **spread across three places**, with no typed accessor and
no environment-override path — awkward for per-tenant/per-environment enterprise
deployments.

### 6.2 Target configuration (**Change**)

- **A `config/settings.py` façade** — typed getters/setters over `app_settings`
  (`get_bool`, `get_decimal`, `feature_enabled(label)`), so call-sites stop
  hand-writing SQL against the settings table and defaults live in one place.
- **Layered precedence** — environment variable > per-firm `app_settings` >
  built-in default. Lets an enterprise set, e.g., the AI endpoint or a feature
  flag per deployment without touching the book. Keep it stdlib (`os.environ`),
  no config framework.
- **Feature flags already exist** (`module:<label>`) — promote them to a
  first-class `config/flags.py` so both UI toggles and *service* toggles (enable
  web, enable AI, enable capture) read one API.
- **Secrets** — none stored today (good). If cloud-AI opt-in lands
  (`AI-MODELS-AND-DEPLOYMENT.md` §6.1), keep keys in the environment / OS
  keystore, never in `app_settings` or the book.

---

## 7. What's implemented vs what needs to change (summary)

### 7.1 Implemented (keep — these are strengths)

- Pure domain core with 605 tests; maths/UI separation; `CrudFrame`/`DocumentFrame`.
- Feature-flag module catalog; opt-in security with roles + audit + write-gating.
- Clean frozen/source path handling; multi-firm/year registry + carry-forward.
- Two front-ends (desktop + web) over one core; local read-only AI sidecar.
- Offline, single-file, no-pip, single-folder distributable.

### 7.2 Change (proposed), by priority

| Pri | Change | Addresses | Effort | Risk |
|---|---|---|---|---|
| **P0** | **Enforce layering with a test** (domain imports no tkinter/ui/services) | C2 | S | none (test only) |
| **P0** | **Consolidate config** behind `config/settings.py` + env precedence | C3 | S–M | low |
| **P1** | **Group modules into layered packages** (`domain/`, `data/`, `services/`, `ui/`, `config/`, `app/`) | C1, C6, C7 | L | medium |
| **P1** | **Extract tab registration** into `app/registry.py`; iterate the catalog | C4 | M | low |
| **P2** | **Extract schema + versioned migrations** from `db.py` | C5 | M | medium |
| **P2** | **Group `tab_*` under `ui/tabs/<section>/`** to mirror the catalog | C1, C6 | M | low |

### 7.3 Migration path (low-risk, phased — respects the constraints)

The tension: package boundaries want `from domain.finance import finance`, but
flat imports (`import finance`) are what keep the single-folder/PyInstaller story
simple, and every module + the AST test + the `.spec` assume them. So migrate in
order of **value-per-risk**, not big-bang:

1. **Phase A (P0, no move):** add the **layering test** and the **`settings`
   façade**. Pure wins, zero file moves, immediately enterprise-grade governance.
2. **Phase B (P1, leaves first):** create the packages and move the **safest
   leaves** — `shared/`, `config/`, `services/ai/`, `services/web/` — updating
   imports and the PyInstaller `hiddenimports`. These have few inbound
   dependencies, so the blast radius is small. Add per-package `__init__.py` that
   re-exports names, or keep a thin top-level shim during transition so
   `import finance` still resolves until every caller is moved.
3. **Phase C (P1/P2):** move `domain/` by bounded context, then `data/`, then
   `ui/tabs/` — one context per PR, tests green after each. Extract `registry.py`
   and `migrations.py` as their contexts move.
4. **Phase D (P2):** delete the transition shims once no flat import remains;
   update `AGENTS.md`'s file map to the package tree; update the installer spec.

Each phase is independently shippable and independently valuable, and the test
suite gates every step — the same discipline the rest of the roadmap uses.

### 7.4 The trade-off, stated plainly

A full package refactor (Phases B–D) has real cost: it touches every file's
imports, the AST/layering tests, the PyInstaller spec, and contributors' muscle
memory, for **no behaviour change**. If the team values the current
zero-ceremony flat layout, **Phase A alone** (enforced layering + config façade)
captures most of the enterprise-governance benefit at almost no risk, and the
package move (B–D) can follow when the module count or the team size makes the
flat namespace genuinely painful. **Recommendation: do Phase A now; schedule
B–D when a second squad starts working the code in parallel** — that is the point
at which flat-namespace collisions (like `lessons.py`) stop being rare.

---

## 8. Summary

Construction OS already has the *hard* half of an enterprise architecture: a
pure, deeply-tested domain core cleanly separated from its two front-ends, with
security, multi-tenancy, offline operation, and a local-AI sidecar. What it lacks
is *structural expression and governance* of that architecture — the 143 modules
sit in one flat namespace, layering is a convention rather than an enforced
boundary, configuration is spread across three mechanisms, and the composition
root hard-wires every tab.

The fix is organisation, not rewrite: **enforce the dependency direction with a
test, consolidate configuration behind one façade, and group the modules into
layered packages** (`app` · `ui` · `services` · `domain` · `data` · `config` ·
`shared`) with a per-module home already specified in §3.2. Done in phases —
governance first (Phase A, near-zero risk), packages later (B–D, when parallelism
demands it) — it delivers an enterprise-grade structure **without sacrificing the
offline, no-pip, single-folder qualities that are the product's real moat.**

---

_Architecture research & target design. Describes and proposes; changes no code.
The per-module mapping (§3.2), menu & workflow model (§5), configuration surface
(§6), and the phased migration (§7.3) are the actionable core. Read with
[`../AGENTS.md`](../AGENTS.md) (current file map & conventions) and
[`ROADMAP.md`](ROADMAP.md)._
