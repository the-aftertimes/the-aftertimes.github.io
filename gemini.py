"""Thin Gemini REST client (free AI Studio tier) + defensive JSON extraction.
Uses the API key from the GEMINI_API_KEY environment variable."""
from __future__ import annotations

import json
import os
import re
import time

import requests


class GeminiError(RuntimeError):
    pass


def extract_json(raw: str):
    """Pull the first JSON object/array out of a model response.
    Handles code fences and surrounding prose."""
    if raw is None:
        raise GeminiError("empty response")
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the first {...} or [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = text.find(opener), text.rfind(closer)
        if 0 <= i < j:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                continue
    raise GeminiError(f"no parseable JSON in response: {raw[:200]!r}")


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiError("GEMINI_API_KEY not set")
    return key


#: The free tier allows 5 requests per MINUTE. A full pipeline is ideate + N
#: drafts + judge + revise + depict, fired back to back in a couple of seconds,
#: so it sits over the limit before a single retry is counted. On 04/09/2026 all
#: four drafts 429'd while ideate succeeded - the classic signature. Nothing in
#: the code paced anything; the nightly cron had simply been getting away with
#: it, and the days where drafts "failed" and the judge chose from a thinner
#: pool than intended were this, not model trouble.
_DEFAULT_MIN_INTERVAL = 13.0
_last_call = 0.0


def _min_interval(g: dict) -> float:
    return float(g.get("min_interval_seconds", _DEFAULT_MIN_INTERVAL))


def _pace(g: dict) -> None:
    """Hold every request at least min_interval apart, process-wide."""
    global _last_call
    gap = _min_interval(g)
    if gap <= 0:
        return
    wait = gap - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def generate(prompt: str, settings: dict, temperature: float,
             model: str | None = None, retries: int | None = None) -> str:
    """Call generateContent and return the model's raw text. Retries on
    transient HTTP errors with linear backoff. `model` overrides the default
    settings model (used by the write stage to try a Pro model). `retries`
    overrides the retry count - the Pro attempt passes 0 so a quota 429 falls
    back to flash immediately instead of wasting the backoff window."""
    g = settings["gemini"]
    model = (model or g["model"]).strip()
    limit = g["max_retries"] if retries is None else retries
    url = f"{g['endpoint']}/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature,
                             "responseMimeType": "application/json"},
    }
    last = None
    for attempt in range(limit + 1):
        _pace(g)
        try:
            resp = requests.post(
                url, params={"key": _api_key()}, json=payload,
                timeout=g["timeout_seconds"],
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            last = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except (requests.RequestException, KeyError, IndexError) as exc:
            last = str(exc)
        # A 429 is a RATE limit, not a transient blip: retrying 1.5s later
        # spends another request against the same window and guarantees another
        # 429. Back off past the minute instead.
        if "HTTP 429" in (last or ""):
            time.sleep(max(_min_interval(g), 20.0) * (attempt + 1))
        else:
            time.sleep(1.5 * (attempt + 1))
    raise GeminiError(f"generate failed after retries: {last}")
