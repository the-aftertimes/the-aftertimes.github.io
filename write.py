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


# Words ending -ize/-ization that are NOT the -ise suffix (they derive from
# "size", "prize" etc.) and must be left alone.
_IZE_EXCEPTIONS = {"capsize", "capsized", "capsizing", "downsize", "downsized",
                   "downsizing", "upsize", "resize", "resized", "resizing",
                   "oversize", "oversized", "midsize", "assize", "assizes"}


def _ise_suffix(text: str) -> str:
    """General -ize/-ization -> -ise/-isation rule, so the paper does not need an
    entry per word (a headline shipped 'civilization'). Requires a 4+ character
    stem and skips the size/prize family."""
    def sub(m):
        word = m.group(0)
        if word.lower() in _IZE_EXCEPTIONS:
            return word
        i = word.lower().rfind("iz")           # swap only the z of the -iz- suffix
        z = word[i + 1]
        return word[:i + 1] + ("S" if z.isupper() else "s") + word[i + 2:]
    return re.sub(r"\b\w{4,}iz(?:e|es|ed|ing|ation|ations)\b", sub, text,
                  flags=re.IGNORECASE)


def _au_spelling(text: str) -> str:
    """Rewrite US spellings to Australian, preserving the original casing.
    Word-boundary matched so 'programmer' / 'kilometers' style stems are safe."""
    def sub(m):
        return _match_case(m.group(0), _AU_SPELLING[m.group(0).lower()])
    pattern = r"\b(" + "|".join(sorted(_AU_SPELLING, key=len, reverse=True)) + r")\b"
    text = re.sub(pattern, sub, text, flags=re.IGNORECASE)
    return _ise_suffix(text)


_MACHINE_PHRASES = (
    "took an unexpected turn", "the scandal deepened", "hit a crisis",
    "raising questions about", "sparking debate", "serving as a reminder",
    "underscoring", "highlighting the", "in a move that",
    "one thing is certain", "only time will tell",
)


def prose_report(body: str) -> dict:
    """Measure the tells that make a dispatch read machine-written: long uniform
    sentences and stock connective phrases. Printed after each run so drift is
    visible in the CI log instead of only being noticed by a reader."""
    flat = re.sub(r"\s+", " ", body).strip()
    # Allow a closing quote after the full stop, or sentences ending inside
    # dialogue get merged with the next one - which inflated the mean and hid
    # short sentences, firing false "reads long/uniform" warnings.
    sents = [s for s in re.split(r"(?<=[.!?])[\"”’']*\s+", flat)
             if s.strip()]
    lens = [len(s.split()) for s in sents] or [0]
    return {
        "words": len(flat.split()),
        "sentences": len(sents),
        "mean_sentence": round(sum(lens) / len(lens), 1),
        "longest": max(lens),
        "short_sentences": sum(1 for n in lens if n <= 6),
        "machine_phrases": [p for p in _MACHINE_PHRASES if p in body.lower()],
    }


def _fix_slips(text: str) -> str:
    for wrong, right in _FIXUPS.items():
        text = re.sub(re.escape(wrong), right, text, flags=re.IGNORECASE)
    return _au_spelling(text)


def _era_rule(years: int) -> str:
    """How strange everything must be, scaled to the distance. Without this the
    model furnishes any date with present-day props: a dispatch set in 37562 came
    back with Boston ferns, candles, handwritten poems and a bronze plaque."""
    if years < 400:
        return ("Institutions are still recognisable but strained; technology and "
                "daily habits have clearly moved a generation or two beyond ours.")
    if years < 4000:
        return ("Centuries have passed. Institutions, jobs, materials and customs "
                "should be UNFAMILIAR - descendants of ours, not ours. Nothing "
                "should be branded or built the way it is today.")
    return ("This is tens of thousands of years out - further from us than we are "
            "from the first cities. Essentially NOTHING of the present survives "
            "unchanged: not our nations, languages, companies, materials, plants, "
            "animals, religions or units. If something ancient does persist, that "
            "persistence must itself be the point of the story.")


