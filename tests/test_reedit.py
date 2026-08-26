"""Re-editing a published dispatch must change prose and preserve everything else.

22/08/2026. Rewriting a dated newspaper's back numbers is an editorial act, so
what these guard is not "did the rewrite land" but "what survived it": the
superseded text, the dateline, the picture, and the front page when an older
dispatch is the one being edited.
"""
import json
import os

import pytest

import reedit


RECORD = {
    "run_date": "2026-08-01",
    "run_time": "2026-08-01T20:00:00+00:00",
    "dispatch": {
        "headline": "Tycho Mayor Who Faked Clumsiness Dies",
        "body": "He governed for thirty years by spilling soup. " * 6,
        "scene": "The mayor on a padded floor.",
        "domain": "politics",
        "dateline": {"place": "Tycho Rim", "year": 2400, "month": 8, "day": 3,
                     "years_from_now": 374},
        "glossary": [],
        "brief": {"subject": "the coach"},
        "image": "assets/img/2026-08-01.jpg",
    },
    "meta": {"run_time": "2026-08-01T20:00:00+00:00",
             "timezone": "Australia/Sydney", "tagline": "t",
             "site_name": "The Aftertimes", "signup_form_url": "", "edition": 4,
             "base_url": "https://example.invalid", "locator_deep_max": 4000},
}

REWRITE = {"headline": "New Headline", "body": "A better body. " * 6}


class _NullArchive:
    def build(self):
        return "archive.html"


class _Repo:
    def __init__(self, path, store):
        self.path, self.store = path, store

    def __truediv__(self, other):
        return self.path / other


