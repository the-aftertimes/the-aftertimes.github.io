"""Anthropic API: the first text provider. Gemini (gemini.py) is the fallback.

Writing stages run on Sonnet, judging stages on Haiku. Every call prints its
token usage and cost, and the run total prints at exit, so the monthly bill can
be read off the Actions logs. Uses the key in ANTHROPIC_API_KEY."""
from __future__ import annotations

import atexit
import sys
import base64
import os

import anthropic

#: tier -> (model, effort). settings.yaml `claude:` overrides either field.
DEFAULTS = {
    "write": ("claude-sonnet-5-5", "medium"),
    "judge": ("claude-haiku-5-5", "medium"),
}

#: US$ per million tokens (input, output). Output includes thinking tokens.
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

#: Sonnet 5.5 re-runs a classifier decline server-side; Haiku 5.5 has no
#: server-side fallback, so its refusals go straight to Gemini.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeError(RuntimeError):
    pass


_client: anthropic.Anthropic | None = None
#: Why Claude is off for the rest of this process, once something says so.
_off: str | None = None
_total = {"calls": 0, "in": 0, "out": 0, "usd": 0.0}


def _live() -> bool:
    """False under pytest, so a test's fake usage never reaches the run's annotations,
    which the stats page reads as real cost and real fallbacks."""
    return "pytest" not in sys.modules


def _warn(msg: str) -> None:
    # A workflow command on stdout becomes an annotation on the run summary.
    print(f"::warning::{msg}" if _live() else msg, flush=True)


def _turn_off(reason: str) -> ClaudeError:
    global _off
    _off = reason
    _warn(f"Claude off for the rest of this run, using Gemini: {reason}")
    return ClaudeError(reason)


def config(settings: dict | None, tier: str) -> tuple[bool, str, str]:
    c = (settings or {}).get("claude") or {}
    model, effort = DEFAULTS[tier]
    t = c.get(tier) or {}
    return (c.get("enabled", True) is not False,
            t.get("model", model), t.get("effort", effort))


def _record(model: str, tier: str, usage) -> None:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    tin, tout = usage.input_tokens, usage.output_tokens
    usd = (tin * pin + tout * pout) / 1e6
    _total["calls"] += 1
    _total["in"] += tin
    _total["out"] += tout
    _total["usd"] += usd
    print(f"    claude: {model} [{tier}] in={tin} out={tout} US${usd:.4f}",
          flush=True)


@atexit.register
def _summary() -> None:
    if _total["calls"]:
        line = (f"claude: run total {_total['calls']} calls, in={_total['in']} "
                f"out={_total['out']} US${_total['usd']:.4f}")
        # As a notice annotation the stats page can read the cost without the log.
        print(f"::notice title=Claude cost::{line}" if _live() else line, flush=True)


def generate(prompt: str, tier: str, settings: dict | None = None,
             images: list[bytes] | None = None) -> str:
    """Return the model's text, or raise ClaudeError so the caller can fall
    back to Gemini. Auth, credit and outage failures turn Claude off for the
    rest of the process; a refusal or a bad prompt fails only this call."""
    global _client
    enabled, model, effort = config(settings, tier)
    if not enabled:
        raise ClaudeError("disabled in settings")
    if _off:
        print(f"    claude: off ({_off}), using Gemini", flush=True)
        raise ClaudeError(_off)
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        raise _turn_off("ANTHROPIC_API_KEY is not set. Add it to this repo's "
                        "Actions secrets; until then every call spends the "
                        "Gemini free tier")
    if _client is None:
        _client = anthropic.Anthropic(timeout=180.0, max_retries=2)

    content = [{"type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg",
                           "data": base64.b64encode(b).decode()}}
               for b in (images or [])]
    content.append({"type": "text", "text": prompt})
    kwargs = dict(model=model, max_tokens=16000,
                  output_config={"effort": effort},
                  messages=[{"role": "user", "content": content}])
    try:
        if model.startswith("claude-sonnet"):
            resp = _client.beta.messages.create(
                **kwargs, betas=[_FALLBACK_BETA], fallbacks="default")
        else:
            resp = _client.messages.create(**kwargs)
    except (anthropic.AuthenticationError,
            anthropic.PermissionDeniedError) as exc:
        raise _turn_off(f"{type(exc).__name__}: {exc}") from exc
    except anthropic.BadRequestError as exc:
        if "credit" in str(exc).lower():
            raise _turn_off(f"credit exhausted: {exc}") from exc
        _warn(f"Claude [{tier}] rejected the request, using Gemini: {exc}")
        raise ClaudeError(str(exc)) from exc
    except anthropic.APIError as exc:
        # Rate limit, overload, 5xx or network, after the SDK's own retries.
        raise _turn_off(f"{type(exc).__name__}: {exc}") from exc

    _record(model, tier, resp.usage)
    if resp.stop_reason in ("refusal", "max_tokens"):
        _warn(f"Claude [{tier}] stopped on {resp.stop_reason}, using Gemini")
        raise ClaudeError(f"stop_reason {resp.stop_reason}")
    text = "".join(b.text for b in resp.content if b.type == "text")
    if not text.strip():
        _warn(f"Claude [{tier}] returned no text, using Gemini")
        raise ClaudeError("empty response")
    return text
