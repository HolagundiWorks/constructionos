# Windows installers

This folder builds standalone Windows installers for **two** apps — the main
**Construction OS**, and its optional companion the **Ollama Manager** (which
installs/runs Ollama and picks the model the AI assistant uses). Each is a
separate installer, because a contractor who does not want the assistant never
needs the manager. The target machine needs **no Python, no internet, and no
admin rights** — each app is bundled with its own Python runtime and installs
per-user.

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
   full installer. Skip it if you just want the portable zip.

PyInstaller is *not* a prerequisite: `build.ps1` installs it into a throwaway
`venv/` here. It is a build tool only; the shipped app stays pure standard
library.

**Full installers (both apps):**

```powershell
cd installer
.\build.ps1
# -> installer\output\ConstructionOS-Setup-1.0.0.exe
#    installer\output\OllamaManager-Setup-1.0.0.exe
```

**Portable zips** (no Inno Setup needed — unzip anywhere and run the .exe):

```powershell
cd installer
.\build.ps1 -Portable
# -> installer\output\ConstructionOS-portable.zip
#    installer\output\OllamaManager-portable.zip
```

**Just one app:**

```powershell
.\build.ps1 -App "Construction OS"      # or "Ollama Manager"
```

## Files

| File | Purpose |
|---|---|
| `ConstructionOS.spec` / `OllamaManager.spec` | PyInstaller specs — freeze each app into `dist\`. Each collects its flat modules (some Construction OS tabs are imported lazily); Construction OS also bundles `resources/`. |
| `ConstructionOS.iss` / `OllamaManager.iss` | Inno Setup scripts — wrap each frozen folder into a `Setup.exe` with shortcuts and an uninstaller. Per-user install, no admin. |
| `build.ps1` | Freezes and packages both apps, with a `-Portable` zip fallback and an `-App` switch to build just one. |

`build/`, `dist/`, `venv/` and `output/` are build artifacts and are
git-ignored.

## Notes

- **Version** lives in two places — bump both: `AppVersion` in
  `ConstructionOS.iss` and, if you want it on the frozen exe's file
  properties, the spec. Keep them in step.
- **Icon** is `construction_app/resources/app.ico`, used for the exe, the
  installer and the shortcuts.
- **The optional AI assistant** needs a separate local Ollama install; the app
  runs fully without it. Ollama is not bundled — see the `ollama_manager`
  helper app in the repo, which is packaged separately if wanted.
- **Antivirus / SmartScreen**: an unsigned PyInstaller exe may trip Windows
  SmartScreen ("unknown publisher") on first run. Code-signing the exe and the
  installer with an authenticode certificate removes this; it is out of scope
  for this build but the hook is the `SignTool` directive in Inno Setup.
