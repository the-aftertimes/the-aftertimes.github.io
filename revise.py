"""Critique and rewrite a winning draft. One model call that returns BOTH the
critique and the revision, so the reasoning benefit arrives without a second
call. The caller decides whether to keep the result - see the acceptance gate in
run.py, which discards a revision that measures worse than the draft."""
from __future__ import annotations

import gemini
from write import normalise


def render_violations(violations: list[dict]) -> str:
    if not violations:
        return "- no measured faults; tighten the comedy only"
    return "\n".join(f"- [{v['severity']}] {v['detail']}" for v in violations)


def build_prompt(dispatch: dict, violations: list[dict]) -> str:
    return f"""You are the editor of The Aftertimes revising a dispatch before
publication. Below is today's draft, followed by faults measured mechanically.

CURRENT HEADLINE: {dispatch['headline']}

CURRENT BODY:
{dispatch['body']}

MEASURED FAULTS:
{render_violations(violations)}

Fix every fault above. At the same time make the piece FUNNIER and more pointed:
sharpen the headline so it lands a joke rather than describing the premise, make
sure a quoted character says something genuinely funny while treating the absurd
world as normal, and make the final line a real kicker that recontextualises
rather than restates.

THEN READ IT ONCE MORE FOR INTERNAL LOGIC. The measured faults above are
mechanical; these are not, and nothing else in the pipeline can see them. All
three shipped on 22/08/2026 in a piece whose premise was strong.
- DOES EACH QUOTE COME FROM WHERE THE STORY SAYS IT DOES? A dispatch whose source
  is a leaked recording cannot then write '"..." said his coach' - nobody was
  being interviewed. Attribute it to the tape: the coach is HEARD saying it.
  Check every "said" against how the reporter could possibly have heard it.
- DOES THE PUNCHLINE OBEY THE STORY'S OWN LOGIC? A public that adored a
  politician for being clumsy does not then elect "a logistics clerk who had
  never once dropped a spoon" - the joke inverts the very thing the story
  established. They would elect someone genuinely, catastrophically clumsy. Trace
  each consequence back and check it follows from the premise rather than
  contradicting it.
- IS EVERY INVENTED TERM UNDERSTANDABLE ON SIGHT? "He dropped his voting wands"
  went out with no explanation and no glossary entry, and a reader simply stops.
  Being made of plain words is not enough; the reader has to be able to picture
  the thing. Either make it obvious in the sentence that uses it, or use the
  ordinary word.

Do NOT blandify. Keep the specific, concrete and strange details; cut the
explanatory and generic sentences instead. Keep the same story, dateline place
and domain. Australian spelling. Plain hyphens only, never em or en dashes.

Return JSON only:
{{"critique": "<two short lines on what was wrong>",
  "revised": {{"headline": "...", "dateline_place": "...", "body": "...",
               "scene": "...", "domain": "...",
               "glossary": [{{"term": "...", "gloss": "..."}}]}}}}"""


def revise(dispatch: dict, violations: list[dict], settings: dict) -> dict:
    """Return {"critique": str, "dispatch": <normalised dispatch>}.
    Raises GeminiError if the model returns nothing usable."""
    raw = gemini.generate(build_prompt(dispatch, violations), settings,
                          settings["gemini"]["temperature_write"])
    data = gemini.extract_json(raw)
    if isinstance(data, list):
        data = data[0] if data else {}
    revised = data.get("revised")
    if not isinstance(revised, dict):
        raise gemini.GeminiError(f"revise returned no usable revision: {data!r}")
    # Validate EVERY field the page needs, not just the body. A revision with a
    # body but no headline used to pass here, then score identically to a good
    # dispatch, and would have published an empty <h1>.
    for field in ("headline", "dateline_place", "body"):
        if not (revised.get(field) or "").strip():
            raise gemini.GeminiError(
                f"revise returned a revision with no {field}: {revised!r}")
    out = normalise(revised, dispatch["dateline"], dispatch["domain"],
                    dispatch.get("premise", ""))
    # THE EDITOR DOES NOT GET TO REWRITE THE PICTURE BRIEF. Caught 22/08/2026 on
    # a dry run: asked to revise an obituary, the model returned
    # `"scene": "OBITUARIES"` - it read the field as a section label, because
    # nothing in THIS prompt explains what a scene line is (the write prompt
    # spends a paragraph on it, and the editor never sees that). The scene drives
    # depict and therefore the illustration, so an accepted revision would have
    # drawn the day's picture from the word OBITUARIES.
    #
    # It is also the right rule regardless of the bug: this is a prose pass. If
    # the rewrite genuinely moves the visual moment, redraw deliberately with
    # reillustrate.py --scene rather than let it happen as a side effect.
    out["scene"] = dispatch.get("scene", "")
    return {"critique": str(data.get("critique", "")).strip(), "dispatch": out}
