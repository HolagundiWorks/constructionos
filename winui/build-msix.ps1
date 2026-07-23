<#
.SYNOPSIS
  Build a signed MSIX for the ACO WinUI 3 client -- headless, no Visual Studio.

.DESCRIPTION
  Finishes U6 packaging without the VS "Windows Application Packaging Project":
    1. Generates the MSIX visual assets from construction_app/resources logos.
    2. Publishes the self-contained Release app to a staging folder.
    3. Bundles the PyInstaller backend sidecar (Backend\ACO.Backend.exe) if built.
    4. Materialises a concrete AppxManifest.xml from the checked-in scaffold
       (resolves the .wapproj $targetnametoken$ / $targetentrypoint$ tokens).
    5. Packs with makeappx.exe.
    6. Signs with signtool.exe using a self-signed CODE-SIGNING cert whose subject
       matches the manifest Publisher (created once in CurrentUser\My; no admin).

  The output .msix + the exported public .cer land under
  %LOCALAPPDATA%\ConstructionOS-build\msix. To install the dev build, first trust
  the .cer (Import into "Trusted People", LocalMachine -- needs admin once), then
  Add-AppxPackage the .msix. For release, sign with a real cert instead.

.PARAMETER Configuration
  Debug or Release (default Release).

.PARAMETER SkipPublish
  Reuse an existing staged publish (asset + pack + sign only).

.PARAMETER CertSubject
  Signing certificate subject. MUST equal the manifest Identity Publisher.
  Default "CN=Human Centric Works".
#>
[CmdletBinding()]
param(
    [ValidateSet('Debug','Release')] [string]$Configuration = 'Release',
    [switch]$SkipPublish,
    [string]$CertSubject = 'CN=Human Centric Works'
)
$ErrorActionPreference = 'Stop'

$root        = $PSScriptRoot
$proj        = Join-Path $root 'ConstructionOS.WinUI\ConstructionOS.WinUI.csproj'
$pkgDir      = Join-Path $root 'ConstructionOS.Package'
$manifestSrc = Join-Path $pkgDir 'Package.appxmanifest'
$resDir      = Join-Path $root '..\construction_app\resources'
$logoSquare  = Join-Path $resDir 'logo_square.png'
$logoRect    = Join-Path $resDir 'logo_rectangle.png'

$outRoot = Join-Path $env:LOCALAPPDATA 'ConstructionOS-build\msix'
$stage   = Join-Path $outRoot 'stage'
$images  = Join-Path $stage 'Images'

# ------------------------------------------------------------ locate SDK tools
function Find-SdkTool([string]$name) {
    $roots = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin",
        "$env:ProgramFiles\Windows Kits\10\bin"
    ) | Where-Object { Test-Path $_ }
    $hit = Get-ChildItem -Path $roots -Recurse -Filter $name -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\' } |
        Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $hit) { throw "Could not find $name under the Windows SDK bin folders." }
    return $hit.FullName
}
$makeappx = Find-SdkTool 'makeappx.exe'
$signtool = Find-SdkTool 'signtool.exe'
Write-Host "makeappx: $makeappx"
Write-Host "signtool: $signtool"

