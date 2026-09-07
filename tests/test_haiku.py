"""The syllable counter is a heuristic, so its accuracy is MEASURED here rather
than asserted in its docstring. A gate nobody has measured is a gate nobody can
size, and this one decides which candidates survive."""
import haiku

#: Hand-counted. Chosen to cover the cases the vowel-run rule gets wrong -
#: silent e, -le, -ed, diphthongs, -ion, and the ordinary words that make up
#: most of any line - rather than to flatter the counter.
FIXTURE = {
    # one syllable, including the traps
    "the": 1, "air": 1, "shift": 1, "signs": 1, "own": 1, "gone": 1, "stone": 1,
    "wave": 1, "field": 1, "hand": 1, "cold": 1, "through": 1, "though": 1,
    "hours": 1, "wires": 1, "fire": 1, "queue": 1, "eight": 1, "sealed": 1,
    "walked": 1, "cranes": 1, "loose": 1, "score": 1, "thumb": 1, "breathe": 1,
    # two
    "water": 2, "engine": 2, "machine": 2, "little": 2, "candle": 2,
    "orbit": 2, "wanted": 2, "folded": 2, "morning": 2, "020": 0, "signal": 2,
    "children": 2, "under": 2, "over": 2, "after": 2, "quiet": 2, "toward": 2,
    "nothing": 2, "someone": 2, "harvest": 2, "counter": 2, "ration": 2,
    "shoulder": 2, "distance": 2, "surface": 2, "pattern": 2, "questions": 2,
    "creature": 2, "future": 2, "iron": 2, "being": 2, "poem": 2, "island": 2,
    # three
    "everyone": 3, "memory": 3, "century": 3, "chemical": 3, "different": 3,
    "gravity": 3, "operate": 3, "understand": 3, "afternoon": 3,
    "regular": 3, "electric": 3, "material": 4, "idea": 3, "committee": 3,
    "delivery": 4, "another": 3, "beginning": 3, "important": 3, "however": 3,
    # four and up
    "ordinary": 4, "temporary": 4, "administrative": 5, "necessary": 4,
    "particular": 4, "immediately": 5, "responsible": 4, "environmental": 5,
}

#: Real 5-7-5 lines, hand-scanned, in the register the paper actually writes in.
GOOD = [
    ["the second shift signs", "for its own air at the gate", "nobody looks up"],
    ["frost on the ration", "the counter clerk folds it twice", "and signs for the loss"],
    ["they seal the deep well", "a boy leaves his name on it", "the crew paints it out"],
]


def test_syllable_counter_is_accurate_enough_to_gate_on():
    """Report the denominator and the misses, not a bare pass. A counter that is
    right 95% of the time on words is right much less often on a nine-word line,
    which is why the line-level test below matters more than this one."""
    words = {w: n for w, n in FIXTURE.items() if n}
    wrong = {w: (haiku.syllables(w), n) for w, n in words.items()
             if haiku.syllables(w) != n}
    rate = 1 - len(wrong) / len(words)
    assert rate >= 0.90, (
        f"syllable counter is {rate:.0%} accurate over {len(words)} words; "
        f"wrong: {wrong}")


def test_it_scans_real_haiku():
    for lines in GOOD:
        counts = [haiku.line_syllables(l) for l in lines]
        assert counts == [5, 7, 5], f"{lines} measured {counts}"
        assert haiku.scans(lines)


def test_it_rejects_lines_that_do_not_scan():
    assert not haiku.scans(["one", "two", "three"])
    assert not haiku.scans(["the second shift signs", "for its own air at the gate"])


def test_parse_keeps_the_good_entries_and_drops_the_broken_ones():
    """One malformed entry in twenty-four must not cost the other twenty-three."""
    got = haiku.parse([
        {"lines": ["a", "b", "c"], "title": "T"},
        {"lines": ["only", "two"]},
        "not an object",
        {"lines": "x\ny\nz", "title": "S"},
    ])
    assert [g["title"] for g in got] == ["T", "S"]
    assert got[1]["lines"] == ["x", "y", "z"]


def test_the_prompt_asks_for_the_whole_batch_in_one_call():
    p = haiku.build_prompt({"place": "Kalyani", "year": 4402,
                            "years_from_now": 2376}, "orbit", 24)
    assert "24 haiku" in p
    assert "Kalyani" in p and "4402" in p and "2376" in p
    assert "DIFFERENT from the others" in p
