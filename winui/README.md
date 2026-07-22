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
| `Views/RisksPage.*` | Risk register (stock `ListView`) |
| `Views/MastersPage.*` | **U2** — generic CRUD register for every master (sites, clients, …), list + form built from the API's field metadata |
| `Views/OpportunitiesPage.*` | Opportunity register |
| `Views/LessonsPage.*` | Lessons Learned register |
| `Views/SubmittalsPage.*` | Submittals |
| `Views/MoneyPage.*` | Payments list (U3) |
| `Views/EvmPage.*` | Earned Value |
| `Views/PortfolioPage.*` | Portfolio roll-up |
| `Views/ProductivityPage.*` | Productivity ratios |
| `Views/ChartsPage.*` | LiveCharts KPI scaffold (U4) |
| `Views/ProcessPage.*` | Workflow "what's next" |
| `Views/CapturePage.*` · `Views/ImportPage.*` | Field capture / GRN-BOQ import (sidecar-assisted) |
| [`PACKAGING.md`](PACKAGING.md) | MSIX + PyInstaller sidecar notes (U6) |

## Hardened client behaviour
- Timeouts + status/body on API errors (plain-language, no stack dumps).
- List pages share `PageLoad` / `JsonRows` (status line + empty/error states).
- Settings gear works offline enough to edit the base URL and Test health.
- Capture page probes OCR/STT/VLM kinds against `/api/sidecar/*`.

## U2 — generic masters CRUD
`MastersPage` is navigated to with a table name (e.g. `"sites"`); it calls
`GET /api/{table}`, builds the list (stock **`ListView`** — the CommunityToolkit
DataGrid was dropped as it's UWP/WinUI-2 and crashes WinUI 3) and the add/edit
`ContentDialog` from the returned `fields` metadata, and writes via
`POST/PUT/DELETE /api/{table}` (CSRF header, Viewer→403 surfaced in an `InfoBar`).
One page replaces the tkinter `CrudFrame` for all ten masters — no per-master
XAML. The rail routes any master tab to it via `MainWindow.MasterTables`. Known
refinement: foreign-key fields are entered by id for now; a picker (a `ComboBox`
from the related master) is next.

## Next (local Windows)
FK pickers on `MastersPage` · bind LiveCharts series · U6 packaging project
(MSIX + PyInstaller sidecar) · retire tkinter-on-Windows when parity is enough.
