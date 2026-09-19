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


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    """The overload ladder and the spent-model set are process-wide state, so
    a PerDay in one test would silence the model name in the next."""
    import gemini
    monkeypatch.setattr(gemini, "_overload_retries", 0)
    monkeypatch.setattr(gemini, "_spent_today", set())


def test_a_503_backs_off_like_a_rate_limit_not_like_a_blip(monkeypatch):
    """05/09/2026: three of four drafts died to a four-minute Gemini 503 spike
    ("this model is currently experiencing high demand"), because the retry
    branch treated it as transient noise and tried again 1.5 and 3 seconds
    later. One unopposed draft published, the judge never ran, and Charlie's
    four complaints about that dispatch followed. A 503 needs a real wait.

    REWRITTEN 19/09/2026. This test used to demand four minutes of waiting
    INSIDE ONE CALL, which encoded the belief that a failed attempt is free.
    It is not: every 503 attempt counts against the 20-a-day cap (see the
    comment on gemini._overload_retries for the count that proved it), and
    four attempts per model per stage is how one long outage on 18/09 spent
    all three models' allowances across four runs. The minutes are now bought
    across the MODEL WALK, not inside one call - see the test below."""
    import gemini
    slept = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(gemini, "_api_key", lambda: "k")
    posts = []
    monkeypatch.setattr(gemini.requests, "post",
                        lambda *a, **k: posts.append(1) or _resp(503, "high demand"))
    with pytest.raises(GeminiError):
        gemini.generate("p", _settings(), 0.9)
    assert slept == [30.0], f"one rung of the ladder per model per call: {slept}"
    assert len(posts) == 2, f"a 503 costs a daily call; two attempts, not four: {posts}"


def test_the_overload_ladder_is_spent_across_the_model_walk(monkeypatch):
    """07/09/2026's four-minute spike must still be walked over, but by the
    three-model list sharing one ladder: 30s on the first model, 75s on the
    second, 150s on the third - 4.25 minutes of waiting for six calls in all
    (two per model), where the old per-call ladder would have made twelve."""
    import gemini
    slept, posts = [], []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(gemini, "_api_key", lambda: "k")
    monkeypatch.setattr(gemini.requests, "post",
                        lambda url, **k: posts.append(url) or _resp(503, "high demand"))
    with pytest.raises(GeminiError, match="no model answered"):
        gemini.generate_first_available("p", _settings(), 0.9, ("a", "b", "c"))
    assert slept == [30.0, 75.0, 150.0], slept
    assert sum(slept) >= 240, "the walk must still outlast a four-minute spike"
    assert [u.split("/")[-1] for u in posts] == [
        "a:generateContent"] * 2 + ["b:generateContent"] * 2 + ["c:generateContent"] * 2
    # With the ladder spent, a later stage's 503 costs ONE call per model and
    # no waiting at all - the next cron rung is the retry.
    slept.clear(); posts.clear()
    with pytest.raises(GeminiError, match="ladder is spent"):
        gemini.generate("p", _settings(), 0.9, model="a")
    assert slept == [] and len(posts) == 1, (slept, posts)


def test_a_model_that_said_per_day_is_not_asked_again_this_run(monkeypatch):
    """18/09/2026 21:41 UTC: every stage re-asked gemini-3.6-flash after it had
    already said its daily 20 were gone, 13 seconds of pacing each time, until
    the 30-minute job timeout. The refusal is on file; the second ask is free."""
    import gemini
    posts = []
    body = ('{"error":{"code":429,"details":[{"violations":[{"quotaId":'
            '"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}')
    monkeypatch.setattr(gemini.time, "sleep", lambda s: None)
    monkeypatch.setattr(gemini, "_api_key", lambda: "k")
    monkeypatch.setattr(gemini.requests, "post",
                        lambda *a, **k: posts.append(1) or _resp(429, body))
    with pytest.raises(GeminiError, match="PER DAY"):
        gemini.generate("p", _settings(), 0.9, model="m")
    assert len(posts) == 1
    with pytest.raises(GeminiError, match="not asking again"):
        gemini.generate("p", _settings(), 0.9, model="m")
    assert len(posts) == 1, "the second ask must not reach the network"
    # A sibling model is untouched by it.
    with pytest.raises(GeminiError, match="PER DAY"):
        gemini.generate("p", _settings(), 0.9, model="other")
    assert len(posts) == 2


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


def test_a_server_stated_retry_delay_is_honoured_exactly(monkeypatch):
    """THE FIX THAT SHOULD HAVE BEEN FIRST, 09/09/2026.

    The same 429 got three wrong diagnoses in two days - an ordinary rate limit,
    then an exhausted DAILY allowance made non-retryable "until the UTC day
    rolls" - and all three came from theorising instead of reading the body.
    Untruncated, Gemini says: "limit: 20, model: gemini-3.6-flash. Please retry
    in 3.231225541s." A three-second wait, stated by the server in every
    response. The non-retryable version turned that into an instant hard failure
    and killed four trial runs on the spot."""
    import gemini
    slept = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(gemini, "_api_key", lambda: "k")
    body = ('{"error":{"code":429,"message":"You exceeded your current quota. '
            '* Quota exceeded for metric: generate_content_free_tier_requests, '
            'limit: 20, model: gemini-3.6-flash\nPlease retry in 3.231225541s."}}')
    calls = []

    def post(*a, **k):
        calls.append(1)
        return _resp(200, "ok") if len(calls) > 1 else _resp(429, body)

    monkeypatch.setattr(gemini.requests, "post", post)
    assert gemini.generate("p", _settings(), 0.9) == "ok"
    assert len(slept) == 1 and abs(slept[0] - 4.231225541) < 1e-6, slept