@pytest.fixture
def repo(tmp_path, monkeypatch):
    for sub in ("data/dispatches", "d"):
        os.makedirs(tmp_path / sub, exist_ok=True)
    (tmp_path / "index.html").write_text("FRONT PAGE UNTOUCHED", encoding="utf-8")
    store = {"data/dispatches/2026-08-01.json": json.loads(json.dumps(RECORD))}
    monkeypatch.setattr(reedit, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(reedit, "read_json",
                        lambda p, default=None: json.loads(json.dumps(store[p]))
                        if p in store else default)
    monkeypatch.setattr(reedit, "write_json",
                        lambda p, o: store.__setitem__(p, json.loads(json.dumps(o))))
    monkeypatch.setattr(reedit, "_latest_date",
                        lambda: max(k.split("/")[-1][:-5] for k in store))
    monkeypatch.setattr(reedit, "archive_mod", _NullArchive())
    return _Repo(tmp_path, store)


def _accept(monkeypatch, accepted=True):
    def fake(dispatch, context, qcfg, settings):
        out = dict(dispatch)
        if accepted:
            out.update(REWRITE)
        return out, {"revision_accepted": accepted, "critique": "flat kicker"}
    monkeypatch.setattr(reedit, "maybe_revise", fake)


def test_the_superseded_text_is_kept(repo, monkeypatch):
    """A dated paper that silently changes its own back numbers is doing
    something worse than publishing a flat joke."""
    _accept(monkeypatch)
    assert reedit.reedit("2026-08-01") == 0
    rec = repo.store["data/dispatches/2026-08-01.json"]
    assert len(rec["revisions"]) == 1
    old = rec["revisions"][0]
    assert old["headline"] == RECORD["dispatch"]["headline"]
    assert old["body"] == RECORD["dispatch"]["body"]
    assert old["reason"] == "flat kicker" and old["replaced_at"]
    assert rec["dispatch"]["headline"] == "New Headline"


def test_only_prose_fields_change(repo, monkeypatch):
    """A re-edit must not be able to turn one dispatch into a different one."""
    _accept(monkeypatch)
    reedit.reedit("2026-08-01")
    after = repo.store["data/dispatches/2026-08-01.json"]["dispatch"]
    for field in ("dateline", "domain", "glossary"):
        assert after[field] == RECORD["dispatch"][field], field


def test_the_picture_is_left_alone(repo, monkeypatch):
    """The illustration is expensive and often hand-corrected. A prose pass has
    no business discarding it - and that includes the SCENE LINE it is drawn
    from. A 22/08 dry run had the editor return the word "OBITUARIES" as the
    scene, which would have drawn the next redraw from a section label."""
    _accept(monkeypatch)
    reedit.reedit("2026-08-01")
    after = repo.store["data/dispatches/2026-08-01.json"]["dispatch"]
    assert after["image"] == RECORD["dispatch"]["image"]
    assert after["brief"] == RECORD["dispatch"]["brief"]
    assert after["scene"] == RECORD["dispatch"]["scene"]


def test_a_rejected_revision_writes_nothing(repo, monkeypatch):
    _accept(monkeypatch, accepted=False)
    assert reedit.reedit("2026-08-01") == 0
    rec = repo.store["data/dispatches/2026-08-01.json"]
    assert "revisions" not in rec
    assert rec["dispatch"]["headline"] == RECORD["dispatch"]["headline"]


def test_dry_run_changes_nothing(repo, monkeypatch):
    _accept(monkeypatch)
    assert reedit.reedit("2026-08-01", dry=True) == 0
    rec = repo.store["data/dispatches/2026-08-01.json"]
    assert "revisions" not in rec
    assert rec["dispatch"]["headline"] == RECORD["dispatch"]["headline"]
    assert (repo / "index.html").read_text(encoding="utf-8") == "FRONT PAGE UNTOUCHED"


def test_editing_an_older_dispatch_leaves_the_front_page_alone(repo, monkeypatch):
    repo.store["data/dispatches/2026-08-02.json"] = RECORD
    _accept(monkeypatch)
    reedit.reedit("2026-08-01")
    assert (repo / "index.html").read_text(encoding="utf-8") == "FRONT PAGE UNTOUCHED"


def test_repeated_edits_accumulate_history(repo, monkeypatch):
    _accept(monkeypatch)
    reedit.reedit("2026-08-01")
    reedit.reedit("2026-08-01")
    assert len(repo.store["data/dispatches/2026-08-01.json"]["revisions"]) == 2


def test_an_unknown_date_is_refused(repo):
    assert reedit.reedit("1999-01-01") == 1


# --- the archaic batch, and its quota gate ----------------------------------
# 26/08/2026. "Run it after 20:13 UTC" was a TODO note, which is exactly the kind
# of instruction that survives nowhere else and gets forgotten. It is code now.

from datetime import datetime, timezone


def test_the_gate_shuts_before_the_cron_on_an_unfiled_day(monkeypatch):
    monkeypatch.setattr(reedit, "read_json", lambda p, default=None: None)
    ok, why = reedit.quota_window_open(
        datetime(2026, 8, 26, 12, 48, tzinfo=timezone.utc))
    assert ok is False and "before 20:13" in why


def test_the_gate_opens_after_the_cron(monkeypatch):
    monkeypatch.setattr(reedit, "read_json", lambda p, default=None: None)
    ok, why = reedit.quota_window_open(
        datetime(2026, 8, 26, 20, 14, tzinfo=timezone.utc))
    assert ok is True and "past 20:13" in why


def test_the_gate_opens_early_once_the_day_has_filed(monkeypatch):
    """The hour is a proxy; what actually matters is whether the dispatch that
    the batch would compete with has already been written."""
    monkeypatch.setattr(reedit, "read_json",
                        lambda p, default=None: {"dispatch": {}})
    ok, why = reedit.quota_window_open(
        datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc))
    assert ok is True and "has filed" in why


def test_archaic_selects_by_measurement_not_by_date_range():
    """The TODO said "the six pre-04/08 pieces". Two of the real six are 08/08
    and 14/08, and 29/07 and 02/08 are clean - the remembered range was wrong."""
    dates = reedit.archaic_dates()
    assert "2026-08-14" in dates and "2026-08-08" in dates
    assert "2026-07-29" not in dates and "2026-08-02" not in dates
