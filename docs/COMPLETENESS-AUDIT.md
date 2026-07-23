# Completeness audit — fake data, placeholders, stubs, and remaining work

**Date:** 2026-07-23  
**Repo tip audited:** `main` @ current (API **u0.11**, **728** tests / 5 skipped)  
**Scope:** Construction OS / ACO — Python domain + JSON API + desktop + WinUI +
sidecars + docs.  
**Method:** ripgrep for stub/placeholder/TODO language; AST purity counts;
catalog ↔ builder / WinUI route cross-check; comparison with
`CLOUD-TASKS.md`, `ROADMAP.md`, `WINUI3-MIGRATION.md`, `AGENTS.md` §14;
headless suite run.

This report answers two questions:

1. Where is the product **faking** readiness (dummy modules, soft stubs,
   mis-routed UI that looks finished)?
2. What is **actually complete** vs what still **needs to be coded**?

---

## 1. Executive verdict

| Layer | Verdict |
|---|---|
| **Python domain maths + SQLite ERP** | **Complete** for the shipping desktop product. No dummy business modules; money/schedule figures return `None` when undefined (never a fake 0). |
| **JSON API (cloud / U0)** | **Complete** for CT-1…CT-10 + C0–C14 surface (u0.11). Test-backed. |
| **Desktop tkinter UI** | **Complete** catalog wiring (52 section tabs + always-on Home/Assistant/AI Engine/Tools). Needs a display to smoke-test. |
| **WinUI 3 client** | **Partial.** Tabs are *wired* (few dead-ends), but several land on the **wrong thin page** or a **read-only list** where desktop has full workflows. Docs that say “parity ✅” overclaim *functional* parity. |
| **AI / sidecars** | **Soft stub floor only.** No OCR/STT/VLM weights in-repo; Foundry/assistant need a local model. |
| **Fake / dummy modules** | **None** that invent business numbers. Intentional: `sampledata.py`, `sidecars/stub_server.py`, `refdata.py`. |

**Bottom line:** Do not rebuild the ERP core. Prioritise (a) honest WinUI depth
for mis-routed tabs, (b) API gaps those tabs need, (c) real sidecar weights
locally, (d) doc honesty on “parity”.

---

## 2. Inventory — fake data, placeholders, stubs

### 2A. Intentional / labelled (OK — keep)

| Item | Path | Why OK |
|---|---|---|
| Sample company book | `construction_app/sampledata.py`, Tools › Load Sample Data | Explicitly a **separate** company file; never overwrites the live book |
| CPWD starter library | `construction_app/refdata.py` | Opt-in reference rates/norms |
| Sidecar soft-fail server | `sidecars/stub_server.py` | Returns `{fields:{}, stub:true}` — documented as no-weights floor |
| Sidecar folders | `sidecars/{ocr,stt,vlm}/README.md` | README-only until weights installed |
| Bridge status | `construction_app/sidecar_bridge.py`, `GET /api/sidecar/status` | Reports `stub` + live probe; fails soft |
| WinUI Capture page | `winui/.../CapturePage.xaml.cs` | Shows stub/live status; draft/confirm still human-gated |
| Foundry empty lists | `foundry_client.py` / `foundry_service.py` | `[]` / `{}` when daemon absent — not fake answers |
| Test fixtures | `tests/` | `Acme`, mocks, temp DBs — test-only |
| HTML `placeholder=` attrs | web search boxes, WinUI `PlaceholderText` | Input hints, not feature stubs |

### 2B. Soft stubs (expected — not fake success)

| Item | Behaviour | Remaining work |
|---|---|---|
| OCR / STT / VLM | Stub HTTP or empty extract | Install real weights + extractors **locally** (L8) |
| Assistant without model | Deterministic quick answers only | Local Foundry / model provision on Windows |
| `pdf_render` without tools | Soft fail / clear error | Optional poppler/gs on host |
| LAN plain HTTP | Trusted network only | Reverse proxy if exposed wider (`docs/LAN.md`) |

### 2C. Hard placeholders / miswires (look finished — fix or label)

These are the main honesty problems. WinUI resolves almost every catalog label
to *some* page, so users can believe the feature exists when they only see a
thin proxy.

