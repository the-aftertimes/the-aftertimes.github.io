"""Stage 2 - select. Pick the first premise that passes the novelty gate;
fall back to the first premise if every candidate is too close to a recent one."""
from __future__ import annotations

from ledger import is_novel


def select(premises: list[str], ledger: list[dict], settings: dict) -> str:
    nov = settings["novelty"]
    for premise in premises:
        if is_novel(premise, ledger, nov["match_threshold"], nov["recent_window"]):
            return premise
    return premises[0]
