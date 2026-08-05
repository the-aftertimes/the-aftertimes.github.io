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
    return {"critique": str(data.get("critique", "")).strip(), "dispatch": out}
