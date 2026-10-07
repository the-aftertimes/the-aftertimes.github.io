import json

import verdict


def test_record_and_read_back(tmp_path, monkeypatch):
    store = tmp_path / "verdicts.json"
    monkeypatch.setattr(verdict, "_PATH", str(store))
    verdict.record("2026-08-04", "good", "kicker lands")
    verdict.record("2026-08-05", "bad", "no target")
    data = json.loads(store.read_text(encoding="utf-8"))
    assert data["2026-08-04"]["verdict"] == "good"
    assert data["2026-08-05"]["note"] == "no target"


def test_recording_the_same_date_twice_overwrites(tmp_path, monkeypatch):
    store = tmp_path / "verdicts.json"
    monkeypatch.setattr(verdict, "_PATH", str(store))
    verdict.record("2026-08-04", "bad", "first call")
    verdict.record("2026-08-04", "good", "changed my mind")
    data = json.loads(store.read_text(encoding="utf-8"))
    assert data["2026-08-04"]["verdict"] == "good"
    assert len(data) == 1


def test_an_unknown_verdict_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(verdict, "_PATH", str(tmp_path / "v.json"))
    try:
        verdict.record("2026-08-04", "brilliant", "")
    except ValueError:
        return
    raise AssertionError("expected ValueError for an unknown verdict")


# --- the page route, 07/10/2026: taps on the page, pulled by the daily job ---

def _store(tmp_path, monkeypatch):
    monkeypatch.setattr(verdict, "_PATH", str(tmp_path / "v.json"))


def test_a_pull_takes_new_taps_and_ignores_the_ones_it_has(tmp_path, monkeypatch):
    _store(tmp_path, monkeypatch)
    remote = {"2026-10-05": {"verdict": "good", "reason": ""},
              "2026-10-06": {"verdict": "bad", "reason": "not funny"}}
    known = {"2026-10-05", "2026-10-06"}
    assert verdict.sync(remote, known) == [("2026-10-05", "good", ""),
                                           ("2026-10-06", "bad", "not funny")]
    # Pulled again every day: the same taps must change nothing, or a "good"
    # would be promoted into the few-shot pool once per run.
    assert verdict.sync(remote, known) == []
    assert verdict.load()["2026-10-06"]["reason"] == "not funny"


def test_a_change_of_mind_on_the_page_is_taken(tmp_path, monkeypatch):
    _store(tmp_path, monkeypatch)
    known = {"2026-10-06"}
    verdict.sync({"2026-10-06": {"verdict": "bad", "reason": "picture"}}, known)
    assert verdict.sync({"2026-10-06": {"verdict": "good"}}, known) == [
        ("2026-10-06", "good", "")]
    assert verdict.load()["2026-10-06"]["verdict"] == "good"


def test_a_tap_for_a_date_with_no_edition_or_a_bad_value_is_dropped(tmp_path, monkeypatch):
    _store(tmp_path, monkeypatch)
    remote = {"1999-01-01": {"verdict": "good"},
              "2026-10-06": {"verdict": "brilliant"}}
    assert verdict.sync(remote, {"2026-10-06"}) == []
    assert verdict.load() == {}


def test_a_cli_note_survives_a_tap_that_agrees_with_it(tmp_path, monkeypatch):
    _store(tmp_path, monkeypatch)
    verdict.record("2026-10-06", "bad", "the kicker explains itself")
    verdict.sync({"2026-10-06": {"verdict": "bad", "reason": "not funny"}},
                 {"2026-10-06"})
    row = verdict.load()["2026-10-06"]
    assert row["note"] == "the kicker explains itself"
    assert row["reason"] == "not funny"


def test_a_failed_pull_never_stops_the_edition(monkeypatch, capsys):
    monkeypatch.setenv("VERDICT_KEY", "k")
    monkeypatch.setattr(verdict, "fetch",
                        lambda url, key: (_ for _ in ()).throw(OSError("down")))
    assert verdict.pull() == 0
    assert "FAILED" in capsys.readouterr().err


def test_no_key_means_no_pull(monkeypatch, capsys):
    monkeypatch.delenv("VERDICT_KEY", raising=False)
    monkeypatch.setattr(verdict, "fetch", lambda *a: (_ for _ in ()).throw(
        AssertionError("fetched without a key")))
    assert verdict.pull() == 0
