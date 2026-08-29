"""Build the social share card for a dispatch.

    python card.py 2026-08-27        # writes assets/card/2026-08-27.jpg

Why this exists: the paper declared `twitter:card=summary_large_image` and shipped
no `og:image` from launch until 29/08/2026, so every share reserved a large image
slot and rendered it empty. That is worse than carrying no card tags at all, which
at least degrades to an honest plain link preview. It went unreported for months
because a broken share card cannot be seen from the site - only from somebody
else's Slack or timeline.

Three decisions worth keeping:

1. **The headline is NOT drawn on the card.** Every platform renders `og:title` as
   text beside the image, so painting it again would duplicate it and force a font
   choice. Leaving it out removes the whole font problem: nothing here needs a
   typeface that has to exist on both a laptop and an Ubuntu runner.
2. **The masthead is the existing `assets/email-masthead.png`**, already rasterised
   from the Fraktur webfont with transparent ink. PIL cannot read woff2, and this
   sidesteps that without converting anything or adding a dependency.
3. **The artwork is COVERED, not resized.** The engravings are 963x850 - nearly
   square - and a card is 1200x630. Scaling to fit would squash them; `cover_box`
   crops the largest correctly-proportioned rectangle instead. This is exactly why
   pointing og:image at the raw illustration was never the fix.

A dispatch with no picture still gets a card: masthead on bone paper. A pictureless
day losing its share card as well would be two failures for the price of one.
"""
from __future__ import annotations

import io
import os
import sys

from PIL import Image, ImageDraw

from common import rel

#: The site's bone paper. Moved from #f4efe3 on 26/08/2026; a card in the old
#: colour would read as a different publication beside the page it links to.
PAPER = (0xEE, 0xEC, 0xE5)

W, H = 1200, 630
#: Height of the masthead band. The rest is artwork.
BAND_H = 210
MASTHEAD = "assets/email-masthead.png"
OUT_DIR = "assets/card"


def cover_box(src_size: tuple[int, int], target: tuple[int, int]) -> tuple[int, int, int, int]:
    """The largest box in `src_size` with `target`'s aspect, centred.

    Centred rather than top-anchored because these engravings put their subject in
    the middle; anchoring to the top reliably cropped heads off during testing.
    """
    sw, sh = src_size
    tw, th = target
    if sw * th > tw * sh:                     # source is wider - trim the sides
        w = round(sh * tw / th)
        left = (sw - w) // 2
        return (left, 0, left + w, sh)
    h = round(sw * th / tw)                   # source is taller - trim top/bottom
    top = (sh - h) // 2
    return (0, top, sw, top + h)


def build(art_path: str | None) -> bytes:
    """Return JPEG bytes for the card. `art_path` may be None or missing."""
    canvas = Image.new("RGB", (W, H), PAPER)

    art_h = H - BAND_H
    full = rel(art_path) if art_path else None
    if full and os.path.exists(full):
        art = Image.open(full).convert("RGB")
        art = art.crop(cover_box(art.size, (W, art_h))).resize((W, art_h), Image.LANCZOS)
        canvas.paste(art, (0, BAND_H))

    mast = Image.open(rel(MASTHEAD)).convert("RGBA")
    # 58% of the width, NOT 78%. At 78% the wordmark scaled to 209px inside a
    # 210px band and sat wall to wall with no air at all - it passed every
    # assertion and looked wrong the moment it was rendered. Sized off the width
    # rather than the height so the proportions survive the masthead PNG being
    # regenerated at a different resolution.
    scale = (W * 0.58) / mast.width
    mast = mast.resize((round(mast.width * scale), round(mast.height * scale)), Image.LANCZOS)
    # Sits slightly above centre: the double rule below needs its own space, and
    # optically-centred type wants to be a touch high in a box.
    canvas.paste(mast, ((W - mast.width) // 2, (BAND_H - mast.height) // 2 - 6), mast)

    # The 3px double rule the masthead carries on the site itself. Without it the
    # band and the artwork just butt together and the join reads as a mistake.
    draw = ImageDraw.Draw(canvas)
    ink = (0x1A, 0x16, 0x11)
    draw.rectangle([0, BAND_H - 9, W, BAND_H - 7], fill=ink)
    draw.rectangle([0, BAND_H - 4, W, BAND_H - 3], fill=ink)

    buf = io.BytesIO()
    canvas.save(buf, "JPEG", quality=86, optimize=True)
    return buf.getvalue()


def write(date: str, art_path: str | None) -> str:
    """Build and save the card. Returns the repo-relative path."""
    relpath = f"{OUT_DIR}/{date}.jpg"
    path = rel(relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(build(art_path))
    return relpath


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python card.py <date>", file=sys.stderr)
        return 2
    date = sys.argv[1]
    art = f"assets/img/{date}.jpg"
    out = write(date, art if os.path.exists(rel(art)) else None)
    print(f">>> CARD {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
