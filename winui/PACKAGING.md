# Construction OS — MSIX packaging scaffold (U6)

Windows-only. This folder documents how to wrap the WinUI client + Python
localhost sidecar into a signed MSIX. **It does not build on Linux.**

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
   pointed at `http://127.0.0.1:8080`.
5. Sign the MSIX with your cert; distribute via sideload or Store.

## Constraints

- Backend listens on **localhost only** in packaged builds.
- No business maths in C# — call `/api/*`.
- Persona menus come from `GET /api/menu?persona=…`.
