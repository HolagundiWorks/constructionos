#!/usr/bin/env python3
"""Regenerate ACO brand assets — Fluent 2 / Microsoft 365–inspired.

Cross-platform canonical generator (Cairo + Pillow). Prefer this over the
Windows GDI+ twin ``make-brand.ps1`` when either is available.

Mark (ACO encoded in openings, all Radiant Orange on transparent):
  * Outer ring — open at the **bottom** → reads as **A**
  * Middle ring — open at the **right** → reads as **C**
  * Centre disc — solid → reads as **O**

Tile / lockups keep Fluent 2 soft plate + stacked wordmark cues.

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

# ACO mark geometry (fractions of reference box S).
# Angles are GDI-style: 0° = right, 90° = bottom, clockwise.
R_OUTER = 0.335
W_OUTER = 0.098
R_INNER = 0.155
W_INNER = 0.070
R_DOT = 0.055
GAP_DEG = 78.0                  # fluid open gap
OUTER_GAP_CENTER = 90.0         # bottom → A
INNER_GAP_CENTER = 0.0          # right  → C

WORDS = ('ACCELERATED', 'CONSTRUCTION', 'OPERATIONS')


def _rgba(rgb, a=1.0):
    r, g, b = rgb
    return (r / 255.0, g / 255.0, b / 255.0, a)


def _gap_start_sweep(gap_center_deg, gap_deg=GAP_DEG):
    """Start angle + clockwise sweep so the open gap is centred at gap_center."""
    start = (gap_center_deg + gap_deg / 2.0) % 360.0
    sweep = 360.0 - gap_deg
    return start, sweep


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
    """Stroke an arc clockwise from start_deg (0° = right, 90° = bottom).

    On Cairo image surfaces Y grows downward, so ``arc`` (angles toward +Y)
    matches GDI-style clockwise sweeps.
    """
    a0 = math.radians(start_deg)
    a1 = math.radians(start_deg + sweep_deg)
    ctx.new_sub_path()
    ctx.arc(cx, cy, radius, a0, a1)


def _draw_mark(ctx, cx, cy, S, fill_rgb, *, soft_depth=False):
    """ACO mark: outer A (gap bottom), middle C (gap right), solid O centre.

    Always drawn on the current (typically transparent) surface.
    """
    r_o = R_OUTER * S
    w_o = W_OUTER * S
    r_i = R_INNER * S
    w_i = W_INNER * S
    r_d = R_DOT * S
    o_start, o_sweep = _gap_start_sweep(OUTER_GAP_CENTER)
    i_start, i_sweep = _gap_start_sweep(INNER_GAP_CENTER)

    if soft_depth:
        ctx.save()
        ctx.translate(0.012 * S, 0.016 * S)
        ctx.set_source_rgba(*_rgba(ORANGE_DEEP, 0.28))
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_width(w_o)
        _arc_path(ctx, cx, cy, r_o, o_start, o_sweep)
        ctx.stroke()
        ctx.set_line_width(w_i)
        _arc_path(ctx, cx, cy, r_i, i_start, i_sweep)
        ctx.stroke()
        ctx.arc(cx, cy, r_d, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()

    ctx.set_source_rgba(*_rgba(fill_rgb))
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    # Outer — A (open bottom)
    ctx.set_line_width(w_o)
    _arc_path(ctx, cx, cy, r_o, o_start, o_sweep)
    ctx.stroke()

    # Middle — C (open right)
    ctx.set_line_width(w_i)
    _arc_path(ctx, cx, cy, r_i, i_start, i_sweep)
    ctx.stroke()

    # Centre — O
    ctx.arc(cx, cy, r_d, 0, 2 * math.pi)
    ctx.fill()


def _surface_to_pil(surface):
    """ARGB32 Cairo surface → RGBA PIL Image."""
    w, h = surface.get_width(), surface.get_height()
    buf = surface.get_data()
    img = Image.frombuffer('RGBA', (w, h), bytes(buf), 'raw', 'BGRA', 0, 1)
    return img.copy()


def render_mark(S=512, color=ORANGE, *, soft_depth=False):
    """Orange (or white) ACO mark on transparent background."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, S, S)
    ctx = cairo.Context(surface)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)
    _draw_mark(ctx, S / 2.0, S / 2.0, S, color, soft_depth=soft_depth)
    return _surface_to_pil(surface)


def render_tile(S=512):
    """App tile: orange ACO mark on transparent (no plate — mark is the icon)."""
    return render_mark(S, ORANGE, soft_depth=True)


def render_favicon(S=64):
    """Browser favicon: orange ACO mark on transparent."""
    return render_mark(S, ORANGE, soft_depth=False)


def _text_width(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def render_lockup(mark_color, body_color, *, vertical=False):
    """Stacked wordmark lockup — Fluent geometric sans, orange initials."""
    font_px = 66 if vertical else 70
    font = _find_font(font_px)
    line_step = int(font_px * 1.28)

    scratch = Image.new('RGBA', (8, 8), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(scratch)
    max_w = max(_text_width(d0, w, font) for w in WORDS)

    if vertical:
        mark_vis = 0.62 * max_w
        mark_box = max(int(mark_vis / (2 * R_OUTER)), 64)
        pad_x, pad_top, gap, pad_bot = 44, 40, 40, 44
        text_h = line_step * len(WORDS)
        W = int(max(mark_vis, max_w) + 2 * pad_x)
        H = int(pad_top + mark_vis + gap + text_h + pad_bot)
        img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        mark = render_mark(
            mark_box, mark_color, soft_depth=(mark_color == ORANGE)
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

    mark_s = 320
    mark_vis = 2 * R_OUTER * mark_s
    pad_x, gap, H = 30, 40, 360
    text_x = pad_x + mark_vis + gap
    W = int(text_x + max_w + pad_x)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    mark = render_mark(mark_s, mark_color, soft_depth=(mark_color == ORANGE))
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
    print('Generating ACO brand assets (A/C/O openings, orange on transparent) into', out)

    # App tile / square = orange mark on transparent (no plate).
    save_png(render_tile(512), os.path.join(out, 'logo_square.png'))
    # Dark-rail knockout = white mark on transparent.
    save_png(render_mark(512, WHITE), os.path.join(out, 'logo_square_white.png'))
    save_png(render_mark(512, ORANGE, soft_depth=True), os.path.join(out, 'logo_mark.png'))
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
    write_ico(os.path.join(out, 'app.ico'))
    print('  app.ico  (sizes: 16, 24, 32, 48, 64, 128, 256)')
    save_png(render_favicon(64), os.path.join(out, 'favicon.png'))
    print('Done.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
