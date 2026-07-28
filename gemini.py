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


def generate(prompt: str, settings: dict, temperature: float) -> str:
    """Call generateContent and return the model's raw text. Retries on
    transient HTTP errors with linear backoff."""
    g = settings["gemini"]
    url = f"{g['endpoint']}/{g['model']}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature,
                             "responseMimeType": "application/json"},
    }
    last = None
    for attempt in range(g["max_retries"] + 1):
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
        time.sleep(1.5 * (attempt + 1))
    raise GeminiError(f"generate failed after retries: {last}")
