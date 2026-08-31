"""Pick the funniest of several drafts - the one question the deterministic
critic cannot answer. One model call; raises GeminiError on anything unusable so
the orchestrator can fall back to the top deterministic score."""
from __future__ import annotations

import gemini


def build_prompt(drafts: list[dict]) -> str:
    blocks = []
    for i, d in enumerate(drafts, start=1):
        blocks.append(f"DRAFT {i}\nHeadline: {d['headline']}\n\n{d['body']}")
    joined = "\n\n" + ("\n\n" + "-" * 40 + "\n\n").join(blocks) + "\n\n"
    return f"""You are the editor of The Aftertimes, a satirical newspaper filing
dispatches from the future. Below are {len(drafts)} candidate dispatches for
today's edition. Choose the ONE to publish.

Judge on which is FUNNIEST and most pointed. Specifically:
- Does it satirise something recognisably true about people or institutions, or
  is it merely a whimsical impossibility that is about nothing?
- Does the headline land a joke rather than describe the premise?
- Does the final line work as a real kicker?
- Does a quoted character say something genuinely funny while treating an absurd
  world as completely normal - or is a source explaining the joke to the reader?
- Does the opening sentence already contain the whole joke, leaving the rest to
  restate it in different words? A dispatch that announces its conceit and then
  circles it has no turn in it. This is the fault no measurement catches: on
  31/08/2026 the piece Charlie called unfunny had the LOWEST theme repetition and
  the HIGHEST lexical variety in the whole archive, because it restates its idea
  semantically rather than by repeating words. Only you can see it.

Ignore polish, grammar and length - those are fixed separately. Pick on comedy
and point alone. Do not be swayed by whichever is longest or most elaborate.
{joined}
Also rate the one you picked out of 10 for how funny it actually is, judged
against a good satirical newspaper and NOT against the other drafts here. A pool
of three weak dispatches still has a best one; say so honestly rather than
grading on the curve. 5 means it would raise a half-smile. 8 means you would send
it to someone.

Return JSON only: {{"pick": <the draft number>, "score": <1-10>,
"reason": "<one short line>"}}"""


def judge(drafts: list[dict], settings: dict) -> dict:
    """Return {"pick": zero-based index, "score": float|None, "reason": str}.

    The score is what lets the caller decide the whole pool is not good enough.
    Without it the judge can only ever return the funniest of what it was given,
    which on a bad night is still a bad dispatch - the fault Charlie named on
    31/08/2026. A missing or unparseable score is None, never a default number:
    inventing one would let a silent API change quietly disable the floor.
    """
    raw = gemini.generate(build_prompt(drafts), settings,
                          settings["gemini"]["temperature_write"])
    data = gemini.extract_json(raw)
    if isinstance(data, list):
        data = data[0] if data else {}
    try:
        pick = int(data.get("pick"))
    except (TypeError, ValueError):
        raise gemini.GeminiError(f"judge returned no usable pick: {data!r}")
    if not 1 <= pick <= len(drafts):
        raise gemini.GeminiError(
            f"judge pick {pick} out of range for {len(drafts)} drafts")
    try:
        score = float(data.get("score"))
    except (TypeError, ValueError):
        score = None
    if score is not None and not 0 <= score <= 10:
        score = None
    return {"pick": pick - 1, "score": score,
            "reason": str(data.get("reason", "")).strip()}
