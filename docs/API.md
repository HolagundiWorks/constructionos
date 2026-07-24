# ACO — JSON API contract (U0)

Localhost backend for the WinUI 3 client and future mobile. Stdlib Python;
routed under `/api/*` by `webapp` → `webapi`. Socket-free unit tests in
`tests/test_web.py` (`TestWebApi`).

**Product:** ACO (Accelerated Construction Operations)  
**Base URL (dev):** `http://127.0.0.1:8080`  
**Version:** `u0.16` (`GET /api/health` → `{"api":"u0.16","service":"aco"}`)  
**Live map:** `GET /api/contract` (authenticated)

## Auth
| Step | Call |
|---|---|
| Companies (public) | `GET /api/companies` → `{items:[{name,path,active,exists}], active}` |
| Login / first-run admin | `POST /api/login` `{"username","password","company?"}` → sets `cosid` cookie, returns `{csrf, role, can_write, company}` |
| Session | `GET /api/me` |
| Writes | Header `X-CSRF-Token: <csrf>` (or body/`form` `csrf`) · Viewers → 403 |

`company` on login is a registered **path** or **display name** from the
registry (`companies.json`). Selecting a company switches the server process's
open book (`db.DB_PATH`) and resets sessions — **one active book per server
process** (fine for a small office LAN). Omit `company` to use the registry
active file. Successful login audits `company_select` into that book.
Create/import/new-year are **write-gated** on the desktop (Viewer may select
but not create).

## Reads
| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | Auth except login; reports `api: u0.15` |
| GET | `/api/companies` | **Public** company picker list (`exists` included) |
| GET | `/api/contract` | Endpoint catalogue for clients; includes `chart_bind` |
| GET | `/api/dashboard` | Snapshot + advisories |
| GET | `/api/home` | Dashboard + companion blocks (one round-trip) |
| GET | `/api/kpi` | Key Numbers rows (`kpi_store`) |
| GET | `/api/insight` | Site profit / progress / material budget |
| GET | `/api/review` | Weekly review pack |
| GET | `/api/portfolio` | Current-file roll-up; `?paths=` federates; includes advisories |
| GET | `/api/menu?persona=Owner` | Sections/tabs for NavigationView |
| GET | `/api/productivity` | Crew/plant utilisation from muster + plant logs |
| GET | `/api/filings/feed` | Overdue/due-soon → gated FILING_DUE drafts |
| GET | `/api/purchase_orders`, `/api/goods_receipts` | Procurement lists (`label`/`columns`/FK names) |
| GET | `/api/work_orders`, `/api/sub_bills` | Subcontractor WO + running bills |
| GET | `/api/match?tolerance=` | Three-way match + narration |
| GET | `/api/ageing` | Receivables ageing + `buckets` + chart `labels`/`values` |
| GET | `/api/cashflow?periods=&mode=week\|month` | Forecast `buckets` + `labels`/`values`/`series` |
| GET | `/api/gst?month=YYYY-MM` | Outward / HSN / inward / TDS; each block has **`cols`** |
| GET | `/api/gst/export?month=` | CA CSV/HTML GST/TDS export pack |
| GET | `/api/pnl?period=YYYY-MM\|FY\|YYYY-YY` | P&L sections + `grand_total` (net profit) |
| GET | `/api/balance_sheet?as_of=YYYY-MM-DD` | Balance sheet; `balanced` bool |
| GET | `/api/lookahead?project_id=&weeks=` | Weekly commitments + PPC + **`reasons`** catalogue |
| GET | `/api/commitments` | Commitment rows (+ reason codes) |
| GET | `/api/timeline?project_id=` | CPM schedule + baseline position |
| GET | `/api/muster?site_id=&att_date=` | Active labour attendance grid |
| GET | `/api/muster/payout?site_id=&week_start=` | 7-day wage compute |
| GET | `/api/bills/previous?contract_id=` | Approved/Paid running-bill sum |
| GET | `/api/boq_items?contract_id=` | BOQ lines for a contract |
| GET | `/api/allocations?payment_id=` | Payment↔bill allocation lines |
| GET | `/api/workflow?infer=1` | Flow graphs + progress (book-inferred by default) |
| GET | `/api/search?q=` | Tabs + records with `nav`/`tag` for WinUI |
| GET | `/api/narrative?kind=kpi\|risk` | Plain-language briefing (`narrative.py`) |
| GET | `/api/agents` | Multi-agent catalog + workflow list |
| GET | `/api/agents/{id}` | One agent (tools + examples) |
| GET | `/api/agents/workflows` | Multi-agent workflow recipes |
| GET | `/api/agents/provider` | Foundry Local / Azure Foundry status |
| GET | `/api/agents/eval` | Golden-question catalogue |
| GET | `/api/sidecar/status` | OCR/STT/VLM stub + live probe |
| GET | `/api/takeoffs` | Takeoff register (label+columns) |
| GET | `/api/takeoffs/{id}` | Takeoff + items + totals |
| GET | `/api/drawings/{id}/elements` | Drawing elements (Phase D) |
| GET | `/api/evm`, `/api/project/{id}/evm` | Earned value; portfolio adds `labels`/`values` (SPI) |
| GET | `/api/risks`, `/api/opportunities`, `/api/lessons`, `/api/submittals` | Registers |
| GET | `/api/audit?origin=ai` | Audit trail (`manual` includes legacy NULL) |
| GET | `/api/{master}` | includes **contracts**, **measurements** (`?contract_id=`); FK `options` |
| GET | `/api/{register}` | Read-only ops tables: `{table,label,columns,items}` with FK names |
| GET | `/api/{doc}` | payments, tax_invoices, vendor_invoices, bills, ra_bills (+ FK options) |

