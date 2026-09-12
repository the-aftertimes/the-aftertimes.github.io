"""Deterministic dispatch scoring - the measurable half of quality control.

Everything checkable in code lives here so the two model calls in the pipeline
(judge, revise) are spent only on the genuinely subjective question of whether a
dispatch is funny. Pure functions: no API calls, no file IO, no globals.

Severity is either "major" or "minor"; the weights and thresholds all come from
the `quality` block in config/settings.yaml so tuning never means editing code.
"""
from __future__ import annotations

import re

from common import _DASH_CODEPOINTS
from write import _AU_SPELLING, _MACHINE_PHRASES, prose_report


def metrics_for(body: str) -> dict:
    """Prose measurements for a body. Thin alias so callers do not reach into
    write.py, and so tests read clearly."""
    return prose_report(body)


def _v(rule: str, detail: str, severity: str) -> dict:
    return {"rule": rule, "detail": detail, "severity": severity}


def check_rhythm(metrics: dict, cfg: dict) -> list[dict]:
    r = cfg["rhythm"]
    out = []
    mean = metrics["mean_sentence"]
    # The FLOOR here is dangerous and was wrong once already. On 10/08/2026 the
    # only trial containing lines Charlie called funny (t002) was the only one
    # the critic docked, purely for mean 13.7 against a then-floor of 14 - and
    # two of the four funny lines were 6 and 10 words, i.e. they were what pulled
    # the mean down. A floor set by taste rather than evidence makes revise.py
    # optimise AWAY from comedy. Keep it low enough to catch only telegram-prose.
    if not (r["mean_min"] <= mean <= r["mean_max"]):
        hard = mean < r["mean_hard_min"] or mean > r["mean_hard_max"]
        out.append(_v("rhythm_mean",
                      f"mean sentence is {mean} words, wanted "
                      f"{r['mean_min']}-{r['mean_max']}",
                      "major" if hard else "minor"))
    if metrics["longest"] > r["longest_max"]:
        out.append(_v("rhythm_longest",
                      f"longest sentence is {metrics['longest']} words, "
                      f"maximum {r['longest_max']}", "major"))
    if metrics["short_sentences"] < r["min_short"]:
        out.append(_v("rhythm_short",
                      f"only {metrics['short_sentences']} sentences of six words "
                      f"or fewer, wanted at least {r['min_short']}", "minor"))
    return out


def check_length(metrics: dict, cfg: dict) -> list[dict]:
    ln = cfg["length"]
    words = metrics["words"]
    if ln["min"] <= words <= ln["max"]:
        return []
    hard = words < ln["hard_min"] or words > ln["hard_max"]
    return [_v("length",
               f"{words} words, wanted {ln['min']}-{ln['max']}",
               "major" if hard else "minor")]


#: The legal/financial register the paper over-used (see config/engines.yaml).
#: Suppressed when the day's comic engine IS the bureaucratic one.
#:
#: UNAMBIGUOUS TERMS ONLY. The first version included bare "fine", "fined",
#: "fines", "permit", "permits", "licence", "insurance" and "liability", which
#: match ordinary English - "it was a fine morning" and "the doors would not
#: permit entry" both tripped it. Since legal_register is a HARD REJECT, those
#: false positives would have binned good drafts routinely and pushed the run
#: into the all-rejected branch as a matter of course.
#: Kept as a plain list as well as a regex so revise.py can SHOW the writer the
#: banned vocabulary instead of only marking it afterwards. 06/09/2026: a re-edit
#: fixed both faults Charlie had named, reached for "bailiffs" while doing it,
#: and was binned for a hard reject it had never been told about - two house
#: rules quietly fighting each other where only one of them was written down.
LEGAL_WORDS = ("sue", "suing", "lawsuit", "court", "magistrate", "tribunal",
               "injunction", "lien", "repossess", "bailiff", "writ", "statute",
               "ordinance", "tax", "levy", "debt")
_LEGAL = re.compile(
    r"\b(sue[sd]?|suing|lawsuit|court|magistrate|tribunal|injunction|lien|liens"
    r"|repossess\w*|bailiff\w*|writ|statute|ordinance"
    r"|tax|taxes|levy|levies|debt|debts)\b", re.I)

