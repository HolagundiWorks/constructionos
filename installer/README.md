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

**Inbuilt offline AI (optional, ~1.7 GB installer):** fetch the AI payload once,
then build as usual. `build.ps1` prints `Inbuilt AI : YES` when it finds the
payload and bundles it; without it you simply get a lean installer where the
assistant pulls a model on first use.

```powershell
cd installer
.\fetch_payload.ps1   # downloads OllamaSetup.exe + qwen2.5-coder-1.5b …q4_k_m.gguf
.\build.ps1           # -> ~1.7 GB Setup.exe carrying the offline AI engine
```

The installer then installs Ollama silently (when the *AI assistant* task stays
ticked) and lays the model beside the app; the app finishes a one-time offline
`ollama create` on first launch (**Assistant › AI Engine › Set up inbuilt
model**), after which the assistant works with no internet at all.

## Files

| File | Purpose |
|---|---|
| `ConstructionOS.spec` | PyInstaller spec — freezes the app into `dist\`. Lists every flat module explicitly (some tabs are imported lazily) and bundles `resources/`. |
| `ConstructionOS.iss` | Inno Setup script — wraps the frozen folder into a `Setup.exe` with shortcuts, an uninstaller and the AGPL licence page. Per-user install, no admin. |
| `build.ps1` | Freezes and packages the app, with a `-Portable` zip fallback. Deletes the intermediate `build\` dir afterwards. Reports whether the inbuilt-AI payload was bundled. |
| `fetch_payload.ps1` | Downloads the optional inbuilt-AI payload — Ollama's installer into `vendor\` and the model GGUF into `ai\`. Run once before `build.ps1` for an offline-AI installer. |
| `ai\Modelfile` | Ollama Modelfile that registers the bundled GGUF offline (`ollama create qwen2.5-coder:1.5b -f Modelfile`). Tracked in git; the GGUF it points at is fetched, not committed. |

`build/`, `dist/`, `venv/` and `output/` are build artifacts and are
git-ignored — as are the fetched `ai\*.gguf` and `vendor\` payload (large
binaries never belong in the repo).

## Notes

- **Version** lives in two places — bump both: `AppVersion` in
  `ConstructionOS.iss` and, if you want it on the frozen exe's file properties,
  the spec. Keep them in step.
- **Icon** is `construction_app/resources/app.ico`, used for the exe, the
  installer and the shortcuts.
- **The optional AI assistant** needs a local Ollama install; the app runs
  fully without it. The installer has a **"Set up the offline AI assistant
  (Ollama + inbuilt model)"** task, ticked by default:
  - if you ran `fetch_payload.ps1` first, `vendor\OllamaSetup.exe` is installed
    **silently during setup** and the model GGUF is laid down beside the app,
    for a fully-offline assistant (the one-time `ollama create` finishes on
    first launch);
  - if you did **not** bundle the payload, the task instead opens
    <https://ollama.com/download> so the user fetches the current build, then
    pulls a model from inside the app.

  Ollama (MIT) and Qwen2.5-Coder (Apache-2.0) are both permissively licensed, so
  shipping their official artefacts is fine. In-app, **Assistant › AI Engine**
  installs Ollama, starts the server, sets up the inbuilt model, and
  pulls/selects models — and the Ask tab shows a **Get Ollama…** button whenever
  the server is not reachable.
- **Antivirus / SmartScreen**: an unsigned PyInstaller exe may trip Windows
  SmartScreen ("unknown publisher") on first run. Code-signing the exe and the
  installer with an authenticode certificate removes this; it is out of scope
  for this build but the hook is the `SignTool` directive in Inno Setup.
