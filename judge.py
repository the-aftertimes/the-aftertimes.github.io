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
  world as completely normal?

Ignore polish, grammar and length - those are fixed separately. Pick on comedy
and point alone. Do not be swayed by whichever is longest or most elaborate.
{joined}
Return JSON only: {{"pick": <the draft number>, "reason": "<one short line>"}}"""


def judge(drafts: list[dict], settings: dict) -> dict:
    """Return {"pick": zero-based index, "reason": str}."""
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
    return {"pick": pick - 1, "reason": str(data.get("reason", "")).strip()}