#: Present-day objects that should not furnish a far-future dispatch unless
#: their survival is the story. A dispatch set in 37562 mourned a Boston fern by
#: candlelight under a bronze plaque; another rolled a coffee press through
#: cobbled alleys.
_PROPS = re.compile(
    r"\b(candle\w*|bronze plaque\w*|handwritten|clipboard\w*|vellum|locker\w*"
    r"|apothecar\w*|cobblestone\w*|lard|typewriter\w*|fax|dollar\w*|euro\w*"
    r"|coffee|espresso|Boston fern\w*"
    # Added 04/09/2026. A dispatch datelined 4792 was furnished with brass
    # megaphones, wooden oars, plastic buckets and ice packs and read as
    # 1950s, and the list above caught NONE of it - every entry was something
    # the paper had already been burned by, so it only ever detected
    # yesterday's failure. These are the ordinary 2026 objects that a "plain
    # working scene" instruction reaches for by default.
    r"|megaphone\w*|bucket\w*|plastic|cardboard|denim|wellington\w*"
    r"|ice pack\w*|clipboard\w*|biro\w*|sneaker\w*|t-shirt\w*)\b", re.I)

#: The narrator or a character explaining the comic mechanism out loud. This is
#: a semantic fault that regex cannot detect reliably, so it is deliberately
#: only ever a minor nudge - a false positive must never bin a draft.
_STATED_JOKE = re.compile(
    r"(\brealis\w+\b|\brealiz\w+\b|too\s+\w+\s+to\s+notice|\blittle did\b)", re.I)

_STATED_JOKE_SENTENCES = 2

#: Same closing-quote allowance as write.prose_report's sentence split, built
#: from codepoints (not literal curly-quote characters) so this file stays
#: copy-paste safe under the editor's dash-mangling behaviour and easy to audit
#: byte-for-byte. Functionally identical to write.py's pattern.
_SENTENCE_SPLIT = re.compile(
    r"(?<=[.!?])[\"" + chr(0x201D) + chr(0x2019) + r"']*\s+")


#: The abbreviation guard, same list as trial.split_sentences and write.prose_report.
#: Lowest consequence of the three - a fragment only changes which two "sentences" the
#: stated-joke check reads - but three copies agreeing is the whole point of copying
#: them, and a fourth that quietly disagrees is worse than no copy at all.
_NOT_AN_END = re.compile(
    r'(?:\b(?:Mr|Mrs|Ms|Dr|St|Prof|Rev|Sr|Jr|Hon|Capt|Gen|Col|Sgt|Lt|Ave|No|vs'
    r'|etc|cf|Fig|Vol|pp|al|Co|Ltd|Inc)|(?:^|[\s("\'])[A-Z])\.$')


def _split(body: str) -> list[str]:
    out: list[str] = []
    for part in _SENTENCE_SPLIT.split(body):
        if out and _NOT_AN_END.search(out[-1]):
            out[-1] += " " + part
        else:
            out.append(part)
    return out


def check_phrases(body: str) -> list[dict]:
    hits = [p for p in _MACHINE_PHRASES if p in body.lower()]
    if not hits:
        return []
    return [_v("machine_phrases", "stock machine phrasing: " + ", ".join(hits),
               "major")]


#: Words that make a "court" a place to play in rather than a place to be tried
#: in. 25/08/2026: "Sentries Turn Missile Silo Into Pickleball Court" was HARD
#: REJECTED for legal register and never reached the judge, which left one
#: survivor - so that day's dispatch was chosen by elimination rather than by
#: comedy, and Charlie said the article was not funny. A word-list that cannot
#: tell a sport from a lawsuit should not have the power to delete a draft.
_COURT_NOT_LEGAL = {
    "pickleball", "tennis", "squash", "badminton", "basketball", "netball",
    "volleyball", "handball", "food", "central", "grass", "clay", "indoor",
    "outdoor", "practice", "training", "exercise",
}
#: The word immediately before a "court", which is what decides its sense.
_COURT_MENTION = re.compile(r"(?:(\w+)[\s-]+)?\bcourts?\b", re.I)


