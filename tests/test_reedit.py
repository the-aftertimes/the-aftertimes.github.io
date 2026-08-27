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

from datetime import datetime, timedelta, timezone


def test_the_gate_shuts_before_the_cron_on_an_unfiled_day(monkeypatch):
    """The expected time is DERIVED, not typed. These two assertions read
    "before 20:13" / "past 20:13" until 27/08/2026, when the primary cron moved
    to 19:13 and they failed - correctly, but for the wrong reason: they were
    pinning a literal, so they would equally have passed on a gate that had
    silently drifted away from the schedule. Derive it and they test the
    relationship instead of the number."""
    monkeypatch.setattr(reedit, "read_json", lambda p, default=None: None)
    hour, minute = reedit._primary_cron_utc()
    ok, why = reedit.quota_window_open(
        datetime(2026, 8, 26, 12, 48, tzinfo=timezone.utc))
    assert ok is False and f"before {hour:02d}:{minute:02d}" in why


def test_the_gate_opens_after_the_cron(monkeypatch):
    monkeypatch.setattr(reedit, "read_json", lambda p, default=None: None)
    hour, minute = reedit._primary_cron_utc()
    after = datetime(2026, 8, 26, hour, minute, tzinfo=timezone.utc) + timedelta(minutes=1)
    ok, why = reedit.quota_window_open(after)
    assert ok is True and f"past {hour:02d}:{minute:02d}" in why


def test_the_gate_opens_early_once_the_day_has_filed(monkeypatch):
    """The hour is a proxy; what actually matters is whether the dispatch that
    the batch would compete with has already been written."""
    monkeypatch.setattr(reedit, "read_json",
                        lambda p, default=None: {"dispatch": {}})
    ok, why = reedit.quota_window_open(
        datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc))
    assert ok is True and "has filed" in why


def test_archaic_selects_by_measurement_not_by_date_range(monkeypatch):
    """Selection is a MEASUREMENT, not a remembered date range - the TODO said
    "the six pre-04/08 pieces" and two of the real six were 08/08 and 14/08.

    Written first against the live archive, which was the wrong scope: it
    asserted that specific dates were faulty, so it went red the moment the
    re-edit fixed them. A test of a selector belongs on synthetic input, or it is
    really a test of today's data.
    """
    archaic = ("The apothecary lit a tallow cresset in the cobblestone "
               "hermitage and intoned the vespers antiphon. ") * 4
    plain = "The crew shut the door and went to lunch. " * 4
    store = {"2026-01-01": archaic, "2026-01-02": plain}
    monkeypatch.setattr(reedit.glob, "glob",
                        lambda pat: [f"{d}.json" for d in store])
    monkeypatch.setattr(reedit, "read_json", lambda p, default=None: {
        "dispatch": {"body": store[os.path.basename(p)[:-5]]}})
    picked = reedit.archaic_dates()
    assert "2026-01-01" in picked, "an archaic body must be selected"
    assert "2026-01-02" not in picked, "a plain body must not be"


def test_archaic_is_empty_once_the_archive_is_clean():
    """The real archive after the 26/08 batch. This one IS about today's data,
    and says so - it is the check that the back-catalogue work actually landed."""
    assert reedit.archaic_dates() == []


def test_the_quota_gate_reads_the_cron_from_the_workflow_not_a_constant():
    """27/08/2026. The gate's cron time was typed into reedit.py as `= 20, 13`.
    The primary cron then moved to 19:13 - to dodge the 20:00-21:00 UTC band
    GitHub had just dropped three of this estate's daily jobs from - and this
    copy was left behind.

    Two real consequences, not cosmetics. The gate would have gone on refusing
    for an hour after the dispatch it protects had already run; and on a day the
    primary was DROPPED it would have opened at 20:13 and let a batch spend the
    Gemini budget the 21:13 backup still needed - which is the exact failure the
    gate was written for on 10/08/2026.

    So the schedule lives in one place. This test fails if a second copy appears
    or the workflow's first cron changes without the derivation still finding
    it."""
    import re
    import reedit
    from common import rel

    with open(rel(".github/workflows/daily.yml"), encoding="utf-8") as fh:
        crons = re.findall(r'cron:\s*"(\d+)\s+(\d+)\s', fh.read())
    assert crons, "daily.yml has no schedule - the gate would silently fall back"

    minute, hour = crons[0]
    assert reedit._primary_cron_utc() == (int(hour), int(minute)), (
        "the quota gate is keyed on a different time than the workflow's first "
        "cron - a batch could spend the budget the dispatch needs")

    assert reedit._primary_cron_utc() != reedit._CRON_FALLBACK or (
        (int(hour), int(minute)) == reedit._CRON_FALLBACK), (
        "derivation returned the fallback, which means it failed to read the "
        "workflow rather than agreeing with it")


def test_every_daily_cron_lands_before_charlie_looks():
    """27/08/2026, and the reason the times moved at all. He opens the site at
    07:55 AEST / 21:55 UTC. On 26/08 GitHub dropped the primary here, in
    photocopy and in the hub's thumbnail job; all three had a backup and every
    backup was scheduled AFTER 07:55, so the estate healed itself once the only
    reader had gone.

    A backup that runs after the reader has left is not a backup. At least one
    cron must land before 21:55 UTC allowing for the 16-22 minutes of scheduler
    lateness this estate consistently shows - so the last useful slot starts no
    later than 21:33."""
    import re
    from common import rel

    with open(rel(".github/workflows/daily.yml"), encoding="utf-8") as fh:
        crons = [(int(h), int(m)) for m, h in
                 re.findall(r'cron:\s*"(\d+)\s+(\d+)\s', fh.read())]
    assert crons, "daily.yml has no schedule"

    LOOKS_AT = 21 * 60 + 55
    LATENESS = 22
    in_time = [(h, m) for h, m in crons if h * 60 + m + LATENESS <= LOOKS_AT]
    assert len(in_time) >= 2, (
        f"only {len(in_time)} of {len(crons)} crons can deliver before 21:55 UTC "
        f"with {LATENESS} min of lateness: {crons}. A dropped primary needs a "
        f"backup he can actually see.")
