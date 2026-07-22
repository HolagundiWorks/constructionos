# Construction OS — WinUI 3 client (hardened U1 scaffold)

Windows-only Fluent UI over the Python localhost JSON API (`webapi.py`).

**This folder does not compile on Linux.** Open it on a Windows 11 (or 10 1809+)
box with Visual Studio 2022 + Windows App SDK. Spec:
[`docs/WINUI3-MIGRATION.md`](../docs/WINUI3-MIGRATION.md).

## Prerequisites
- Visual Studio 2022 with **.NET Desktop Development** + WinUI / Windows App SDK
- .NET 8 SDK
- Python 3.8+ for the backend

## First run
1. Backend (repo root):
   ```bash
   cd construction_app
   python web_main.py --host 127.0.0.1 --port 8080
   ```
2. Optional sidecar soft-fail stubs (no model weights):
   ```bash
   python sidecars/stub_server.py --kind ocr
   python sidecars/health_check.py
   ```
3. Verify contract: `GET http://127.0.0.1:8080/api/health` or
   `python -m unittest discover -s tests`.
4. Open `winui/ConstructionOS.WinUI/ConstructionOS.WinUI.csproj` in VS 2022,
   restore NuGet, build (x64), run.
5. On first launch the client loads
   `%LOCALAPPDATA%\Construction OS\winui-settings.json` (defaults if missing),
   calls `POST /api/login`, builds the `NavigationView` from
   `GET /api/menu?persona=…`, and probes `GET /api/health`. Use the **Settings**
   gear to change URL / user / persona and reconnect.

## Layout
| Path | Role |
|---|---|
| `MainWindow.*` | NavigationView shell + typed `NavRoute` |
| `Services/ApiClient.cs` | Cookie + CSRF client; Put/Delete; `ApiException` |
| `Services/AppSettings.cs` | Persisted base URL / login / persona / timeout |
| `Helpers/` | `JsonRows`, `PageLoad`, `NavRoute` |
| `Views/SettingsPage.*` | Connection settings (gear) |
| `Views/HomePage.*` | Dashboard / advisories |
| `Views/*Page.*` | Registers, money, EVM, portfolio, process, charts, capture, import |
| [`PACKAGING.md`](PACKAGING.md) | MSIX + PyInstaller sidecar notes (U6) |

## Hardened client behaviour
- Timeouts + status/body on API errors (plain-language, no stack dumps).
- List pages share `PageLoad` / `JsonRows` (status line + empty/error states).
- Settings gear works offline enough to edit the base URL and Test health.
- Capture page probes OCR/STT/VLM kinds against `/api/sidecar/*`.

## Next (local Windows)
Build/run against `web_main.py` · bind LiveCharts series · packaging project ·
retire tkinter-on-Windows when parity is enough. **Cannot be compiled in this
cloud environment.**
