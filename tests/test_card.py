"""The social share card.

Written 29/08/2026. The Aftertimes had declared `twitter:card=summary_large_image`
and shipped no `og:image` since launch, so every share of the paper reserved a
large image slot and rendered it empty - worse than carrying no card tags at all,
which at least produces an honest plain link preview. Nobody reported it because a
broken share card is invisible from the site itself; it only shows in somebody
else's Slack.
"""
import io

import pytest
from PIL import Image

import card


def test_the_card_is_the_size_the_platforms_actually_want():
    """1200x630 is the large-card ratio. The engravings are 963x850 - nearly
    square - which is exactly why pointing og:image at the raw illustration was
    never the fix: it would be cropped to ribbons by every platform."""
    raw = card.build("assets/img/2026-08-27.jpg")
    im = Image.open(io.BytesIO(raw))
    assert im.size == (1200, 630)
    assert im.format == "JPEG"


def test_the_paper_colour_matches_the_live_site():
    """The card is the paper the masthead sits on, so it has to be the same bone
    as the site - #eeece5 since 26/08/2026. A card in the old #f4efe3 would look
    like a different publication next to the page it links to."""
    raw = card.build("assets/img/2026-08-27.jpg")
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    # top-left corner is masthead band, never artwork
    assert im.getpixel((4, 4)) == pytest.approx(card.PAPER, abs=3)


def test_the_masthead_is_actually_drawn_not_just_reserved():
    """A band of blank paper would pass a size check. Assert the ink is there:
    the masthead is near-black on bone, so the band must contain dark pixels."""
    raw = card.build("assets/img/2026-08-27.jpg")
    im = Image.open(io.BytesIO(raw)).convert("L")
    band = im.crop((0, 0, 1200, card.BAND_H))
    darkest = min(band.getdata())
    assert darkest < 90, f"masthead band has no ink in it (darkest={darkest})"


def test_a_missing_illustration_still_produces_a_card():
    """A dispatch can publish with no picture - that is what happens when the
    Cloudflare allocation is spent. The card must degrade to masthead-on-paper
    rather than raising, or a pictureless day would also lose its share card."""
    raw = card.build(None)
    im = Image.open(io.BytesIO(raw))
    assert im.size == (1200, 630)


def test_the_artwork_is_not_squashed():
    """Fitting 963x850 into a 1200x~400 well must CROP, never distort. A stretched
    engraving is the tell that someone resized instead of covering, so compare the
    aspect of what was drawn against the source."""
    src = Image.open(card.rel("assets/img/2026-08-27.jpg"))
    box = card.cover_box(src.size, (1200, 630 - card.BAND_H))
    left, top, right, bottom = box
    crop_aspect = (right - left) / (bottom - top)
    target_aspect = 1200 / (630 - card.BAND_H)
    assert crop_aspect == pytest.approx(target_aspect, rel=0.01)
