# CLAUDE.md — memory for Claude Code / Cursor agents

Full guide: **[`AGENTS.md`](AGENTS.md)** (read it before changing code). This file
is the short, always-loaded memory.

## What this is
**ACO** (**Accelerated Construction Operations**, formerly Construction OS) —
a full **ERP for Indian construction contractors**: pure **Python standard
library**, **tkinter** desktop UI, optional **stdlib web/LAN** front-end, a
single **SQLite** file, **no pip dependencies**. Business maths lives in
**~118** AST tkinter-free modules; `tab_*.py` are a thin GUI over them. Brand
mark = existing logo geometry in **Radiant Orange** (`branding.py` /
`tokens` accent `#FF4F18`).

## Hard rules (don't break without explicit instruction)
- **Stdlib only, no pip** in the domain/backend. New business maths → a **pure,
  tkinter-free module with a unit test**, never buried in a GUI callback.
- **Single SQLite file**; schema is one `SCHEMA` string in `db.py` with additive
  `_ADD_COLUMNS` migrations. Registers cascade on project delete.
- **Explainable over clever**: money/schedule/risk figures are deterministic and
  return `None` when undefined (never a fake 0/∞). AI proposes; a human approves
  anything that moves money or a date.
- **Docs map (no duplicates):** living status → `docs/ROADMAP.md` only; history →
  `docs/CHANGELOG.md`; research → `docs/RESEARCH.md` only. Do **not** recreate
  `CLOUD-TASKS`, gap-roadmap, completeness-audit, or split `RESEARCH-*` files.

## Verify your changes
```bash
python -m unittest discover -s tests        # headless suite (pure maths, DB stores, web)
cd construction_app && python -m compileall -q .
```
- The suite is **headless-first**. GUI/`tab_*` import `tkinter`; on a box without
  it (or the stub in AGENTS.md §2), those tests **error on import** — environment
  limit, not a logic failure. **Say so explicitly; never claim you tested a UI
  you couldn't render.**
- Run headless via: `cd construction_app && python web_main.py`.

## Current direction
- **Status board:** [`docs/ROADMAP.md`](docs/ROADMAP.md) — Completed (§1) vs
  Pending P0–P4 (§2). Do not invent a second roadmap.
- **WinUI 3 replatform** (Windows-only, C#/.NET, **stock Fluent only**) — approved
  front-end departure. Python domain + tests stay as **localhost JSON API
  (u0.12)**. Specs: `docs/WINUI3-MIGRATION.md`,
  `docs/UI-PRINCIPLES-AND-GUIDELINES.md`, `.github/instructions/winui3.instructions.md`.
- **Two environments:**
  - **Cloud (this agent):** domain / API / tests / docs. Cloud CT backlog
    **closed** (ROADMAP §1.3). No display, no .NET, no ML weights.
  - **Local (Windows):** WinUI workflow depth (ROADMAP §2), MSIX release
    signing, sidecars/weights, tkinter smoke.

## Watch out
- **Flat ~181-module namespace** — `lessons.py` (rate realisation) ≠
  `lessons_register.py` / `tab_lessons_learned.py`. Grep before adding a module.
- Catalog: **8 sections / 52 modules**; API **u0.12**. Headline counts (verify
  before quoting): **181** modules / **118** AST-pure / **85** tables / **61**
  indexes / **738** tests (5 skipped headless).
- Keep this file and `AGENTS.md` accurate in the **same commit** as the change
  they describe.

## Key docs
| Role | Path |
|---|---|
| Status | `docs/ROADMAP.md` |
| History | `docs/CHANGELOG.md` |
| Research (single) | `docs/RESEARCH.md` |
| Product / brand | `docs/PRODUCT.md`, `docs/BRAND.md` |
| Architecture | `docs/APP-ARCHITECTURE.md`, `AGENTS.md` |
| API | `docs/API.md` |
| WinUI | `docs/WINUI3-MIGRATION.md`, `docs/UI-PRINCIPLES-AND-GUIDELINES.md` |
| Enterprise PM design | `docs/ENTERPRISE-PM-SOLUTION.md`, `docs/EXECUTION-PART2.md` |
| AI design | `docs/AI-DRAWING-TAKEOFF.md`, `docs/AI-MODELS-AND-DEPLOYMENT.md` |
| LAN / SOPs / tests | `docs/LAN.md`, `docs/SOP-manual.md`, `docs/TEST_PLAN.md` |