def legal_hits(body: str) -> list[str]:
    """The legal-register words in a body, with the sport sense of `court`
    excluded. Everything else in the list is unambiguous enough to take at face
    value; `court` is the one word in it with a common innocent meaning.

    EVERY mention is judged separately, and one legal court is enough to keep the
    flag - a piece that plays pickleball and also sues somebody is still leaning
    on the register.
    """
    hits = {m.group(0).lower() for m in _LEGAL.finditer(body)}
    if "court" in hits:
        senses = [(m.group(1) or "").lower()
                  for m in _COURT_MENTION.finditer(body)]
        if senses and all(s in _COURT_NOT_LEGAL for s in senses):
            hits.discard("court")
    return sorted(hits)


def check_register(body: str, engine: str) -> list[dict]:
    if (engine or "") == "bureaucratic":
        return []
    hits = legal_hits(body)
    if not hits:
        return []
    return [_v("legal_register",
               "legal/financial crutch: " + ", ".join(hits), "major")]


def check_props(text: str, years_from_now: int) -> list[dict]:
    hits = sorted({m.group(0).lower() for m in _PROPS.finditer(text)})
    if not hits:
        return []
    severity = "major" if int(years_from_now) >= 400 else "minor"
    return [_v("present_day_props",
               "present-day props: " + ", ".join(hits), severity)]


#: A capitalised word is skipped by check_plainness: invented place names, ships,
#: institutions and people are SUPPOSED to be unfamiliar, and the paper would be
#: nothing without them. What makes a dispatch hard to read is the ordinary
#: vocabulary around them - "apothecary", "chrism", "cobblestone", "gantry" -
#: which is exactly what is left once the proper nouns are set aside.
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def rare_words(body: str, common: frozenset[str]) -> list[str]:
    """Lowercase words a reader has to stop and decode, in order of appearance.

    Hyphenated coinages are split and judged part by part, so an invented
    compound built from plain words ("seal-brusher", "spit-tray") costs nothing
    while one built from archaic ones is still caught. Parts of three letters or
    fewer are skipped, matching the word list's own floor.
    """
    out = []
    for tok in _WORD.findall(body):
        if tok[:1].isupper():
            continue
        for part in re.split(r"[-']", tok.lower()):
            if len(part) > 3 and part not in common:
                out.append(part)
    return out


def check_plainness(body: str, common: frozenset[str] | None,
                    cfg: dict) -> list[dict]:
    """Flag prose the reader has to decode. Added 17/08/2026, when Charlie said
    the dispatches were "hard to read, they don't read like a news article, they
    use really archaic words".

    He was right, and the reason it had drifted is that plainness was the ONE
    quality dimension with no measurement behind it. The write prompt has always
    asked for plain Anglo-Saxon words, but rhythm, length, the legal register and
    present-day props were all measured and therefore selected for across the
    three drafts, while vocabulary was not - so the instruction lost every time
    it competed with "invent the era's own objects, materials and rituals".

    Graded, never a hard reject: an unfamiliar word is sometimes the right word,
    and a threshold that could refuse a draft outright would be taste dressed up
    as measurement. It costs the draft points and it names the offending words in
    the detail line, which is what the revise pass reads.
    """
    if common is None:
        return []
    words = len(body.split()) or 1
    hits = rare_words(body, common)
    rate = 100.0 * len(hits) / words
    p = cfg.get("plainness") or {}
    minor_at, major_at = p.get("rate_max", 5.0), p.get("rate_major", 7.0)
    if rate < minor_at:
        return []
    shown = sorted(set(hits))
    return [_v("plainness",
               f"{len(hits)} words a reader must decode in {words} "
               f"({rate:.1f}%, wanted under {minor_at:.0f}%) - replace with the "
               f"blunt everyday word: " + ", ".join(shown),
               "major" if rate >= major_at else "minor")]


def check_stated_joke(body: str) -> list[dict]:
    flat = re.sub(r"\s+", " ", body).strip()
    opening = " ".join(_split(flat)[:_STATED_JOKE_SENTENCES])
    m = _STATED_JOKE.search(opening)
    if not m:
        return []
    return [_v("stated_joke",
               f"the opening states the conceit ({m.group(0)!r}) instead of "
               "reporting facts", "minor")]


