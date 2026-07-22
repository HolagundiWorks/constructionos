# Cloud-agent task backlog

**For the cloud/headless agent only** (the "C" track — headless Python:
domain/data/backend, the JSON API, purity, unit tests, docs). **No display, no
.NET/WinUI, no ML model weights.** The local/Windows agent owns the WinUI client
(`winui/`) and anything that needs a display or the .NET SDK — do not touch those.

## Standing rules (every task)
- **Pure Python standard library, no pip** in the domain/backend.
- New business maths → a **pure, tkinter-free module with a unit test**, never in
  a GUI callback. Reuse existing pure modules; don't reimplement money maths.
- **Single SQLite file**; new columns via `db._ADD_COLUMNS`, new tables via
  `db.SCHEMA` (both idempotent). Registers cascade on project delete.
- Every `/api/*` endpoint delegates to a **pure domain module** and serialises —
  **no logic in the transport**. Gate writes with `ui_guard`/CSRF; audit every
  write (`auth.audit`, `origin='ai'` for AI-drafted, `'manual'` otherwise).
- Money-moving automations stay **gated drafts**; a human approves anything that
  moves money or a date. Money docs post **only** via `journal_post.post_all`.
- Verify headless: `python -m unittest discover -s tests` must stay green, and
  `cd construction_app && python -m compileall -q .`. Add tests to
  `tests/test_web.py` (`TestWebApi`, socket-free via `webapp.handle`) or
  `tests/test_core.py` (pure logic). **Say explicitly** what you ran.
- Keep `docs/API.md`, `docs/CHANGELOG.md`, `AGENTS.md`/`CLAUDE.md` in sync in the
  **same commit** as the change they describe.

---

## Tasks (priority order)

### CT-1 — Extract a pure `gst.py` (purity) ✅
**Why:** the GST/TDS compute (`outward` / `inward` / `hsn_summary` /
`tds_register`) currently lives in the **tkinter** module `tab_gst.py`, so the
browser `/gst` route and any future `/api/gst` must lazy-import Tk. Pull the pure
logic out.
**Do:**
- Create `construction_app/gst.py` (tkinter-free) holding `outward(conn, month)`,
  `inward(conn, month)`, `hsn_summary(conn, month)`, `tds_register(conn, month)`
  and their helpers (`_fmt`, `_month_clause`, `_works_gst_pct`). They already only
  use `conn` + `finance` — no Tk.
- `tab_gst.py` imports them from `gst` (keep the `GstTab` GUI there).
- `webapp._gst` imports `gst` instead of `tab_gst` (drop the lazy Tk import).
**Done when:** `tests/test_core.py` has a `TestGst` seeding a tax invoice + a
vendor invoice and asserting outward/inward/HSN/TDS totals; web `/gst` test still
green; no behaviour change (identical figures).
**Status:** shipped — `gst.py` + `TestGst`; browser `/gst` imports `gst`.

### CT-2 — `/api/gst?month=YYYY-MM` (read) ✅
**Why:** the WinUI/mobile clients need the GST/TDS report as JSON (parity with the
browser `/gst` view).
**Do:** add a `GET /api/gst` handler in `webapi.py` returning
`{month, outward:{rows,totals}, hsn:{rows,totals}, inward:{rows,totals},
tds:{rows,total}}` over `gst.py` (CT-1). Session-gated read; no writes.
**Done when:** `TestWebApi` asserts 200 + the four blocks on a seeded month;
`docs/API.md` lists it under Reads.
**Status:** shipped — `GET /api/gst` + tests; API **u0.8**.

### CT-3 — `/api/measurements` CRUD (write) ✅
**Why:** browser measurement entry shipped; the JSON API + WinUI/mobile need the
same. Quantity is derived (`Nos×L×B×D`), a **blank dimension stays NULL**
(factor 1), never 0.
**Do:** `GET /api/measurements?contract_id=` (list), `POST/PUT/DELETE
/api/measurements[/{id}]`. Reuse the derive logic — the cleanest is to move
`web_masters._derive_measurement` (or `civil.measurement_quantity`) so both the
browser register and the API share **one** quantity computation. Role-gated,
CSRF, audited.
**Done when:** `TestWebApi` creates a measurement with a blank breadth and asserts
`quantity` is right (not zeroed) and `breadth` is NULL; delete/update covered;
`docs/API.md` updated.
**Status:** shipped — `measurements` in `_API_MASTERS`; create/update call
`web_masters.derive`.

### CT-4 — Chart-ready shapes for WinUI U4 (read, thin) ✅
**Why:** the WinUI Charts/EVM/Money pages bind LiveCharts series; they render best
from `{labels:[...], values:[...]}` arrays rather than nested records.
**Do:** confirm `GET /api/cashflow`, `/api/ageing`, `/api/evm` each expose (or add
a sibling that exposes) a flat **`labels` + `values`** (or `series`) array
alongside the existing detail — no new maths, just a serialisation shape. Note in
`docs/API.md` which key the client should bind.
**Done when:** `TestWebApi` asserts each endpoint returns parallel `labels`/`values`
arrays of equal length; existing detail keys unchanged.
**Status:** shipped — cashflow `labels`/`values`/`series`; ageing + evm
`labels`/`values`; `chart_bind` on `/api/contract`.

### CT-5 — Coverage + audit sweep ✅
**Why:** keep the governance guarantee ("every write audited") honest as endpoints
grow.
**Do:** a `TestWebApi` test that drives create/update/delete on the new
measurements endpoint (CT-3) and asserts the `api_*` rows appear in
`GET /api/audit`. Sweep every **read** endpoint for a 200 on an empty DB.
**Done when:** the sweep test is green and lists every endpoint it hit.
**Status:** shipped — `test_ct_gst_measurements_chart_shapes_audit`.

---

## Not for the cloud agent (local/Windows only)
WinUI `winui/**` (needs .NET SDK + Windows App SDK), the tkinter GUI smoke tests
(need a display), MSIX packaging, and installing ML sidecar weights. Those are the
local agent's; leave them untouched.
