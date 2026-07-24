<#
.SYNOPSIS
  Regenerate the ACO brand assets (Windows / GDI+ twin of make_brand.py).

.DESCRIPTION
  Prefer the cross-platform canonical generator when available:

      python branding/make_brand.py

  This PowerShell script mirrors the same geometry for Windows boxes without Cairo:

    * Outer ring open at bottom → A; middle open at right → C; solid centre → O
    * All three rings Radiant Orange on transparent (no plate)
    * Stacked wordmark; A/C/O initials in Radiant Orange

  Emits the full asset set into construction_app/resources (or -OutDir).

.PARAMETER OutDir
  Where to write the assets. Default: construction_app/resources.
#>
[CmdletBinding()]
param([string]$OutDir = (Join-Path $PSScriptRoot '..\construction_app\resources'))

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$OutDir = [System.IO.Path]::GetFullPath($OutDir)
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

# Prefer Python canonical generator when Cairo+Pillow are available.
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $script = Join-Path $PSScriptRoot 'make_brand.py'
    if (Test-Path $script) {
        Write-Host "Delegating to make_brand.py (canonical Fluent 2 generator)..." -ForegroundColor Cyan
        & $py.Source $script --out-dir $OutDir
        if ($LASTEXITCODE -eq 0) { return }
        Write-Host "Python generator failed; falling back to GDI+ twin." -ForegroundColor Yellow
    }
}

$ORANGE       = [System.Drawing.Color]::FromArgb(255, 255, 79, 24)    # #FF4F18
$ORANGE_LIGHT = [System.Drawing.Color]::FromArgb(255, 255, 154, 92)   # #FF9A5C
$ORANGE_MID   = [System.Drawing.Color]::FromArgb(255, 255, 95, 40)
$ORANGE_DEEP  = [System.Drawing.Color]::FromArgb(255, 217, 50, 0)     # #D93200
$INK          = [System.Drawing.Color]::FromArgb(255, 20, 24, 31)     # #14181F
$WHITE        = [System.Drawing.Color]::White

$CORNER_RATIO = 0.235
$R_OUTER = 0.335; $W_OUTER = 0.098
$R_INNER = 0.155; $W_INNER = 0.070; $R_DOT = 0.055
$GAP_DEG = 78.0
$OUTER_GAP_CENTER = 90.0   # bottom → A
$INNER_GAP_CENTER = 0.0    # right  → C

function Get-GapStartSweep([double]$gapCenter) {
    $start = ($gapCenter + $GAP_DEG / 2.0) % 360.0
    $sweep = 360.0 - $GAP_DEG
    return ,@($start, $sweep)
}

