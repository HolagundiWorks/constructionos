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
- **UI replatform to native WinUI 3** (Windows-only, C#/.NET, **stock Fluent
  components only, no custom items**) — an *owner-approved* departure from the
  tkinter/cross-platform/no-pip constraints **for the front-end only**. The
  **Python domain core + tests stay** and are reused as a **localhost backend
  service** (a JSON API the WinUI 3 client calls). Spec:
  [`docs/WINUI3-MIGRATION.md`](docs/WINUI3-MIGRATION.md).
- **Two development environments** — the actionable split lives in
  [`docs/ENTERPRISE-PM-GAP-AND-ROADMAP.md`](docs/ENTERPRISE-PM-GAP-AND-ROADMAP.md)
  §5A / §5B:
  - **Cloud (this agent, headless Python):** domain/data/backend, JSON API
    (**U0 `webapi.py` — built**), purity fixes, signal feed / event hooks /
    audit origin (C3–C6), unit tests, docs. **No display, no .NET, no ML
    models.**
  - **Local (Windows + display + .NET):** residual tkinter Controls / Process /
    persona **shipped** (smoke on a display still L0); WinUI 3 client scaffolds
    (**U1–U6** — build/run/MSIX on Windows); model sidecars under `sidecars/`
    (install weights locally). Field capture: browser `/m/capture`.

## Watch out
- **Flat 159-module namespace** invites filename collisions — `lessons.py`
  (rate realisation), `lessons_register.py` / `tab_lessons_learned.py` (lessons-
  learned register) are different features; don't merge them. Check for an
  existing module before adding one.
- Keep this file and `AGENTS.md` accurate: if you change something they describe,
  update them in the same commit. Catalog is **8 sections / 52 modules** (incl.
  Controls + Productivity); API version **u0.6**. Cloud track (deterministic
  floors + JSON API) is complete; remaining roadmap work is local/Windows.

## Key docs
Architecture & menu/workflow: `docs/APP-ARCHITECTURE.md` · Enterprise AI PM +
roadmap: `docs/ENTERPRISE-PM-SOLUTION.md`, `docs/ENTERPRISE-PM-GAP-AND-ROADMAP.md`
· Execution (risk/opportunity/KPIs): `docs/EXECUTION-PART2.md` · AI:
`docs/AI-DRAWING-TAKEOFF.md`, `docs/AI-MODELS-AND-DEPLOYMENT.md` · UI replatform:
`docs/WINUI3-MIGRATION.md` · UI principles (Fluent / WinUI):
`docs/UI-PRINCIPLES-AND-GUIDELINES.md` · Product & scope: `docs/PRODUCT.md`.