### Register tables (`label` + `columns` + FK names)
Whitelisted in `webapi._API_TABLES` (attendance, payroll, ncrs, …). Specs in
`web_tables.py`. Each column is `{key, label, align}`. FK ids stay on the row;
display names are added as `site` / `labor` / `vendor` / `client` / `project` /
`contract` / `material` / …

### Report `cols` contract
Array-of-arrays reports (`/api/gst`, and each P&L/BS section) include an ordered
**`cols`** header list whose length matches each row. Prefer `cols` over
hardcoding in the client.

## Writes
| Method | Path | Notes |
|---|---|---|
| POST | `/api/assistant` | NL→SQL ask (Foundry Local; read-only) |
| POST | `/api/agents/ask` | Persona agent ask `{question, agent_id?, use_model?}` — **proposals only** |
| POST | `/api/agents/workflow` | Multi-agent handoff `{workflow_id, context?}` |
| POST | `/api/agents/eval` | Run golden suite `{use_model?}` |
| POST/PUT/DELETE | `/api/risks[/{id}]` etc. | Registers + masters (incl. contracts, **measurements**) |
| POST | `/api/risks/detect` | Live snapshot → detected risks; `{apply:true}` persists drafts |
| POST | `/api/risks/accept` | `{ids}` and/or `{detect_and_apply:true}` → Accepted |
| POST | `/api/{doc}` | Money docs — **create only**; payments may return gated `followups` |
| POST | `/api/purchase_orders` | Header + `items[]`; `total_amount` = sum of line amounts |
| POST | `/api/work_orders` | Header + `items[]`; subcontractor WO |
| POST | `/api/sub_bills` | Sub running bill; totals via `subcontract.sub_bill_totals` |
| POST | `/api/ra_bills/generate` | MB → Draft RA (`ra_generate`) |
| POST | `/api/allocations` | Replace lines for a payment (`payment_id`, `lines`) |
| POST | `/api/capture/draft` | Stage extraction for human review |
| POST | `/api/capture/confirm` | Confirm → `work_done` / `daily_progress` / `ncr` / `snag` |
| POST | `/api/text/extract` | Free-text → draft fields (`text_extract`) |
| POST | `/api/muster/draft` | Name list → labour match drafts |
| POST | `/api/muster/confirm` | Write attendance rows |
| GET\|POST | `/api/muster` | Day grid load / save for Active labour |
| GET\|POST | `/api/muster/payout` | Compute / record weekly wages (idempotent) |
| POST/PUT/DELETE | `/api/commitments[/{id}]` | Look-ahead promises; POST id marks Done |
| POST | `/api/boq/import/draft` | CSV/TSV/plain → BOQ line drafts |
| POST | `/api/boq/import/confirm` | Write `boq_items` for a contract |
| POST | `/api/grn/draft` \| `/api/grn/confirm` | Challan paste → Draft GRN (no stock post) |
| POST | `/api/vendor_invoice/draft` \| `confirm` | Invoice paste → vendor invoice |
| POST | `/api/pdf/extract` | Soft-fail `pdftotext` |
| POST | `/api/patterns/learn`, `/api/signals/*`, `/api/intent`, `/api/sidecar/extract` | AI floors — drafts only |
| POST/PUT/DELETE | `/api/takeoffs[/{id}]` | Save takeoff + items (qty via `takeoff.measure`) |
| POST | `/api/takeoffs/{id}/to-estimate` | Draft estimate from takeoff (rates 0) |
| POST | `/api/drawings/elements/draft` | Normalize AI/vector elements (no write) |
| POST | `/api/drawings/elements/confirm` | Persist elements; optional `sync_takeoff` |
| POST | `/api/drawings/elements/ingest` | Already-parsed vector JSON → quantities |
| POST | `/api/drawings/revision-delta` | Element diff + gated variation draft |
| POST | `/api/drawings/revision-delta/confirm` | Persist `element_changes` (VO still gated) |
| POST | `/api/events`, `/api/signals/feed`, `/api/forecast`, `/api/drift` | Hooks / prediction |

### Measurements
`POST/PUT /api/measurements` derive `quantity = Nos×L×B×D` via `web_masters.derive` →
`civil.measurement_quantity`. A **blank dimension stays SQL NULL** (factor 1), never 0.
List with `GET /api/measurements?contract_id=`.

## Notes for WinUI
- Master/doc list payloads include **resolved FK `options`** — do not run `fk_sql` in C#.
- Register tables: bind `columns` + `items` (FK display keys); do not hardcode headers.
- Search record hits include `nav` / `tag` (`Section/Tab`) for `NavigationView` routing.
- Charts: bind LiveCharts to parallel **`labels` + `values`** on `/api/cashflow`,
  `/api/ageing`, and `/api/evm` (detail keys unchanged). Cashflow also exposes
  `series.{in,out,balance}`. See `GET /api/contract` → `chart_bind`.
- GST/TDS: bind `GET /api/gst?month=` using each section's **`cols`**.
- Accounting: prefer `/api/pnl` + `/api/balance_sheet` over raw `journal_entries`.
- Look-ahead: `/api/lookahead?project_id=` (resolves via `projects.site_id`).
- Agents: `GET /api/agents*` + `POST /api/agents/ask|workflow` (proposals only;
  see `docs/AI-FOUNDRY-AGENTS.md`).
- Login: optional Settings **Company** → `POST /api/login` `company` field;
  list choices from `GET /api/companies`.
- Money docs stay **create-only** by design (AGENTS.md §14).
