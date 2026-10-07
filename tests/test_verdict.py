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
