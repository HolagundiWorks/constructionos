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
- ✅ **PyInstaller sidecar (step 2) — done.** `winui/build-sidecar.ps1` freezes
  `web_main.py` → a standalone `ACO.Backend.exe` (onefile, ~9 MB, headless — no
  tkinter, no Python install needed) and drops it in the app's `Backend\`.
  Throwaway venv at a short path (OneDrive paths blow past MAX_PATH); drops the
  `hook-workflow.py` that collides with our `workflow.py`. **Verified end-to-end:**
  killed the Python backend → the app launched the bundled `ACO.Backend.exe`
  (backend process = `ACO.Backend`, not python) and loaded.
- ✅ **Packaging (step 3) + signing (step 6) — done, headless.**
  `winui/build-msix.ps1` builds a signed MSIX **without Visual Studio**: it
  generates the visual assets from `construction_app/resources/logo_*.png`,
  publishes the self-contained Release app, bundles `Backend\ACO.Backend.exe`,
  materialises a concrete `AppxManifest.xml` from the checked-in scaffold
  (resolving the `.wapproj` `$targetnametoken$` / `$targetentrypoint$` tokens),
  packs with `makeappx.exe`, and signs with `signtool.exe` using a self-signed
  code-signing cert whose subject matches the manifest `Publisher`. Output +
  exported public `.cer` land in `%LOCALAPPDATA%\ConstructionOS-build\msix`.
  **Verified:** produces a ~77 MB signed `ACO_1.0.0.0_x64.msix`
  (`CN=Human Centric Works`).

  ```powershell
  pwsh winui/build-sidecar.ps1   # once, to freeze ACO.Backend.exe
  pwsh winui/build-msix.ps1      # -> signed MSIX + dev .cer
  ```

  **Install the dev build** (trust the self-signed cert once — needs admin):
  ```powershell
  Import-Certificate -FilePath <..>\ACO-dev-cert.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople
  Add-AppxPackage      <..>\ACO_1.0.0.0_x64.msix
  ```
  For **release**, sign with a real code-signing cert instead (re-run with
  `-CertSubject` matching your cert, or re-sign the produced `.msix`). Building
  the `.wapproj` in VS 2022 remains a supported alternative (see
  `ConstructionOS.Package/README.md`).

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
