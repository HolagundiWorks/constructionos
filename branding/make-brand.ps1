<#
.SYNOPSIS
  Regenerate the ACO brand assets (Windows / GDI+ twin of make_brand.py).

.DESCRIPTION
  Prefer the cross-platform canonical generator when available:

      python branding/make_brand.py

  This PowerShell script mirrors the same Fluent 2 / Microsoft 365–inspired
  geometry for Windows boxes without Cairo:

    * Soft continuous-corner squircle plate
    * Analogous Radiant-Orange gradient (~120 deg) on the tile
    * Layered gauge-C mark (open ring + ring + dot) with soft depth shadow
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
$R_OUTER = 0.335; $W_OUTER = 0.098; $GAP_DEG = 82.0
$R_INNER = 0.142; $W_INNER = 0.062; $R_DOT = 0.052

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

function Add-RoundRect($path, [single]$x, [single]$y, [single]$w, [single]$h, [single]$r) {
    $d = 2 * $r
    $path.AddArc($x, $y, $d, $d, 180, 90)
    $path.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
    $path.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
    $path.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
    $path.CloseFigure()
}

function Draw-Mark($g, [single]$cx, [single]$cy, [single]$S, $color, [bool]$shadow = $false) {
    if ($shadow) {
        $shadowColor = [System.Drawing.Color]::FromArgb(56, 0, 0, 0)
        $penS = New-Object System.Drawing.Pen($shadowColor, [single]($W_OUTER * $S * 1.05))
        $penS.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
        $penS.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
        $ox = 0.022 * $S; $oy = 0.032 * $S
        $rO = $R_OUTER * $S
        $start = $GAP_DEG / 2.0
        $sweep = 360.0 - $GAP_DEG
        $g.DrawArc($penS, [single]($cx + $ox - $rO), [single]($cy + $oy - $rO),
                   [single](2 * $rO), [single](2 * $rO), $start, $sweep)
        $penS.Dispose()
        $penSi = New-Object System.Drawing.Pen($shadowColor, [single]($W_INNER * $S))
        $rI = $R_INNER * $S
        $g.DrawEllipse($penSi, [single]($cx + $ox - $rI), [single]($cy + $oy - $rI),
                       [single](2 * $rI), [single](2 * $rI))
        $penSi.Dispose()
        $brS = New-Object System.Drawing.SolidBrush($shadowColor)
        $rD = $R_DOT * $S
        $g.FillEllipse($brS, [single]($cx + $ox - $rD), [single]($cy + $oy - $rD),
                       [single](2 * $rD), [single](2 * $rD))
        $brS.Dispose()
    }

    $rO = $R_OUTER * $S; $wO = $W_OUTER * $S
    $pen = New-Object System.Drawing.Pen($color, [single]$wO)
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
    $start = $GAP_DEG / 2.0
    $sweep = 360.0 - $GAP_DEG
    $g.DrawArc($pen, [single]($cx - $rO), [single]($cy - $rO),
               [single](2 * $rO), [single](2 * $rO), $start, $sweep)
    $pen.Dispose()

    $rI = $R_INNER * $S; $wI = $W_INNER * $S
    $pen2 = New-Object System.Drawing.Pen($color, [single]$wI)
    $g.DrawEllipse($pen2, [single]($cx - $rI), [single]($cy - $rI),
                   [single](2 * $rI), [single](2 * $rI))
    $pen2.Dispose()

    $rD = $R_DOT * $S
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
    $c = New-Canvas $S $S; $bmp = $c[0]; $g = $c[1]
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    Add-RoundRect $path 0 0 $S $S ([single]($CORNER_RATIO * $S))
    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        [System.Drawing.PointF]::new(0.05 * $S, 0.02 * $S),
        [System.Drawing.PointF]::new(0.98 * $S, 0.98 * $S),
        $ORANGE_LIGHT, $ORANGE_DEEP)
    $blend = New-Object System.Drawing.Drawing2D.ColorBlend
    $blend.Colors = @($ORANGE_LIGHT, $ORANGE_MID, $ORANGE, $ORANGE_DEEP)
    $blend.Positions = @(0.0, 0.28, 0.62, 1.0)
    $brush.InterpolationColors = $blend
    $g.FillPath($brush, $path)
    $brush.Dispose(); $path.Dispose()
    Draw-Mark $g ([single]($S / 2)) ([single]($S / 2)) $S $WHITE $true
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