#: A quoted source second-guessing the reader's reaction instead of treating the
#: absurd world as ordinary. The write prompt is explicit that nobody in the story
#: knows it is funny, and on 31/08/2026 Charlie said the dispatch was not funny;
#: its Guildmaster was doing exactly this, four times over.
#:
#: MEASURED BEFORE IT WAS WRITTEN, because a plausible rule that fires on nothing
#: is worse than none. Over the 33 dispatches in the archive this matches ONE - the
#: 31/08 piece - and catches all four of its constructions. That also means it is
#: fitted to a single example, so it is a MINOR, like _STATED_JOKE: it nudges
#: revise.py and can never bin a draft. Widen it only against the archive.
_WINK = re.compile(
    r"\b(no ?one wants|nobody wants|would much rather|would rather not|"
    r"the public expects|people expect|let's be honest|as everyone knows|"
    r"which is (?:exactly )?the point|that's the (?:whole )?point)\b", re.I)

#: Three items in a comma list. A list is not an escalation - each beat should be
#: worse than the last in the same direction, and a tricolon lets a draft fake the
#: build with three unrelated nouns. 6 of 33 archived dispatches contain one, so it
#: is rare enough to be signal rather than noise, and minor for the same reason as
#: _WINK.
_TRICOLON = re.compile(
    r"\b[\w'-]+(?:\s+[\w'-]+){0,4},\s+[\w'-]+(?:\s+[\w'-]+){0,4},\s+(?:and|or)\s+", re.I)


def check_wink(body: str) -> list[dict]:
    """Nobody in the story is allowed to know it is funny."""
    hits = sorted({m.group(0).lower() for m in _WINK.finditer(body or "")})
    if not hits:
        return []
    return [_v("wink", "a source is commenting on the joke rather than living in "
                       "it: " + ", ".join(repr(h) for h in hits), "minor")]


#: A short sentence that announces a REGULATION and nothing else. Charlie,
#: 06/09/2026, on "Removal is forbidden under environmental law.": "these sorts
#: of lines dont really land".
#:
#: The class is narrow and the narrowness is the point. The paper's whole subject
#: is bureaucracy, so rules are not the problem - a rule with a PERSON in it is
#: usually the joke. Two lines in the archive prove it: "He is now only permitted
#: to speak in numbers" and "Under ship law, his top half ceased to be a real
#: person" both land, and both put a human on the receiving end. The dead version
#: has an abstract noun as its subject, no person anywhere, and no consequence -
#: it is the sound of a draft filling a paragraph. It also tends to arrive as its
#: own one-line paragraph, where the reader stops for it and gets nothing.
#:
#: MEASURED FIRST, per the house rule. Across the 39 archived dispatches this
#: matches exactly ONE: the line Charlie flagged. That is fitted to a single
#: example, so it is a MINOR like _WINK and _STATED_JOKE - it can nudge revise.py
#: and can never bin a draft. Widen it only against the archive.
_RULE_WORD = re.compile(
    r"\b(forbidden|prohibited|permitted|mandatory|compulsory|illegal|unlawful|"
    r"banned|exempt|liable|not allowed|required by|punishable)\b", re.I)
_UNDER_LAW = re.compile(
    r"\bunder (?:the )?[\w\s-]{0,30}\b(law|laws|act|code|codes|statute|statutes|"
    r"ordinance|regulations?|rules?|charter)\b", re.I)
#: A person anywhere in the sentence excuses it: a pronoun, or a capitalised word
#: that is not simply the sentence's first.
_PERSON = re.compile(r"\b(he|she|they|him|her|them|his|their|hers|theirs|"
                     r"someone|anyone|nobody|everyone|who)\b", re.I)
_MID_CAP = re.compile(r"(?<=[a-z,] )[A-Z][a-z]")


