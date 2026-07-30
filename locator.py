"""A small ink-on-bone "locator" chart for each dispatch: a celestial/temporal
plot placing the story relative to now. The dateline places are invented, so
there are no real coordinates - the position is derived deterministically from a
hash of the (scrubbed) place name and year, with the radius scaled by how far in
the future the dispatch is set. Pure functions returning inline SVG; no files,
no API, web only (SVG does not render in email clients).

Deterministic by construction: same dispatch -> byte-identical SVG every time,
so the index page, the permalink and any replay all draw the same chart.
"""
from __future__ import annotations

import hashlib
import math
import re

# Palette mirrors render.py's bone-broadsheet variables.
_INK = "#1a1611"
_MUTED = "#6b5f4d"
_ACCENT = "#7a2b2b"
_RULE = "#cdc3ad"

_CX = _CY = 130.0
_R_MAX = 104.0     # outermost radius the target can sit at
_R_MIN = 24.0      # nearest-future target radius (keeps it clear of the centre)


def _scrub(place: str) -> str:
    """Match render.py's place scrub so the label and the seed agree."""
    return re.sub(r"\s*\(\d{2,}\)\s*$", "", (place or "")).strip()


def _seed(place: str, year: int) -> int:
    digest = hashlib.sha256(f"{place}|{year}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class _Det:
    """Tiny deterministic PRNG (splitmix64) - avoids any global RNG state and is
    stable across Python versions, unlike hash()."""

    def __init__(self, seed: int) -> None:
        self._s = seed & 0xFFFFFFFFFFFFFFFF

    def _next(self) -> int:
        self._s = (self._s + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = self._s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        return z ^ (z >> 31)

    def rand(self) -> float:
        return self._next() / 0x10000000000000000

    def uniform(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self.rand()


def _target_radius(years_from_now: int, deep_max: int) -> float:
    """Log-scaled: near-future sits close in, deep-future near the rim."""
    y = max(1, min(int(years_from_now), deep_max))
    frac = math.log(y) / math.log(max(2, deep_max))
    return _R_MIN + (_R_MAX - _R_MIN) * frac


def _geom(dl: dict, deep_max: int):
    place = _scrub(dl.get("place") or "")
    rng = _Det(_seed(place, int(dl["year"])))
    angle = rng.uniform(0, 2 * math.pi)
    radius = _target_radius(dl.get("years_from_now", 1), deep_max)
    tx = _CX + radius * math.cos(angle)
    ty = _CY + radius * math.sin(angle)
    return place, rng, angle, radius, tx, ty


def _bg_stars(rng: _Det, n: int, keep_out: float = 14.0,
              tx: float = 0.0, ty: float = 0.0):
    """Scatter faint stars inside the plate, avoiding the marked target."""
    pts = []
    tries = 0
    while len(pts) < n and tries < n * 6:
        tries += 1
        a = rng.uniform(0, 2 * math.pi)
        r = math.sqrt(rng.rand()) * (_R_MAX - 4)
        x, y = _CX + r * math.cos(a), _CY + r * math.sin(a)
        if math.hypot(x - tx, y - ty) < keep_out:
            continue
        pts.append((x, y, 0.5 + rng.rand() * 1.1, 0.25 + rng.rand() * 0.5))
    return pts


def _caption(place: str, years: int) -> str:
    if years >= 1000:
        far = f"{round(years / 1000)},000 years hence" if years % 1000 == 0 \
            else f"~{years // 1000},{years % 1000:03d} years hence"
    else:
        far = f"{years} years hence"
    label = place or "Somewhere"
    return label, far


def _svg_open(extra: str = "") -> str:
    # The place label is rendered as an HTML figcaption by render.py (bigger,
    # in the page serif), so the SVG itself is just the chart.
    return (f'<svg viewBox="0 0 260 250" width="220" role="img" '
            f'xmlns="http://www.w3.org/2000/svg" class="locator-svg" {extra}>')


def caption_text(dl: dict):
    """(place label, 'N years hence') for the HTML caption - scrubbed to match
    the drawn chart's seed."""
    return _caption(_scrub(dl.get("place") or ""), int(dl.get("years_from_now", 0)))


# ---------------------------------------------------------------------------
# Variant A - circular celestial plate (astrolabe-style rings + radial spokes)
# ---------------------------------------------------------------------------
def variant_plate(dl: dict, deep_max: int) -> str:
    place, rng, angle, radius, tx, ty = _geom(dl, deep_max)
    label, far = _caption(place, int(dl.get("years_from_now", 0)))
    parts = [_svg_open(f'aria-label="Locator chart: {label}, {far}">')]
    parts.append(f'<title>Locator chart for {label} ({far})</title>')
    # outer double frame
    parts.append(f'<circle cx="{_CX}" cy="{_CY}" r="{_R_MAX + 8:.1f}" fill="none" '
                 f'stroke="{_INK}" stroke-width="1.4"/>')
    parts.append(f'<circle cx="{_CX}" cy="{_CY}" r="{_R_MAX + 4:.1f}" fill="none" '
                 f'stroke="{_INK}" stroke-width="0.6"/>')
    # concentric rings
    for frac in (0.32, 0.62, 0.9):
        parts.append(f'<circle cx="{_CX}" cy="{_CY}" r="{_R_MAX * frac:.1f}" fill="none" '
                     f'stroke="{_RULE}" stroke-width="0.7"/>')
    # radial spokes
    for k in range(12):
        a = k * math.pi / 6
        x2, y2 = _CX + _R_MAX * math.cos(a), _CY + _R_MAX * math.sin(a)
        parts.append(f'<line x1="{_CX}" y1="{_CY}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'stroke="{_RULE}" stroke-width="0.4" opacity="0.6"/>')
    # background stars
    for x, y, r, op in _bg_stars(rng, 46, 16, tx, ty):
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" '
                     f'fill="{_MUTED}" opacity="{op:.2f}"/>')
    # centre "now"
    parts.append(f'<circle cx="{_CX}" cy="{_CY}" r="2.6" fill="none" stroke="{_INK}" '
                 f'stroke-width="1"/>')
    parts.append(f'<text x="{_CX}" y="{_CY + 12:.0f}" text-anchor="middle" '
                 f'font-family="system-ui,sans-serif" font-size="7" fill="{_MUTED}" '
                 f'letter-spacing="1.5">NOW</text>')
    # sight line + marked target
    parts.append(f'<line x1="{_CX}" y1="{_CY}" x2="{tx:.1f}" y2="{ty:.1f}" '
                 f'stroke="{_ACCENT}" stroke-width="0.8" stroke-dasharray="2 2"/>')
    parts.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="8" fill="none" '
                 f'stroke="{_ACCENT}" stroke-width="1"/>')
    parts.append(f'<line x1="{tx - 12:.1f}" y1="{ty:.1f}" x2="{tx + 12:.1f}" y2="{ty:.1f}" '
                 f'stroke="{_ACCENT}" stroke-width="0.7"/>')
    parts.append(f'<line x1="{tx:.1f}" y1="{ty - 12:.1f}" x2="{tx:.1f}" y2="{ty + 12:.1f}" '
                 f'stroke="{_ACCENT}" stroke-width="0.7"/>')
    parts.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="2.4" fill="{_ACCENT}"/>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Variant B - rectangular sky-survey plate (cartographic, corner ticks)
# ---------------------------------------------------------------------------
def variant_survey(dl: dict, deep_max: int) -> str:
    place, rng, angle, radius, tx, ty = _geom(dl, deep_max)
    label, far = _caption(place, int(dl.get("years_from_now", 0)))
    x0, y0, x1, y1 = 18, 18, 242, 242
    parts = [_svg_open(f'aria-label="Locator chart: {label}, {far}">')]
    parts.append(f'<title>Locator chart for {label} ({far})</title>')
    parts.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" '
                 f'fill="none" stroke="{_INK}" stroke-width="1.3"/>')
    parts.append(f'<rect x="{x0 + 4}" y="{y0 + 4}" width="{x1 - x0 - 8}" '
                 f'height="{y1 - y0 - 8}" fill="none" stroke="{_RULE}" stroke-width="0.6"/>')
    # edge coordinate ticks
    for i in range(1, 8):
        gx = x0 + (x1 - x0) * i / 8
        gy = y0 + (y1 - y0) * i / 8
        parts.append(f'<line x1="{gx:.1f}" y1="{y1 - 4}" x2="{gx:.1f}" y2="{y1}" '
                     f'stroke="{_MUTED}" stroke-width="0.6"/>')
        parts.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x0 + 4}" y2="{gy:.1f}" '
                     f'stroke="{_MUTED}" stroke-width="0.6"/>')
    # faint grid
    for i in range(1, 8):
        gx = x0 + (x1 - x0) * i / 8
        gy = y0 + (y1 - y0) * i / 8
        parts.append(f'<line x1="{gx:.1f}" y1="{y0}" x2="{gx:.1f}" y2="{y1}" '
                     f'stroke="{_RULE}" stroke-width="0.3" opacity="0.5"/>')
        parts.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}" '
                     f'stroke="{_RULE}" stroke-width="0.3" opacity="0.5"/>')
    for x, y, r, op in _bg_stars(rng, 52, 15, tx, ty):
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" '
                     f'fill="{_MUTED}" opacity="{op:.2f}"/>')
    # "now" origin marker (bottom-left corner of the survey)
    parts.append(f'<circle cx="{_CX}" cy="{_CY}" r="2.4" fill="none" stroke="{_INK}" '
                 f'stroke-width="1"/>')
    parts.append(f'<text x="{_CX + 5:.0f}" y="{_CY + 3:.0f}" '
                 f'font-family="system-ui,sans-serif" font-size="7" fill="{_MUTED}" '
                 f'letter-spacing="1.5">NOW</text>')
    # boxed target
    parts.append(f'<line x1="{_CX}" y1="{_CY}" x2="{tx:.1f}" y2="{ty:.1f}" '
                 f'stroke="{_ACCENT}" stroke-width="0.7" stroke-dasharray="2 2"/>')
    parts.append(f'<rect x="{tx - 7:.1f}" y="{ty - 7:.1f}" width="14" height="14" '
                 f'fill="none" stroke="{_ACCENT}" stroke-width="1"/>')
    parts.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="2.4" fill="{_ACCENT}"/>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Variant C - minimal time-rings (spare: labelled distance rings, one bearing)
