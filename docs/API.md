# Construction OS — JSON API contract (U0)

Localhost backend for the WinUI 3 client and future mobile. Stdlib Python;
routed under `/api/*` by `webapp` → `webapi`. Socket-free unit tests in
`tests/test_web.py` (`TestWebApi`).

**Base URL (dev):** `http://127.0.0.1:8080`  
**Version:** `u0.7` (`GET /api/health` → `{"api":"u0.7"}`)  
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
| GET | `/api/health` | Auth except login; reports `api: u0.7` |
| GET | `/api/contract` | Endpoint catalogue for clients |
| GET | `/api/dashboard`, `/api/kpi` | Snapshot + advisories |
| GET | `/api/review` | Weekly review pack |
| GET | `/api/portfolio` | Current-file roll-up; `?paths=` federates; includes advisories |
| GET | `/api/menu?persona=Owner` | Sections/tabs for NavigationView |
| GET | `/api/productivity` | Crew/plant utilisation from muster + plant logs |
| GET | `/api/filings/feed` | Overdue/due-soon → gated FILING_DUE drafts |
| GET | `/api/purchase_orders`, `/api/goods_receipts` | Procurement lists |
| GET | `/api/match?tolerance=` | Three-way match + narration |
| GET | `/api/ageing` | Receivables ageing + plottable `buckets` |
| GET | `/api/cashflow?periods=&mode=week\|month` | Forecast buckets (`cashflow_assemble`) |
| GET | `/api/bills/previous?contract_id=` | Approved/Paid running-bill sum |
| GET | `/api/boq_items?contract_id=` | BOQ lines for a contract |
| GET | `/api/allocations?payment_id=` | Payment↔bill allocation lines |
| GET | `/api/workflow?infer=1` | Flow graphs + progress (book-inferred by default) |
| GET | `/api/search?q=` | Tabs + records with `nav`/`tag` for WinUI |
| GET | `/api/narrative?kind=kpi\|risk` | Plain-language briefing (`narrative.py`) |
| GET | `/api/sidecar/status` | OCR/STT/VLM stub + live probe |
| GET | `/api/evm`, `/api/project/{id}/evm` | Earned value |
| GET | `/api/risks`, `/api/opportunities`, `/api/lessons`, `/api/submittals` | Registers |
| GET | `/api/audit?origin=ai` | Audit trail (`manual` includes legacy NULL) |
| GET | `/api/{master}` | includes **contracts**; FK fields carry resolved `options:[{id,label}]` |
| GET | `/api/{doc}` | payments, tax_invoices, vendor_invoices, bills, ra_bills (+ FK options) |

## Writes
| Method | Path | Notes |
|---|---|---|
| POST/PUT/DELETE | `/api/risks[/{id}]` etc. | Registers + masters (incl. contracts) |
| POST | `/api/{doc}` | Money docs — **create only**; payments may return gated `followups` |
| POST | `/api/purchase_orders` | Header + `items[]`; `total_amount` = sum of line amounts |
| POST | `/api/allocations` | Replace lines for a payment (`payment_id`, `lines`) |
| POST | `/api/capture/draft` | Stage extraction for human review |
| POST | `/api/capture/confirm` | Confirm → `work_done` / `daily_progress` / `ncr` / `snag` |
| POST | `/api/text/extract` | Free-text → draft fields (`text_extract`) |
| POST | `/api/muster/draft` | Name list → labour match drafts |
| POST | `/api/muster/confirm` | Write attendance rows |
| POST | `/api/boq/import/draft` | CSV/TSV/plain → BOQ line drafts |
| POST | `/api/boq/import/confirm` | Write `boq_items` for a contract |
| POST | `/api/grn/draft` \| `/api/grn/confirm` | Challan paste → Draft GRN (no stock post) |
| POST | `/api/vendor_invoice/draft` \| `confirm` | Invoice paste → vendor invoice |
| POST | `/api/pdf/extract` | Soft-fail `pdftotext` |
| POST | `/api/patterns/learn`, `/api/signals/*`, `/api/intent`, `/api/sidecar/extract` | AI floors — drafts only |
| POST | `/api/events`, `/api/signals/feed`, `/api/forecast`, `/api/drift` | Hooks / prediction |

## Notes for WinUI
- Master/doc list payloads include **resolved FK `options`** — do not run `fk_sql` in C#.
- Search record hits include `nav` / `tag` (`Section/Tab`) for `NavigationView` routing.
- Charts: bind LiveCharts to `/api/cashflow` buckets and `/api/ageing` buckets (no maths in C#).
- Money docs stay **create-only** by design (AGENTS.md §14).
