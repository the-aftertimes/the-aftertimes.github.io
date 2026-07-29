"""Stage 3 - write. Turn the chosen premise into a full dispatch record."""
from __future__ import annotations

import gemini
from common import hyphenate


def build_prompt(premise: str, dateline: dict, domain: str,
                 style_guidance: str) -> str:
    return f"""You are a correspondent for The Aftertimes. Write a single news
dispatch, datelined the year {dateline['year']}
({dateline['years_from_now']} years from now), in the domain: {domain}.

The premise: {premise}

Today's dispatch format: {style_guidance}

The house voice is intelligent, dry and deadpan. Lead with a clear, absurd
premise and keep the joke legible. Favour wit and clarity over dense
science-fiction jargon - the humour comes from a simple absurd idea taken
seriously, not from piling on invented vocabulary.

Rules:
- 250 to 350 words. Straight-faced, as a real wire story. Dry wit, never winking.
- Invent a readable, evocative dateline place a reader can picture - a city,
  region, settlement or landmark (a plausible future or off-world place is
  fine). Do NOT use technical infrastructure jargon (no "sub-relay", "node",
  "array", "hub" type names).
- File it under an invented future newswire.
- Coin at most two world-specific terms, and only if they are genuinely funny
  or necessary; if the story needs none, return an empty glossary. Only
  glossary a term a reader could not infer from context.
- Separate paragraphs with a blank line.
- Do not use em dashes or en dashes. Use plain hyphens.
- Use Australian English spelling (organise, colour, defence, metre, favour).
- Vary character names and places widely; do not reuse common names. Do not default the day to Tuesday - vary or omit the weekday.
- Do not put the year in the dateline place; the date is shown separately.

Return JSON only:
{{"headline": "...", "dateline_place": "...", "body": "...",
  "wire_name": "...", "wire_gloss": "...", "domain": "{domain}",
  "glossary": [{{"term": "...", "gloss": "..."}}]}}"""


def write(premise: str, dateline: dict, domain: str, settings: dict,
          style_guidance: str) -> dict:
    prompt = build_prompt(premise, dateline, domain, style_guidance)
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
