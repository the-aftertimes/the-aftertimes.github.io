"""The paper's self-improvement loop: a champion and a challenger set of house notes.

Charlie, 07/10/2026: "set up a way to recursively improve it each day? just hone
the prompt so it gets funnier", and then "i don't want to have to be involved".
So the signal is automated, and it is one the pipeline already pays for.

HOW IT WORKS
- The write prompt carries a short block of HOUSE NOTES: a few craft lines that
  sit on top of the fixed rules. Only this block is ever machine-edited. The
  hand-written prompt - the deadpan rule, the register guards, the spelling, the
  critic's hard rejects - is never touched, so the worst a bad note can do is
  write a weaker draft that then has to win the day's contest to be published.
- When there is a CHALLENGER (the champion plus one edit), each day's drafts
  alternate between the two sets of notes.
- The day's committee of comedians and the judge then choose the edition as
  they always have, blind to which notes wrote which draft. If both sets had a
  draft in front of them and one of them actually chose, the published draft's
  notes win that day. Zero extra calls: the contest was already being run.
- After `trials` decided days, the challenger is promoted if it won at least
  `promote_at` of them, otherwise retired. Either way one Gemini call proposes
  the next challenger, from the critiques the revise pass stores on every record.

THE STATED COST, ONCE: this learns what the Gemini committee finds funny, which
is not guaranteed to be what Charlie finds funny. It is the trade for him not
being in the loop, and it was made with that said. The bounded block, the
blind contest and the fixed rules are what keep it from drifting somewhere
strange; the history in config/house_notes.yaml is how to see if it has.

At 10 trials and 7 wins, a challenger no better than the champion is promoted
about 17% of the time by luck. A wrong promotion costs one weak note, and the
next challenger is free to delete it.

Pure except for load/save and propose(), which makes one model call.
"""
from __future__ import annotations

import re
from datetime import date

import yaml

from common import rel

STATE_PATH = "config/house_notes.yaml"
CHAMPION, CHALLENGER = "champion", "challenger"

#: The notes may not ask for any of these. Each is a settled house decision
#: that a loop optimising for a model's laughter could plausibly talk itself
#: into, and each has already been tried and rejected by Charlie.
_FORBIDDEN = re.compile(
    r"\b(first[- ]person|haiku|surreal\w*|dreamlike|escalat\w*|"
    r"more absurd|wilder|zany|whimsical|em dash\w*)\b|—|–",
    re.I)


def empty_state() -> dict:
    return {"champion": [], "challenger": None, "why": "", "since": "",
            "results": {}, "history": []}


def load() -> dict:
    try:
        with open(rel(STATE_PATH), encoding="utf-8") as fh:
            state = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        state = {}
    return {**empty_state(), **state}


def save(state: dict) -> None:
    with open(rel(STATE_PATH), "w", encoding="utf-8") as fh:
        fh.write("# Machine-edited by tune.py. Read its docstring before changing "
                 "anything here.\n")
        yaml.safe_dump(state, fh, allow_unicode=True, sort_keys=False, width=100)


def variant_for(state: dict, position: int) -> str:
    """Alternate the day's drafts, champion first, when there is a challenger."""
    if state.get("challenger") is None:
        return CHAMPION
    return CHALLENGER if position % 2 == 1 else CHAMPION


def notes_for(state: dict, variant: str) -> list[str]:
    if variant == CHALLENGER and state.get("challenger") is not None:
        return list(state["challenger"])
    return list(state.get("champion") or [])


def block(notes: list[str]) -> str:
    """The prompt text. Empty for no notes, so the prompt is unchanged."""
    if not notes:
        return ""
    return ("House notes, learnt from earlier editions:\n"
            + "\n".join(f"- {n}" for n in notes) + "\n")


def outcome(info: dict, chosen_variant: str | None) -> str | None:
    """'win' or 'loss' for the challenger, or None when the day decides nothing.

    A day only counts when BOTH sets of notes had a draft in the contest and the
    committee or the judge actually chose. A pick made by the critic's score
    alone is a measure of rule-keeping, not of funniness, and a day where only
    one side wrote anything is a walkover."""
    present = set(info.get("contest_variants") or [])
    if not {CHAMPION, CHALLENGER} <= present:
        return None
    if info.get("panel") is None and info.get("judge_pick") is None:
        return None
    if chosen_variant not in (CHAMPION, CHALLENGER):
        return None
    return "win" if chosen_variant == CHALLENGER else "loss"


def record(state: dict, run_date: str, result: str | None) -> dict:
    """Keyed by date, so a day can never be counted twice."""
    if result and state.get("challenger") is not None:
        state["results"] = {**(state.get("results") or {}), run_date: result}
    return state


def decide(state: dict, cfg: dict, today: str) -> str | None:
    """Promote or retire the challenger once it has enough decided days.
    Returns 'promoted', 'retired' or None, and mutates state."""
    if state.get("challenger") is None:
        return None
    results = list((state.get("results") or {}).values())
    if len(results) < int(cfg.get("trials", 10)):
        return None
    wins = results.count("win")
    verdict = "promoted" if wins >= int(cfg.get("promote_at", 7)) else "retired"
    state["history"] = (state.get("history") or []) + [{
        "decided": today, "verdict": verdict, "wins": wins, "of": len(results),
        "since": state.get("since", ""), "why": state.get("why", ""),
        "champion_before": list(state.get("champion") or []),
        "challenger": list(state["challenger"])}]
    if verdict == "promoted":
        state["champion"] = list(state["challenger"])
    state.update(challenger=None, why="", since="", results={})
    return verdict


