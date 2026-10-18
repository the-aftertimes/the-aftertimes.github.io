import json
from types import SimpleNamespace

import anthropic
import pytest

import claude
import gemini
import judge as judge_stage
import write as write_stage


def _msg(text='{"ok": 1}', stop="end_turn", tin=1000, tout=2000):
    return SimpleNamespace(
        stop_reason=stop,
        content=[SimpleNamespace(type="thinking", thinking=""),
                 SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=tin, output_tokens=tout))


class FakeClient:
    def __init__(self, reply=None, raises=None):
        self.calls = []
        self.reply = reply or _msg()
        self.raises = raises
        self.messages = SimpleNamespace(create=self._create("plain"))
        self.beta = SimpleNamespace(messages=SimpleNamespace(
            create=self._create("beta")))

    def _create(self, path):
        def create(**kw):
            self.calls.append((path, kw))
            if self.raises:
                raise self.raises
            return self.reply
        return create


def _api_error(cls, message):
    """An SDK error without a live response, whatever HTTP library it uses."""
    exc = cls.__new__(cls)
    Exception.__init__(exc, message)
    exc.message = message
    return exc


@pytest.fixture
def live(monkeypatch):
    """Claude on, a key in the environment, a fake client, a clean tally."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(claude, "_off", None)
    monkeypatch.setattr(claude, "_total",
                        {"calls": 0, "in": 0, "out": 0, "usd": 0.0})
    fake = FakeClient()
    monkeypatch.setattr(claude, "_client", fake)
    return fake


def test_missing_key_warns_once_and_turns_claude_off(monkeypatch, capsys):
    monkeypatch.setattr(claude, "_off", None)
    with pytest.raises(claude.ClaudeError):
        claude.generate("p", "write")
    with pytest.raises(claude.ClaudeError):
        claude.generate("p", "judge")
    out = capsys.readouterr().out
    assert out.count("::warning::") == 1
    assert "ANTHROPIC_API_KEY" in out


def test_write_tier_is_sonnet_with_server_fallback(live, capsys):
    assert claude.generate("p", "write") == '{"ok": 1}'
    path, kw = live.calls[0]
    assert path == "beta"
    assert kw["model"] == "claude-sonnet-5-5"
    assert kw["fallbacks"] == "default"
    assert kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["output_config"] == {"effort": "medium"}
    assert "temperature" not in kw
    out = capsys.readouterr().out
    # 1000 in x $2 + 2000 out x $10 per million.
    assert "claude-sonnet-5-5 [write] in=1000 out=2000 US$0.0220" in out


def test_judge_tier_is_haiku_without_fallbacks(live):
    claude.generate("p", "judge")
    path, kw = live.calls[0]
    assert path == "plain"
    assert kw["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in kw


def test_settings_override_model_and_effort(live):
    claude.generate("p", "write", {"claude": {"write": {"effort": "high"}}})
    assert live.calls[0][1]["output_config"] == {"effort": "high"}


def test_disabled_in_settings_never_calls(live):
    with pytest.raises(claude.ClaudeError):
        claude.generate("p", "write", {"claude": {"enabled": False}})
    assert live.calls == []


def test_images_ride_before_the_text(live):
    claude.generate("which is clearer", "judge", images=[b"a", b"b"])
    blocks = live.calls[0][1]["messages"][0]["content"]
    assert [b["type"] for b in blocks] == ["image", "image", "text"]
    assert blocks[0]["source"]["media_type"] == "image/jpeg"


def test_run_total_sums_every_call(live, capsys):
    claude.generate("p", "write")
    claude.generate("p", "judge")
    claude._summary()
    out = capsys.readouterr().out
    assert "run total 2 calls, in=2000 out=4000" in out


def test_auth_failure_turns_claude_off_for_the_run(live):
    live.raises = _api_error(anthropic.AuthenticationError, "bad key")
    with pytest.raises(claude.ClaudeError):
        claude.generate("p", "write")
    live.raises = None
    with pytest.raises(claude.ClaudeError):
        claude.generate("p", "write")
    assert len(live.calls) == 1


def test_outage_turns_claude_off_for_the_run(live):
    live.raises = _api_error(anthropic.InternalServerError, "overloaded")
    with pytest.raises(claude.ClaudeError):
        claude.generate("p", "write")
    assert claude._off


def test_refusal_fails_one_call_not_the_run(live, capsys):
    live.reply = _msg(stop="refusal")
    with pytest.raises(claude.ClaudeError):
        claude.generate("p", "write")
    assert claude._off is None
    assert "::warning::" in capsys.readouterr().out


def test_bad_request_fails_one_call_but_credit_exhaustion_is_the_run(live):
    live.raises = _api_error(anthropic.BadRequestError, "image too large")
    with pytest.raises(claude.ClaudeError):
        claude.generate("p", "judge")
    assert claude._off is None
    live.raises = _api_error(anthropic.BadRequestError,
                             "Your credit balance is too low")
    with pytest.raises(claude.ClaudeError):
        claude.generate("p", "judge")
    assert claude._off


def test_gemini_generate_asks_claude_first(live, monkeypatch):
    posted = []
    monkeypatch.setattr(gemini.requests, "post",
                        lambda *a, **k: posted.append(1))
    assert gemini.generate("p", {"gemini": {}}, 0.9, tier="judge") == '{"ok": 1}'
    assert posted == []


def test_gemini_generate_falls_back_when_claude_fails(live, monkeypatch):
    live.raises = _api_error(anthropic.AuthenticationError, "bad key")

    class R:
        status_code = 200
        text = ""
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "gem"}]}}]}

    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setattr(gemini.requests, "post", lambda *a, **k: R())
    settings = {"gemini": {"model": "gemini-3.6-flash", "endpoint": "x",
                           "timeout_seconds": 1, "max_retries": 0,
                           "min_interval_seconds": 0}}
    assert gemini.generate("p", settings, 0.9, tier="write") == "gem"


def test_walk_reports_claude_as_the_model_that_answered(live):
    raw, model = gemini.generate_first_available(
        "p", {"gemini": {}}, 0.9, ("gemini-3.6-flash",), tier="judge")
    assert model == "claude-haiku-5-5"


def test_judge_stage_runs_on_the_judge_tier(live):
    live.reply = _msg(json.dumps({"pick": 1, "score": 7, "reason": "r"}))
    judge_stage.judge([{"headline": "h", "body": "b"}] * 2,
                      {"gemini": {"temperature_write": 0.9}})
    assert live.calls[0][1]["model"] == "claude-haiku-5-5"


def test_write_stage_is_served_by_sonnet(live, capsys):
    live.reply = _msg(json.dumps({"headline": "H", "dateline_place": "P",
                                  "body": "b", "scene": "s", "domain": "law",
                                  "glossary": []}))
    settings = {"gemini": {"model": "gemini-3.6-flash", "write_model": "",
                           "temperature_write": 0.9}}
    d = write_stage.write(
        premise="p", dateline={"place": "", "year": 3000,
                               "years_from_now": 974, "month": 9, "day": 4},
        domain="law", settings=settings, style_guidance="s")
    assert d["headline"] == "H"
    assert live.calls[0][1]["model"] == "claude-sonnet-5-5"
    assert "served by claude-sonnet-5-5" in capsys.readouterr().err
