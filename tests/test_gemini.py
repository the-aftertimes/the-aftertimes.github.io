import pytest

from gemini import extract_json, GeminiError


def test_extract_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    raw = "```json\n{\"headline\": \"hi\"}\n```"
    assert extract_json(raw) == {"headline": "hi"}


def test_extract_json_with_prose_around_it():
    raw = "Sure! Here is your object:\n{\"x\": [1, 2, 3]}\nHope that helps."
    assert extract_json(raw) == {"x": [1, 2, 3]}


def test_extract_json_raises_on_garbage():
    with pytest.raises(GeminiError):
        extract_json("no json here at all")


def test_pacing_holds_calls_apart(monkeypatch):
    """04/09/2026: ideate succeeded and all four drafts 429'd - the signature of
    the 5-requests-per-minute free-tier cap. Nothing paced anything."""
    import gemini
    slept = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(gemini.time, "monotonic", lambda: 100.0)
    gemini._last_call = 95.0            # 5s ago, interval is 13s
    gemini._pace({"min_interval_seconds": 13})
    assert slept and 7.9 < slept[0] < 8.1


def test_pacing_can_be_disabled(monkeypatch):
    import gemini
    slept = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    gemini._pace({"min_interval_seconds": 0})
    assert slept == []


def test_settings_declare_a_pacing_interval_under_the_free_tier_cap():
    from common import load_settings
    gap = load_settings()["gemini"]["min_interval_seconds"]
    # 5 requests/minute means 12s apart; anything less is over the cap.
    assert gap >= 12, "pacing must respect the 5 requests-per-minute free tier"