# ------------------------------------------------------------------- assets
# Fit-contain the source onto a transparent square/rect canvas, high quality.
Add-Type -AssemblyName System.Drawing
function New-Asset([string]$srcPath, [int]$w, [int]$h, [string]$dst) {
    $src = [System.Drawing.Image]::FromFile($srcPath)
    try {
        $bmp = New-Object System.Drawing.Bitmap $w, $h
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        try {
            $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $g.PixelOffsetMode   = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $g.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
            $g.Clear([System.Drawing.Color]::Transparent)
            $scale = [Math]::Min($w / $src.Width, $h / $src.Height)
            $dw = [int]([Math]::Round($src.Width * $scale))
            $dh = [int]([Math]::Round($src.Height * $scale))
            $dx = [int](($w - $dw) / 2)
            $dy = [int](($h - $dh) / 2)
            $g.DrawImage($src, $dx, $dy, $dw, $dh)
        } finally { $g.Dispose() }
        $bmp.Save($dst, [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp.Dispose()
    } finally { $src.Dispose() }
}

if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $images -Force | Out-Null

Write-Host "Generating visual assets from $logoSquare / $logoRect ..." -ForegroundColor Cyan
# Square tiles/logos from the square mark; wide tile + splash from the rectangle.
New-Asset $logoSquare  44  44  (Join-Path $images 'Square44x44Logo.png')
New-Asset $logoSquare 150 150  (Join-Path $images 'Square150x150Logo.png')
New-Asset $logoSquare  71  71  (Join-Path $images 'SmallTile.png')
New-Asset $logoSquare 310 310  (Join-Path $images 'LargeTile.png')
New-Asset $logoSquare  50  50  (Join-Path $images 'StoreLogo.png')
New-Asset $logoRect   310 150  (Join-Path $images 'Wide310x150Logo.png')
New-Asset $logoRect   620 300  (Join-Path $images 'SplashScreen.png')
# Unplated target-size variant MSIX expects for the 44x44 (taskbar / title bar).
New-Asset $logoSquare  44  44  (Join-Path $images 'Square44x44Logo.targetsize-44_altform-unplated.png')

# -------------------------------------------------------------------- publish
if (-not $SkipPublish) {
    Write-Host "Publishing ($Configuration, win-x64, self-contained) to stage ..." -ForegroundColor Cyan
    & dotnet publish $proj -c $Configuration -r win-x64 --self-contained `
        -p:Platform=x64 -p:WindowsPackageType=None -p:UseRidGraph=true `
        -p:WindowsAppSDKSelfContained=true -p:GenerateAppxPackageOnBuild=false `
        -o $stage -v minimal -nologo
    if ($LASTEXITCODE -ne 0) { throw "publish failed (exit $LASTEXITCODE)." }
} elseif (-not (Test-Path (Join-Path $stage 'ConstructionOS.WinUI.exe'))) {
    throw "-SkipPublish but no staged app at $stage. Run once without it."
}

# ---------------------------------------------------------------- sidecar
$sidecar = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'ConstructionOS-build') `
    -Recurse -Filter 'ACO.Backend.exe' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($sidecar) {
    New-Item -ItemType Directory -Path (Join-Path $stage 'Backend') -Force | Out-Null
    Copy-Item $sidecar.FullName (Join-Path $stage 'Backend\ACO.Backend.exe') -Force
    Write-Host "Bundled backend sidecar from $($sidecar.FullName)" -ForegroundColor Green
} else {
    Write-Host "WARNING: no ACO.Backend.exe found -- build it with build-sidecar.ps1" -ForegroundColor Yellow
    Write-Host "         The MSIX still installs, but cannot auto-start the backend." -ForegroundColor Yellow
}

# ---------------------------------------------------------------- manifest
# Resolve the .wapproj tokens the checked-in scaffold carries, add the package
# processor architecture, and drop it in as the concrete AppxManifest.xml.
[xml]$doc = Get-Content $manifestSrc
$ns = New-Object System.Xml.XmlNamespaceManager($doc.NameTable)
$ns.AddNamespace('m', 'http://schemas.microsoft.com/appx/manifest/foundation/windows10')
$doc.DocumentElement.SelectSingleNode('m:Identity', $ns).SetAttribute('ProcessorArchitecture', 'x64')
$app = $doc.DocumentElement.SelectSingleNode('m:Applications/m:Application', $ns)
$app.SetAttribute('Executable', 'ConstructionOS.WinUI.exe')
$app.SetAttribute('EntryPoint', 'Windows.FullTrustApplication')
$version = $doc.DocumentElement.SelectSingleNode('m:Identity', $ns).Version
$manifestOut = Join-Path $stage 'AppxManifest.xml'
$doc.Save($manifestOut)
Write-Host "Wrote $manifestOut (v$version, x64)" -ForegroundColor Green

# -------------------------------------------------------------------- pack
$msix = Join-Path $outRoot ("ACO_{0}_x64.msix" -f $version)
if (Test-Path $msix) { Remove-Item $msix -Force }
Write-Host "Packing to $msix ..." -ForegroundColor Cyan
& $makeappx pack /d $stage /p $msix /o
if ($LASTEXITCODE -ne 0) { throw "makeappx failed (exit $LASTEXITCODE)." }

# -------------------------------------------------------------------- sign
$cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq $CertSubject -and
                   ($_.EnhancedKeyUsageList.FriendlyName -contains 'Code Signing') } |
    Sort-Object NotAfter -Descending | Select-Object -First 1
if (-not $cert) {
    Write-Host "Creating self-signed code-signing cert '$CertSubject' (CurrentUser\My) ..." -ForegroundColor Cyan
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $CertSubject `
        -KeyUsage DigitalSignature -FriendlyName 'ACO dev signing' `
        -CertStoreLocation Cert:\CurrentUser\My `
        -NotAfter (Get-Date).AddYears(3)
}
$cer = Join-Path $outRoot 'ACO-dev-cert.cer'
Export-Certificate -Cert $cert -FilePath $cer | Out-Null
Write-Host "Signing with $($cert.Thumbprint) ..." -ForegroundColor Cyan
& $signtool sign /fd SHA256 /sha1 $cert.Thumbprint $msix
if ($LASTEXITCODE -ne 0) { throw "signtool failed (exit $LASTEXITCODE)." }

Write-Host ""
Write-Host "OK -- signed MSIX:" -ForegroundColor Green
Write-Host "  $msix"
Write-Host "Dev cert (trust once to sideload):" -ForegroundColor Green
Write-Host "  $cer"
Write-Host ""
Write-Host "Install (PowerShell; one-time cert trust needs admin):" -ForegroundColor Yellow
Write-Host "  Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople"
Write-Host "  Add-AppxPackage $msix"
