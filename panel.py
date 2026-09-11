"""A committee of comic sensibilities, each RANKING the same candidates.

Charlie, 11/09/2026: "maybe we should create a committee of comedians that audits
the article each day", then "maybe we can add committee of comedians to the judge".

Two design choices worth defending, because the obvious version of this does not
work here.

RANK, NEVER SCORE. The existing judge scores out of 10 and is saturated: 37 of 65
drafts scored a perfect 1.0 on the critic and the judge's own spread across three
candidates was exactly zero on 8 of 22 editions. A model asked to score each item
in isolation has no reason to discriminate; one asked to put four items in order
has to. Every member here returns an ordering and nothing else.

SEPARATE CALLS, NOT ONE PROMPT WEARING THREE HATS. A single call asked to
role-play a panel collapses into one voice agreeing with itself, which buys the
appearance of a committee for none of the disagreement that makes it useful. Each
member is its own call with its own prompt, and they are combined by Borda count -
so a candidate that every member puts second beats one that is first for a single
member and last for the others. That is the whole point: it selects for broad
appeal over a divisive favourite, which is the right bias for a daily paper.

COST. One call per member per use. The free tier is 20 generate calls PER DAY PER
MODEL across three models, and a full pipeline already runs about eight, so the
member list is config and deliberately short. Every failure path degrades to the
caller's existing behaviour rather than losing the edition.
"""
from __future__ import annotations

import re
import sys

import gemini


def build_prompt(member: dict, items: list[str], kind: str) -> str:
    """One member's ranking prompt. `items` are already numbered 1..n for them."""
    listed = "\n\n".join(f"{i}. {t}" for i, t in enumerate(items, start=1))
    return (
        f"{member['persona']}\n\n"
        f"Below are {len(items)} candidate {kind} for a satirical newspaper "
        "filing dispatches from the future. It reports absurd events completely "
        "straight, like a wire service that has not noticed anything is wrong.\n\n"
        f"{listed}\n\n"
        f"Rank ALL {len(items)} from best to worst, judged on "
        f"{member['looks_for']}\n\n"
        "You must commit to an order. Do not call them equally good, do not "
        "refuse to separate them, and do not rank on polish, length or grammar.\n"
        "Reply with ONLY the numbers, best first, separated by commas. "
        "No explanation, no other text. For example: 3,1,4,2"
    )


_NUMS = re.compile(r"\d+")


def parse_ranking(raw: str, n: int) -> list[int]:
    """Zero-based order, best first. Tolerant on purpose: the member is told to
    reply with bare numbers and sometimes says a sentence first.

    A partial reply is USED rather than discarded - a member who ranks three of
    four has still told us something, and the missing item simply scores as if it
    came last. Refusing the whole reply would throw that away and, with a short
    member list, silently turn the panel back into a single judge."""
    seen: list[int] = []
    for tok in _NUMS.findall(raw or ""):
        v = int(tok) - 1
        if 0 <= v < n and v not in seen:
            seen.append(v)
    if not seen:
        raise ValueError(f"no usable ranking in {(raw or '')[:120]!r}")
    return seen


def borda(rankings: list[list[int]], n: int) -> list[float]:
    """Points per candidate: first of n scores n-1, last scores 0.

    An item a member omitted scores 0 for that member, which is the same as being
    ranked last - the honest reading of "did not make my list"."""
    points = [0.0] * n
    for order in rankings:
        for place, idx in enumerate(order):
            points[idx] += float(n - 1 - place)
    return points


def convene(items: list[str], members: list[dict], settings: dict,
            kind: str = "items") -> dict | None:
    """Run the panel. Returns {"winner", "points", "rankings", "voted"} or None.

    None means the caller keeps whatever it was going to do anyway. That is the
    contract everywhere in this pipeline: a taste mechanism may cost a better
    edition, never the edition."""
    if len(items) < 2 or not members:
        return None
    rankings, voted = [], []
    for m in members:
        try:
            raw = gemini.generate(build_prompt(m, items, kind), settings,
                                  settings["gemini"].get("temperature_judge", 0.4))
            rankings.append(parse_ranking(raw, len(items)))
            voted.append(m["name"])
        except Exception as exc:  # noqa: BLE001 - one member must not lose the day
            print(f"    panel: {m['name']} did not vote ({str(exc)[:90]})",
                  file=sys.stderr)
    if not rankings:
        print("    panel: nobody voted; leaving the choice as it was",
              file=sys.stderr)
        return None
    points = borda(rankings, len(items))
    winner = max(range(len(items)), key=lambda i: points[i])
    return {"winner": winner, "points": points, "rankings": rankings,
            "voted": voted}
