#!/usr/bin/env python3
"""Regenerate ACO brand assets — Fluent 2 / Microsoft 365–inspired.

Cross-platform canonical generator (Cairo + Pillow). Prefer this over the
Windows GDI+ twin ``make-brand.ps1`` when either is available.

Design (Fluent 2 product-icon language, M365 2024 refresh cues):
  * Soft continuous-corner squircle plate
  * Rich analogous orange gradient (~120°) on the tile
  * Layered gauge-C mark (open ring + ring + dot) with soft depth shadow
  * Stacked wordmark in a geometric sans; A/C/O initials in Radiant Orange

Requires: python3-cairo, python3-pil (apt: ``python3-cairo python3-pil``).
Not a runtime app dependency — build/brand tooling only.
"""
from __future__ import annotations

import argparse
import math
import os
import struct
import sys
from io import BytesIO

try:
    import cairo
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        'make_brand.py needs python3-cairo (apt install python3-cairo)\n'
    )
    raise SystemExit(1) from exc

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        'make_brand.py needs Pillow (apt install python3-pil)\n'
    )
    raise SystemExit(1) from exc

# --- Brand tokens -----------------------------------------------------------
ORANGE = (255, 79, 24)          # #FF4F18 Radiant Orange
ORANGE_LIGHT = (255, 154, 92)   # #FF9A5C analogous highlight
ORANGE_DEEP = (217, 50, 0)      # #D93200 analogous shadow
ORANGE_MID = (255, 95, 40)      # soft mid for mark gradients
INK = (20, 24, 31)              # #14181F
SLATE = (107, 114, 128)         # #6B7280
WHITE = (255, 255, 255)

# Fluent / Windows 11–ish continuous corner (~22–24% of edge)
CORNER_RATIO = 0.235

# Gauge-C geometry (fractions of reference box S)
R_OUTER = 0.335
W_OUTER = 0.098
GAP_DEG = 82.0                  # more open / fluid than the flat 70° mark
R_INNER = 0.142
W_INNER = 0.062
R_DOT = 0.052

WORDS = ('ACCELERATED', 'CONSTRUCTION', 'OPERATIONS')


def _rgba(rgb, a=1.0):
    r, g, b = rgb
    return (r / 255.0, g / 255.0, b / 255.0, a)


def _find_font(size_px):
    """Prefer Segoe / Fluent faces; fall back to Liberation (metrical cousin)."""
    candidates = [
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        'C:/Windows/Fonts/segoeuib.ttf',
        'C:/Windows/Fonts/seguisb.ttf',
        'C:/Windows/Fonts/arialbd.ttf',
    ]
    for path in candidates:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size=int(size_px))
    return ImageFont.load_default()


def _squircle_path(ctx, x, y, w, h, r):
    """Continuous-corner round rect (Fluent plate)."""
    r = min(r, w / 2.0, h / 2.0)
    ctx.new_path()
    ctx.move_to(x + r, y)
    ctx.line_to(x + w - r, y)
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.line_to(x + w, y + h - r)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.line_to(x + r, y + h)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.line_to(x, y + r)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def _arc_path(ctx, cx, cy, radius, start_deg, sweep_deg):
    """Cairo arcs are CCW from +X; GDI DrawArc used clockwise from +X."""
    # Match prior GDI: start at start_deg, sweep clockwise sweep_deg.
    a0 = math.radians(start_deg)
    a1 = math.radians(start_deg + sweep_deg)
    ctx.new_sub_path()
    # Cairo: positive angles CCW — negate for clockwise sweep.
    ctx.arc_negative(cx, cy, radius, -a0, -a1)


