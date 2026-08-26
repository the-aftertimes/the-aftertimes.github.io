"""Wiring of the learning loop into run.py: build_avoid_block must never raise."""
import run as run_mod

CFG_ON = {"enabled": True, "window": 30, "min_count": 3, "avoid_char_cap": 1200,
          "exemplar_cap": 24, "proposals_weekday": 0}


def _recs(n, phrase):
    return [{"run_date": f"2026-08-{i + 1:02d}",
             "dispatch": {"headline": "H", "body": f"{phrase} number {i}.",
                          "domain": "law",
                          "dateline": {"place": "P", "year": 2500,
                                       "years_from_now": 474}}}
            for i in range(n)]


def test_build_avoid_block_finds_a_repeated_phrase():
    block = run_mod.build_avoid_block(_recs(5, "the council sealed the shaft"),
                                      CFG_ON)
    assert "council sealed" in block


def test_build_avoid_block_is_empty_when_disabled():
    recs = _recs(5, "the council sealed the shaft")
    assert run_mod.build_avoid_block(recs, dict(CFG_ON, enabled=False)) == ""


def test_build_avoid_block_never_raises_on_bad_input():
    """A trend-spotting fault must never take the daily publish down with it."""
    assert run_mod.build_avoid_block([{"broken": True}], CFG_ON) == ""


def test_run_passes_the_word_list_into_the_critic():
    """The plainness check no-ops when `common_words` is missing from the
    context, so a silent unwiring would look exactly like clean prose. This
    repo has shipped config pointing at code nothing calls before - assert the
    wiring, not just the function."""
    import inspect
    src = inspect.getsource(run_mod)
    assert '"common_words": load_common_words()' in src


def test_the_word_list_loads_and_holds_plain_english():
    from common import load_common_words
    words = load_common_words()
    assert len(words) > 20_000
    for plain in ("chest", "drill", "spoon", "vault", "morning"):
        assert plain in words
    for hard in ("apothecary", "chrism", "vespers", "thorax", "girder"):
        assert hard not in words


# --- proposals.py is CALLED now ---------------------------------------------
# It was written, documented and tested for a month while nothing invoked it,
# and settings.yaml carried a proposals_weekday pointing at a Monday run that did
# not exist. Wired 26/08/2026; these guard the wiring, not the document.

import datetime


def _lcfg(weekday):
    return {"enabled": True, "window": 30, "min_count": 3, "avoid_char_cap": 1200,
            "exemplar_cap": 24, "proposals_weekday": weekday}


def test_proposals_are_written_on_the_configured_weekday(tmp_path, monkeypatch):
    today = datetime.date(2026, 8, 24)          # a Monday
    written = {}
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    out = run_mod.maybe_write_proposals(_recs(4, "the council sealed the shaft"),
                                        _lcfg(today.weekday()), today)
    assert out == "docs/proposals.md"
    assert (tmp_path / "docs/proposals.md").read_text(encoding="utf-8")


def test_no_proposals_on_any_other_day(tmp_path, monkeypatch):
    today = datetime.date(2026, 8, 25)          # a Tuesday
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    assert run_mod.maybe_write_proposals([], _lcfg(0), today) is None
    assert not (tmp_path / "docs/proposals.md").exists()


def test_the_kill_switch_stops_it(tmp_path, monkeypatch):
    today = datetime.date(2026, 8, 24)
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    cfg = _lcfg(today.weekday()); cfg["enabled"] = False
    assert run_mod.maybe_write_proposals([], cfg, today) is None


def test_a_proposals_failure_never_takes_down_the_publish(tmp_path, monkeypatch):
    """It is a weekly nicety attached to the daily publish path."""
    today = datetime.date(2026, 8, 24)
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(run_mod.proposals, "build",
                        lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    assert run_mod.maybe_write_proposals([], _lcfg(today.weekday()), today) is None


def test_the_daily_workflow_actually_commits_the_document():
    """Writing it without committing it is the same failure in a new costume."""
    import os
    wf = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), ".github/workflows/daily.yml"),
        encoding="utf-8").read()
    assert "docs/proposals.md" in wf