| Catalog / always-on tab | WinUI lands on | Desktop reality | Severity |
|---|---|---|---|
| **Assistant** | `CapturePage` (sidecar probe) | RAG text-to-SQL assistant (`tab_assistant.py`) | **High** |
| **AI Engine** | `CapturePage` | Foundry start/stop (`tab_aiengine.py`) | **High** |
| **BOQ / RA Bills** | `ImportPage` (paste → BOQ draft APIs) | Measurement Book + RA bill generation + CPWA forms (`tab_boq_ra.py`) | **High** |
| **Subcontractors** | `MastersPage("thekedars")` | Work orders + subcontractor running bills (`tab_subcontract.py`) | **High** |
| **Cash Flow** | `MoneyPage` (payments — via `Has("Cash")`) | Cash-flow forecast (`tab_cashflow.py`); chart already on `ChartsPage` | **High** |
| **Cash & Parties** | `MoneyPage` (payments) | Party balances / statements (`tab_money.py` views) | **Medium–High** |
| **Key Numbers** + **Insight** | Same `ChartsPage` | Separate KPI + analytics surfaces | **Medium** |
| **Timeline** | `DataTablePage` → `timeline_tasks` | Gantt + CPM + baseline (`tab_timeline.py`) | **Medium** |
| **~21 ops / billing / purchase tabs** | `DataTablePage` read-only | Full CrudFrame / DocumentFrame / bespoke workflows | **Medium** |
| **Goods Receipt** (NavRoute) | Can hit `ImportPage` (Import/GRN draft) *or* table route depending on order | Desktop GRN + three-way match + stock post | **Medium** |
| **Process** | Thin workflow string list | Desktop process board | **Low–Medium** |
| **Tools** | `ToolsPage` (firm + module toggles) | Backup/restore, sample data, refdata, language, security still desktop/API-incomplete | **Medium** (partially labelled) |
| `InfoPage` | Fallback only | Honest placeholder — currently rare for catalog tabs | Low (good) |

Evidence:

```31:34:winui/ConstructionOS.WinUI/Helpers/NavRoute.cs
        (t => Has(t, "Capture") || Has(t, "AI Engine") || Has(t, "Assistant"),
            typeof(CapturePage)),
        (t => Has(t, "Import") || Has(t, "Goods Receipt") || Has(t, "BOQ")
              || Has(t, "Requisition") || Has(t, "Sourcing"), typeof(ImportPage)),
```

```22:29:winui/ConstructionOS.WinUI/MainWindow.xaml.cs
        ["Subcontractors"] = "thekedars", ["Thekedars"] = "thekedars",
```

### 2D. Not found (clean)

- No `NotImplementedError` / `TODO` / `FIXME` in domain Python or WinUI C# feature code (packaging manifest has a signing TODO).
- No `*dummy*` / `*fake*` / `*mock*` product modules.
- No `/api/*` handlers that return canned *business* KPIs when data is empty (empty lists / `None` / honest zeros where maths defines them).
- Desktop `SECTIONS_CATALOG` labels all have builders in `main.BUILDERS` (verified by layout; headless import of `main` needs tkinter).

---

## 3. What is complete (evidence-backed)

Counts at audit time:

| Metric | Value |
|---|---|
| `construction_app/*.py` | **180** |
| AST tkinter-free | **117** (includes web/infra; ~90+ domain pure) |
| `tab_*.py` | **55** |
| Catalog section tabs | **52** |
| Unittest suite | **728** OK, **5** skipped (GUI smoke without Tk) |
| API version | **u0.11** |
| WinUI Views `*.xaml` | **22** pages |

### 3.1 Cloud / domain / API — COMPLETE

| Area | Evidence |
|---|---|
| Finance / GST / TDS / posting | `finance.py`, `gst.py`, `posting.py`, `journal_post.py`, `TestFinance`, `TestGst`, `TestJournalPosting*` |
| Civil billing spine | `civil.py`, `mb.py`, measurements API, BOQ import drafts |
| Money | ageing, cashflow, retention, allocation, payments docs |
| Accounts reports | `/api/gst`, `/api/pnl`, `/api/balance_sheet` (`reports_store.py`) |
| EVM / CPM / planning | `earnedvalue`/`evm`, `cpm`, `planning`, `/api/evm`, `/api/lookahead` |
| Risk / opportunity / lessons / submittals | stores + CRUD API + tests |
| Multi-company | `company.py` create/import/export/select/carry-forward + audit (CT-10) |
| Register table metadata | `web_tables.py` label/columns/FK names (CT-6) |
| CT-1…CT-10 | All marked ✅ in `docs/CLOUD-TASKS.md` |
| Web / LAN | `webapp`/`webrender` + `tests/test_web.py` |
| AI *draft* floors | capture, muster, GRN, vendor invoice, BOQ import, signals — gated confirm |

