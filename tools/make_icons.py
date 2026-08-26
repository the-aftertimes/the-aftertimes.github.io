"""Rasterise assets/favicon.svg into the four icon files.

    python tools/make_icons.py

These four were made by hand once, which is why the palette change on 26/08/2026
left them behind: the bone-paper hex moved #f4efe3 -> #eeece5 across all 36 text
files and the "A" glyph in the icons stayed on the old colour. This script exists
so the next palette change is one command rather than a rediscovery.

Two targets that want OPPOSITE things:

- **Browser tabs** (favicon.ico, favicon-192.png, favicon-48.png) want the corners
  TRANSPARENT, so the rounded tile reads as a tile rather than as a square with
  four light dots on a dark tab bar.
- **apple-touch-icon.png** wants NO transparency and NO rounding: iOS applies its
  own mask and paints anything transparent BLACK. So it is drawn full-bleed in the
  tile colour with square corners and iOS does the rounding.

Both conventions were already correct in the hand-made files; this reproduces them
rather than inventing them.

**This SVG draws its glyph with `<text font-family="Georgia, serif">`, so the
output depends on the rendering machine having Georgia.** It does on Windows and
macOS; a Linux box or a CI runner will silently substitute a different serif and
produce a visibly different "A". Run this on a laptop, eyeball the result, and
commit it - do not wire it into Actions. (The hub's equivalent script is safe to
run anywhere because its mark is pure geometry.)

Rasterised with Playwright rather than a native SVG library, so it needs nothing
beyond what the thumbnail tooling already installs.
"""

import io
import re
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
SVG = (OUT / "favicon.svg").read_text(encoding="utf-8")

# The tile colour, read from the SVG rather than repeated here - one source of truth.
TILE = re.search(r'<rect[^>]*fill="(#[0-9a-fA-F]{6})"', SVG).group(1)

# apple-touch: same glyph, full-bleed tile, square corners.
SVG_SQUARE = re.sub(r'\srx="\d+"', '', SVG, count=1)

ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128)]


def render(pw, svg: str, size: int, transparent: bool) -> Image.Image:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": size, "height": size})
    pg.set_content(
        f"<style>html,body{{margin:0;padding:0;background:transparent}}"
        f"svg{{display:block;width:{size}px;height:{size}px}}</style>{svg}"
    )
    png = pg.screenshot(omit_background=transparent)
    b.close()
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main():
    with sync_playwright() as pw:
        big = render(pw, SVG, 192, True)
        big.save(OUT / "favicon-192.png")
        big.resize((48, 48), Image.LANCZOS).save(OUT / "favicon-48.png")
        # A real multi-size .ico: 16 is what a tab actually draws.
        big.save(OUT / "favicon.ico", sizes=ICO_SIZES)

        touch = render(pw, SVG_SQUARE, 180, False)
        flat = Image.new("RGB", touch.size, TILE)
        flat.paste(touch, mask=touch.split()[3])
        flat.save(OUT / "apple-touch-icon.png")

    print(f"tile {TILE}")
    for f in ("favicon-192.png", "favicon-48.png", "favicon.ico", "apple-touch-icon.png"):
        im = Image.open(OUT / f).convert("RGBA")
        w, h = im.size
        print(f"  {f:22} {w}x{h}  corner={im.getpixel((0, 0))}")


if __name__ == "__main__":
    main()
