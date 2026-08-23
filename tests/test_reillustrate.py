"""Redrawing a published dispatch must change the PICTURE and nothing else.

19/08/2026. The risk this file exists for is not a bad picture, it is a redraw
of an old date quietly rolling the front page back to that day, or a failed
Cloudflare call blanking a good image.
"""
import json
import os

import pytest

import reillustrate as reill


RECORD = {
    "run_date": "2026-08-01",
    "run_time": "2026-08-01T20:00:00+00:00",
    "dispatch": {
        "headline": "Mother Freezes Family For Better Lighting",
        "body": "Seven members of the family were admitted to the cold ward.",
        "scene": "A family in matching jumpers on a hull.",
        "domain": "family",
        "dateline": {"place": "Deep-Lanthorn Nine", "year": 5657, "month": 8,
                     "day": 3, "years_from_now": 3631},
        "glossary": [],
        "brief": {"subject": "old subject", "action": "old action",
                  "setting": "", "light": "", "materials": "", "anomaly": ""},
        "image": "assets/img/2026-08-01.jpg",
    },
    "meta": {"run_time": "2026-08-01T20:00:00+00:00",
             "timezone": "Australia/Sydney", "tagline": "t",
             "site_name": "The Aftertimes", "signup_form_url": "", "edition": 4,
             "base_url": "https://example.invalid", "locator_deep_max": 4000},
}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway repo tree, so a test can never write over the real site.

    Only the file-facing helpers reillustrate imports are redirected - NOT
    common.ROOT, which would send load_settings() looking for config/ in the
    temp dir. The real settings are wanted; the real output files are not.
    """
    for sub in ("data/dispatches", "d", "assets/img"):
        os.makedirs(tmp_path / sub, exist_ok=True)
    (tmp_path / "index.html").write_text("FRONT PAGE UNTOUCHED", encoding="utf-8")
    store = {"data/dispatches/2026-08-01.json": json.loads(json.dumps(RECORD))}

    monkeypatch.setattr(reill, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(reill, "read_json",
                        lambda p, default=None: json.loads(json.dumps(store[p]))
                        if p in store else default)
    monkeypatch.setattr(reill, "write_json",
                        lambda p, obj: store.__setitem__(
                            p, json.loads(json.dumps(obj))))
    monkeypatch.setattr(reill, "_latest_date", lambda: max(
        k.split("/")[-1][:-5] for k in store))
    monkeypatch.setattr(reill, "archive_mod", _NullArchive())
    # A pathlib.Path has no __dict__, so the record store rides alongside it
    # rather than as an attribute on it.
    return _Repo(tmp_path, store)


class _Repo:
    """The temp tree plus the in-memory dispatch store, so a test can assert on
    what was WRITTEN without the assertion depending on real file IO."""

    def __init__(self, path, store):
        self.path, self.store = path, store

    def __truediv__(self, other):
        return self.path / other


class _NullArchive:
    """archive.build() walks the real dispatch tree; not what is under test."""
    def build(self):
        return "archive.html"


def _patch_stages(monkeypatch, brief, image):
    monkeypatch.setattr(reill.depict, "depict", lambda d, s: brief)
    monkeypatch.setattr(reill.illustrate_mod, "generate",
                        lambda d, rd, s, b=None: image)


def test_a_failed_draw_writes_nothing(repo, monkeypatch, capsys):
    """A Cloudflare failure must leave the published record exactly as it was -
    the old picture is better than no picture and a half-updated record."""
    _patch_stages(monkeypatch, {"subject": "new"}, None)
    assert reill.reillustrate("2026-08-01") == 1
    after = repo.store["data/dispatches/2026-08-01.json"]
    assert after["dispatch"]["brief"]["subject"] == "old subject"
    assert after["dispatch"]["image"] == "assets/img/2026-08-01.jpg"
    assert (repo / "index.html").read_text(encoding="utf-8") == "FRONT PAGE UNTOUCHED"


def test_redrawing_an_older_date_leaves_the_front_page_alone(repo, monkeypatch):
    """The dangerous failure: index.html shows ONE dispatch, so rewriting it
    from an older record would roll the whole site back to that day."""
    repo.store["data/dispatches/2026-08-02.json"] = RECORD   # a newer one exists
    _patch_stages(monkeypatch, {"subject": "new subject"},
                  "assets/img/2026-08-01.jpg")
    assert reill.reillustrate("2026-08-01") == 0
    assert (repo / "index.html").read_text(encoding="utf-8") == "FRONT PAGE UNTOUCHED"
    assert (repo / "d/2026-08-01.html").exists()


def test_redrawing_the_latest_updates_the_front_page(repo, monkeypatch):
    _patch_stages(monkeypatch, {"subject": "new subject"},
                  "assets/img/2026-08-01.jpg")
    assert reill.reillustrate("2026-08-01") == 0
    assert "FRONT PAGE" not in (repo / "index.html").read_text(encoding="utf-8")


def test_the_words_are_never_touched(repo, monkeypatch):
    _patch_stages(monkeypatch, {"subject": "new subject"},
                  "assets/img/2026-08-01.jpg")
    reill.reillustrate("2026-08-01")
    after = repo.store["data/dispatches/2026-08-01.json"]["dispatch"]
    for field in ("headline", "body", "scene", "domain", "dateline"):
        assert after[field] == RECORD["dispatch"][field], field
    assert after["brief"]["subject"] == "new subject"


def test_an_unknown_date_is_refused(repo):
    assert reill.reillustrate("1999-01-01") == 1


def test_a_scene_override_changes_the_picture_and_nothing_else(repo, monkeypatch):
    """22/08/2026: a redraw could not fix a picture whose SCENE LINE was the
    fault - depict is handed that line and told to draw it, so the same wrong
    picture came back. The override must reach the brief and leave the prose
    alone."""
    seen = {}
    monkeypatch.setattr(reill.depict, "depict",
                        lambda d, s: seen.setdefault("scene", d["scene"]) and None
                        or {"subject": "the mayor"})
    monkeypatch.setattr(reill.illustrate_mod, "generate",
                        lambda d, rd, s, b=None: "assets/img/2026-08-01.jpg")
    assert reill.reillustrate("2026-08-01", scene="The mayor on the floor.") == 0
    assert seen["scene"] == "The mayor on the floor."
    after = repo.store["data/dispatches/2026-08-01.json"]["dispatch"]
    assert after["scene"] == "The mayor on the floor."
    assert after["body"] == RECORD["dispatch"]["body"]
    assert after["headline"] == RECORD["dispatch"]["headline"]


def test_no_override_keeps_the_stored_scene(repo, monkeypatch):
    seen = {}
    monkeypatch.setattr(reill.depict, "depict",
                        lambda d, s: seen.setdefault("scene", d["scene"]) and None
                        or {"subject": "x"})
    monkeypatch.setattr(reill.illustrate_mod, "generate",
                        lambda d, rd, s, b=None: "assets/img/2026-08-01.jpg")
    reill.reillustrate("2026-08-01")
    assert seen["scene"] == RECORD["dispatch"]["scene"]
