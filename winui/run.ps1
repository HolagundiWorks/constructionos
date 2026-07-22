<#
.SYNOPSIS
  Build and launch the Construction OS WinUI 3 client.

.DESCRIPTION
  Builds the unpackaged, self-contained WinUI app and launches it. Build output
  is redirected OUT of OneDrive (see Directory.Build.props) to %LOCALAPPDATA%,
  because OneDrive briefly locks / re-syncs files under bin\ and that makes the
  running app crash intermittently in combase.dll with 0x80070002
  (ERROR_FILE_NOT_FOUND) -- a native fail-fast the app cannot catch.

  Prereq: start the Python backend first (from repo root):
      cd construction_app; python web_main.py --host 127.0.0.1 --port 8080

.PARAMETER Configuration
  Debug (default) or Release.

.PARAMETER NoBuild
  Skip the build and just launch the last-built exe.

.EXAMPLE
  .\run.ps1
  .\run.ps1 -Configuration Release
#>
[CmdletBinding()]
param(
    [ValidateSet('Debug','Release')] [string]$Configuration = 'Debug',
    [switch]$NoBuild
)
$ErrorActionPreference = 'Stop'
$proj = Join-Path $PSScriptRoot 'ConstructionOS.WinUI\ConstructionOS.WinUI.csproj'
$rid  = 'win-x64'
$tfm  = 'net8.0-windows10.0.19041.0'

# Mirrors Directory.Build.props: LOCALAPPDATA\ConstructionOS-build\<ProjectName>
$exe = Join-Path $env:LOCALAPPDATA "ConstructionOS-build\ConstructionOS.WinUI\bin\x64\$Configuration\$tfm\$rid\ConstructionOS.WinUI.exe"

if (-not $NoBuild) {
    Write-Host "Building ($Configuration, $rid, self-contained) into LOCALAPPDATA\ConstructionOS-build ..." -ForegroundColor Cyan
    & dotnet build $proj -c $Configuration -p:Platform=x64 -r $rid --self-contained `
        -p:WindowsPackageType=None -p:UseRidGraph=true -p:WindowsAppSDKSelfContained=true `
        -v minimal -nologo
    if ($LASTEXITCODE -ne 0) { throw "Build failed (exit $LASTEXITCODE)." }
}

if (-not (Test-Path $exe)) { throw "Executable not found: $exe. Run without -NoBuild first." }

# Warn (do not block) if the backend is not up -- the app shows a friendly offline page.
try {
    $null = Invoke-WebRequest 'http://127.0.0.1:8080/api/health' -TimeoutSec 2 -UseBasicParsing
} catch {
    Write-Host "Note: backend not answering on http://127.0.0.1:8080 -- start it with:" -ForegroundColor Yellow
    Write-Host "  cd ..\construction_app; python web_main.py --host 127.0.0.1 --port 8080" -ForegroundColor Yellow
}

Write-Host "Launching $exe" -ForegroundColor Green
Start-Process $exe
