"""Bounded rectangle coverage for split native full-screen windows."""
import math
from itertools import islice

MAX_SCAN_WINDOWS = 512
MAX_WINDOWS_PER_OWNER = 64


def _edges(rect):
    x, y, w, h = rect
    if w <= 0 or h <= 0 or not all(math.isfinite(v) for v in rect):
        return None
    right, bottom = x + w, y + h
    return (x, y, right, bottom) if math.isfinite(right) and math.isfinite(bottom) else None


def rectangles_cover(display, rectangles):
    """True only when the clipped union covers every point of the display.

    Sweep each vertical strip bounded by a rectangle edge and merge its covered
    y intervals. No pixel tolerance or bounding-box approximation: even a small
    gap prevents yielding. Extra windows beyond the cap cannot add coverage.
    """
    screen = _edges(display)
    if screen is None:
        return False
    x0, y0, x1, y1 = screen
    clipped = []
    for rect in islice(rectangles, MAX_WINDOWS_PER_OWNER):
        edges = _edges(rect)
        if edges is None:
            continue
        left, top, right, bottom = edges
        left, top, right, bottom = max(left, x0), max(top, y0), min(right, x1), min(bottom, y1)
        if left >= right or top >= bottom:
            continue
        if (left, top, right, bottom) == screen:
            return True
        clipped.append((left, top, right, bottom))
    xs = sorted({x0, x1, *(v for r in clipped for v in (r[0], r[2]))})
    for left, right in zip(xs, xs[1:]):
        covered_y = y0
        spans = sorted((top, bottom) for a, top, b, bottom in clipped if a <= left and b >= right)
        for top, bottom in spans:
            if top > covered_y:
                return False
            covered_y = max(covered_y, bottom)
            if covered_y >= y1:
                break
        if covered_y < y1:
            return False
    return True


def full_screen_coverage(displays, windows_by_owner):
    """Keep owners separate; two apps tiled together are not one full-screen app."""
    return [tuple(display) for display in displays
            if any(rectangles_cover(display, rectangles) for rectangles in windows_by_owner.values())]
