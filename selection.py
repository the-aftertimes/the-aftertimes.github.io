"""Stage 2 - select. Pick premises that pass the novelty gate against the ledger
AND are not near-duplicates of each other; fall back to the head of the list if
too few survive, because publishing beats not publishing."""
from __future__ import annotations

from ledger import is_novel


def select(premises: list[str], ledger: list[dict], settings: dict) -> str:
    nov = settings["novelty"]
    for premise in premises:
        if is_novel(premise, ledger, nov["match_threshold"], nov["recent_window"]):
            return premise
    return premises[0]


def select_many(premises: list[str], ledger: list[dict], settings: dict,
                n: int) -> list[str]:
    """Up to `n` premises, strongest first (ideate already sorts them), each novel
    against the ledger and against the ones already chosen."""
    nov = settings["novelty"]
    chosen: list[str] = []
    for premise in premises:
        if len(chosen) >= n:
            break
        if not is_novel(premise, ledger, nov["match_threshold"],
                        nov["recent_window"]):
            continue
        # compare against the picks so far by reusing the same gate, treating
        # each chosen premise as though it were a recent headline
        peers = [{"headline": c} for c in chosen]
        if chosen and not is_novel(premise, peers, nov["match_threshold"],
                                   nov["recent_window"]):
            continue
        chosen.append(premise)
    return chosen or premises[:1]