def build_prompt(premise: str, dateline: dict, domain: str,
                 style_guidance: str, place_guidance: str = "",
                 avoid_block: str = "") -> str:
    place_rule = (f"\nToday's dateline setting: {place_guidance}\n"
                  if place_guidance else "")
    era_rule = _era_rule(int(dateline.get("years_from_now") or 0))
    avoid_extra = f"\n{avoid_block}\n" if avoid_block else ""
    return f"""You are a correspondent for The Aftertimes. Write a single news
dispatch, datelined the year {dateline['year']}
({dateline['years_from_now']} years from now), in the domain: {domain}.

The premise: {premise}

Today's dispatch format: {style_guidance}
{place_rule}

The house voice is intelligent, dry and deadpan. This must actually be FUNNY and
interesting, not merely competent sci-fi. Commit fully to the one absurd idea and
follow its internal logic to increasingly ridiculous but consistent conclusions.
Favour wit and clarity over dense jargon. Do NOT force a strained running metaphor
(for instance narrating a court ruling as though it were a sports match) unless it
genuinely lands.

REPORT THE FACTS; NEVER STATE THE JOKE. Open on concrete news - what happened, to
whom, where, when - and get to it fast, without burying it under worldbuilding.
But the absurdity must be VISIBLE IN THE FACTS, never asserted in a summary
clause. Do not have the narrator, or a character, describe the comic mechanism out
loud. Characters must behave as though their world is entirely normal; they cannot
see the joke.
  Bad: "They realised the settlement was too distraught over a dead fern to notice
  the missing crew." (states the conceit flatly, and has the characters
  understanding the joke's own mechanics - it reads very odd)
  Good: report that the shaft was sealed on the Tuesday, that three days of
  mourning for the fern were already scheduled, and that no one filed a query.
  Let the reader put it together. That realisation IS the joke.

THE DISPATCH MUST BE ABOUT SOMETHING. Whimsy alone is not satire. Before writing,
decide what recognisably human or institutional behaviour this story is mocking -
status anxiety, procedure defeating its own purpose, professional vanity,
sentimentality misapplied, how fast people normalise the monstrous, the gap
between a stated reason and the real one - and make sure a reader finishes the
piece having felt that point land. The absurd premise is the vehicle, not the
destination. A story where a strange thing simply happens and people react to it
is a FAILURE.

IT MUST FEEL LIKE THE FUTURE, AND SPECIFICALLY LIKE **{dateline['years_from_now']}
YEARS FROM NOW**. {era_rule}

Two failure modes, both of which have shipped:
- Do NOT write a pre-industrial or Victorian scene with one futuristic object
  dropped in - no cobblestones, lard, apothecaries, guildish trades or medieval
  alleyways standing in for a future city. (A dispatch set in 2059 read like 1890
  with a lab-grown organ in it.)
- Do NOT furnish the far future with PRESENT-DAY props and names. Banned unless
  the story is specifically about their survival: candles, handwritten poems,
  bronze plaques, dormitory lockers, boots, clipboards, paper files, vellum,
  present-day plant and pet breeds ("a Boston fern"), current company or country
  names, and current units of currency. (A dispatch set in 37562 mourned a Boston
  fern by candlelight under a bronze plaque.)

Invent the era's own objects, materials, rituals and turns of phrase, and use them
casually as though everyone knows what they are. Show how people live, work,
travel, grieve and believe here. The illustrations are deliberately antique
engravings; the WRITING must supply the future, or the whole thing reads historical.

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
- 200 to 280 words. Straight-faced, as a real wire story. Dry wit, never winking.
- RHYTHM, measured. Average sentence length between 14 and 20 words. Include at
  least two sentences of SIX WORDS OR FEWER, and no sentence over 35 words. VARY
  it: a run of uniformly long sentences is the clearest sign a machine wrote it,
  but a run of uniformly short ones reads like a telegram. Mostly medium
  sentences, then land a short one hard, then carry on.
  EVERY example in these instructions illustrates RHYTHM, SHAPE or a MISTAKE only.
  Never copy an example's words, names or subject matter into the dispatch.
- WRITE PLAINLY. Prefer the short Anglo-Saxon word to the Latinate one. Cut every
  adjective and adverb that is not doing real work - "supreme", "utterly",
  "entirely", "merely", "precise", "heart-wrenching", "deep". One adjective per
  sentence at most, usually none.
- NAME A THING ONCE, THEN REUSE THE SAME WORDS. Do not elegantly vary: if it is a
  "thought feed", it stays a "thought feed" - not "raw neural architecture", then
  "the subconscious stream", then "the recorded link". Rotating synonyms for one
  object is the loudest AI tell in the paper.
- DO NOT EXPLAIN THE STORY'S SIGNIFICANCE. Never write a sentence that tells the
  reader what the trend means, was intended as, or reveals. Report what happened
  and what people said; let the point be obvious without being stated.
- Only the central figure gets a descriptor. Do not label every name
  ("bio-tech heiress", "eighty-nine-year-old matriarch", "senior crew chief").
- BANNED PHRASES - these are machine connective tissue: "took an unexpected
  turn", "the scandal deepened", "hit a crisis", "raising questions about",
  "sparking debate", "serving as a reminder", "underscoring", "highlighting the",
  "marking a", "in a move that", "one thing is certain", "only time will tell".
  Also avoid the "Rather than X, Y" and "not out of X but Y" constructions.
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
  single visual moment from the story that an illustrator could draw.
  CENTRE IT ON PEOPLE AND WHAT THEY ARE DOING - their posture, tools, clothing
  and setting. The illustrator renders humans, animals, vehicles, machinery and
  architecture well, but CANNOT render exotic or shapeless things
  recognisably: a strange organ, a mass of tissue, an energy field, a cloud or
  an abstract object will come out as an unidentifiable blob. So never make such
  a thing the visual subject - keep it out of the scene, or reduce it to a small
  background element, and let the PEOPLE carry the picture.
  Good: "an armoured military unit pulls up to a suburban driveway while a couple
  hides beneath a dining table".
  Bad: "a glistening forty-tonne whale liver rolls past a clock tower" (the
  subject cannot be drawn, and it was rendered as a giant bean).
- Separate paragraphs with a blank line.
- Do not use em dashes or en dashes. Use plain hyphens.
- Use Australian English spelling (organise, colour, defence, metre, favour).
- Give every named person a fresh, varied, culturally diverse name. Do NOT use the names "Vance", "Elena", "Rostova", "Marcus" or "Kovac" - invent new ones each time. Do not default the weekday to Tuesday; vary or omit the day.
- Do not put the year in the dateline place; the date is shown separately.
- Invented names of groups, bodies, products or places should be concrete and evocative, not vague abstractions.
{avoid_extra}
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


def normalise(d: dict, dateline: dict, domain: str, premise: str) -> dict:
    """Turn a raw parsed model object into a dispatch record, applying every
    deterministic fixer. Shared by the write and revise stages so a revision gets
    exactly the same cleanup as a fresh draft."""
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


def write(premise: str, dateline: dict, domain: str, settings: dict,
          style_guidance: str, place_guidance: str = "",
          avoid_block: str = "") -> dict:
    prompt = build_prompt(premise, dateline, domain, style_guidance,
                          place_guidance, avoid_block)
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
    return normalise(d, dateline, domain, premise)
