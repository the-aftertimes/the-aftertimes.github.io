"""Stage 3 - write. Turn the chosen premise into a full dispatch record."""
from __future__ import annotations

import gemini
from common import hyphenate


def build_prompt(premise: str, dateline: dict, domain: str) -> str:
    return f"""You are a correspondent for The Aftertimes. Write a single news
dispatch, datelined the year {dateline['year']}
({dateline['years_from_now']} years from now), in the domain: {domain}.

The premise: {premise}

Rules:
- 250 to 350 words. Straight-faced, as a real wire story. Dry wit, never winking.
- Invent a plausible future place for the dateline.
- File it under an invented future newswire.
- Coin 1 to 3 world-specific terms and define each in one line for the glossary.
- Do not use em dashes or en dashes. Use plain hyphens.

Return JSON only:
{{"headline": "...", "dateline_place": "...", "body": "...",
  "wire_name": "...", "wire_gloss": "...", "domain": "{domain}",
  "glossary": [{{"term": "...", "gloss": "..."}}]}}"""


def write(premise: str, dateline: dict, domain: str, settings: dict) -> dict:
    prompt = build_prompt(premise, dateline, domain)
    raw = gemini.generate(prompt, settings,
                          settings["gemini"]["temperature_write"])
    d = gemini.extract_json(raw)
    dl = dict(dateline)
    dl["place"] = hyphenate((d.get("dateline_place") or "").strip())
    return {
        "headline": hyphenate((d.get("headline") or "").strip()),
        "body": hyphenate((d.get("body") or "").strip()),
        "dateline": dl,
        "wire": {"name": hyphenate((d.get("wire_name") or "").strip()),
                 "gloss": hyphenate((d.get("wire_gloss") or "").strip())},
        "domain": (d.get("domain") or domain).strip(),
        "glossary": [{"term": hyphenate(g.get("term", "").strip()),
                      "gloss": hyphenate(g.get("gloss", "").strip())}
                     for g in d.get("glossary", []) if g.get("term")],
        "premise": premise,
    }
