<#
.SYNOPSIS
  Regenerate the ACO brand assets from one parametric source (Windows / GDI+).

.DESCRIPTION
  The ACO mark is a "gauge C": a bold open ring (C = Construction) around a
  concentric target (ring + dot = Operations / precision / control), in Radiant
  Orange (#FF4F18). This script draws it vector-crisp at any size and emits the
  full asset set, so the logo never has to be hand-edited pixel by pixel:

    logo_square.png            white mark on a Radiant-Orange squircle (app tile)
    logo_square_white.png      white mark on transparent (dark rail)
    logo_mark.png              orange mark on transparent (documents / favicon)
    logo_rectangle.png         orange mark + "ACO" + tagline (light backgrounds)
    logo_rectangle_white.png   white  mark + "ACO" + tagline (dark backgrounds)
    app.ico                    multi-size icon (16..256) for the exe / window
    favicon.png                32px orange mark on white (browser tab)

  ASCII-only (PowerShell 5.1 reads .ps1 as ANSI).

.PARAMETER OutDir
  Where to write the assets. Default: construction_app/resources (the live set).
#>
[CmdletBinding()]
param([string]$OutDir = (Join-Path $PSScriptRoot '..\construction_app\resources'))

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$OutDir = [System.IO.Path]::GetFullPath($OutDir)
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$ORANGE = [System.Drawing.Color]::FromArgb(255, 255, 79, 24)   # #FF4F18
$INK    = [System.Drawing.Color]::FromArgb(255, 20, 24, 31)    # #14181F
$GRAY   = [System.Drawing.Color]::FromArgb(255, 107, 114, 128) # #6B7280
$WHITE  = [System.Drawing.Color]::White
$FAINT  = [System.Drawing.Color]::FromArgb(255, 209, 213, 219) # light tagline on dark

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

# The mark: gauge C (open ring) + concentric ring + centre dot, all one colour.
# $S is the reference diameter box; the mark's outer diameter is 0.72*$S so it
# sits with even padding when $S is the tile size.
function Draw-Mark($g, [single]$cx, [single]$cy, [single]$S, $color) {
    $rO = 0.360 * $S; $wO = 0.116 * $S
    $pen = New-Object System.Drawing.Pen($color, [single]$wO)
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
    # Gap of 70deg facing right (3 o'clock): draw 35deg -> 325deg clockwise.
    $g.DrawArc($pen, [single]($cx - $rO), [single]($cy - $rO),
               [single](2 * $rO), [single](2 * $rO), 35, 290)
    $pen.Dispose()

    $rI = 0.156 * $S; $wI = 0.076 * $S
    $pen2 = New-Object System.Drawing.Pen($color, [single]$wI)
    $g.DrawEllipse($pen2, [single]($cx - $rI), [single]($cy - $rI),
                   [single](2 * $rI), [single](2 * $rI))
    $pen2.Dispose()

    $rD = 0.060 * $S
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

# ---- square tile (white mark on Radiant-Orange squircle) --------------------
function Make-Square([int]$S, [string]$name) {
    $c = New-Canvas $S $S; $bmp = $c[0]; $g = $c[1]
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    Add-RoundRect $path 0 0 $S $S ([single](0.22 * $S))
    $br = New-Object System.Drawing.SolidBrush($ORANGE)
    $g.FillPath($br, $path); $br.Dispose(); $path.Dispose()
    Draw-Mark $g ([single]($S / 2)) ([single]($S / 2)) $S $WHITE
    if ($name) { Save-Png $bmp $name }
    $g.Dispose()
    return $bmp
}

# ---- mark only, on transparent ---------------------------------------------
function Make-Mark([int]$S, $color, [string]$name) {
    $c = New-Canvas $S $S; $bmp = $c[0]; $g = $c[1]
    Draw-Mark $g ([single]($S / 2)) ([single]($S / 2)) $S $color
    if ($name) { Save-Png $bmp $name }
    $g.Dispose()
    return $bmp
}

# ---- horizontal lockup: mark + STACKED wordmark ----------------------------
# The three words stack (Good-Times-style wide techno caps via BankGothic); the
# A/C/O initials are picked out in Radiant Orange so the acronym reads down the
# left edge and explains the name.
function Make-Lockup($markColor, $bodyColor, [string]$name) {
    $H = 360
    $markS = 320.0                       # reference box; visible mark = 0.72*markS
    $markVis = 0.72 * $markS
    $padX = 30.0
    $gap = 46.0
    $words = @('ACCELERATED', 'CONSTRUCTION', 'OPERATIONS')
    $fontPx = 70.0
    $lineStep = $fontPx * 1.30
    $font = New-Object System.Drawing.Font('BankGothic Md BT', [single]$fontPx,
        [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
    $sf = [System.Drawing.StringFormat]::GenericTypographic
    $sf.FormatFlags = [System.Drawing.StringFormatFlags]::MeasureTrailingSpaces

    # Measure the widest line on a scratch surface.
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

    Draw-Mark $g ([single]($padX + $markVis / 2)) ([single]($H / 2)) $markS $markColor

    $orange = New-Object System.Drawing.SolidBrush($ORANGE)
    $body = New-Object System.Drawing.SolidBrush($bodyColor)
    $totalH = $lineStep * $words.Count
    $y = ($H - $totalH) / 2.0 + ($lineStep - $fontPx) / 2.0
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

# ---- multi-size .ico from freshly rendered squares -------------------------
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
    $bw.Write([UInt16]0); $bw.Write([UInt16]1); $bw.Write([UInt16]$entries.Count)  # ICONDIR
    $offset = 6 + 16 * $entries.Count
    foreach ($e in $entries) {
        $sz = $e[0]; $data = $e[1]
        $bw.Write([Byte]($(if ($sz -ge 256) { 0 } else { $sz })))   # width
        $bw.Write([Byte]($(if ($sz -ge 256) { 0 } else { $sz })))   # height
        $bw.Write([Byte]0); $bw.Write([Byte]0)                       # colours, reserved
        $bw.Write([UInt16]1); $bw.Write([UInt16]32)                  # planes, bpp
        $bw.Write([UInt32]$data.Length); $bw.Write([UInt32]$offset)  # size, offset
        $offset += $data.Length
    }
    foreach ($e in $entries) { $bw.Write($e[1]) }
    $bw.Flush()
    [System.IO.File]::WriteAllBytes((Join-Path $OutDir $name), $out.ToArray())
    $bw.Dispose(); $out.Dispose()
    Write-Host ("  {0}  (sizes: {1})" -f $name, ($sizes -join ', '))
}

# ---- favicon (orange mark on white) ----------------------------------------
function Make-Favicon([int]$S, [string]$name) {
    $c = New-Canvas $S $S; $bmp = $c[0]; $g = $c[1]
    $g.Clear($WHITE)
    Draw-Mark $g ([single]($S / 2)) ([single]($S / 2)) $S $ORANGE
    Save-Png $bmp $name
    $g.Dispose(); $bmp.Dispose()
}

Write-Host "Generating ACO brand assets into $OutDir" -ForegroundColor Cyan
(Make-Square 512 'logo_square.png').Dispose()
(Make-Mark 512 $WHITE  'logo_square_white.png').Dispose()
(Make-Mark 512 $ORANGE 'logo_mark.png').Dispose()
Make-Lockup $ORANGE $INK   'logo_rectangle.png'
Make-Lockup $WHITE  $WHITE 'logo_rectangle_white.png'
Make-Ico @(16, 24, 32, 48, 64, 128, 256) 'app.ico'
Make-Favicon 64 'favicon.png'
Write-Host "Done." -ForegroundColor Green
