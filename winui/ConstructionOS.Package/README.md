# ACO — MSIX package (U6)

This folder holds the **`Package.appxmanifest`** (ACO branding, `runFullTrust`,
sidecar notes) used to wrap the WinUI 3 client + the PyInstaller backend sidecar
into a signed MSIX.

## Build it headlessly (no Visual Studio) — recommended
`winui/build-msix.ps1` does the whole job with the Windows SDK's `makeappx.exe`
+ `signtool.exe` — no `.wapproj`, no VS packaging workload:

```powershell
pwsh winui/build-sidecar.ps1   # once — freezes web_main.py -> ACO.Backend.exe
pwsh winui/build-msix.ps1      # assets -> publish -> pack -> sign
```

It generates the visual assets from `construction_app/resources/logo_*.png`,
publishes the self-contained Release app, bundles `Backend\ACO.Backend.exe`,
materialises a concrete `AppxManifest.xml` from this scaffold (resolving the
`$targetnametoken$` / `$targetentrypoint$` tokens and adding
`ProcessorArchitecture`), packs, and signs with a self-signed code-signing cert
whose subject matches `Identity/@Publisher` (`CN=Human Centric Works`). Output +
the exported public `.cer` land in `%LOCALAPPDATA%\ConstructionOS-build\msix`.
Verified: ~77 MB signed `ACO_1.0.0.0_x64.msix`.

**Install the dev build** (trust the self-signed cert once — needs admin):
```powershell
Import-Certificate -FilePath <..>\ACO-dev-cert.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople
Add-AppxPackage      <..>\ACO_1.0.0.0_x64.msix
```

**For release**, sign with a real code-signing cert instead: set
`Identity/@Publisher` to that cert's subject and run
`build-msix.ps1 -CertSubject "<that subject>"` (or re-sign the produced `.msix`).

## What's already done (elsewhere in the repo)
- **Backend sidecar** — `winui/build-sidecar.ps1` freezes `web_main.py` into a
  standalone `ACO.Backend.exe` (no Python needed). ✅
- **Auto-launch** — `Services/BackendLauncher.cs` starts `Backend\ACO.Backend.exe`
  (next to the app) when the port is free. ✅ Verified end-to-end.
- **Assets + pack + sign** — `winui/build-msix.ps1` (above). ✅

## Alternative: finish in VS 2022 (packaging project)
If you prefer the IDE flow:
1. **Build the sidecar:** `pwsh winui/build-sidecar.ps1`.
2. **Add the packaging project:** solution → *Add → New Project → Windows
   Application Packaging Project* → name it `ConstructionOS.Package` here.
3. **Reference the app:** add a project reference to `ConstructionOS.WinUI`, set
   it as the **Entry Point** (Applications node).
4. **Replace the manifest:** overwrite the generated `Package.appxmanifest` with
   this one; set `Identity/@Publisher` to your signing cert's subject. (Keep
   `rescap:runFullTrust` — the app launches the localhost sidecar.)
5. **Bundle the sidecar:** add `ACO.Backend.exe` under a `Backend\` folder with
   *Package Action = Content* (lands at `Backend\ACO.Backend.exe`).
6. **Visual assets:** generate all tiles/logos from
   `construction_app/resources/logo_square.png` (Radiant Orange).
7. **Package + sign:** *Publish → Create App Packages* → sideload → sign.

## Constraints (unchanged)
- Backend listens on **127.0.0.1 only**.
- No business maths in C# — the client calls `/api/*`.
- The one client settings file: `%LOCALAPPDATA%\ACO\winui-settings.json`.