def valid(notes, champion: list[str], cfg: dict) -> bool:
    """A proposal must be a short list of short lines, differ from the champion
    by a single edit, and ask for nothing the house has already ruled out."""
    if not isinstance(notes, list) or not all(isinstance(n, str) for n in notes):
        return False
    notes = [n.strip() for n in notes]
    if not all(notes) or len(notes) > int(cfg.get("max_lines", 8)):
        return False
    if any(len(n) > int(cfg.get("max_line_chars", 220)) for n in notes):
        return False
    if any(_FORBIDDEN.search(n) for n in notes):
        return False
    if notes == list(champion):
        return False
    # One edit: an add, a delete, or one line reworded.
    old, new = list(champion), notes
    if abs(len(old) - len(new)) > 1:
        return False
    if len(new) == len(old):
        return sum(a != b for a, b in zip(old, new)) == 1
    small, big = (old, new) if len(old) < len(new) else (new, old)
    return any(big[:i] + big[i + 1:] == small for i in range(len(big)))


def evidence(records: list[dict], n: int = 10) -> str:
    """What the next proposal is written from: the most recent editions'
    headlines with the revise pass's critique and the judge's reason."""
    lines = []
    for r in records[-n:]:
        q = r.get("quality") or {}
        d = r.get("dispatch") or {}
        bits = [f"Headline: {d.get('headline', '')}"]
        if q.get("critique"):
            bits.append(f"Editor's critique: {q['critique']}")
        if q.get("judge_reason"):
            bits.append(f"Why it won the day: {q['judge_reason']}")
        lines.append(" | ".join(bits))
    return "\n".join(lines)


def proposal_prompt(champion: list[str], records: list[dict], history: list[dict],
                    cfg: dict) -> str:
    current = "\n".join(f"- {n}" for n in champion) or "(none yet)"
    tried = "\n".join(
        f"- {h['verdict']} ({h['wins']}/{h['of']}): {h.get('why', '')}"
        for h in (history or [])[-6:]) or "(nothing tried yet)"
    return f"""You edit the house notes for The Aftertimes, a deadpan satirical
newspaper that reports absurd future events completely straight, like a wire
service. The notes are a few short craft lines added to the writer's prompt.
The writer already has fixed rules you must not restate or contradict: report
the facts and never state the joke, one absurdity per dispatch with everything
else ordinary, satirise something real, third person news only, plain modern
words, a real kicker, Australian spelling, no dashes.

Current house notes:
{current}

Recent editions, with the editor's critique and why each won its day:
{evidence(records)}

Recent changes already tried, and whether they won:
{tried}

Propose exactly ONE change that would make tomorrow's drafts funnier: add one
note, delete one note, or reword one note. A note is one concrete, checkable
instruction about craft (how a sentence, a quote, a headline or a kicker is
built), under {int(cfg.get('max_line_chars', 220))} characters. Aim at the
fault the critiques keep naming. Never ask for more absurdity, escalation,
whimsy, first person, or a different format. At most
{int(cfg.get('max_lines', 8))} notes in total.

Return JSON only: {{"notes": ["...the full new list..."], "why": "one sentence"}}"""


def propose(state: dict, records: list[dict], settings: dict, today: str) -> bool:
    """One model call. Sets a new challenger if the proposal is valid. Never
    raises: a failed proposal just means another try on the next edition."""
    import write as write_stage
    cfg = settings.get("tune") or {}
    prompt = proposal_prompt(state.get("champion") or [], records,
                             state.get("history") or [], cfg)
    for model in write_stage.models(settings):
        try:
            got = write_stage._generate_json(prompt, settings, model, retries=0)
        except Exception as exc:  # noqa: BLE001 - see docstring
            print(f"    tune: {model} failed ({str(exc)[:120]})")
            continue
        notes = [n.strip() for n in (got.get("notes") or [])
                 if isinstance(n, str)] if isinstance(got, dict) else None
        if notes is not None and valid(notes, state.get("champion") or [], cfg):
            state.update(challenger=notes, why=str(got.get("why", "")).strip(),
                         since=today, results={})
            return True
        print(f"    tune: {model} proposed an invalid change; not taken")
        return False
    return False


def after_edition(settings: dict, run_date: str, info: dict,
                  chosen_variant: str | None, records: list[dict]) -> dict:
    """The whole daily step, run once an edition has filed. Returns a summary
    for the dispatch record. Never raises."""
    cfg = settings.get("tune") or {}
    if not cfg.get("enabled"):
        return {}
    state = load()
    result = outcome(info, chosen_variant)
    record(state, run_date, result)
    summary = {"variant": chosen_variant, "result": result,
               "challenger_record": dict(state.get("results") or {})}
    verdict = decide(state, cfg, run_date)
    if verdict:
        summary["decision"] = verdict
        print(f"    tune: challenger {verdict}")
    if state.get("challenger") is None:
        if propose(state, records, settings, run_date):
            print(f"    tune: new challenger - {state['why']}")
            summary["new_challenger"] = state["why"]
    save(state)
    return summary
