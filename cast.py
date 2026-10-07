"""Draw the names a dispatch's people are given.

The writer was asked for "fresh, varied" names for two months and settled on a
handful of favourites anyway - see config/names.yaml for the count. So the run
now hands it a cast. Pure functions: the caller loads the pool and the archive.

Deterministic on its seed, which is the run date plus the premise, so a run
that resumes from data/wip.json gives a draft the same names it had, and two
drafts of one edition get different ones.
"""
from __future__ import annotations

import hashlib
import random
import re

_WORD = re.compile(r"[A-Z][A-Za-z'\-]+")


def recent_names(bodies: list[str]) -> set[str]:
    """Every capitalised word in these bodies. Cruder than a name finder and
    deliberately so: a pool name that merely LOOKS used is skipped, which costs
    nothing, while one that IS used and gets missed repeats a face."""
    out: set[str] = set()
    for body in bodies:
        out.update(_WORD.findall(body or ""))
    return out


def draw(seed: str, given: list[str], family: list[str],
         avoid: set[str] = frozenset(), n: int = 3) -> list[str]:
    """n full names, no given or family name repeated within the cast, none
    whose parts appear in `avoid`. Falls back to the whole pool if `avoid`
    would leave it too small, rather than returning a short cast."""
    rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16))
    g = [x for x in given if x not in avoid] or list(given)
    f = [x for x in family if x not in avoid] or list(family)
    if len(g) < n:
        g = list(given)
    if len(f) < n:
        f = list(family)
    return [f"{a} {b}" for a, b in zip(rng.sample(g, n), rng.sample(f, n))]


def rule(names: list[str]) -> str:
    """The prompt line. Empty when there is no cast, so the old wording returns."""
    if not names:
        return ""
    return ("- The people in this dispatch are called, in order of appearance: "
            + ", ".join(names) + ". Use these names and no others for people; "
            "use only as many as the story needs. Do not default the weekday to "
            "Tuesday; vary or omit the day.")
