# Construction OS — WinUI 3 client (U1 scaffold)

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
2. Verify contract: `GET http://127.0.0.1:8080/api/contract` (after login) or
   run `python -m unittest discover -s tests`.
3. Open `winui/ConstructionOS.WinUI/ConstructionOS.WinUI.csproj` in VS 2022,
   restore NuGet, build (x64), run.
4. On first launch the client calls `POST /api/login` (default `admin` /
   `BuildSite#2026` — change for real deployments) and builds the
   `NavigationView` from `GET /api/menu?persona=Owner`.

## Layout
| Path | Role |
|---|---|
| `MainWindow.*` | NavigationView shell (U1) |
| `Services/ApiClient.cs` | Cookie + CSRF HttpClient over `/api/*` |
| `Views/HomePage.*` | Dashboard / advisories |
| `Views/RisksPage.*` | Risk register DataGrid |
| `Views/OpportunitiesPage.*` | Opportunity register |
| `Views/LessonsPage.*` | Lessons Learned register |
| `Views/SubmittalsPage.*` | Submittals |
| `Views/MoneyPage.*` | Payments list (U3) |
| `Views/EvmPage.*` | Earned Value |
| `Views/ChartsPage.*` | LiveCharts KPI scaffold (U4) |
| `Views/ProcessPage.*` | Workflow "what's next" |
| [`PACKAGING.md`](PACKAGING.md) | MSIX + PyInstaller sidecar notes (U6) |

## Next (local Windows)
Build/run against `web_main.py` · bind LiveCharts · packaging project · retire tkinter-on-Windows decision when parity is enough.
