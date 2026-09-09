"""Thin Gemini REST client (free AI Studio tier) + defensive JSON extraction.
Uses the API key from the GEMINI_API_KEY environment variable."""
from __future__ import annotations

import json
import os
import re
import sys
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

#: Waits after an HTTP 503 UNAVAILABLE ("this model is currently experiencing
#: high demand"), in seconds. See the comment at the retry branch in generate()
#: for why these are longer than the 429 waits and how the numbers were chosen.
_OVERLOAD_WAITS = (30.0, 75.0, 150.0)


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


#: Longest wait we will honour from a server-stated retry delay. Beyond this the
#: honest outcome is a failure the caller can see, not a job that sits blocked -
#: the daily run has a backup two hours behind it.
_MAX_TOLD_WAIT = 90.0

#: Both spellings Gemini uses for "come back in N seconds": the sentence at the
#: end of the message, and RetryInfo's retryDelay in the details array.
_RETRY_AFTER = re.compile(
    r'(?:please retry in|"retrydelay"\s*:\s*")\s*([0-9]+(?:\.[0-9]+)?)s',
    re.I)


def _retry_after(body: str | None) -> float | None:
    """Seconds the server asked us to wait, or None if it did not say."""
    m = _RETRY_AFTER.search(body or "")
    return float(m.group(1)) if m else None


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
            # NOT TRUNCATED. An error body is a few hundred bytes and it is the
            # only evidence there is; truncating it hid the answer three times
            # in two days. At 200 characters it cut off mid-URL, before the
            # retry delay - which is what let a three-second wait be diagnosed
            # as an exhausted daily allowance and made non-retryable. Raised to
            # 900, and that cut off inside the word "quota", one field before
            # the quotaId that says whether the limit is per-minute or per-day.
            # There is no length worth guessing at here, so there is no length.
            last = f"HTTP {resp.status_code}: {resp.text}"
        except (requests.RequestException, KeyError, IndexError) as exc:
            last = str(exc)
        # A 429 is a RATE limit, not a transient blip: retrying 1.5s later
        # spends another request against the same window and guarantees another
        # 429. Back off past the minute instead.
        #
        # A 503 needs the SAME treatment, and until 06/09/2026 it did not get
        # it. Google returns 503 UNAVAILABLE - "this model is currently
        # experiencing high demand... please try again later" - and the old
        # `else` branch obliged by trying again 1.5 and then 3 seconds later,
        # which is not "later" by any reading. That cost 06/09 its whole pool:
        # drafts 2, 3 and 4 each burned their two retries inside 45 seconds of
        # the same demand spike, one unopposed draft was published, and the
        # judge never ran. Charlie's four complaints about that dispatch were
        # all downstream of an election with one candidate. The spike itself
        # lasted about four minutes, which a real backoff walks straight over.
        #
        # 503 GETS A LONGER LADDER THAN 429, from 07/09/2026, because the two
        # are waiting for different things. A 429 clears when the minute rolls,
        # so 20/40/60 is generous. A 503 is Google's capacity, and the two
        # spikes actually observed - 05/09 and 07/09, two days apart - lasted
        # about four minutes each; the 07/09 one walked straight through all
        # three of the 429-sized waits and lost the run. 30/75/150 buys four and
        # a quarter minutes, which covers both. There is no cost on a clean run,
        # and the daily job has a backup two hours behind it.
        #
        # This matters MORE under the haiku pivot, not less: the whole edition
        # now comes from a single call for two dozen poems, so where the prose
        # pipeline could lose three of four drafts and still publish, one 503
        # here loses the day.
        # STOP INVENTING A BACKOFF: THE SERVER STATES ITS OWN, 09/09/2026.
        #
        # Three wrong diagnoses of one 429 in two days, each confidently worded,
        # and every one of them came from theorising instead of reading the
        # body. First it was called an ordinary rate limit. Then it was called
        # an exhausted DAILY allowance that "cannot clear until the UTC day
        # rolls", and made non-retryable on that basis - which was the most
        # expensive of the three, because it turned a three-second wait into an
        # instant hard failure and every trial run after it died on the spot.
        # A refused run at 00:33 UTC on a fresh UTC day then disproved the
        # UTC-midnight story outright.
        #
        # What Google actually says, once the body is not truncated:
        #   "Quota exceeded for metric: generate_content_free_tier_requests,
        #    limit: 20, model: gemini-3.6-flash. Please retry in 3.231225541s."
        # A three-second retry is a SHORT window, not a day. The server has
        # known the answer the whole time and says it in every response.
        #
        # So the rule is now: if the response tells us how long to wait, wait
        # exactly that (plus a small margin) and try again. No ladder, no
        # theory, no reset time asserted anywhere. `_RETRY_AFTER` reads both
        # spellings - the prose "Please retry in Xs" and RetryInfo's
        # "retryDelay": "Xs" - because Gemini has been seen emitting each.
        # Capped, so a genuinely long delay still fails rather than hanging CI.
        told = _retry_after(last)
        if told is not None:
            wait = min(told + 1.0, _MAX_TOLD_WAIT)
            print(f"    gemini: server asked for {told:.1f}s, waiting {wait:.1f}s "
                  f"({attempt + 1}/{limit})", file=sys.stderr)
            time.sleep(wait)
            continue
        if "HTTP 503" in (last or ""):
            time.sleep(_OVERLOAD_WAITS[min(attempt, len(_OVERLOAD_WAITS) - 1)])
        elif "HTTP 429" in (last or ""):
            time.sleep(max(_min_interval(g), 20.0) * (attempt + 1))
        else:
            time.sleep(1.5 * (attempt + 1))
    raise GeminiError(f"generate failed after retries: {last}")
