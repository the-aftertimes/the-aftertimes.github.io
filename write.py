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

The house voice is intelligent, dry and deadpan. This must actually be FUNNY and
interesting, not merely competent sci-fi. Commit fully to the one absurd idea and
follow its internal logic to increasingly ridiculous but consistent conclusions.
Make the comic idea clear within the first two sentences - never bury it under
procedure or worldbuilding. Favour wit and clarity over dense jargon. End on a
strong final line that lands or twists the joke (a real kicker), not a limp
summary. Do NOT force a strained running metaphor (for instance narrating a court
ruling or an interest-rate rise as though it were a sports match) unless it
genuinely lands.

Never build humour on gender, race, religion, nationality or similar
demographic stereotypes (no nagging-wife / clueless-husband cliches and the
like). The comedy comes from absurd systems, institutions, technologies and
bureaucratic logic - punch at ideas, not at people.

Rules:
- 250 to 350 words. Straight-faced, as a real wire story. Dry wit, never winking.
- The headline must be a concise, punchy single-line news headline, ideally
  under 10 words. Do NOT prefix it with a format label such as "Product
  Review:", "Obituary:", "Analysis:" or "Opinion:" - convey the format
  through the writing itself, not a tag.
- Invent a readable, evocative dateline place a reader can picture - a city,
  region, settlement or landmark (a plausible future or off-world place is
  fine). Do NOT use technical infrastructure jargon (no "sub-relay", "node",
  "array", "hub" type names).
- Coin at most two world-specific terms, and only if they are genuinely funny
  or necessary; if the story needs none, return an empty glossary. Only
  glossary a term a reader could not infer from context.
- Also provide "scene": ONE vivid, concrete, physical sentence describing a
  single visual moment from the story that an illustrator could draw -
  specific people, objects and setting, not abstract concepts. Example: "an
  armoured military unit pulls up to a suburban driveway while a couple hides
  beneath a dining table".
- Separate paragraphs with a blank line.
- Do not use em dashes or en dashes. Use plain hyphens.
- Use Australian English spelling (organise, colour, defence, metre, favour).
- Give every named person a fresh, varied, culturally diverse name. Do NOT use the names "Vance", "Elena", "Rostova", "Marcus" or "Kovac" - invent new ones each time. Do not default the weekday to Tuesday; vary or omit the day.
- Do not put the year in the dateline place; the date is shown separately.
- Invented names of groups, bodies, products or places should be concrete and evocative, not vague abstractions.

Return JSON only:
{{"headline": "...", "dateline_place": "...", "body": "...", "scene": "...",
  "domain": "{domain}", "glossary": [{{"term": "...", "gloss": "..."}}]}}"""


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
        "scene": hyphenate((d.get("scene") or "").strip()),
        "dateline": dl,
        "domain": (d.get("domain") or domain).strip(),
        "glossary": [{"term": hyphenate(g.get("term", "").strip()),
                      "gloss": hyphenate(g.get("gloss", "").strip())}
                     for g in d.get("glossary", []) if g.get("term")],
        "premise": premise,
    }
