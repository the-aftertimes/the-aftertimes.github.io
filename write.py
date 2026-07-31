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


# US -> AU spellings. The prompt asks for Australian English but the model still
# slips (31/07/2026 shipped a headline reading "Neighbor's"), so normalise
# deterministically here. Case-preserving for capitalised words.
_AU_SPELLING = {
    "neighbor": "neighbour", "neighbors": "neighbours",
    "neighborhood": "neighbourhood", "neighboring": "neighbouring",
    "color": "colour", "colors": "colours", "colored": "coloured",
    "favor": "favour", "favors": "favours", "favorite": "favourite",
    "honor": "honour", "honors": "honours", "labor": "labour",
    "harbor": "harbour", "harbors": "harbours", "odor": "odour",
    "rumor": "rumour", "rumors": "rumours", "vapor": "vapour",
    "behavior": "behaviour", "behaviors": "behaviours",
    "center": "centre", "centers": "centres", "centered": "centred",
    "meter": "metre", "meters": "metres", "liter": "litre", "liters": "litres",
    "theater": "theatre", "theaters": "theatres", "fiber": "fibre",
    # NOTE deliberately omitted as context-dependent: program (software vs
    # programme), license/practice (noun vs verb differ in AU English).
    "defense": "defence", "offense": "offence",
    "organize": "organise", "organized": "organised",
    "organization": "organisation", "organizations": "organisations",
    "recognize": "recognise", "recognized": "recognised",
    "realize": "realise", "realized": "realised",
    "apologize": "apologise", "apologized": "apologised",
    "authorize": "authorise", "authorized": "authorised",
    "specialize": "specialise", "specialized": "specialised",
    "analyze": "analyse", "analyzed": "analysed", "paralyzed": "paralysed",
    "localized": "localised", "localize": "localise",
    "traveled": "travelled", "traveling": "travelling", "traveler": "traveller",
    "canceled": "cancelled", "canceling": "cancelling",
    "modeling": "modelling", "labeled": "labelled", "labeling": "labelling",
    "fueled": "fuelled", "signaled": "signalled",
    "gray": "grey", "plow": "plough", "mold": "mould", "smolder": "smoulder",
    "aluminum": "aluminium",
}


def _match_case(src: str, repl: str) -> str:
    if src.isupper():
        return repl.upper()
    if src[:1].isupper():
        return repl[:1].upper() + repl[1:]
    return repl


def _au_spelling(text: str) -> str:
    """Rewrite US spellings to Australian, preserving the original casing.
    Word-boundary matched so 'programmer' / 'kilometers' style stems are safe."""
    def sub(m):
        return _match_case(m.group(0), _AU_SPELLING[m.group(0).lower()])
    pattern = r"\b(" + "|".join(sorted(_AU_SPELLING, key=len, reverse=True)) + r")\b"
    return re.sub(pattern, sub, text, flags=re.IGNORECASE)


def _fix_slips(text: str) -> str:
    for wrong, right in _FIXUPS.items():
        text = re.sub(re.escape(wrong), right, text, flags=re.IGNORECASE)
    return _au_spelling(text)


def build_prompt(premise: str, dateline: dict, domain: str,
                 style_guidance: str, place_guidance: str = "") -> str:
    place_rule = (f"\nToday's dateline setting: {place_guidance}\n"
                  if place_guidance else "")
    return f"""You are a correspondent for The Aftertimes. Write a single news
dispatch, datelined the year {dateline['year']}
({dateline['years_from_now']} years from now), in the domain: {domain}.

The premise: {premise}

Today's dispatch format: {style_guidance}
{place_rule}

The house voice is intelligent, dry and deadpan. This must actually be FUNNY and
interesting, not merely competent sci-fi. Commit fully to the one absurd idea and
follow its internal logic to increasingly ridiculous but consistent conclusions.
Make the comic idea clear within the first two sentences - never bury it under
procedure or worldbuilding. Favour wit and clarity over dense jargon. Do NOT force
a strained running metaphor (for instance narrating a court ruling or an
interest-rate rise as though it were a sports match) unless it genuinely lands.

COMEDY IS STRUCTURE, NOT VOCABULARY. The single most common failure is a flat
list of escalating consequences decorated with invented compound nouns
("hydro-hammock", "melt-rig"). Funny coinages are garnish, not the joke. So:
- Give the piece a TURN. Somewhere in the middle, the story must reveal something
  that reframes what came before - not just "and then it got worse". Vary WHERE
  the turn comes from; do not default to a rival claimant or an official body.
  It might be: someone's private and completely different motive, a physical
  consequence nobody anticipated, a social custom that makes the situation
  normal, a much older cause surfacing, an expert calmly explaining that this is
  routine, or a detail revealing everyone involved has misunderstood the point.
- Let a named person say something revealing IN THEIR OWN WORDS, quoted directly,
  and make the quote funnier than the narration around it. The best comedy comes
  from someone treating the absurd as completely reasonable.
- The last line must be a real KICKER: it should recontextualise, undercut, or
  escalate to a punchline - a joke that only works because of everything before
  it. A threat, a summary, or a restatement is not a kicker.
- Cut anything that is merely world-building. If a sentence does not advance the
  story or land a joke, delete it.
- AVOID THE LEGAL/FINANCIAL CRUTCH. Unless the premise is genuinely about money or
  law, do not resolve or escalate the story through debts, taxes, fines, liens,
  injunctions, permits, lawsuits, insurance or repossession. The paper leaned on
  that register far too heavily. Find the consequence somewhere else: physical,
  social, emotional, practical, ecological or ceremonial.

Never build humour on gender, race, religion, nationality or similar
demographic stereotypes (no nagging-wife / clueless-husband cliches and the
like). The comedy comes from absurd systems, institutions, technologies and
bureaucratic logic - punch at ideas, not at people.

Rules:
- Follow the SHAPE of today's dispatch format above. Unless that format is a court
  ruling or an official notice, do NOT frame the story as an authority handing down
  a ruling with a spokesperson quote - use the format's own structure and voice.
- 250 to 350 words. Straight-faced, as a real wire story. Dry wit, never winking.
- THE HEADLINE MUST CARRY THE JOKE, in under 10 words. A newspaper-accurate but
  purely descriptive label is a failure. Do NOT use the pattern
  "'Branded Product' Does Literal Thing To Place" - that describes the premise
  instead of being funny about it. The headline should make a reader smile before
  they read a word of the body: find the absurd juxtaposition, the deadpan
  understatement, or the institutional euphemism, and lead with THAT.
  Weak: "Neighbour's 'Alpine Blizzard' Garden Package Dumps Snowdrifts Over Fence"
  Strong: "Council Rules Snow Is Trespassing"
  Do NOT prefix it with a format label such as "Product Review:", "Obituary:",
  "Analysis:" or "Opinion:" - convey the format through the writing itself.
- Invent a readable, evocative dateline place a reader can picture, matching
  today's dateline setting above. It must feel genuinely FUTURE and off-world.
  NEVER name it "New " plus an existing Earth city (no New Wollongong, no New
  Sydney, no New Cairo) - that is lazy and it has happened too often. Do NOT use
  technical infrastructure jargon (no "sub-relay", "node", "array", "hub" type
  names). Vary the linguistic root widely - any Earth language or invented; the
  Australian-spelling rule below is about SPELLING and is emphatically not a
  reason to use Australian place names.
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
          style_guidance: str, place_guidance: str = "") -> dict:
    prompt = build_prompt(premise, dateline, domain, style_guidance,
                          place_guidance)
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
