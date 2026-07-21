# Windows installer

This folder builds a standalone Windows installer for **Construction OS**. The
target machine needs **no Python, no internet, and no admin rights** — the app
is bundled with its own Python runtime and installs per-user.

(Managing the local Ollama server and models is now part of the app itself —
**Assistant › AI Engine** — so there is no longer a separate Ollama Manager to
build.)

## What the end user gets

- A single `ConstructionOS-Setup-1.0.0.exe` (or a portable `.zip`).
- Start-menu and optional desktop shortcuts, and an entry in *Apps & features*
  with a working uninstaller.
- Their data — the SQLite database(s) and the company registry — kept in
  `%LOCALAPPDATA%\Construction OS`, **not** in the install folder. So the app
  works from a read-only Program Files location, and **uninstalling or
  upgrading never deletes their books**. To wipe the data, delete that folder
  by hand.

Run from source is unaffected: `python construction_app/main.py` still keeps
`construction.db` next to the code exactly as before. The data only moves for
an installed (frozen) build — see `construction_app/paths.py`.

## Build it

**Prerequisites** (developer machine only — never shipped to the user):

1. **Python 3.8+** with tkinter (the standard python.org installer includes it).
2. **Inno Setup 6** (free) from <https://jrsoftware.org/isdl.php> — only for the
   full installer. Skip it if you just want the portable zip. `winget install
   JRSoftware.InnoSetup` works; `build.ps1` finds it whether it lands in
   Program Files or the per-user `%LOCALAPPDATA%\Programs`.

PyInstaller is *not* a prerequisite: `build.ps1` installs it into a throwaway
`venv/` here. It is a build tool only; the shipped app stays pure standard
library.

**Full installer:**

```powershell
cd installer
.\build.ps1
# -> installer\output\ConstructionOS-Setup-1.0.0.exe
```

**Portable zip** (no Inno Setup needed — unzip to a normal local folder, *not*
OneDrive, and run the .exe):

```powershell
cd installer
.\build.ps1 -Portable
# -> installer\output\ConstructionOS-portable.zip
```

## Files

| File | Purpose |
|---|---|
| `ConstructionOS.spec` | PyInstaller spec — freezes the app into `dist\`. Lists every flat module explicitly (some tabs are imported lazily) and bundles `resources/`. |
| `ConstructionOS.iss` | Inno Setup script — wraps the frozen folder into a `Setup.exe` with shortcuts, an uninstaller and the AGPL licence page. Per-user install, no admin. |
| `build.ps1` | Freezes and packages the app, with a `-Portable` zip fallback. Deletes the intermediate `build\` dir afterwards. |

`build/`, `dist/`, `venv/` and `output/` are build artifacts and are
git-ignored.

## Notes

- **Version** lives in two places — bump both: `AppVersion` in
  `ConstructionOS.iss` and, if you want it on the frozen exe's file properties,
  the spec. Keep them in step.
- **Icon** is `construction_app/resources/app.ico`, used for the exe, the
  installer and the shortcuts.
- **The optional AI assistant** needs a local Ollama install; the app runs
  fully without it. The installer offers an **unchecked "Set up Ollama for the
  AI assistant (optional)"** task on the final page:
  - if you drop the official `OllamaSetup.exe` into `installer\vendor\` before
    building, it is bundled and run for a fully-offline setup;
  - otherwise the task opens <https://ollama.com/download> so the user fetches
    the current official build.

  We never silently redistribute Ollama (it is a separate product with its own
  licence). In-app, **Assistant › AI Engine** installs Ollama, starts the
  server, and pulls/selects models — and the Ask tab shows a **Get Ollama…**
  button whenever the server is not reachable.
- **Antivirus / SmartScreen**: an unsigned PyInstaller exe may trip Windows
  SmartScreen ("unknown publisher") on first run. Code-signing the exe and the
  installer with an authenticode certificate removes this; it is out of scope
  for this build but the hook is the `SignTool` directive in Inno Setup.