function New-Canvas([int]$w, [int]$h) {
    $bmp = New-Object System.Drawing.Bitmap($w, $h,
        [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode      = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode  = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode    = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.TextRenderingHint  = [System.Drawing.Text.TextRenderingHint]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)
    return ,@($bmp, $g)
}

function Draw-Mark($g, [single]$cx, [single]$cy, [single]$S, $color, [bool]$shadow = $false) {
    $rO = $R_OUTER * $S; $wO = $W_OUTER * $S
    $rI = $R_INNER * $S; $wI = $W_INNER * $S
    $rD = $R_DOT * $S
    $o = Get-GapStartSweep $OUTER_GAP_CENTER
    $i = Get-GapStartSweep $INNER_GAP_CENTER
    $oStart = $o[0]; $oSweep = $o[1]
    $iStart = $i[0]; $iSweep = $i[1]

    if ($shadow) {
        $shadowColor = [System.Drawing.Color]::FromArgb(70, 217, 50, 0)
        $ox = 0.012 * $S; $oy = 0.016 * $S
        $penS = New-Object System.Drawing.Pen($shadowColor, [single]$wO)
        $penS.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
        $penS.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
        $g.DrawArc($penS, [single]($cx + $ox - $rO), [single]($cy + $oy - $rO),
                   [single](2 * $rO), [single](2 * $rO), $oStart, $oSweep)
        $penS.Dispose()
        $penSi = New-Object System.Drawing.Pen($shadowColor, [single]$wI)
        $penSi.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
        $penSi.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
        $g.DrawArc($penSi, [single]($cx + $ox - $rI), [single]($cy + $oy - $rI),
                   [single](2 * $rI), [single](2 * $rI), $iStart, $iSweep)
        $penSi.Dispose()
        $brS = New-Object System.Drawing.SolidBrush($shadowColor)
        $g.FillEllipse($brS, [single]($cx + $ox - $rD), [single]($cy + $oy - $rD),
                       [single](2 * $rD), [single](2 * $rD))
        $brS.Dispose()
    }

    $pen = New-Object System.Drawing.Pen($color, [single]$wO)
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
    $g.DrawArc($pen, [single]($cx - $rO), [single]($cy - $rO),
               [single](2 * $rO), [single](2 * $rO), $oStart, $oSweep)
    $pen.Dispose()

    $pen2 = New-Object System.Drawing.Pen($color, [single]$wI)
    $pen2.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen2.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
    $g.DrawArc($pen2, [single]($cx - $rI), [single]($cy - $rI),
               [single](2 * $rI), [single](2 * $rI), $iStart, $iSweep)
    $pen2.Dispose()

    $br = New-Object System.Drawing.SolidBrush($color)
    $g.FillEllipse($br, [single]($cx - $rD), [single]($cy - $rD),
                   [single](2 * $rD), [single](2 * $rD))
    $br.Dispose()
}

function Save-Png($bmp, [string]$name) {
    $p = Join-Path $OutDir $name
    $bmp.Save($p, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host ("  {0}  ({1}x{2})" -f $name, $bmp.Width, $bmp.Height)
}

function Make-Square([int]$S, [string]$name) {
    # Orange ACO mark on transparent — no plate.
    $c = New-Canvas $S $S; $bmp = $c[0]; $g = $c[1]
    Draw-Mark $g ([single]($S / 2)) ([single]($S / 2)) $S $ORANGE $true
    if ($name) { Save-Png $bmp $name }
    $g.Dispose()
    return $bmp
}

function Make-Mark([int]$S, $color, [string]$name) {
    $c = New-Canvas $S $S; $bmp = $c[0]; $g = $c[1]
    Draw-Mark $g ([single]($S / 2)) ([single]($S / 2)) $S $color $false
    if ($name) { Save-Png $bmp $name }
    $g.Dispose()
    return $bmp
}

function Resolve-WordFont([single]$fontPx) {
    foreach ($face in @('Segoe UI Semibold', 'Segoe UI', 'Arial')) {
        try {
            return New-Object System.Drawing.Font($face, [single]$fontPx,
                [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
        } catch { }
    }
    return New-Object System.Drawing.Font('Arial', [single]$fontPx,
        [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
}

function Make-Lockup($markColor, $bodyColor, [string]$name) {
    $H = 360
    $markS = 320.0
    $markVis = 2 * $R_OUTER * $markS
    $padX = 30.0
    $gap = 40.0
    $words = @('ACCELERATED', 'CONSTRUCTION', 'OPERATIONS')
    $fontPx = 70.0
    $lineStep = $fontPx * 1.28
    $font = Resolve-WordFont $fontPx
    $sf = [System.Drawing.StringFormat]::GenericTypographic
    $sf.FormatFlags = [System.Drawing.StringFormatFlags]::MeasureTrailingSpaces

    $m = New-Canvas 8 8; $mg = $m[1]
    $maxW = 0.0
    foreach ($w in $words) {
        $ww = $mg.MeasureString($w, $font, [int]4000, $sf).Width
        if ($ww -gt $maxW) { $maxW = $ww }
    }
    $m[0].Dispose()

    $textX = $padX + $markVis + $gap
    $W = [int]($textX + $maxW + $padX)
    $c = New-Canvas $W $H; $bmp = $c[0]; $g = $c[1]

    Draw-Mark $g ([single]($padX + $markVis / 2)) ([single]($H / 2)) $markS $markColor $false

    $orange = New-Object System.Drawing.SolidBrush($ORANGE)
    $body = New-Object System.Drawing.SolidBrush($bodyColor)
    $totalH = $lineStep * $words.Count
    $y = ($H - $totalH) / 2.0
    foreach ($w in $words) {
        $first = $w.Substring(0, 1)
        $rest = $w.Substring(1)
        $g.DrawString($first, $font, $orange, [single]$textX, [single]$y, $sf)
        $fw = $g.MeasureString($first, $font, [int]4000, $sf).Width
        $g.DrawString($rest, $font, $body, [single]($textX + $fw), [single]$y, $sf)
        $y += $lineStep
    }
    $orange.Dispose(); $body.Dispose()

    Save-Png $bmp $name
    $font.Dispose(); $g.Dispose(); $bmp.Dispose()
}

function Make-VerticalLockup($markColor, $bodyColor, [string]$name) {
    $words = @('ACCELERATED', 'CONSTRUCTION', 'OPERATIONS')
    $fontPx = 66.0
    $lineStep = $fontPx * 1.28
    $font = Resolve-WordFont $fontPx
    $sf = [System.Drawing.StringFormat]::GenericTypographic
    $sf.FormatFlags = [System.Drawing.StringFormatFlags]::MeasureTrailingSpaces

    $m = New-Canvas 8 8; $mg = $m[1]
    $maxW = 0.0
    foreach ($w in $words) {
        $ww = $mg.MeasureString($w, $font, [int]4000, $sf).Width
        if ($ww -gt $maxW) { $maxW = $ww }
    }
    $m[0].Dispose()

    $markVis = 0.62 * $maxW
    $markS = $markVis / (2 * $R_OUTER)
    $padX = 44.0; $padTop = 40.0; $gap = 40.0; $padBot = 44.0
    $textH = $lineStep * $words.Count
    $W = [int]([Math]::Max($markVis, $maxW) + 2 * $padX)
    $H = [int]($padTop + $markVis + $gap + $textH + $padBot)
    $c = New-Canvas $W $H; $bmp = $c[0]; $g = $c[1]

    Draw-Mark $g ([single]($W / 2)) ([single]($padTop + $markVis / 2)) $markS $markColor $false

    $blockX = ($W - $maxW) / 2.0
    $orange = New-Object System.Drawing.SolidBrush($ORANGE)
    $body = New-Object System.Drawing.SolidBrush($bodyColor)
    $y = $padTop + $markVis + $gap
    foreach ($w in $words) {
        $first = $w.Substring(0, 1)
        $rest = $w.Substring(1)
        $g.DrawString($first, $font, $orange, [single]$blockX, [single]$y, $sf)
        $fw = $g.MeasureString($first, $font, [int]4000, $sf).Width
        $g.DrawString($rest, $font, $body, [single]($blockX + $fw), [single]$y, $sf)
        $y += $lineStep
    }
    $orange.Dispose(); $body.Dispose()

    Save-Png $bmp $name
    $font.Dispose(); $g.Dispose(); $bmp.Dispose()
}

function Make-Ico([int[]]$sizes, [string]$name) {
    $entries = @()
    foreach ($s in $sizes) {
        $bmp = Make-Square $s ''
        $ms = New-Object System.IO.MemoryStream
        $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
        $entries += ,@($s, $ms.ToArray())
        $bmp.Dispose(); $ms.Dispose()
    }
    $out = New-Object System.IO.MemoryStream
    $bw = New-Object System.IO.BinaryWriter($out)
    $bw.Write([UInt16]0); $bw.Write([UInt16]1); $bw.Write([UInt16]$entries.Count)
    $offset = 6 + 16 * $entries.Count
    foreach ($e in $entries) {
        $sz = $e[0]; $data = $e[1]
        $bw.Write([Byte]($(if ($sz -ge 256) { 0 } else { $sz })))
        $bw.Write([Byte]($(if ($sz -ge 256) { 0 } else { $sz })))
        $bw.Write([Byte]0); $bw.Write([Byte]0)
        $bw.Write([UInt16]1); $bw.Write([UInt16]32)
        $bw.Write([UInt32]$data.Length); $bw.Write([UInt32]$offset)
        $offset += $data.Length
    }
    foreach ($e in $entries) { $bw.Write($e[1]) }
    $bw.Flush()
    [System.IO.File]::WriteAllBytes((Join-Path $OutDir $name), $out.ToArray())
    $bw.Dispose(); $out.Dispose()
    Write-Host ("  {0}  (sizes: {1})" -f $name, ($sizes -join ', '))
}

function Make-Favicon([int]$S, [string]$name) {
    $bmp = Make-Square $S ''
    Save-Png $bmp $name
    $bmp.Dispose()
}

Write-Host "Generating Fluent 2 ACO brand assets (GDI+) into $OutDir" -ForegroundColor Cyan
(Make-Square 512 'logo_square.png').Dispose()
(Make-Mark 512 $WHITE  'logo_square_white.png').Dispose()
(Make-Mark 512 $ORANGE 'logo_mark.png').Dispose()
Make-Lockup $ORANGE $INK   'logo_rectangle.png'
Make-Lockup $WHITE  $WHITE 'logo_rectangle_white.png'
Make-VerticalLockup $ORANGE $INK   'logo_vertical.png'
Make-VerticalLockup $WHITE  $WHITE 'logo_vertical_white.png'
Make-Ico @(16, 24, 32, 48, 64, 128, 256) 'app.ico'
Make-Favicon 64 'favicon.png'
Write-Host "Done." -ForegroundColor Green
