"""Generate and sieve haiku datelined from the future.

THE PIVOT, 07/09/2026. Charlie, after forty dispatches: "i feel like a lot of
them just aren't funny, not futuristic enough, not funny enough. and just don't
make sense... should I pivot this to be a haiku thing instead?" The paper keeps
its masthead, its dateline, its locator plate and its engraving; what changes is
that the dispatch is now seventeen syllables instead of two hundred and thirty
words.

Three things about the form are worth writing down, because they are the reason
this is likely to work where the prose did not:

1. THE ECONOMICS INVERT. A 230-word dispatch cost a Gemini call each, so the
   pipeline could afford four candidates and picked the best of four. A haiku is
   about fifteen tokens, so ONE call returns twenty-four of them for less output
   than a single dispatch. Selection stops being a formality and becomes the
   whole mechanism: sieve twenty-four down to the handful that survive, then
   judge those. The old pipeline's real problem was that "best of four" is not
   selective enough to be funny, and no prompt fixes that.

2. THE FAILURE MODE GETS CHEAP. A bad 230-word story wastes a minute of the
   reader's time and reads as broken - Charlie's "just don't make sense" was
   about invented mechanisms that used real technical words wrongly, which is a
   fault only a long piece can commit. A weak haiku costs three seconds, and
   ambiguity in seventeen syllables reads as intent rather than as error.

3. IT FIXES THE PICTURE. Every illustration complaint for a month came down to
   the same thing: a 230-word story has no single visual moment, so `depict` had
   to invent one and kept inventing the wrong one. A haiku IS one concrete
   image. The brief no longer has to choose.

What this module does NOT do is decide what is good. It counts syllables and
removes what is mechanically wrong. See `judge` for the rest.
"""
from __future__ import annotations

import re

#: 5-7-5. Written down rather than inlined because the sieve, the prompt and the
#: tests must all mean the same thing by "a haiku", and three copies of a tuple
#: is how they stop meaning the same thing.
PATTERN = (5, 7, 5)

_WORD = re.compile(r"[a-z']+")
_VOWEL_RUN = re.compile(r"[aeiouy]+")

#: Words the vowel-run heuristic gets wrong, with their real counts. Kept SHORT
#: and only for words that actually turn up in this register - a long list is a
#: dictionary badly reimplemented, and the heuristic is right about ordinary
#: English roughly nineteen times in twenty (measured in tests/test_haiku.py
#: against a hand-counted fixture, which is the only reason that claim is here).
_EXCEPTIONS = {
    "the": 1, "are": 1, "were": 1, "gone": 1, "come": 1, "some": 1, "done": 1,
    "one": 1, "once": 1, "none": 1, "there": 1, "where": 1, "here": 1,
    "more": 1, "before": 2, "every": 2, "many": 2, "any": 2, "very": 2,
    "being": 2, "doing": 2, "going": 2, "seeing": 2, "science": 2,
    "quiet": 2, "quieter": 3, "poem": 2, "poems": 2, "real": 1, "really": 2,
    "fire": 1, "fires": 1, "hour": 1, "hours": 1, "our": 1, "ours": 1,
    "iron": 2, "wire": 1, "wires": 1, "hire": 1, "tired": 1, "hired": 1,
    "aisle": 1, "isle": 1, "idea": 3, "ideas": 3, "area": 3, "areas": 3,
    "orange": 2, "engine": 2, "engines": 2, "machine": 2, "machines": 2,
    "people": 2, "little": 2, "middle": 2, "cattle": 2, "settle": 2,
    "business": 2, "evening": 2, "different": 3, "family": 3, "camera": 3,
    "average": 3, "several": 3, "general": 3, "interest": 3, "memory": 3,
    "history": 3, "century": 3, "factory": 3, "ordinary": 4, "temporary": 4,
    "everyone": 3, "everything": 3, "anyone": 3, "anything": 3,
    "nothing": 2, "something": 2, "someone": 2, "nobody": 3, "somebody": 3,
    "towards": 2, "toward": 2, "forward": 2, "backward": 2,
    "creature": 2, "creatures": 2, "future": 2, "futures": 2, "nature": 2,
    "picture": 2, "pictures": 2, "measure": 2, "measures": 2,
    "material": 4, "materials": 4, "radial": 3, "cereal": 3,
    "water": 2, "waters": 2, "winter": 2, "summer": 2, "weather": 2,
}


