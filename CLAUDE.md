# CLAUDE.md — memory for Claude Code

Full guide: **[`AGENTS.md`](AGENTS.md)** (read it before changing code). This file
is the short, always-loaded memory.

## What this is
**ACO** (**Accelerated Construction Operations**, formerly Construction OS) —
a full **ERP for Indian construction contractors**: pure **Python standard
library**, **tkinter** desktop UI, optional **stdlib web/LAN** front-end, a
single **SQLite** file, **no pip dependencies**. Business maths lives in ~99
**pure, tkinter-free modules**; `tab_*.py` are a thin GUI over them. Brand
mark = existing logo geometry in **Radiant Orange** (`branding.py` /
`tokens` accent).

## Hard rules (don't break without explicit instruction)
- **Stdlib only, no pip** in the domain/backend. New business maths → a **pure,
  tkinter-free module with a unit test**, never buried in a GUI callback.
- **Single SQLite file**; schema is one `SCHEMA` string in `db.py` with additive
  `_ADD_COLUMNS` migrations. Registers cascade on project delete.
- **Explainable over clever**: money/schedule/risk figures are deterministic and
  return `None` when undefined (never a fake 0/∞). AI proposes; a human approves
  anything that moves money or a date.

## Verify your changes
```bash
python -m unittest discover -s tests        # headless suite (pure maths, DB stores, web)
cd construction_app && python -m compileall -q .
```
- The suite is **headless-first**. GUI/`tab_*` and some newer tabs import
  `tkinter`; on a box without it (or the stub in AGENTS.md §2), those tests
  **error on import** — that is an environment limit, not a logic failure. **Say
  so explicitly; never claim you tested a UI you couldn't render.**
- Run the app headless via the web server: `cd construction_app && python web_main.py`.

## Current direction (in progress)
- **Single status board:** [`docs/ROADMAP.md`](docs/ROADMAP.md) — completed vs
  pending (P0–P4). History: [`docs/CHANGELOG.md`](docs/CHANGELOG.md).
- **UI replatform to native WinUI 3** (Windows-only, C#/.NET, **stock Fluent
  components only, no custom items**) — an *owner-approved* departure from the
  tkinter/cross-platform/no-pip constraints **for the front-end only**. The
  **Python domain core + tests stay** and are reused as a **localhost backend
  service** (JSON API **u0.12**). Spec:
  [`docs/WINUI3-MIGRATION.md`](docs/WINUI3-MIGRATION.md).
- **Two development environments:**
  - **Cloud (this agent, headless Python):** domain/API/tests/docs. Cloud CT
    backlog is **closed** (ROADMAP §1.3). **No display, no .NET, no ML.**
  - **Local (Windows + display + .NET):** WinUI workflow depth (ROADMAP §2),
    MSIX release signing, sidecars/weights, tkinter smoke.

## Watch out
- **Flat 159-module namespace** invites filename collisions — `lessons.py`
  (rate realisation), `lessons_register.py` / `tab_lessons_learned.py` (lessons-
  learned register) are different features; don't merge them. Check for an
  existing module before adding one.
- Keep this file and `AGENTS.md` accurate: if you change something they describe,
  update them in the same commit. Catalog is **8 sections / 52 modules** (incl.
  Controls + Productivity); API version **u0.12** (`/api/firm` + `/api/modules`
  for Tools; `/api/assistant[/quick]` for the Assistant page). Cloud track (deterministic
  floors + JSON API) is complete; remaining roadmap work is local/Windows.

## Key docs
**Status (done vs pending):** `docs/ROADMAP.md` · History: `docs/CHANGELOG.md` ·
Architecture & menu/workflow: `docs/APP-ARCHITECTURE.md` · Enterprise AI PM
design: `docs/ENTERPRISE-PM-SOLUTION.md` · Execution (risk/opportunity/KPIs):
`docs/EXECUTION-PART2.md` · AI: `docs/AI-DRAWING-TAKEOFF.md`,
`docs/AI-MODELS-AND-DEPLOYMENT.md` · UI replatform: `docs/WINUI3-MIGRATION.md` ·
UI principles (Fluent / WinUI): `docs/UI-PRINCIPLES-AND-GUIDELINES.md` · WinUI 3
coding standard: `.github/instructions/winui3.instructions.md` · Product:
`docs/PRODUCT.md` · Brand: `docs/BRAND.md` · Research (not status):
`docs/RESEARCH-UI-FLUENT-DEEP-DIVE.md`, `docs/RESEARCH-COMPETITIVE-CASE-STUDY.md`.
