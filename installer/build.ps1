<#
    build.ps1 — build the Construction OS Windows installer.

    Usage:
        .\build.ps1              Full build: PyInstaller freeze + Inno Setup -> Setup.exe
        .\build.ps1 -Portable    PyInstaller only -> a portable .zip (no Inno Setup needed)

    PyInstaller is installed into a throwaway venv here. It is a BUILD tool only;
    the shipped app remains pure standard library with no pip dependency.
#>
param([switch]$Portable)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

# 1. A real Python — the Microsoft Store stub on PATH cannot build.
$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $py = $cmd.Source }
}
if (-not (Test-Path $py)) { throw "No usable Python found. Install Python 3.8+ from python.org." }
Write-Host "Python : $py"

# 2. Build-only venv with PyInstaller.
$venv = Join-Path $here 'venv'
if (-not (Test-Path $venv)) {
    Write-Host "Creating build venv..."
    & $py -m venv $venv
}
$vpy = Join-Path $venv 'Scripts\python.exe'
Write-Host "Installing PyInstaller (build tool only)..."
& $vpy -m pip install --quiet --upgrade pip pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Could not install PyInstaller (network?)." }

# 3. Freeze the app.
Write-Host "Freezing the app..."
& $vpy -m PyInstaller --noconfirm --clean `
    --distpath (Join-Path $here 'dist') `
    --workpath (Join-Path $here 'build') `
    (Join-Path $here 'ConstructionOS.spec')
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
$appDir = Join-Path $here 'dist\ConstructionOS'
if (-not (Test-Path (Join-Path $appDir 'ConstructionOS.exe'))) {
    throw "Expected ConstructionOS.exe was not produced."
}
Write-Host "Frozen build: $appDir"

# 4a. Portable path: just zip the folder.
if ($Portable) {
    $out = Join-Path $here 'output'
    New-Item -ItemType Directory -Force $out | Out-Null
    $zip = Join-Path $out 'ConstructionOS-portable.zip'
    if (Test-Path $zip) { Remove-Item $zip }
    Compress-Archive -Path (Join-Path $appDir '*') -DestinationPath $zip
    Write-Host "Portable build ready: $zip"
    Write-Host "Distribute the zip; the user unzips anywhere and runs ConstructionOS.exe."
    return
}

# 4b. Installer path: compile the Inno Setup script.
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    foreach ($c in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
                     "$env:ProgramFiles\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $c) { $iscc = $c; break }
    }
}
if (-not $iscc) {
    Write-Warning "Inno Setup (ISCC.exe) not found."
    Write-Warning "Install it (free) from https://jrsoftware.org/isdl.php, then re-run,"
    Write-Warning "or run '.\build.ps1 -Portable' for a zip that needs no installer."
    return
}
Write-Host "Compiling installer with $iscc ..."
& $iscc (Join-Path $here 'ConstructionOS.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }
Write-Host "Installer ready in installer\output\ (ConstructionOS-Setup-*.exe)."