def syllables(word: str) -> int:
    """Syllables in one word, by vowel runs with the usual corrections.

    Deliberately a heuristic and not a dictionary. CMUdict would be exact and is
    a 3MB dependency for a decision that is only ever "does this line scan", and
    the sieve is allowed to be slightly wrong in a form where the model is
    generating twenty-four candidates and we keep the ones that survive. What it
    must NOT be is silently wrong, so its accuracy is measured in the tests
    rather than asserted here."""
    w = "".join(_WORD.findall(word.lower()))
    if not w:
        return 0
    if w in _EXCEPTIONS:
        return _EXCEPTIONS[w]
    runs = _VOWEL_RUN.findall(w)
    n = len(runs)
    # A trailing silent e ("stone", "wave") is a vowel run that is not a
    # syllable - unless dropping it would leave the word with none at all.
    if w.endswith("e") and not w.endswith(("le", "ee", "ye", "oe")) and n > 1:
        n -= 1
    # "-le" after a consonant is its own syllable and the rule above would have
    # taken it ("candle", "cattle"), but "-ale" and "-ile" are not.
    if w.endswith("le") and len(w) > 2 and w[-3] not in "aeiouy":
        n = max(n, len(_VOWEL_RUN.findall(w[:-2])) + 1)
    # "-ed" is silent after most consonants ("walked") and sounded after t/d
    # ("wanted", "folded").
    if w.endswith("ed") and len(w) > 3 and w[-3] not in "aeiouytd":
        n -= 1
    # A plural of a silent-e word ("cranes", "leaves", "waves") keeps the silent
    # e, and the rule above cannot see it because the word now ends in s. Only
    # after a non-sibilant: "boxes", "wishes" and "faces" DO sound the e.
    elif w.endswith("es") and len(w) > 3 and w[-3] not in "aeiouysxzhcg":
        n -= 1
    return max(1, n)


def line_syllables(line: str) -> int:
    return sum(syllables(w) for w in _WORD.findall((line or "").lower()))


def scans(lines, pattern=PATTERN) -> bool:
    """True when the three lines measure 5-7-5."""
    if len(lines) != len(pattern):
        return False
    return all(line_syllables(l) == n for l, n in zip(lines, pattern))


def build_prompt(dateline: dict, domain: str, count: int, avoid_block: str = "",
                 guidance: str = "") -> str:
    """Ask for `count` haiku in one call.

    ONE CALL, NOT `count` CALLS. The whole reason this pivot is affordable is
    that seventeen syllables is nothing to generate, so the model can be asked
    for two dozen at once and the pipeline can afford to throw most of them
    away. Asking in one call also lets the instruction "make them different from
    each other" mean something, which N independent calls cannot."""
    place = (dateline or {}).get("place", "")
    year = (dateline or {}).get("year", "")
    ahead = int((dateline or {}).get("years_from_now") or 0)
    avoid = f"\n{avoid_block}\n" if avoid_block else ""
    extra = f"\n{guidance}\n" if guidance else ""
    # The place is INVENTED HERE rather than passed in, because dates.py leaves
    # it blank for the writer to fill and one edition is one place. Asking for
    # it alongside the poems keeps the world consistent across all of them.
    where = (f"datelined {place}, {year}" if place else
             f"datelined {year}, somewhere you will name")
    return f"""You are the poet for The Aftertimes, a newspaper that files from
the future. Today's edition is {where} - {ahead} years from
now. Write {count} haiku from that place and that year.

A haiku here is a NEWS ITEM compressed to seventeen syllables: five, seven,
five, three lines, no title, no rhyme, no capital at the start of a line unless
the word needs one, and no full stop at the end.

WHAT MAKES ONE WORK. It reports ONE concrete thing somebody can see, and the
third line turns it - a consequence, a cost, a detail that reframes the first
two. Never explain the turn. Never tell the reader how to feel. The strangeness
of the year is in the FURNITURE, not in the commentary: name the era's own
objects, jobs, materials and rituals plainly, as things everyone there uses
without thinking, and let the reader work out where they are.

- Nothing that exists in 2026. No plastic, denim, wool, brass, clipboards,
  phones, email, offices, police, courts, schools, hospitals, insurance or
  money as we have it. Name the descendant instead and use it casually.
- No abstractions where a thing would do. "the loneliness of work" is not an
  image; "the second shift signs for its own air" is.
- No poeticism. No "whispers", "echoes", "shimmering", "eternal", "silence
  falls", "the void", "stars weep". If a line could appear in any poem about
  any time, it is the wrong line.

THE SUBJECT IS A SYSTEM WORKING EXACTLY AS INTENDED, and the joke is what it
was intended to do. Not hardship. The first batch went straight to scarcity -
rations, a rot pit, a dead man's crate weighed in for garden feed, teeth left in
a vat - because "the future" plus "no modern objects" reads as privation unless
something stops it. Sixty-four per cent of them carried a word like dead, rot,
dust, hunger or cold. That is a bleak paper, not a funny one.
So: nothing about death, corpses, hunger, rationing, disease, decay, cold, dirt
or exhaustion. Write instead about a PROCEDURE - a form, a licence, a queue, an
inspection, a job title, a category, a rule being applied correctly to something
absurd, an institution solving a problem nobody has. The people in it are
competent and unbothered; they have done this for years. The funniest line
available is almost always somebody being professional about something insane.

- AND IT MUST NOT READ AS THE PAST. The first batch was datelined six hundred
  years out and came back with rakes, shovels, lime dust, quilts, kelp, cabbage
  beds, a mud barge and a gas wick - sixty-four per cent carried a
  pre-industrial prop. Banning present-day objects leaves the nineteenth century
  as the only other era you know, and that is worse: a future that looks like
  1850 is a costume, not a world. No hand tools, no sacks, no carts, no lamps,
  no vats, no rope, no timber, no coal, no soot. Invent the era's own equipment
  and name it plainly - things that are grown, printed, issued, assigned,
  scheduled, revoked, or simply switched on without anybody thinking about it.
- Ordinary words. A reader should never have to decode a coinage; if you invent
  a noun, build it from plain words and make the line explain it by using it.

Each haiku must be about something DIFFERENT from the others - a different job,
a different object, a different corner of that world. Do not write twenty
variations on one idea.
{avoid}{extra}
Return JSON only:
{{"place": "the settlement these are filed from",
 "haiku": [{{"lines": ["...", "...", "..."],
             "title": "two or three plain words"}}]}}

`place` is one invented place name for the whole edition - a settlement, station
or district that sounds like somewhere people actually live and work, not a
portentous compound. Every haiku is filed from it.

The title is for the archive index, not for the reader of the poem. It names
the subject flatly. Never a joke, never a summary, never a full sentence.

LAST, AND IT IS THE ONE MECHANICAL REQUIREMENT: COUNT THE SYLLABLES. Five in
the first line, seven in the second, five in the third. Say each line out loud
and count on your fingers before you write it down. Compound words are where
this goes wrong - "reassigned" is three, "corridor" is three, "approved" is two.
A line that does not scan is thrown away by a program before anybody reads it,
however good it is.

This instruction is at the END on purpose. It was in the middle, and the batch
that followed had seven of twenty-four scanning where an earlier and much
shorter prompt got seventeen - the rules above are worth having and they buried
the only one that is checkable. Whatever you read last is what you obey."""


