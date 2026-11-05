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
    # NAME AT MOST TWO PEOPLE. Charlie, 06/11/2026, on dispatches carrying
    # Tavita Jaramillo, Dorcas Paewai, Mireille Hoang and Astrid Mirzoyan: the
    # writing is "still bad". Three uncommon full names in two hundred words is
    # the name salad that reads as generated - the pool is deliberately unusual
    # (see config/names.yaml) to stop repeats, which is right, so the fix is
    # how MANY names appear and how they are used, not which ones. A paper names
    # the people the story is about, calls everyone else by what they do, and
    # uses the surname alone after first mention.
    return ("- Name at most two people, using these names and no others: "
            + ", ".join(names[:2]) + ". Everyone else is a role, never a name: "
            "'the foreman's daughter', 'a clerk', 'the assembly chair'. After first "
            "mention use the surname alone, as a newspaper does. Do not default the "
            "weekday to Tuesday; vary or omit the day.")
