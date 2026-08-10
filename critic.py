"""Deterministic dispatch scoring - the measurable half of quality control.

Everything checkable in code lives here so the two model calls in the pipeline
(judge, revise) are spent only on the genuinely subjective question of whether a
dispatch is funny. Pure functions: no API calls, no file IO, no globals.

Severity is either "major" or "minor"; the weights and thresholds all come from
the `quality` block in config/settings.yaml so tuning never means editing code.
"""
from __future__ import annotations

import re

from common import _DASH_CODEPOINTS
from write import _AU_SPELLING, _MACHINE_PHRASES, prose_report


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
    # The FLOOR here is dangerous and was wrong once already. On 10/08/2026 the
    # only trial containing lines Charlie called funny (t002) was the only one
    # the critic docked, purely for mean 13.7 against a then-floor of 14 - and
    # two of the four funny lines were 6 and 10 words, i.e. they were what pulled
    # the mean down. A floor set by taste rather than evidence makes revise.py
    # optimise AWAY from comedy. Keep it low enough to catch only telegram-prose.
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
#:
#: UNAMBIGUOUS TERMS ONLY. The first version included bare "fine", "fined",
#: "fines", "permit", "permits", "licence", "insurance" and "liability", which
#: match ordinary English - "it was a fine morning" and "the doors would not
#: permit entry" both tripped it. Since legal_register is a HARD REJECT, those
#: false positives would have binned good drafts routinely and pushed the run
#: into the all-rejected branch as a matter of course.
_LEGAL = re.compile(
    r"\b(sue[sd]?|suing|lawsuit|court|magistrate|tribunal|injunction|lien|liens"
    r"|repossess\w*|bailiff\w*|writ|statute|ordinance"
    r"|tax|taxes|levy|levies|debt|debts)\b", re.I)

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


_US_WORDS = re.compile(
    r"\b(" + "|".join(sorted(_AU_SPELLING, key=len, reverse=True)) + r")\b", re.I)


def check_residue(text: str) -> list[dict]:
    """A hit here means one of the deterministic fixers has a GAP - the text was
    supposed to be cleaned before it ever reached the critic. Treated as major
    for exactly that reason."""
    out = []
    dashes = sorted({hex(ord(c)) for c in text if ord(c) in _DASH_CODEPOINTS})
    if dashes:
        out.append(_v("dash_residue",
                      "dash characters survived hyphenate(): " + ", ".join(dashes),
                      "major"))
    us = sorted({m.group(0).lower() for m in _US_WORDS.finditer(text)})
    if us:
        out.append(_v("us_spelling",
                      "US spellings survived the normaliser: " + ", ".join(us),
                      "major"))
    return out


def check_structure(dispatch: dict, cfg: dict) -> list[dict]:
    """The parts a dispatch cannot be published without. Nothing else in the
    critic looks at whether a field is actually THERE - so before this existed, a
    revision that came back with a body but no headline scored identically to a
    good one (1.0), sailed through the acceptance gate, and would have published
    an empty <h1> and emailed it to subscribers."""
    out = []
    if not (dispatch.get("headline") or "").strip():
        out.append(_v("structure", "no headline", "major"))
    if not ((dispatch.get("dateline") or {}).get("place") or "").strip():
        out.append(_v("structure", "no dateline place", "major"))
    words = len((dispatch.get("headline") or "").split())
    cap = cfg.get("headline_max_words", 7)
    if words > cap:
        out.append(_v("headline_length",
                      f"headline is {words} words, wanted {cap} or fewer",
                      "minor"))
    body = (dispatch.get("body") or "").strip()
    floor = cfg["length"]["hard_min"]
    if len(body.split()) < floor:
        out.append(_v("structure",
                      f"body is {len(body.split())} words, below the {floor}-word "
                      "absolute floor", "major"))
    return out


def score(dispatch: dict, context: dict, cfg: dict) -> dict:
    """Measure a dispatch. `context` carries years_from_now and engine, both of
    which make some checks conditional. Returns the score, the violations and the
    raw metrics; a draft breaking any cfg["hard_reject"] rule is flagged
    `rejected` but still returned, because the orchestrator may need it as a last
    resort rather than failing to publish."""
    body = dispatch.get("body", "") or ""
    text = f"{dispatch.get('headline', '')} {body}"
    metrics = metrics_for(body)
    violations = []
    violations += check_structure(dispatch, cfg)
    violations += check_rhythm(metrics, cfg)
    violations += check_length(metrics, cfg)
    violations += check_phrases(body)
    violations += check_register(body, context.get("engine", ""))
    violations += check_props(text, context.get("years_from_now", 0))
    violations += check_stated_joke(body)
    violations += check_residue(text)
    weights = cfg["weights"]
    penalty = sum(weights.get(v["severity"], weights["minor"])
                  for v in violations)
    hard = set(cfg["hard_reject"])
    return {
        "score": round(max(0.0, 1.0 - penalty), 3),
        "rejected": any(v["rule"] in hard for v in violations),
        "violations": violations,
        "metrics": metrics,
    }
