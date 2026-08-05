import json

import gemini
import judge

SETTINGS = {"gemini": {"model": "gemini-3.6-flash", "endpoint": "x",
                       "timeout_seconds": 1, "max_retries": 0,
                       "temperature_ideate": 1.1, "temperature_write": 0.9}}

DRAFTS = [
    {"headline": "One", "body": "First body."},
    {"headline": "Two", "body": "Second body."},
]


def test_prompt_lists_every_draft_and_asks_for_the_funniest():
    p = judge.build_prompt(DRAFTS)
    assert "One" in p and "Two" in p
    assert "DRAFT 1" in p and "DRAFT 2" in p
    assert "funniest" in p.lower()


def test_judge_returns_pick_and_reason(monkeypatch):
    monkeypatch.setattr(gemini, "generate",
                        lambda *a, **k: json.dumps({"pick": 2, "reason": "kicker"}))
    out = judge.judge(DRAFTS, SETTINGS)
    assert out["pick"] == 1          # converted to a zero-based index
    assert out["reason"] == "kicker"


def test_judge_rejects_an_out_of_range_pick(monkeypatch):
    monkeypatch.setattr(gemini, "generate",
                        lambda *a, **k: json.dumps({"pick": 9, "reason": "x"}))
    try:
        judge.judge(DRAFTS, SETTINGS)
    except gemini.GeminiError:
        return
    raise AssertionError("expected GeminiError for an out-of-range pick")


def test_judge_rejects_a_malformed_response(monkeypatch):
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: "not json at all")
    try:
        judge.judge(DRAFTS, SETTINGS)
    except gemini.GeminiError:
        return
    raise AssertionError("expected GeminiError for a malformed response")
