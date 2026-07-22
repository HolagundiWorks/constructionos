# Construction OS — JSON API contract (U0)

Localhost backend for the WinUI 3 client and future mobile. Stdlib Python;
routed under `/api/*` by `webapp` → `webapi`. Socket-free unit tests in
`tests/test_web.py` (`TestWebApi`).

**Base URL (dev):** `http://127.0.0.1:8080`  
**Version:** `u0.5` (`GET /api/health` → `{"api":"u0.5"}`)  
**Live map:** `GET /api/contract` (authenticated)

## Auth
| Step | Call |
|---|---|
| Login / first-run admin | `POST /api/login` `{"username","password"}` → sets `cosid` cookie, returns `{csrf, role, can_write}` |
| Session | `GET /api/me` |
| Writes | Header `X-CSRF-Token: <csrf>` (or body/`form` `csrf`) · Viewers → 403 |

## Reads
| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | Auth except login; reports `api: u0.5` |
| GET | `/api/contract` | Endpoint catalogue for clients |
| GET | `/api/dashboard`, `/api/kpi` | Snapshot + advisories |
| GET | `/api/review` | Weekly review pack |
| GET | `/api/portfolio` | Current-file roll-up; `?paths=` federates; includes advisories |
| GET | `/api/menu?persona=Owner` | Sections/tabs for NavigationView |
| GET | `/api/productivity` | Crew/plant utilisation from muster + plant logs |
| GET | `/api/filings/feed` | Overdue/due-soon → gated FILING_DUE drafts |
| GET | `/api/purchase_orders`, `/api/goods_receipts` | Procurement lists |
| GET | `/api/match?tolerance=` | Three-way match + narration |
| GET | `/api/ageing` | Receivables ageing buckets |
| GET | `/api/workflow?infer=1` | Flow graphs + progress (book-inferred by default) |
| GET | `/api/search?q=` | Tabs + records (N4) |
| GET | `/api/narrative?kind=kpi\|risk` | Plain-language briefing (`narrative.py`) |
| GET | `/api/sidecar/status` | OCR/STT/VLM stub + live probe |
| GET | `/api/evm`, `/api/project/{id}/evm` | Earned value |
| GET | `/api/risks`, `/api/opportunities`, `/api/lessons`, `/api/submittals` | Registers |
| GET | `/api/audit?origin=ai` | Audit trail (`manual` includes legacy NULL) |
| GET | `/api/{master}` | sites, clients, vendors, materials, labor, equipment, projects, milestones, thekedars, rate_book |
| GET | `/api/{doc}` | payments, tax_invoices, vendor_invoices, bills, ra_bills |

## Writes
| Method | Path | Notes |
|---|---|---|
| POST/PUT/DELETE | `/api/risks[/{id}]` etc. | Registers + masters |
| POST | `/api/{doc}` | Money docs — **create only**; payments may return gated `followups` |
| POST | `/api/capture/draft` | Stage extraction for human review |
| POST | `/api/capture/confirm` | Confirm → `work_done` / `daily_progress` / `ncr` / `snag` |
| POST | `/api/text/extract` | Free-text → draft fields (`text_extract`) |
| POST | `/api/muster/draft` | Name list → labour match drafts |
| POST | `/api/muster/confirm` | Write attendance marks |
| POST | `/api/boq/import/draft` | CSV/TSV/plain → BOQ line drafts |
| POST | `/api/boq/import/confirm` | Write `boq_items` for a contract |
| POST | `/api/grn/draft` | Challan paste → matched GRN line drafts |
| POST | `/api/patterns/learn` | Preview/apply cross-lesson AI drafts |
| POST | `/api/signals/preview` | Forecast/drift drafts without writing |
| POST | `/api/signals/suggest` | Soft signals from live book → drafts (`apply?`) |
| POST | `/api/sidecar/extract` | `{kind: ocr\|stt\|vlm, payload?}` → capture draft (soft-fail `ok:false`) |
| POST | `/api/intent` | `{text}` → gated follow-up / workflow drafts (`nl_intent`) |
| POST | `/api/reconcile` | `{po_subtotal, invoice_subtotal, tolerance?}` + narration |
| POST | `/api/events` | `{event, payload?, include_detect?, apply_risks?}` |
| POST | `/api/signals/feed` | Prediction → AI risk drafts |
| POST | `/api/forecast` | `{series, periods_ahead?}` or `{baseline_duration, spi}` |
| POST | `/api/drift` | Soft-signal dict → drift assessment |

## Rules
- No business maths in the transport — domain modules compute; API serialises.
- AI drafts audit with `origin=ai`; human writes `origin=manual`.
- Money/date-moving automations stay **gated** drafts (`event_hooks` / `followups`).
- Sidecars bind **loopback only**; missing models degrade to empty drafts.

See also: [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md), [`winui/README.md`](../winui/README.md),
[`CONCURRENCY.md`](CONCURRENCY.md).
