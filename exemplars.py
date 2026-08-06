"""Promote Charlie-endorsed premises into the few-shot pool.

This is the mechanism by which the paper actually gets funnier: few-shot examples
dominate model output far more than instructions do, so a growing pool of premises
Charlie personally liked steers every future generation.

For exactly that reason the pool's REGISTER is guarded. Letting it fill with legal
and financial premises would re-create the collapse where every dispatch became a
story about debt, tax and injunctions.
"""
from __future__ import annotations

import re

_LEGAL = re.compile(
    r"\b(sue[sd]?|suing|lawsuit|court|magistrate|tribunal|injunction|lien|liens"
    r"|repossess\w*|bailiff\w*|writ|statute|ordinance|tax|taxes|levy|levies"
    r"|debt|debts|money|budget|paperwork|accountant)\b", re.I)

#: Maximum share of the pool that may be legal or financial in register.
_MAX_LEGAL_SHARE = 0.25


def is_legal(premise: str) -> bool:
    return bool(_LEGAL.search(premise or ""))


def legal_share(pool: list[str]) -> float:
    return (sum(1 for p in pool if is_legal(p)) / len(pool)) if pool else 0.0


def promote(pool: list[str], premise: str, cap: int) -> list[str]:
    """Add `premise` unless it would unbalance the register. Returns the new pool;
    the caller decides whether anything changed."""
    premise = (premise or "").strip()
    if not premise or premise in pool:
        return list(pool)
    if is_legal(premise):
        would_be = list(pool) + [premise]
        if legal_share(would_be) > _MAX_LEGAL_SHARE:
            return list(pool)          # refused, deliberately silent to callers
    out = list(pool) + [premise]
    return out[-cap:] if len(out) > cap else out
