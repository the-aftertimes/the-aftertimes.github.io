"""Deterministic dispatch scoring - the measurable half of quality control.

Everything checkable in code lives here so the two model calls in the pipeline
(judge, revise) are spent only on the genuinely subjective question of whether a
dispatch is funny. Pure functions: no API calls, no file IO, no globals.

Severity is either "major" or "minor"; the weights and thresholds all come from
the `quality` block in config/settings.yaml so tuning never means editing code.
"""
from __future__ import annotations

import re

from write import _MACHINE_PHRASES, prose_report


def metrics_for(body: str) -> dict:
    """Prose measurements for a body. Thin alias so callers do not reach into
    write.py, and so tests read clearly."""
    return prose_report(body)


def _v(rule: str, detail: str, severity: str) -> dict:
    return {"rule": rule, "detail": detail, "severity": severity}


def check_rhythm(metrics: dict, cfg: dict) -> list[dict]:
    r = cfg["rhythm"]
    out = []
    mean = metrics["mean_sentence"]
    if not (r["mean_min"] <= mean <= r["mean_max"]):
        hard = mean < r["mean_hard_min"] or mean > r["mean_hard_max"]
        out.append(_v("rhythm_mean",
                      f"mean sentence is {mean} words, wanted "
                      f"{r['mean_min']}-{r['mean_max']}",
                      "major" if hard else "minor"))
    if metrics["longest"] > r["longest_max"]:
        out.append(_v("rhythm_longest",
                      f"longest sentence is {metrics['longest']} words, "
                      f"maximum {r['longest_max']}", "major"))
    if metrics["short_sentences"] < r["min_short"]:
        out.append(_v("rhythm_short",
                      f"only {metrics['short_sentences']} sentences of six words "
                      f"or fewer, wanted at least {r['min_short']}", "minor"))
    return out


def check_length(metrics: dict, cfg: dict) -> list[dict]:
    ln = cfg["length"]
    words = metrics["words"]
    if ln["min"] <= words <= ln["max"]:
        return []
    hard = words < ln["hard_min"] or words > ln["hard_max"]
    return [_v("length",
               f"{words} words, wanted {ln['min']}-{ln['max']}",
               "major" if hard else "minor")]


#: The legal/financial register the paper over-used (see config/engines.yaml).
#: Suppressed when the day's comic engine IS the bureaucratic one.
_LEGAL = re.compile(
    r"\b(sue[sd]?|suing|lawsuit|court|magistrate|tribunal|injunction|lien|liens"
    r"|repossess\w*|bailiff\w*|writ|statute|ordinance|permit|permits|licence"
    r"|tax|taxes|levy|levies|debt|debts|fine|fined|fines|insurance"
    r"|liability|liabilities)\b", re.I)

#: Present-day objects that should not furnish a far-future dispatch unless
#: their survival is the story. A dispatch set in 37562 mourned a Boston fern by
#: candlelight under a bronze plaque; another rolled a coffee press through
#: cobbled alleys.
_PROPS = re.compile(
    r"\b(candle\w*|bronze plaque\w*|handwritten|clipboard\w*|vellum|locker\w*"
    r"|apothecar\w*|cobblestone\w*|lard|typewriter\w*|fax|dollar\w*|euro\w*"
    r"|coffee|espresso|Boston fern\w*)\b", re.I)

#: The narrator or a character explaining the comic mechanism out loud. This is
#: a semantic fault that regex cannot detect reliably, so it is deliberately
#: only ever a minor nudge - a false positive must never bin a draft.
_STATED_JOKE = re.compile(
    r"(\brealis\w+\b|\brealiz\w+\b|too\s+\w+\s+to\s+notice|\blittle did\b)", re.I)

_STATED_JOKE_SENTENCES = 2

#: Same closing-quote allowance as write.prose_report's sentence split, built
#: from codepoints (not literal curly-quote characters) so this file stays
#: copy-paste safe under the editor's dash-mangling behaviour and easy to audit
#: byte-for-byte. Functionally identical to write.py's pattern.
_SENTENCE_SPLIT = re.compile(
    r"(?<=[.!?])[\"" + chr(0x201D) + chr(0x2019) + r"']*\s+")


def check_phrases(body: str) -> list[dict]:
    hits = [p for p in _MACHINE_PHRASES if p in body.lower()]
    if not hits:
        return []
    return [_v("machine_phrases", "stock machine phrasing: " + ", ".join(hits),
               "major")]


def check_register(body: str, engine: str) -> list[dict]:
    if (engine or "") == "bureaucratic":
        return []
    hits = sorted({m.group(0).lower() for m in _LEGAL.finditer(body)})
    if not hits:
        return []
    return [_v("legal_register",
               "legal/financial crutch: " + ", ".join(hits), "major")]


def check_props(text: str, years_from_now: int) -> list[dict]:
    hits = sorted({m.group(0).lower() for m in _PROPS.finditer(text)})
    if not hits:
        return []
    severity = "major" if int(years_from_now) >= 400 else "minor"
    return [_v("present_day_props",
               "present-day props: " + ", ".join(hits), severity)]


def check_stated_joke(body: str) -> list[dict]:
    flat = re.sub(r"\s+", " ", body).strip()
    opening = " ".join(_SENTENCE_SPLIT.split(flat)[:_STATED_JOKE_SENTENCES])
    m = _STATED_JOKE.search(opening)
    if not m:
        return []
    return [_v("stated_joke",
               f"the opening states the conceit ({m.group(0)!r}) instead of "
               "reporting facts", "minor")]