#: THE LEDE OPENS ON A PERSON OR A THING, NEVER ON AN ABSTRACTION. Charlie,
#: 12/09/2026, quoting the first two paragraphs: "it's just way too wordy". The
#: piece was 234 words, inside the band, and its lede was 20 words - UNDER the
#: archive median of 23. The count was not the fault. The shape was: "The
#: municipal zoning policy that classified Neptune's crushing diamond-rain layer
#: as a utility basement has been retired" holds a fourteen-word noun phrase
#: before the reader reaches a verb. Compare the ledes that read fine - "Brother
#: Julian, who...", "Soraya Blythe and her husband...", "A ten-metre asteroid
#: won..." - all longer or as long, all opening on something you can see.
#:
#: Same family as `flat_rule` (06/09: "Removal is forbidden under environmental
#: law"): a sentence whose subject is an institution or a document rather than
#: anyone, and it reads as paperwork because it is.
#:
#: MEASURED FIRST. Matches 7 of the 45 archived prose dispatches, 3 of the last
#: 6 days, and among them the 31/08 piece Charlie called unfunny on the day. Not
#: fitted to one example; rare enough to be signal. MINOR, so it feeds revise.py
#: with a concrete instruction and can never bin a draft.
_ABSTRACT_LEDE = re.compile(
    r"^(?:[A-Z][A-Z\s-]+:\s*)?(?:an?|the)\s+(?:[\w-]+\s+){0,3}?"
    r"(study|investigation|inquiry|review|report|survey|audit|analysis|"
    r"policy|rule|ruling|regulation|law|statute|ordinance|decision|"
    r"announcement|scheme|programme|program|proposal|plan|initiative|"
    r"agreement|arrangement|measure|motion|bill|amendment|reform|"
    r"classification|designation|ban|moratorium|dispute|debate|controversy)\b",
    re.I)


def check_lede(body: str) -> list[dict]:
    """The first sentence's subject is somebody, or something you can see."""
    flat = re.sub(r"\s+", " ", body or "").strip()
    first = (_split(flat) or [""])[0].strip()
    m = _ABSTRACT_LEDE.match(first)
    if not m:
        return []
    return [_v("lede_subject",
               f"the lede opens on an abstraction ({m.group(1)!r}) - the reader "
               f"holds a noun phrase before any verb. Open on the person or the "
               f"thing instead, and let the {m.group(1)} arrive later: "
               f"{first[:80]!r}", "minor")]


def check_flat_rule(body: str) -> list[dict]:
    """A regulation stated at nobody, standing in for a joke."""
    flat = re.sub(r"\s+", " ", body or "").strip()
    for sentence in _split(flat):
        s = sentence.strip()
        if len(s.split()) > 12 or '"' in s:
            continue
        if not (_RULE_WORD.search(s) or _UNDER_LAW.search(s)):
            continue
        if _PERSON.search(s) or _MID_CAP.search(s):
            continue
        return [_v("flat_rule",
                   "a rule announced at nobody, with no person and no "
                   f"consequence in it: {s!r}", "minor")]
    return []


def check_tricolon(body: str) -> list[dict]:
    m = _TRICOLON.search(body or "")
    if not m:
        return []
    return [_v("tricolon", "three items in a comma list stand in for an "
                           f"escalation: {m.group(0).strip()!r}", "minor")]


_US_WORDS = re.compile(
    r"\b(" + "|".join(sorted(_AU_SPELLING, key=len, reverse=True)) + r")\b", re.I)


def check_residue(text: str) -> list[dict]:
    """A hit here means one of the deterministic fixers has a GAP - the text was
    supposed to be cleaned before it ever reached the critic. Treated as major
    for exactly that reason."""
    out = []
    dashes = sorted({hex(ord(c)) for c in text if ord(c) in _DASH_CODEPOINTS})
    if dashes:
        out.append(_v("dash_residue",
                      "dash characters survived hyphenate(): " + ", ".join(dashes),
                      "major"))
    us = sorted({m.group(0).lower() for m in _US_WORDS.finditer(text)})
    if us:
        out.append(_v("us_spelling",
                      "US spellings survived the normaliser: " + ", ".join(us),
                      "major"))
    return out