# ---------------------------------------------------------------------------
def variant_rings(dl: dict, deep_max: int) -> str:
    place, rng, angle, radius, tx, ty = _geom(dl, deep_max)
    label, far = _caption(place, int(dl.get("years_from_now", 0)))
    parts = [_svg_open(f'aria-label="Locator chart: {label}, {far}">')]
    parts.append(f'<title>Locator chart for {label} ({far})</title>')
    # a few sparse stars only
    for x, y, r, op in _bg_stars(rng, 18, 16, tx, ty):
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" '
                     f'fill="{_MUTED}" opacity="{op * 0.8:.2f}"/>')
    # distance rings, labelled near / mid / deep
    for frac, name in ((_R_MIN / _R_MAX, "near"), (0.62, "mid"), (0.98, "deep")):
        rr = _R_MAX * frac
        parts.append(f'<circle cx="{_CX}" cy="{_CY}" r="{rr:.1f}" fill="none" '
                     f'stroke="{_RULE}" stroke-width="0.7"/>')
        parts.append(f'<text x="{_CX:.0f}" y="{_CY - rr + 9:.0f}" text-anchor="middle" '
                     f'font-family="system-ui,sans-serif" font-size="6.5" '
                     f'fill="{_MUTED}" letter-spacing="1">{name.upper()}</text>')
    # centre now
    parts.append(f'<circle cx="{_CX}" cy="{_CY}" r="2.4" fill="{_INK}"/>')
    parts.append(f'<text x="{_CX}" y="{_CY + 12:.0f}" text-anchor="middle" '
                 f'font-family="system-ui,sans-serif" font-size="7" fill="{_MUTED}" '
                 f'letter-spacing="1.5">NOW</text>')
    # single bearing to the target
    parts.append(f'<line x1="{_CX}" y1="{_CY}" x2="{tx:.1f}" y2="{ty:.1f}" '
                 f'stroke="{_ACCENT}" stroke-width="1"/>')
    parts.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="3.4" fill="{_ACCENT}"/>')
    parts.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="7" fill="none" '
                 f'stroke="{_ACCENT}" stroke-width="0.7"/>')
    parts.append("</svg>")
    return "".join(parts)




_VARIANTS = {"plate": variant_plate, "survey": variant_survey, "rings": variant_rings}


def render_locator_svg(dl: dict, deep_max: int, variant: str = "plate") -> str:
    """Return the inline SVG for the chosen variant. `dl` should carry the
    already-scrubbed place (render.py scrubs before calling)."""
    return _VARIANTS.get(variant, variant_plate)(dl, deep_max)
