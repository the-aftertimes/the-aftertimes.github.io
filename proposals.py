"""The weekly, human-gated half of the learning loop.

Writes a document proposing changes to the HAND-WRITTEN prompts, with the evidence
behind each. It is never applied automatically: an unattended process editing the
core house voice is the highest-blast-radius change available, and one bad edit
would degrade every dispatch after it, silently.
"""
from __future__ import annotations

from collections import Counter


def build(records: list[dict], verdicts: dict, hits: list[dict]) -> str:
    tally = Counter(v.get("verdict") for v in verdicts.values())
    lines = [
        "# Prompt proposals",
        "",
        "Generated from the archive and Charlie's verdicts. These are SUGGESTIONS.",
        "Nothing here is applied automatically; the hand-written prompts",
        "change only when Charlie says so.",
        "",
        f"## Verdicts so far: good: {tally.get('good', 0)}, "
        f"bad: {tally.get('bad', 0)}",
        "",
    ]
    bad_notes = [v.get("note", "") for v in verdicts.values()
                 if v.get("verdict") == "bad" and v.get("note")]
    if bad_notes:
        lines += ["### What Charlie disliked, in his words", ""]
        lines += [f"- {n}" for n in bad_notes] + [""]
    if hits:
        lines += ["### Over-used lately", ""]
        lines += [f"- {h['kind']}: \"{h['item']}\" in {h['count']} dispatches"
                  for h in hits[:20]] + [""]
    lines += [
        "### Suggested next step",
        "",
        "Read the items above. If a pattern here reflects a rule that should",
        "change, edit the prompt yourself or ask for the change - the loop will",
        "not touch it.",
        "",
    ]
    return "\n".join(lines)