### 3.2 Desktop ERP — COMPLETE (feature surface)

Full rail: Masters, Project Management, Controls, Operations, Billing,
Purchases, Money, Accounts + Home / Assistant / AI Engine / Tools. Business
rules live in pure modules; tabs are thin. **GUI smoke not run in this cloud
environment** (no display / no tkinter).

### 3.3 WinUI — COMPLETE for U0–U5 *shell + API binding*

Working client patterns: ribbon from `/api/menu`, masters CRUD, money doc
create+list, register tables, GST, Accounting (P&L/BS/journal), Look-ahead,
Controls registers, Home/Charts/EVM, Capture/Import, Settings company picker,
Tools firm/modules. Packaging (U6) documented as built on Windows with
dev-signed MSIX — **not re-verified in this Linux cloud agent**.

---

## 4. What still needs to be coded

Prioritised for product honesty and contractor value. Effort is characterised by
**surface area**, not calendar time.

### P0 — Fix WinUI miswires (or show honest InfoPage)

| Work item | Code / API needed | Notes |
|---|---|---|
| **Assistant page** | New WinUI page + likely `POST /api/assistant` (or reuse desktop pipeline over HTTP) | Today CapturePage; no chat API |
| **AI Engine page** | WinUI controls over Foundry status start/stop APIs | Desktop `tab_aiengine` / `foundry_service` |
| **BOQ / RA Bills page** | Measurements CRUD UI + RA generate/approve; may need richer API beyond list/import | Highest billing gap |
| **Subcontractors** | API for `work_orders` / `sub_bills` + WinUI page (or InfoPage until ready) | Not in `_API_TABLES` / masters today |
| **Cash Flow tab** | Route to `ChartsPage` cash series *or* dedicated forecast page | `/api/cashflow` already exists |
| **Cash & Parties** | Party outstanding / statement API or dedicated page | Don’t leave as bare payments list |

Until built: route these labels to `InfoPage` with “desktop/LAN only for now”
copy — better than a wrong screen.

### P1 — WinUI depth for read-only tables that are workflows on desktop

Generic `DataTablePage` is fine for *registers*; not for:

| Tab family | Needs |
|---|---|
| Muster & Wages / Labour Ops | Editable muster grid, weekly payout, payroll generate |
| Goods Receipt / Purchase Orders | Header+lines, three-way match, stock post |
| Quality / Safety / Closeout | ITP/NCR/permit/incident/snag entry (not NCR list alone) |
| Timeline | Gantt + dependencies (or explicit “table only” label) |
| Quotations / Estimates / Variations | DocumentFrame-class editors |
| Warehouse | Stock IN/OUT with materials |

Pattern: either promote to dedicated pages (like Accounting/Lookahead) or add
create/edit to `DataTablePage` where masters-style CRUD is enough.

### P2 — API gaps still missing for parity

| Gap | Why |
|---|---|
| Subcontractor work orders / sub bills | Desktop Purchases › Subcontractors |
| Assistant ask endpoint | WinUI Assistant |
| RA bill **create** from measurements | U3 follow-up in WINUI3-MIGRATION |
| Tools: backup/restore, sample data, refdata, language, security users | Desktop Tools only |
| Journal write / Auto-Post from WinUI | AccountingPage is report-heavy |
| Print / HTML export from WinUI | Desktop uses `bill_export` → browser |

### P3 — Local / Windows-only (not cloud)

| Item | Owner |
|---|---|
| Real OCR/STT/VLM weights + extractors (L8) | Local |
| Production code-signing cert (replace MSIX dev cert) | Local / release |
| Interactive a11y walkthrough + keyboard pass | Local |
| Retire tkinter on Windows (product call after Tools API parity) | Local U7 |
| Display GUI smoke (`test_smoke_tabs`) in CI with Tk | Local / CI image |

