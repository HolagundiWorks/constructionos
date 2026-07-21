<#
    build.ps1 — build the Windows installers for Construction OS and its
    companion, the Ollama Manager.

    Usage:
        .\build.ps1                 Both apps: freeze + Inno Setup -> two Setup.exe
        .\build.ps1 -Portable       Both apps: freeze -> two portable .zip (no Inno)
        .\build.ps1 -App "Construction OS"   Just one app (name as below)

    PyInstaller is installed into a throwaway venv here — a BUILD tool only; the
    shipped apps stay pure standard library with no pip dependency. The target
    machine needs no Python and no internet.
#>
param(
    [switch]$Portable,
    [ValidateSet('Construction OS', 'Ollama Manager')]
    [string]$App
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$apps = @(
    @{ Name = 'Construction OS'; Spec = 'ConstructionOS.spec'; Iss = 'ConstructionOS.iss'; Dir = 'ConstructionOS'; Exe = 'ConstructionOS.exe' },
    @{ Name = 'Ollama Manager';  Spec = 'OllamaManager.spec';  Iss = 'OllamaManager.iss';  Dir = 'OllamaManager';  Exe = 'OllamaManager.exe' }
)
if ($App) { $apps = $apps | Where-Object { $_.Name -eq $App } }

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

# 3. Locate Inno Setup once (only needed for the non-portable path).
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    foreach ($c in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
                     "$env:ProgramFiles\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $c) { $iscc = $c; break }
    }
}

$out = Join-Path $here 'output'
New-Item -ItemType Directory -Force $out | Out-Null

foreach ($a in $apps) {
    Write-Host "`n=== $($a.Name) ==="
    # Freeze.
    & $vpy -m PyInstaller --noconfirm --clean `
        --distpath (Join-Path $here 'dist') `
        --workpath (Join-Path $here 'build') `
        (Join-Path $here $a.Spec)
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for $($a.Name)." }
    $appDir = Join-Path $here "dist\$($a.Dir)"
    if (-not (Test-Path (Join-Path $appDir $a.Exe))) {
        throw "Expected $($a.Exe) was not produced."
    }

    if ($Portable) {
        $zip = Join-Path $out ("{0}-portable.zip" -f ($a.Dir))
        if (Test-Path $zip) { Remove-Item $zip }
        Compress-Archive -Path (Join-Path $appDir '*') -DestinationPath $zip
        Write-Host "Portable build: $zip"
        continue
    }

    if (-not $iscc) {
        Write-Warning "Inno Setup (ISCC.exe) not found - skipping the $($a.Name) installer."
        Write-Warning "Install it (free) from https://jrsoftware.org/isdl.php, or use -Portable."
        continue
    }
    & $iscc (Join-Path $here $a.Iss)
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed for $($a.Name)." }
}

Write-Host "`nDone. Output is in installer\output"
