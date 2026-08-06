"""Deterministic staleness detection over the archive.

Finds what the paper has started REPEATING - phrasing, sentence openers, names,
place-name formulas. This half is automated precisely because repetition is
measurable; humour is not, and is handled by Charlie's verdicts instead.

Pure functions over already-loaded records. No file IO, no API calls.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

#: Ordinary news phrasing that is not evidence of staleness.
_STOP_PHRASES = {
    "of the", "in the", "on the", "to the", "for the", "at the", "and the",
    "it is", "there is", "there are", "this is", "that the", "with the",
}

#: Function words. A gram made up ENTIRELY of these is ordinary grammatical
#: glue, not a writing tic - real over-used tics carry at least one content
#: word ("the council sealed", "beneath the reactor"), whereas "from the",
#: "when the" or "in a" recur constantly in any prose purely by chance,
#: especially over a small archive. This is the guard that keeps min_count
#: from being the only thing standing between the detector and ordinary English.
_FUNCTION_WORDS = {
    "a", "an", "the", "of", "in", "on", "to", "for", "at", "and", "or", "but",
    "it", "its", "is", "are", "was", "were", "be", "been", "being", "as",
    "that", "this", "these", "those", "with", "from", "into", "onto", "by",
    "his", "her", "their", "its", "our", "your", "my", "he", "she", "they",
    "we", "you", "not", "no", "so", "if", "than", "then", "when", "while",
    "after", "before", "over", "under", "about", "against", "through",
    "between", "during", "without", "within", "up", "down", "out", "off",
    "again", "further", "once", "here", "there", "all", "each", "few",
    "more", "most", "other", "some", "such", "only", "own", "same", "too",
    "very", "will", "would", "can", "could", "should", "must", "shall",
    "has", "have", "had", "do", "does", "did", "having",
}


def _has_content_word(gram: str) -> bool:
    """A gram is only a candidate tic if at least one word in it is not pure
    grammatical glue. Filters out chance recurrences of function-word strings
    like "from the" or "in a", which are common in any prose regardless of
    whether the paper is actually repeating itself."""
    return any(w not in _FUNCTION_WORDS for w in gram.split())

_WORD = re.compile(r"[A-Za-z']+")
#: A capitalised forename followed by a capitalised surname, as the writer names
#: characters. Deliberately conservative: two capitalised words in a row.
_NAME = re.compile(r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b")


def _bodies(records):
    """(dispatch index, run_date, body) triples. The index is what dedup keys on
    - it identifies a DISPATCH uniquely, even when two dispatches happen to share
    a run_date (as synthetic/test records sometimes do); run_date is carried
    through separately, purely for display in the hit's "dates" list."""
    return [(i, r.get("run_date", ""), r["dispatch"].get("body", "") or "")
            for i, r in enumerate(records)]


def _hit(kind, item, count, dates):
    return {"kind": kind, "item": item, "count": count,
            "dates": sorted(set(d for d in dates if d))[:6]}


def repeated_phrases(records, min_count=3, n_range=(3, 4)):
    """Word n-grams appearing in min_count or more DISPATCHES (not occurrences,
    so one dispatch repeating a phrase does not flag it). n_range starts at 3,
    not 2: pure function-word bigrams ("from the", "in a") recur constantly by
    chance in any prose, especially over a small archive, and are not evidence
    of a writing tic - see _has_content_word for the same guard applied to
    every gram length."""
    seen = defaultdict(set)
    dates_seen = defaultdict(set)
    for idx, date, body in _bodies(records):
        words = [w.lower() for w in _WORD.findall(body)]
        grams = set()
        for n in range(n_range[0], n_range[1] + 1):
            for i in range(len(words) - n + 1):
                g = " ".join(words[i:i + n])
                if g not in _STOP_PHRASES and _has_content_word(g):
                    grams.add(g)
        for g in grams:
            seen[g].add(idx)
            if date:
                dates_seen[g].add(date)
    out = [_hit("phrase", g, len(ds), dates_seen.get(g, set())) for g, ds in seen.items()
           if len(ds) >= min_count]
    # keep the longest phrase when one contains another, so the report is not
    # three overlapping versions of the same tic
    out.sort(key=lambda h: (-len(h["item"]), -h["count"]))
    kept = []
    for h in out:
        if not any(h["item"] in k["item"] for k in kept):
            kept.append(h)
    return sorted(kept, key=lambda h: -h["count"])


def repeated_openers(records, min_count=3, words=3):
    """The first few words of each paragraph, which is where formulaic openings
    show up ("Municipal logs reveal", "Station files show")."""
    seen = defaultdict(set)
    dates_seen = defaultdict(set)
    for idx, date, body in _bodies(records):
        for para in body.split("\n"):
            ws = [w.lower() for w in _WORD.findall(para)][:words]
            if len(ws) == words:
                key = " ".join(ws)
                if not _has_content_word(key):
                    continue
                seen[key].add(idx)
                if date:
                    dates_seen[key].add(date)
    return sorted([_hit("opener", k, len(ds), dates_seen.get(k, set()))
                   for k, ds in seen.items()
                   if len(ds) >= min_count], key=lambda h: -h["count"])


def repeated_names(records, min_count=3):
    """Character names reused across dispatches."""
    seen = defaultdict(set)
    dates_seen = defaultdict(set)
    for idx, date, body in _bodies(records):
        for first, last in _NAME.findall(body):
            key = f"{first} {last}"
            seen[key].add(idx)
            if date:
                dates_seen[key].add(date)
    return sorted([_hit("name", k, len(ds), dates_seen.get(k, set()))
                   for k, ds in seen.items()
                   if len(ds) >= min_count], key=lambda h: -h["count"])


def place_formulas(records, min_count=3):
    """Dateline PATTERNS rather than literal names, so 'New Wollongong' and
    'New Cairo' count as the same tired formula."""
    pats = [(re.compile(r"^New\s+\w+"), "New <place>"),
            (re.compile(r"^Port\s+\w+"), "Port <place>"),
            (re.compile(r"\w+-on-\w+"), "<place>-on-<place>"),
            (re.compile(r"\w+\s+Ring\b"), "<place> Ring"),
            (re.compile(r"\w+\s+Deck\b"), "<place> Deck"),
            (re.compile(r"\w+\s+Station\b"), "<place> Station")]
    seen = defaultdict(set)
    for r in records:
        place = (r["dispatch"].get("dateline") or {}).get("place") or ""
        for rx, label in pats:
            if rx.search(place):
                seen[label].add(r.get("run_date", "") or place)
    return sorted([_hit("place_formula", k, len(ds), ds) for k, ds in seen.items()
                   if len(ds) >= min_count], key=lambda h: -h["count"])


def detect(records, min_count=3):
    """Every detector, strongest first."""
    hits = (repeated_phrases(records, min_count)
            + repeated_openers(records, min_count)
            + repeated_names(records, min_count)
            + place_formulas(records, min_count))
    return sorted(hits, key=lambda h: -h["count"])
