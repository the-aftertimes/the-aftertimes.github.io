import io

from PIL import Image

import illustrate


SETTINGS = {"image": {"enabled": True, "model": "@cf/x", "steps": 8, "timeout": 5,
                      "crop": [0.03, 0.03, 0.97, 0.86], "dir": "assets/img"}}


def _jpeg_bytes(w, h):
    im = Image.new("RGB", (w, h), (200, 190, 170))
    out = io.BytesIO(); im.save(out, format="JPEG"); return out.getvalue()


def test_build_prompt_uses_scene_when_present():
    p = illustrate.build_prompt({
        "headline": "Moon Court Rules on Time",
        "scene": "a bailiff hammers a gavel shaped like a clock face",
    })
    assert "a bailiff hammers a gavel shaped like a clock face" in p
    assert "no text" in p.lower()


def test_build_prompt_falls_back_to_headline_when_no_scene():
    p = illustrate.build_prompt({"headline": "Moon Court Rules on Time"})
    assert "Moon Court Rules on Time" in p
    assert "no text" in p.lower()


def test_generate_none_when_disabled():
    assert illustrate.generate({"headline": "x"}, "2026-07-28",
                               {"image": {"enabled": False}}) is None


def test_generate_none_when_no_creds(monkeypatch):
    monkeypatch.delenv("CF_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    # enabled + creds missing -> _cf_image returns None -> generate returns None, no network
    assert illustrate.generate({"headline": "x"}, "2026-07-28", SETTINGS) is None


def test_generate_saves_cropped_image(monkeypatch, tmp_path):
    raw = _jpeg_bytes(1000, 1000)
    monkeypatch.setattr(illustrate, "_cf_image", lambda *a, **k: raw)
    saved = {}
    monkeypatch.setattr(illustrate, "rel", lambda p: str(tmp_path / p))
    path = illustrate.generate({"headline": "x"}, "2026-07-28", SETTINGS)
    assert path == "assets/img/2026-07-28.jpg"
    out = tmp_path / "assets/img/2026-07-28.jpg"
    assert out.exists()
    w, h = Image.open(out).size
    assert w < 1000 and h < 1000   # cropped smaller than the 1000x1000 source


def test_crop_dimensions():
    raw = _jpeg_bytes(1000, 1000)
    cropped = illustrate._crop(raw, [0.03, 0.03, 0.97, 0.86])
    w, h = Image.open(io.BytesIO(cropped)).size
    assert w == 940 and h == 830