def check_structure(dispatch: dict, cfg: dict, haiku: bool = False) -> list[dict]:
    """The parts a dispatch cannot be published without. Nothing else in the
    critic looks at whether a field is actually THERE - so before this existed, a
    revision that came back with a body but no headline scored identically to a
    good one (1.0), sailed through the acceptance gate, and would have published
    an empty <h1> and emailed it to subscribers."""
    out = []
    if not (dispatch.get("headline") or "").strip():
        out.append(_v("structure", "no headline", "major"))
    if not ((dispatch.get("dateline") or {}).get("place") or "").strip():
        out.append(_v("structure", "no dateline place", "major"))
    words = len((dispatch.get("headline") or "").split())
    cap = cfg.get("headline_max_words", 7)
    if words > cap:
        out.append(_v("headline_length",
                      f"headline is {words} words, wanted {cap} or fewer",
                      "minor"))
    body = (dispatch.get("body") or "").strip()
    # A HAIKU IS THREE LINES, NOT A SHORT ARTICLE. The 150-word absolute floor
    # exists to stop a truncated or empty body publishing an empty page, and a
    # seventeen-syllable poem trips it every time - it measured 14 words and was
    # hard-rejected on 09/09/2026 while wiring the pivot. So the structural
    # question changes shape rather than being dropped: a haiku must have three
    # lines and they must scan. That is a REAL floor, not a waived one, and it is
    # the same guard against a truncated body that the word count was.
    if haiku:
        lines = [l for l in body.splitlines() if l.strip()]
        if len(lines) != 3:
            out.append(_v("structure",
                          f"a haiku is three lines, got {len(lines)}", "major"))
        return out
    floor = cfg["length"]["hard_min"]
    if len(body.split()) < floor:
        out.append(_v("structure",
                      f"body is {len(body.split())} words, below the {floor}-word "
                      "absolute floor", "major"))
    return out


def score(dispatch: dict, context: dict, cfg: dict) -> dict:
    """Measure a dispatch. `context` carries years_from_now and engine, both of
    which make some checks conditional, plus `common_words` for the plainness
    check - omit it and that check is skipped, which keeps this module free of
    file IO. Returns the score, the violations and the
    raw metrics; a draft breaking any cfg["hard_reject"] rule is flagged
    `rejected` but still returned, because the orchestrator may need it as a last
    resort rather than failing to publish."""
    body = dispatch.get("body", "") or ""
    text = f"{dispatch.get('headline', '')} {body}"
    metrics = metrics_for(body)
    violations = []
    haiku = (context.get("form") or "prose") == "haiku"
    violations += check_structure(dispatch, cfg, haiku=haiku)
    # WHICH CHECKS SURVIVE THE HAIKU PIVOT, 09/09/2026. Four of them measure
    # things seventeen syllables cannot have: a 180-240 word count, a mean
    # sentence length, a three-item comma list, and a short flat regulation
    # standing as its own paragraph. Run against a haiku they fire on every
    # single candidate, which would reject the entire batch.
    #
    # The rest all still earn their place and are exactly the ones that were
    # doing real work: machine phrases, the legal register, US spellings, the
    # decode rate, and the present-day/pre-industrial prop rules - that last
    # pair being the whole reason the first haiku batch was measurable as 64%
    # pre-industrial.
    if not haiku:
        violations += check_rhythm(metrics, cfg)
        violations += check_length(metrics, cfg)
    violations += check_phrases(body)
    violations += check_register(body, context.get("engine", ""))
    violations += check_props(text, context.get("years_from_now", 0))
    violations += check_stated_joke(body)
    violations += check_wink(body)
    if not haiku:
        violations += check_tricolon(body)
        violations += check_flat_rule(body)
        violations += check_lede(body)
    violations += check_plainness(body, context.get("common_words"), cfg)
    violations += check_residue(text)
    weights = cfg["weights"]
    penalty = sum(weights.get(v["severity"], weights["minor"])
                  for v in violations)
    hard = set(cfg["hard_reject"])
    return {
        "score": round(max(0.0, 1.0 - penalty), 3),
        "rejected": any(v["rule"] in hard for v in violations),
        "violations": violations,
        "metrics": metrics,
    }