def parse(raw) -> list[dict]:
    """Coerce a model response into a list of {lines, title}.

    Tolerant on purpose: one malformed entry in twenty-four must not lose the
    other twenty-three, which is exactly what a strict schema would do here."""
    if isinstance(raw, dict):
        raw = raw.get("haiku") or raw.get("items") or [raw]
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        lines = item.get("lines")
        if isinstance(lines, str):
            lines = [l.strip() for l in lines.splitlines() if l.strip()]
        if not isinstance(lines, list):
            continue
        lines = [str(l).strip() for l in lines if str(l).strip()]
        if len(lines) != 3:
            continue
        out.append({"lines": lines,
                    "title": str(item.get("title", "") or "").strip()})
    return out


def judge_prompt(candidates: list[dict]) -> str:
    """Rank the survivors and pick one.

    ASKED TO RANK, NOT TO SCORE. The prose judge scored each draft in isolation
    and gave 37 of 65 a perfect 1.0, so "best of four" was picking at random
    while the run reported success - a saturated metric looks exactly like a
    passing one. Thirty candidates make that impossible to hide: a model asked
    to put thirty things in an order has to discriminate."""
    blocks = "\n".join(
        f"{i}. {' / '.join(h['lines'])}" for i, h in enumerate(candidates, 1))
    return f"""You are the editor of The Aftertimes, a newspaper filing from the
future. Below are {len(candidates)} haiku written for today's edition. Exactly
one is published.

{blocks}

Pick the one a reader would repeat to somebody else. What that means here:
- The third line TURNS the first two. It is not a summary of them, and it is not
  a third fact in a list.
- The joke is in the situation, not in the wording. Nobody in it knows it is
  funny; the absurdity is treated as ordinary procedure.
- It is about something recognisably true - an institution, a rule, a job, a
  small human accommodation - rather than a whimsical impossibility about
  nothing.
- Its objects belong to its own era. Anything that reads as either 2026 or the
  nineteenth century is disqualified however neat the line is.

Do not pick on prettiness, mood or imagery. A merely atmospheric haiku is the
failure mode here, not the goal.

Then rate the one you picked out of 10 against a good satirical publication and
NOT against the others in this list. Thirty weak haiku still have a best one, so
say so honestly rather than grading on the curve. 5 raises a half-smile; 8 is
one you would send to someone.

Return JSON only: {{"pick": <the number>, "score": <1-10>,
"reason": "<one short line>"}}"""


def to_dispatch(chosen: dict, dateline: dict, domain: str) -> dict:
    """Shape a haiku like a dispatch, so nothing downstream has to change.

    render.py already splits `body` on newlines into paragraphs, and archive.py,
    card.py and email_render.py all read `headline`, `body` and `dateline`. So
    the pivot does not need those four files rewritten - it needs the poem put
    in the shape they already read. The title becomes the headline because the
    archive index, the permalink and og:title all need a name, and a haiku has
    no first line worth using as one.

    `scene` is deliberately the poem itself rather than a sentence about it: the
    picture brief is built from it, and a haiku IS one concrete image, which is
    the thing depict.py could never get out of a 230-word story."""
    return {
        "headline": (chosen.get("title") or "").strip() or "Dispatch",
        "body": "\n".join(chosen["lines"]),
        "lines": list(chosen["lines"]),
        "scene": " / ".join(chosen["lines"]),
        "domain": (domain or "").strip() or "notice",
        "dateline": dict(dateline),
        "glossary": [],
        "premise": " / ".join(chosen["lines"]),
    }
