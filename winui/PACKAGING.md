# ACO — MSIX packaging scaffold (U6)

Windows-only. This folder documents how to wrap the WinUI client + Python
localhost sidecar into a signed MSIX. **It does not build on Linux.**

## Status
- ✅ **Backend auto-launch (step 4) — done.** `Services/BackendLauncher.cs` starts
  the localhost backend before the shell loads if it isn't already up: a bundled
  sidecar `Backend\ACO.Backend.exe` next to the app (packaged), else the dev
  command from Settings (`Auto-start the local backend` toggle + a python path +
  the `construction_app` working dir). No-op if the port is already listening or
  the API is remote. Verified in a dev run (killed the backend → the app started
  it and loaded).
- ⏳ **PyInstaller sidecar (step 2)** — build `web_main.py` → `ACO.Backend.exe`
  via `installer/build.ps1`, drop it under the package's `Backend\`.
- ⏳ **Packaging project (step 3)** + signing (steps 6) — add in VS 2022.

## Intended layout (local Windows)

```
winui/
  ConstructionOS.WinUI/          # Fluent client (this repo)
  ConstructionOS.Package/        # Optional Windows Application Packaging Project
                                 # (add in VS 2022: File → New → Packaging Project)
```

## Steps on a Windows box

1. Build `ConstructionOS.WinUI` (x64 Release).
2. Build the Python backend sidecar with the existing
   `installer/build.ps1` / PyInstaller throwaway venv so `web_main.py` ships
   as a localhost-only helper (127.0.0.1).
3. Add a **Windows Application Packaging Project** that references the WinUI
   app; include the sidecar binaries under `Backend\`.
4. App startup: launch sidecar if port 8080 is free, then open the WinUI shell
   pointed at `http://127.0.0.1:8080` (overridable via Settings /
   `winui-settings.json`).
5. Optional model sidecars: ship `sidecars/stub_server.py` for soft-fail, or
   real OCR/STT/VLM binaries under `sidecars/{ocr,stt,vlm}/` (weights local-only).
6. Sign the MSIX with your cert; distribute via sideload or Store.

## Constraints

- Backend listens on **localhost only** in packaged builds.
- No business maths in C# — call `/api/*`.
- Persona menus come from `GET /api/menu?persona=…`.
- Client settings file:
  `%LOCALAPPDATA%\Construction OS\winui-settings.json`.
