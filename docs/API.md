# Construction OS — JSON API contract (U0)

Localhost backend for the WinUI 3 client and future mobile. Stdlib Python;
routed under `/api/*` by `webapp` → `webapi`. Socket-free unit tests in
`tests/test_web.py` (`TestWebApi`).

**Base URL (dev):** `http://127.0.0.1:8080`  
**Version:** `u0.1` (`GET /api/health` → `{"api":"u0.1"}`)  
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
| GET | `/api/health` | Public after… actually needs auth except login |
| GET | `/api/contract` | Endpoint catalogue for clients |
| GET | `/api/dashboard`, `/api/kpi` | Snapshot + advisories |
| GET | `/api/review` | Weekly review pack |
| GET | `/api/portfolio` | Current-file roll-up; `?paths=a.db,b.db` federates |
| GET | `/api/menu?persona=Owner` | Sections/tabs for NavigationView |
| GET | `/api/workflow?infer=1` | Flow graphs + progress (book-inferred by default) |
| GET | `/api/search?q=` | Command-palette hits over the catalog |
| GET | `/api/evm`, `/api/project/{id}/evm` | Earned value |
| GET | `/api/risks`, `/api/opportunities`, `/api/lessons`, `/api/submittals` | Registers |
| GET | `/api/audit?origin=ai` | Audit trail |
| GET | `/api/{master}` | sites, clients, vendors, materials, labor, equipment, projects, milestones, thekedars, rate_book |
| GET | `/api/{doc}` | payments, tax_invoices, vendor_invoices, bills, ra_bills |

## Writes
| Method | Path | Notes |
|---|---|---|
| POST/PUT/DELETE | `/api/risks[/{id}]` etc. | Registers + masters |
| POST | `/api/{doc}` | Money docs — **create only**; payments may return gated `followups` |
| POST | `/api/capture/draft` | Stage extraction for human review |
| POST | `/api/capture/confirm` | Confirm → `work_done_entries` (never without confirm) |
| POST | `/api/events` | `{event, payload?, include_detect?, apply_risks?}` |
| POST | `/api/signals/feed` | Prediction → AI risk drafts |
| POST | `/api/forecast` | `{series, periods_ahead?}` or `{baseline_duration, spi}` |
| POST | `/api/drift` | Soft-signal dict → drift assessment |

## Rules
- No business maths in the transport — domain modules compute; API serialises.
- AI drafts audit with `origin=ai`; human writes `origin=manual`.
- Money/date-moving automations stay **gated** drafts (`event_hooks` / `followups`).

See also: [`WINUI3-MIGRATION.md`](WINUI3-MIGRATION.md), [`winui/README.md`](../winui/README.md).