def _draw_mark_layers(
    ctx, cx, cy, S, fill_rgb, *, shadow=False, soft_highlight=False, layered_white=False
):
    """Layered gauge-C: outer open ring, inner ring, centre dot."""
    r_o = R_OUTER * S
    w_o = W_OUTER * S
    r_i = R_INNER * S
    w_i = W_INNER * S
    r_d = R_DOT * S
    gap = GAP_DEG
    start = gap / 2.0
    sweep = 360.0 - gap

    if shadow:
        # Soft ambient depth — light from top-left (Fluent / Win icon guidance).
        ctx.save()
        ctx.translate(0.022 * S, 0.032 * S)
        ctx.set_source_rgba(0, 0, 0, 0.22)
        ctx.set_line_width(w_o * 1.05)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        _arc_path(ctx, cx, cy, r_o, start, sweep)
        ctx.stroke()
        ctx.set_line_width(w_i)
        ctx.new_sub_path()
        ctx.arc(cx, cy, r_i, 0, 2 * math.pi)
        ctx.stroke()
        ctx.arc(cx, cy, r_d, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

    # Outer C — primary layer
    if layered_white:
        ctx.set_source_rgba(1.0, 0.98, 0.96, 1.0)  # warm white body
    else:
        ctx.set_source_rgba(*_rgba(fill_rgb))
    ctx.set_line_width(w_o)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    _arc_path(ctx, cx, cy, r_o, start, sweep)
    ctx.stroke()

    if soft_highlight:
        # Specular rim on the upper-left arc (fluid / M365 cue).
        if layered_white:
            ctx.set_source_rgba(1, 1, 1, 0.85)
        else:
            ctx.set_source_rgba(1, 1, 1, 0.40)
        ctx.set_line_width(w_o * 0.38)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        _arc_path(ctx, cx, cy, r_o, 200, 105)
        ctx.stroke()

    # Inner ring — slightly translucent when layered (separate elevation).
    if layered_white:
        ctx.set_source_rgba(1, 1, 1, 0.90)
    else:
        ctx.set_source_rgba(*_rgba(fill_rgb))
    ctx.set_line_width(w_i)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.new_sub_path()
    ctx.arc(cx, cy, r_i, 0, 2 * math.pi)
    ctx.stroke()

    # Centre dot — full opacity focal point
    if layered_white:
        ctx.set_source_rgba(1, 1, 1, 1.0)
    else:
        ctx.set_source_rgba(*_rgba(fill_rgb))
    ctx.arc(cx, cy, r_d, 0, 2 * math.pi)
    ctx.fill()


def _surface_to_pil(surface):
    """ARGB32 Cairo surface → RGBA PIL Image."""
    w, h = surface.get_width(), surface.get_height()
    buf = surface.get_data()
    img = Image.frombuffer('RGBA', (w, h), bytes(buf), 'raw', 'BGRA', 0, 1)
    return img.copy()


def render_tile(S=512):
    """White layered mark on Fluent orange-gradient squircle."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, S, S)
    ctx = cairo.Context(surface)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)

    # Rich analogous plate gradient ~120° (M365 2024: exaggerated analogous).
    pat = cairo.LinearGradient(0.05 * S, 0.02 * S, 0.98 * S, 0.98 * S)
    pat.add_color_stop_rgba(0.0, *_rgba(ORANGE_LIGHT))
    pat.add_color_stop_rgba(0.28, *_rgba(ORANGE_MID))
    pat.add_color_stop_rgba(0.62, *_rgba(ORANGE))
    pat.add_color_stop_rgba(1.0, *_rgba(ORANGE_DEEP))
    _squircle_path(ctx, 0, 0, S, S, CORNER_RATIO * S)
    ctx.set_source(pat)
    ctx.fill()

    # Soft inner light wash (top-left) + edge falloff — depth without chrome.
    vig = cairo.RadialGradient(
        0.34 * S, 0.30 * S, 0.08 * S, 0.52 * S, 0.55 * S, 0.78 * S
    )
    vig.add_color_stop_rgba(0.0, 1, 1, 1, 0.18)
    vig.add_color_stop_rgba(0.45, 1, 1, 1, 0.04)
    vig.add_color_stop_rgba(1.0, 0, 0, 0, 0.14)
    _squircle_path(ctx, 0, 0, S, S, CORNER_RATIO * S)
    ctx.set_source(vig)
    ctx.fill()

    cx = cy = S / 2.0
    _draw_mark_layers(
        ctx, cx, cy, S, WHITE, shadow=True, soft_highlight=True, layered_white=True
    )
    return _surface_to_pil(surface)


def render_mark(S=512, color=ORANGE, *, with_gradient=False):
    """Mark on transparent. Optional soft analogous gradient fill."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, S, S)
    ctx = cairo.Context(surface)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)
    cx = cy = S / 2.0

    if with_gradient:
        # Soft elevation only — no glossy tubular rim (Fluent 2 is layered, not bevelled).
        ctx.save()
        ctx.translate(0.010 * S, 0.014 * S)
        ctx.set_source_rgba(*_rgba(ORANGE_DEEP, 0.35))
        ctx.set_line_width(W_OUTER * S)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        start = GAP_DEG / 2.0
        sweep = 360.0 - GAP_DEG
        _arc_path(ctx, cx, cy, R_OUTER * S, start, sweep)
        ctx.stroke()
        ctx.set_line_width(W_INNER * S)
        ctx.new_sub_path()
        ctx.arc(cx, cy, R_INNER * S, 0, 2 * math.pi)
        ctx.stroke()
        ctx.arc(cx, cy, R_DOT * S, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        # Primary body in Radiant Orange; light analogous rim on upper-left only.
        _draw_mark_layers(ctx, cx, cy, S, ORANGE, shadow=False)
        ctx.set_source_rgba(*_rgba(ORANGE_LIGHT, 0.55))
        ctx.set_line_width(W_OUTER * S * 0.28)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        _arc_path(ctx, cx, cy, R_OUTER * S, 205, 95)
        ctx.stroke()
        return _surface_to_pil(surface)

    _draw_mark_layers(ctx, cx, cy, S, color, shadow=False)
    return _surface_to_pil(surface)


def render_favicon(S=64):
    """Compact tile: soft gradient plate + white mark (browser / small)."""
    return render_tile(S)


def _text_width(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def render_lockup(mark_color, body_color, *, vertical=False):
    """Stacked wordmark lockup — Fluent geometric sans, orange initials."""
    font_px = 66 if vertical else 70
    font = _find_font(font_px)
    line_step = int(font_px * 1.28)

    # Measure on a scratch image.
    scratch = Image.new('RGBA', (8, 8), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(scratch)
    max_w = max(_text_width(d0, w, font) for w in WORDS)

    if vertical:
        mark_vis = 0.62 * max_w
        # Full canvas size so visible outer diameter ≈ mark_vis
        mark_box = max(int(mark_vis / (2 * R_OUTER)), 64)
        pad_x, pad_top, gap, pad_bot = 44, 40, 40, 44
        text_h = line_step * len(WORDS)
        W = int(max(mark_vis, max_w) + 2 * pad_x)
        H = int(pad_top + mark_vis + gap + text_h + pad_bot)
        img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        mark = render_mark(
            mark_box, mark_color, with_gradient=(mark_color == ORANGE)
        )
        mx = (W - mark.size[0]) // 2
        my = int(pad_top - (mark.size[0] - mark_vis) / 2)
        img.alpha_composite(mark, (mx, max(my, 0)))
        draw = ImageDraw.Draw(img)
        block_x = (W - max_w) / 2.0
        y = pad_top + mark_vis + gap
        for word in WORDS:
            first, rest = word[0], word[1:]
            draw.text((block_x, y), first, font=font, fill=ORANGE + (255,))
            fw = _text_width(draw, first, font)
            draw.text((block_x + fw, y), rest, font=font, fill=body_color + (255,))
            y += line_step
        return img

    # Horizontal
    mark_s = 320
    mark_vis = 2 * R_OUTER * mark_s
    pad_x, gap, H = 30, 40, 360
    text_x = pad_x + mark_vis + gap
    W = int(text_x + max_w + pad_x)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    mark = render_mark(mark_s, mark_color, with_gradient=(mark_color == ORANGE))
    mx = int(pad_x - (mark_s - mark_vis) / 2)
    my = (H - mark_s) // 2
    img.alpha_composite(mark, (mx, my))
    draw = ImageDraw.Draw(img)
    total_h = line_step * len(WORDS)
    y = (H - total_h) / 2.0
    for word in WORDS:
        first, rest = word[0], word[1:]
        draw.text((text_x, y), first, font=font, fill=ORANGE + (255,))
        fw = _text_width(draw, first, font)
        draw.text((text_x + fw, y), rest, font=font, fill=body_color + (255,))
        y += line_step
    return img


def write_ico(path, sizes=(16, 24, 32, 48, 64, 128, 256)):
    """PNG-compressed multi-size ICO (Windows-compatible)."""
    entries = []
    for s in sizes:
        tile = render_tile(s)
        bio = BytesIO()
        tile.save(bio, format='PNG')
        entries.append((s, bio.getvalue()))

    out = bytearray()
    out += struct.pack('<HHH', 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    for s, data in entries:
        w_b = 0 if s >= 256 else s
        h_b = 0 if s >= 256 else s
        out += struct.pack('<BBBBHHII', w_b, h_b, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    for _, data in entries:
        out += data
    with open(path, 'wb') as f:
        f.write(out)


def save_png(img, path):
    img.save(path, format='PNG', optimize=True)
    print('  {}  ({}x{})'.format(os.path.basename(path), img.width, img.height))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        '--out-dir',
        default=os.path.join(os.path.dirname(__file__), '..', 'construction_app', 'resources'),
        help='Output directory (default: construction_app/resources)',
    )
    args = ap.parse_args(argv)
    out = os.path.abspath(args.out_dir)
    os.makedirs(out, exist_ok=True)
    print('Generating Fluent 2 ACO brand assets into', out)

    save_png(render_tile(512), os.path.join(out, 'logo_square.png'))
    save_png(render_mark(512, WHITE), os.path.join(out, 'logo_square_white.png'))
    save_png(
        render_mark(512, ORANGE, with_gradient=True),
        os.path.join(out, 'logo_mark.png'),
    )
    save_png(
        render_lockup(ORANGE, INK, vertical=False),
        os.path.join(out, 'logo_rectangle.png'),
    )
    save_png(
        render_lockup(WHITE, WHITE, vertical=False),
        os.path.join(out, 'logo_rectangle_white.png'),
    )
    save_png(
        render_lockup(ORANGE, INK, vertical=True),
        os.path.join(out, 'logo_vertical.png'),
    )
    save_png(
        render_lockup(WHITE, WHITE, vertical=True),
        os.path.join(out, 'logo_vertical_white.png'),
    )
    ico_path = os.path.join(out, 'app.ico')
    write_ico(ico_path)
    print('  app.ico  (sizes: 16, 24, 32, 48, 64, 128, 256)')
    save_png(render_favicon(64), os.path.join(out, 'favicon.png'))
    print('Done.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
