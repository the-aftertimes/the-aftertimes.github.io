"""Stage 2 - select. Pick premises that pass the novelty gate against the ledger
AND are not near-duplicates of each other; fall back to the head of the list if
too few survive, because publishing beats not publishing."""
from __future__ import annotations

import sys

from ledger import is_novel

#: Never return fewer than this many premises: with one draft there is nothing for
#: the judge to choose between and the multi-draft pipeline is a no-op.
_MIN_DRAFTS = 2


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
    # Returning ONE premise would silently collapse the whole multi-draft pipeline
    # to a single draft, with nothing in the log to say why. So guarantee the judge
    # always has something to choose between. We top up only to _MIN_DRAFTS, NOT to
    # n: padding with premises the novelty gate just rejected as near-duplicates
    # would buy a third draft that is a near-clone of another, which costs a call
    # and adds no variety.
    if len(chosen) < _MIN_DRAFTS:
        novel = len(chosen)
        for premise in premises:
            if len(chosen) >= _MIN_DRAFTS:
                break
            if premise not in chosen:
                chosen.append(premise)
        print(f"    note: only {novel} premise(s) passed the novelty gate; "
              f"topped up to {len(chosen)} so the judge has a choice",
              file=sys.stderr)
    return chosen or premises[:1]
