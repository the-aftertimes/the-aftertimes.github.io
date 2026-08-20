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


# --- Cloudflare retry -------------------------------------------------------
# 20/08/2026: a redraw died on a bare 429. The free image tier is a short rolling
# window, not a daily allowance, so waiting is the fix and giving up is not.

def _fake_urlopen(codes, sleeps):
    """Raise the given HTTP codes in order, then succeed."""
    import urllib.error
    seq = list(codes)

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"success": true, "result": {"image": "eA=="}}'

    def opener(req, timeout=None):
        if seq:
            raise urllib.error.HTTPError("u", seq.pop(0), "m", {}, None)
        return _Resp()
    return opener


def test_a_429_is_retried_and_can_succeed(monkeypatch):
    import json as _json
    import illustrate
    waits = []
    monkeypatch.setattr(illustrate.time, "sleep", waits.append)
    monkeypatch.setattr(illustrate.urllib.request, "urlopen",
                        _fake_urlopen([429], waits))
    monkeypatch.setattr(illustrate.json, "load",
                        lambda fh: _json.loads(fh.read().decode()))
    out = illustrate._post_with_retry(object(), {"timeout": 1})
    assert out == {"success": True, "result": {"image": "eA=="}}
    assert waits[:1] == [20], "first retry should back off before trying again"


def test_retries_are_bounded(monkeypatch):
    import illustrate
    monkeypatch.setattr(illustrate.time, "sleep", lambda s: None)
    monkeypatch.setattr(illustrate.urllib.request, "urlopen",
                        _fake_urlopen([429, 429, 429, 429], []))
    assert illustrate._post_with_retry(object(), {"timeout": 1}) is None


def test_a_bad_token_is_not_retried(monkeypatch):
    """403 is a credentials problem. Retrying it burns quota and delays an
    honest failure - the caller can then fall back or fail fast."""
    import illustrate
    calls = []
    monkeypatch.setattr(illustrate.time, "sleep",
                        lambda s: calls.append(s))
    monkeypatch.setattr(illustrate.urllib.request, "urlopen",
                        _fake_urlopen([403], []))
    assert illustrate._post_with_retry(object(), {"timeout": 1}) is None
    assert calls == [], "a 403 must not sleep or retry"


def test_background_figures_are_allowed_but_crowds_are_not():
    """20/08/2026. The negative block used to say "no background figures" while
    depict was putting the scene's other people in `setting` - the two halves of
    the prompt contradicted each other and flux picked a side. Charlie saw the
    result and kept it: "it actually looks fine here with multiple figures"."""
    import illustrate
    out = illustrate.build_prompt({"headline": "H", "scene": "s"},
                                  {"subject": "a woman at a tripod",
                                   "setting": "her family lined up behind her"})
    assert "no background figures" not in out
    assert "may stand behind them" in out
    # the thing the cap was actually protecting against must still be banned
    assert "No dense crowd" in out and "competing with the subject" in out
