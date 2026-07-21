"""Quantity-takeoff maths (pure, stdlib) — the calculation half of a
Bluebeam-style on-drawing takeoff.

A takeoff measures quantities off a scaled drawing: run a **polyline** along a
wall to get its length, trace a **polygon** around a slab to get its area (times
a depth for volume), or drop **count** points on each door. The only trick is the
**scale**: the user calibrates it once by drawing a line of known real length,
which gives *real units per pixel*; every measurement then converts from pixels
to metres/feet with that factor (areas by the square of it).

This module is the geometry and the conversion — no tkinter, no image, no
database — so it is exact and unit-testable. Points are ``(x, y)`` pixel pairs
from the canvas. Lengths use segment sums; areas use the shoelace formula.
"""

import math

LENGTH, AREA, COUNT, VOLUME = 'length', 'area', 'count', 'volume'
KINDS = (LENGTH, AREA, COUNT, VOLUME)

# A sensible default unit per measurement kind, by the calibrated linear unit.
UNIT_FOR = {
    LENGTH: {'m': 'm', 'ft': 'ft', 'mm': 'mm'},
    AREA: {'m': 'sqm', 'ft': 'sqft', 'mm': 'sqmm'},
    VOLUME: {'m': 'cum', 'ft': 'cft', 'mm': 'cumm'},
    COUNT: {'m': 'nos', 'ft': 'nos', 'mm': 'nos'},
}


def distance(p, q):
    """Pixel distance between two ``(x, y)`` points."""
    return math.hypot(q[0] - p[0], q[1] - p[1])


def polyline_length(points):
    """Sum of segment lengths along an open polyline, in pixels."""
    pts = list(points or [])
    return sum(distance(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def polygon_area(points):
    """Absolute area of a closed polygon (shoelace), in pixels². The polygon is
    implicitly closed from the last point back to the first; winding direction
    doesn't matter."""
    pts = list(points or [])
    if len(pts) < 3:
        return 0.0
    s = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def scale_from(pixel_length, real_length):
    """Real units per pixel from a calibration line: draw a line over a known
    dimension, tell it the real length, get the factor. 0 if degenerate."""
    if pixel_length <= 0 or real_length <= 0:
        return 0.0
    return float(real_length) / float(pixel_length)


def length_quantity(points, scale):
    return polyline_length(points) * float(scale or 0)


def area_quantity(points, scale):
    return polygon_area(points) * float(scale or 0) ** 2


def volume_quantity(points, scale, depth):
    return area_quantity(points, scale) * float(depth or 0)


def count_quantity(points):
    return float(len(points or []))


def measure(kind, points, scale=0.0, depth=0.0):
    """Quantity for a measurement of ``kind`` from its ``points`` and the
    calibrated ``scale`` (real units/pixel). ``depth`` applies to volume only."""
    if kind == LENGTH:
        return round(length_quantity(points, scale), 4)
    if kind == AREA:
        return round(area_quantity(points, scale), 4)
    if kind == VOLUME:
        return round(volume_quantity(points, scale, depth), 4)
    if kind == COUNT:
        return count_quantity(points)
    return 0.0


def unit_for(kind, linear_unit):
    """The measurement's unit given the calibrated linear unit (m/ft/mm)."""
    return UNIT_FOR.get(kind, {}).get(linear_unit, linear_unit or '')


def min_points(kind):
    """Points needed before a measurement of ``kind`` is meaningful."""
    if kind == AREA or kind == VOLUME:
        return 3
    if kind == LENGTH:
        return 2
    return 1        # count


def totals_by_unit(items):
    """Sum quantities by unit across a list of ``{'unit', 'quantity'}`` dicts —
    the takeoff footing (e.g. 42.5 sqm, 18 nos, 63.2 m)."""
    out = {}
    for it in items or []:
        u = (it.get('unit') or '').strip()
        try:
            out[u] = round(out.get(u, 0.0) + float(it.get('quantity') or 0), 4)
        except (TypeError, ValueError):
            continue
    return out
