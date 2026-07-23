<#
.SYNOPSIS
  Freeze the Python backend (web_main.py) into a standalone ACO.Backend.exe (U6).

.DESCRIPTION
  Builds a headless, no-Python-required localhost backend the WinUI client can
  bundle + auto-launch (see Services/BackendLauncher.cs). Uses a throwaway venv
  with PyInstaller (a BUILD tool only -- the app itself stays stdlib/no-pip).

  The venv lives at a SHORT path (%USERPROFILE%\.aco-sidecar) because this repo
  is under OneDrive, whose deep paths blow past Windows MAX_PATH during pip.

.PARAMETER OutDir
  Where to copy ACO.Backend.exe. Default: the dev app's Backend\ folder (where
  run.ps1's build lands), so `run.ps1 -NoBuild` then auto-starts the sidecar.

.EXAMPLE
  .\build-sidecar.ps1
  .\build-sidecar.ps1 -OutDir C:\path\to\Package\Backend
#>
[CmdletBinding()]
param([string]$OutDir = "")
$ErrorActionPreference = 'Stop'

$repo = Split-Path $PSScriptRoot -Parent
$ca = Join-Path $repo 'construction_app'
if (-not (Test-Path (Join-Path $ca 'web_main.py'))) { throw "web_main.py not found under $ca" }

$build = Join-Path $env:USERPROFILE '.aco-sidecar'
New-Item -ItemType Directory -Force $build | Out-Null

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" }
if (-not (Test-Path $py)) { throw "Python not found. Install Python 3.12+." }

$venv = Join-Path $build 'venv'
$vpy = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $vpy)) { Write-Host "Creating build venv..."; & $py -m venv $venv }
Write-Host "Installing PyInstaller (build tool only)..."
& $vpy -m pip install --quiet --upgrade pip pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed (network / long-path support?)." }

# Our construction_app\workflow.py shares a name with a PyPI package that
# pyinstaller-hooks-contrib ships a hook for; that hook reads the PyPI package's
# metadata and errors on our local module. Drop any hooks whose name collides
# with one of our module names (throwaway venv -- safe).
$hookDir = Join-Path $venv 'Lib\site-packages\_pyinstaller_hooks_contrib\stdhooks'
if (Test-Path $hookDir) {
    $mods = Get-ChildItem $ca -Filter *.py | ForEach-Object { $_.BaseName }
    Get-ChildItem $hookDir -Filter 'hook-*.py' | Where-Object {
        $mods -contains ($_.BaseName -replace '^hook-','')
    } | ForEach-Object { Write-Host "Dropping colliding hook $($_.Name)"; Remove-Item $_.FullName -Force }
}

Write-Host "Freezing web_main.py -> ACO.Backend.exe (onefile, headless)..."
& $vpy -m PyInstaller --noconfirm --clean --onefile --console --name ACO.Backend `
    --exclude-module tkinter --exclude-module _tkinter --exclude-module turtle --exclude-module PIL `
    --distpath (Join-Path $build 'dist') --workpath (Join-Path $build 'work') `
    --specpath $build --paths $ca (Join-Path $ca 'web_main.py')
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$exe = Join-Path $build 'dist\ACO.Backend.exe'
if (-not (Test-Path $exe)) { throw "ACO.Backend.exe was not produced." }

if (-not $OutDir) {
    $OutDir = Join-Path $env:LOCALAPPDATA `
        'ConstructionOS-build\ConstructionOS.WinUI\bin\x64\Debug\net8.0-windows10.0.19041.0\win-x64\Backend'
}
New-Item -ItemType Directory -Force $OutDir | Out-Null
Copy-Item $exe (Join-Path $OutDir 'ACO.Backend.exe') -Force
$mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "Sidecar built (${mb} MB): $exe"
Write-Host "Placed at: $OutDir\ACO.Backend.exe"
Write-Host "The WinUI app (BackendLauncher) will auto-start it when the backend isn't already running."
