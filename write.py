"""Stage 3 - write. Turn the chosen premise into a full dispatch record."""
from __future__ import annotations

import re
import sys

import gemini
from common import hyphenate


# Common English idiom/spelling slips the model sometimes makes, corrected
# deterministically here (no extra API call). Add new ones as they are spotted.
_FIXUPS = {
    "for all intent and purpose": "for all intents and purposes",
    "for all intensive purposes": "for all intents and purposes",
    "peaked my interest": "piqued my interest",
    "peaked his interest": "piqued his interest",
    "peaked her interest": "piqued her interest",
    "peaked their interest": "piqued their interest",
    "case and point": "case in point",
    "one in the same": "one and the same",
    "deep-seeded": "deep-seated",
    "baited breath": "bated breath",
    "make due": "make do",
    "wet your appetite": "whet your appetite",
    "tow the line": "toe the line",
    "free reign": "free rein",
    "sneak peak": "sneak peek",
}


def _fix_slips(text: str) -> str:
    for wrong, right in _FIXUPS.items():
        text = re.sub(re.escape(wrong), right, text, flags=re.IGNORECASE)
    return text


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
- Follow the SHAPE of today's dispatch format above. Unless that format is a court
  ruling or an official notice, do NOT frame the story as an authority handing down
  a ruling with a spokesperson quote - use the format's own structure and voice.
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


def _generate_json(prompt: str, settings: dict, model: str | None,
                   retries: int | None = None) -> dict:
    """One generate + parse attempt on a given model; raises GeminiError on a
    transport error OR unparseable JSON, so the caller can fall back cleanly."""
    raw = gemini.generate(prompt, settings,
                          settings["gemini"]["temperature_write"], model=model,
                          retries=retries)
    return gemini.extract_json(raw)


def write(premise: str, dateline: dict, domain: str, settings: dict,
          style_guidance: str) -> dict:
    prompt = build_prompt(premise, dateline, domain, style_guidance)
    g = settings["gemini"]
    pro = (g.get("write_model") or "").strip()
    d = None
    served = g["model"]
    # Try the sharper Pro model first; fall back to flash on ANY failure
    # (a wrong/gated model name 404s, quota 429s, or Pro returns bad JSON) so
    # the dispatch still files rather than crash-publishing a stale page.
    if pro and pro != g["model"]:
        try:
            d = _generate_json(prompt, settings, pro, retries=0)
            served = pro
        except gemini.GeminiError as exc:
            print(f"    write: {pro} failed ({exc}); falling back to {g['model']}",
                  file=sys.stderr)
    if d is None:
        d = _generate_json(prompt, settings, g["model"])
        served = g["model"]
    print(f"    write: served by {served}", file=sys.stderr)
    dl = dict(dateline)
    dl["place"] = hyphenate((d.get("dateline_place") or "").strip())
    return {
        "headline": hyphenate(_fix_slips((d.get("headline") or "").strip())),
        "body": hyphenate(_fix_slips((d.get("body") or "").strip())),
        "scene": hyphenate((d.get("scene") or "").strip()),
        "dateline": dl,
        "domain": (d.get("domain") or domain).strip(),
        "glossary": [{"term": hyphenate(g.get("term", "").strip()),
                      "gloss": hyphenate(g.get("gloss", "").strip())}
                     for g in d.get("glossary", []) if g.get("term")],
        "premise": premise,
    }