### P4 — Intentional product limits (do **not** “fix” without a feature ask)

From `AGENTS.md` §14 — still true:

- Auto-post is manual; no reverse/un-post  
- Journal may save unbalanced  
- No retroactive `previous_billed` / RA snapshot behaviour  
- Weekly payout no dedupe  
- No PDF library (HTML → print)  
- Security opt-in; LAN plain HTTP  
- Project cost via `site_id`  

---

## 5. Documentation accuracy (overclaim / stale)

| Doc | Issue | Fix direction |
|---|---|---|
| `docs/ROADMAP.md` U7 | “parity pass ✅ (every catalog tab wired)” | Clarify **nav-wired ≠ feature-complete**; list miswires |
| `docs/ROADMAP.md` U5 | “honest placeholders for the rest” | Most tabs are thin proxies, not `InfoPage` |
| `docs/CLOUD-TASKS.md` CT-9 blurb | Still says WinUI shows a placeholder for look-ahead | Stale — `LookaheadPage` shipped |
| `docs/SOP-manual.md` / older gap reports | Some features still marked `[gap]` that exist | Refresh or point to this audit |
| `docs/APP-ARCHITECTURE.md` / AI deploy docs | May still mention Ollama modules (removed for Foundry) | Align with `foundry_*` |
| `AGENTS.md` module counts | May lag (~150 vs **180** `.py`) | Recount on next AGENTS edit |
| `winui/README.md` | May still describe NavigationView shell | Ribbon is current |

---

## 6. Recommended coding backlog (ordered)

**Cloud / headless (this agent class):**

1. JSON API for **work orders + sub bills** (list/create) + tests.  
2. **`POST /api/assistant`** (or `/api/ask`) wrapping existing `assistant.answer` — read-only, audited.  
3. Optional **party balances** endpoint for Cash & Parties.  
4. Tools settings expansion: backup path metadata, sample-data trigger (gated), refdata load — only if WinUI will consume them.  
5. Soften stale docs (`CLOUD-TASKS` CT-9 note; ROADMAP parity wording) in the same commits as behaviour fixes.

**Local / Windows:**

1. Remount Assistant / AI Engine / BOQ-RA / Subcontractors / Cash Flow to real pages (or InfoPage).  
2. Muster / GRN / document editors beyond read-only tables.  
3. Sidecar weights (L8).  
4. Release signing + clean-box MSIX install test.  
5. Retire tkinter only after Tools + billing depth decision.

---

## 7. How to re-run this audit

```bash
# Headless suite
python -m unittest discover -s tests

# Stub / placeholder language (ignore SQL ? placeholders)
rg -n -i 'NotImplemented|FIXME|TODO|stub_server|sampledata|InfoPage|coming soon' \
  construction_app winui sidecars docs --glob '!**/CHANGELOG.md'

# WinUI route map
sed -n '1,60p' winui/ConstructionOS.WinUI/Helpers/NavRoute.cs
sed -n '20,80p' winui/ConstructionOS.WinUI/MainWindow.xaml.cs

# Module counts
python -c "import os,ast; ..."  # see §3 counts method in this doc's PR notes
```

---

## 8. Summary table — complete vs needs coding

| Product area | Complete | Needs coding |
|---|---|---|
| Masters | Desktop + API + WinUI CRUD | — |
| Operations | Desktop full; API lists | WinUI workflows (muster, GRN, quality entry) |
| Billing / civil | Desktop full; measurements/import API | WinUI BOQ/MB/RA; RA create |
| Purchases | Desktop full | Subcontractor WO/bills API + WinUI; GRN depth |
| Money | Desktop + API reports | WinUI Cash Flow / party statement routing |
| Accounts | Desktop + GST/P&L/BS API + WinUI reports | Journal write / auto-post in WinUI |
| PM / Controls | Desktop + API + WinUI pages | Timeline Gantt; thinner Process |
| AI | Draft floors + soft sidecars | Assistant API/page; Engine page; real models |
| Multi-company | Backend + login + WinUI picker | — |
| Packaging | Dev MSIX on Windows (claimed) | Prod cert; clean install verify |
| Docs | Mostly current | Soften “parity ✅”; fix stale SOP/Ollama/CT-9 |

---

*Generated by cloud completeness audit. Update this file when P0 miswires are
fixed or when API version / test counts change materially.*