def test_a_stated_delay_beats_the_invented_ladder(monkeypatch):
    """A 503 that carries a delay uses the delay, not the 30/75/150 ladder."""
    import gemini
    slept = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(gemini, "_api_key", lambda: "k")
    monkeypatch.setattr(gemini.requests, "post",
                        lambda *a, **k: _resp(503, '"retryDelay": "7s"'))
    with pytest.raises(GeminiError):
        gemini.generate("p", _settings(), 0.9)
    assert set(slept) == {8.0}, slept


def test_an_absurd_stated_delay_is_capped(monkeypatch):
    """A job that sits blocked for an hour is worse than one that fails and lets
    the backup run take it."""
    import gemini
    slept = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(gemini, "_api_key", lambda: "k")
    monkeypatch.setattr(gemini.requests, "post",
                        lambda *a, **k: _resp(429, "Please retry in 3600s."))
    with pytest.raises(GeminiError):
        gemini.generate("p", _settings(), 0.9)
    assert max(slept) <= gemini._MAX_TOLD_WAIT, slept


def test_a_429_with_no_stated_delay_falls_back_to_the_ladder(monkeypatch):
    """When the server says nothing, the invented wait is all there is."""
    import gemini
    slept = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(gemini, "_api_key", lambda: "k")
    monkeypatch.setattr(gemini.requests, "post",
                        lambda *a, **k: _resp(429, '{"error":{"message":"rate"}}'))
    with pytest.raises(GeminiError):
        gemini.generate("p", _settings(), 0.9)
    assert slept and min(slept) >= 20, slept


def test_the_error_body_is_not_truncated_at_all(monkeypatch):
    """A Google 429 says WHICH allowance and WHEN it returns. Truncation hid it
    twice: 200 chars cut off mid-URL before the retry delay, and 900 cut off
    inside the word "quota", one field before the quotaId. The body is a few
    hundred bytes and is the only evidence there is, so it is kept whole."""
    import gemini
    body = ('{"error":{"code":429,"message":"You exceeded your current quota, '
            'please check your plan and billing details. For more information '
            'on this error, head to: https://ai.google.dev/gemini-api/docs/'
            'rate-limits.","details":[{"@type":"type.googleapis.com/google.rpc.'
            'QuotaFailure","violations":[{"quotaMetric":"generativelanguage.'
            'googleapis.com/generate_content_free_tier_requests","quotaId":'
            '"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},'
            '{"@type":"type.googleapis.com/google.rpc.RetryInfo",'
            '"retryDelay":"31s"}]}}')
    monkeypatch.setattr(gemini.time, "sleep", lambda s: None)
    monkeypatch.setattr(gemini, "_api_key", lambda: "k")
    monkeypatch.setattr(gemini.requests, "post", lambda *a, **k: _resp(429, body))
    with pytest.raises(GeminiError) as exc:
        gemini.generate("p", _settings(), 0.9)
    msg = str(exc.value)
    assert "PerDay" in msg, "the quotaId must survive into the error"
    assert "retryDelay" in msg, "the retry delay must survive into the error"
    assert body in msg, "the body must reach the log whole, not truncated"


def test_a_404_is_not_retried(monkeypatch):
    """09/09/2026: a retired model name returned 404 "no longer available to new
    users" and the loop asked three more times, 13 seconds apart. Only a 429 is
    a 4xx worth a second attempt - illustrate.py has drawn that line since
    August."""
    import gemini
    calls, slept = [], []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(gemini, "_api_key", lambda: "k")

    def post(*a, **k):
        calls.append(1)
        return _resp(404, '{"error":{"message":"no longer available"}}')

    monkeypatch.setattr(gemini.requests, "post", post)
    with pytest.raises(GeminiError) as exc:
        gemini.generate("p", _settings(), 0.9)
    assert "not retryable" in str(exc.value)
    assert len(calls) == 1, f"asked {len(calls)} times for a dead model name"
    assert slept == []


def test_prose_write_walks_the_same_model_list_as_haiku():
    """10/09/2026: the haiku path walked a model list and prose did not, so the
    first prose run after the revert lost all four drafts to an exhausted
    gemini-3.6-flash while two spare models on the same key sat untouched. The
    free tier is 20 calls PER DAY PER MODEL."""
    import run
    import write
    from common import load_settings
    s = load_settings()
    assert len(write.models(s)) >= 2, "a single model is one bad day from no edition"
    assert tuple(run.HAIKU_MODELS) == write.models(s), "one list, not two"


def test_models_falls_back_to_the_single_default():
    import write
    assert write.models({"gemini": {"model": "only-one"}}) == ("only-one",)


def test_generate_without_an_explicit_model_walks_the_list(monkeypatch):
    """10/09: write walked the list and ideate did not, so the prose path could
    not start once the default model's 20-a-day was spent. Fixed centrally
    because fixing it per-caller is what left the gap twice."""
    import gemini
    tried = []

    def fake(prompt, settings, temperature, model=None, retries=None):
        tried.append(model)
        if model != "spare-b":
            raise gemini.GeminiError("HTTP 429 daily quota")
        return "ok"

    monkeypatch.setattr(gemini, "generate", fake)
    raw, served = gemini.generate_first_available(
        "p", {"gemini": {"models": ("spare-a", "spare-b")}}, 1.0,
        ("spare-a", "spare-b"))
    assert raw == "ok" and served == "spare-b"
    assert tried == ["spare-a", "spare-b"]
