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


def _resp(code, text="x"):
    class R:
        status_code = code
        def json(self): return {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    R.text = text
    return R()


def _settings(retries=2):
    return {"gemini": {"model": "m", "endpoint": "e", "timeout_seconds": 1,
                       "max_retries": retries, "min_interval_seconds": 0}}


def test_a_503_backs_off_like_a_rate_limit_not_like_a_blip(monkeypatch):
    """05/09/2026: three of four drafts died to a four-minute Gemini 503 spike
    ("this model is currently experiencing high demand"), because the retry
    branch treated it as transient noise and tried again 1.5 and 3 seconds
    later. One unopposed draft published, the judge never ran, and Charlie's
    four complaints about that dispatch followed. A 503 needs the same backoff
    a 429 gets - long enough to walk over the spike."""
    import gemini
    slept = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(gemini, "_api_key", lambda: "k")
    monkeypatch.setattr(gemini.requests, "post",
                        lambda *a, **k: _resp(503, "high demand"))
    with pytest.raises(GeminiError):
        gemini.generate("p", _settings(), 0.9)
    assert slept, "a 503 must be waited out"
    assert min(slept) >= 20, f"503 backoff is far too short: {slept}"


def test_a_500_is_still_treated_as_an_ordinary_blip(monkeypatch):
    """Only the overload code gets the long wait; widening it to every 5xx would
    add a minute to every genuine server error for no reason."""
    import gemini
    slept = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(gemini, "_api_key", lambda: "k")
    monkeypatch.setattr(gemini.requests, "post", lambda *a, **k: _resp(500, "oops"))
    with pytest.raises(GeminiError):
        gemini.generate("p", _settings(), 0.9)
    assert max(slept) < 20, f"a 500 should not buy a rate-limit backoff: {slept}"


def test_settings_allow_enough_retries_to_outlast_a_short_overload():
    from common import load_settings
    assert load_settings()["gemini"]["max_retries"] >= 3
