"""Deterministic dispatch scoring."""
import yaml

from common import rel


def test_quality_config_present_and_complete():
    with open(rel("config/settings.yaml"), encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)["quality"]
    assert cfg["n_drafts"] == 3
    assert cfg["judge"] is True
    assert cfg["revise"] is True
    assert set(cfg["hard_reject"]) == {
        "structure", "machine_phrases", "legal_register", "dash_residue",
        "us_spelling"}
    assert cfg["weights"]["major"] > cfg["weights"]["minor"] > 0
    r = cfg["rhythm"]
    # The floor was 14 until 10/08/2026, when the only trial containing lines
    # Charlie called funny was the ONLY one the critic docked - for a mean of
    # 13.7. Two of those funny lines were 6 and 10 words, so they were what
    # pulled the mean down: the floor was penalising the comedy, and revise.py
    # optimises toward the score. Assert the INVARIANT, not the old magic number.
    assert r["mean_min"] <= 12, "a high floor penalises short, funny lines"
    assert r["mean_hard_min"] < r["mean_min"] < r["mean_max"] < r["mean_hard_max"]
    assert cfg["headline_max_words"] <= 7
    assert r["longest_max"] == 35 and r["min_short"] == 2
    ln = cfg["length"]
    assert ln["hard_min"] < ln["min"] < ln["max"] < ln["hard_max"]


import critic


def _body(sentences):
    return " ".join(sentences)


def test_rhythm_flags_long_uniform_prose(quality_cfg):
    # every sentence 25 words, no short ones
    long_s = " ".join(["word"] * 24) + " end."
    v = critic.check_rhythm(critic.metrics_for(_body([long_s] * 4)), quality_cfg)
    rules = {x["rule"] for x in v}
    assert "rhythm_mean" in rules
    assert "rhythm_short" in rules


def test_rhythm_flags_an_overlong_sentence(quality_cfg):
    body = ("Short one here now. " + " ".join(["word"] * 40) + ". "
            "Also short here now.")
    v = critic.check_rhythm(critic.metrics_for(body), quality_cfg)
    assert any(x["rule"] == "rhythm_longest" and x["severity"] == "major"
               for x in v)


def test_rhythm_clean_on_good_prose(quality_cfg):
    # mean sentence length 14.0 (in range), longest 22 (<=35), two short
    # sentences (<=6 words) - deliberately built to satisfy quality_cfg's
    # rhythm thresholds rather than eyeballed prose.
    body = ("The council quietly sealed the ageing transfer shaft on a still "
            "Tuesday morning without any formal announcement or public "
            "ceremony at all. "
            "Nobody in the cramped little harbourmaster office filed a single "
            "query about the missing overnight crew during that entire "
            "uneasy week. "
            "She walked out. "
            "Three full days of formal mourning had already been scheduled "
            "for the office fern long before anyone else noticed the "
            "silence. "
            "It stayed sealed.")
    assert critic.check_rhythm(critic.metrics_for(body), quality_cfg) == []


def test_length_minor_and_major(quality_cfg):
    short = " ".join(["word"] * 180) + "."
    v = critic.check_length(critic.metrics_for(short), quality_cfg)
    assert any(x["rule"] == "length" and x["severity"] == "minor" for x in v)
    tiny = " ".join(["word"] * 100) + "."
    v = critic.check_length(critic.metrics_for(tiny), quality_cfg)
    assert any(x["rule"] == "length" and x["severity"] == "major" for x in v)


def test_machine_phrases_are_major():
    v = critic.check_phrases("The proceedings took an unexpected turn today.")
    assert v and v[0]["rule"] == "machine_phrases"
    assert v[0]["severity"] == "major"
    assert "took an unexpected turn" in v[0]["detail"]


def test_legal_register_flagged_but_not_for_the_bureaucratic_engine():
    body = "The tribunal issued a writ and the bailiff served an injunction."
    assert critic.check_register(body, "logistics")
    assert critic.check_register(body, "bureaucratic") == []


def test_present_day_props_escalate_with_distance():
    body = "She lit a candle beside the bronze plaque and drank her coffee."
    near = critic.check_props(body, 120)
    far = critic.check_props(body, 3000)
    assert near and near[0]["severity"] == "minor"
    assert far and far[0]["severity"] == "major"


def test_props_clean_text_passes():
    assert critic.check_props("The sculptor whipped the cloud perimeter.", 3000) == []


def test_stated_joke_is_only_a_minor_nudge():
    body = ("They realised the settlement was too distraught over a fern to "
            "notice the missing crew. More text follows here to pad it out.")
    v = critic.check_stated_joke(body)
    assert v and v[0]["rule"] == "stated_joke"
    assert v[0]["severity"] == "minor"


def test_stated_joke_ignores_later_paragraphs():
    body = ("The shaft was sealed on Tuesday. Nobody filed a query. "
            "Weeks later the inspector realised the logs were missing.")
    assert critic.check_stated_joke(body) == []


def test_residue_checks_detect_fixer_gaps():
    v = critic.check_residue("a" + chr(0x2014) + "b")
    assert any(x["rule"] == "dash_residue" and x["severity"] == "major"
               for x in v)
    v = critic.check_residue("the neighbor complained")
    assert any(x["rule"] == "us_spelling" and x["severity"] == "major"
               for x in v)


def test_residue_clean_text_passes():
    assert critic.check_residue("the neighbour complained - loudly") == []


def _clean_dispatch():
    """A dispatch that breaks no rule: mean sentence 15 words, longest 18, three
    short sentences, 225 words. Padded with whole SENTENCES on purpose - padding
    with a bare word list produced one 180-word sentence, which tripped
    rhythm_mean and rhythm_longest and made this fixture unpassable."""
    long_s = ("The council sealed the shaft on Tuesday and nobody filed a query "
              "about the missing crew that week. ")
    short_s = "She walked out. "
    body = (long_s * 12 + short_s * 3).strip()
    return {"headline": "Shaft Sealed Quietly", "body": body,
            "dateline": {"place": "Oronko"}}


def test_clean_dispatch_scores_well_and_is_not_rejected(quality_cfg):
    r = critic.score(_clean_dispatch(),
                     {"years_from_now": 300, "engine": "logistics"}, quality_cfg)
    assert r["rejected"] is False
    assert r["score"] > 0.8
    assert r["metrics"]["words"] > 0


def test_hard_reject_rules_set_the_rejected_flag(quality_cfg):
    d = _clean_dispatch()
    d["body"] += " The tribunal served an injunction on the bailiff."
    r = critic.score(d, {"years_from_now": 300, "engine": "logistics"},
                     quality_cfg)
    assert r["rejected"] is True
    assert any(x["rule"] == "legal_register" for x in r["violations"])


def test_engine_bureaucratic_prevents_that_rejection(quality_cfg):
    d = _clean_dispatch()
    d["body"] += " The tribunal served an injunction on the bailiff."
    r = critic.score(d, {"years_from_now": 300, "engine": "bureaucratic"},
                     quality_cfg)
    assert r["rejected"] is False


def test_score_floors_at_zero(quality_cfg):
    d = {"headline": "Neighbor" + chr(0x2014) + "Dispute",
         "body": "The proceedings took an unexpected turn. "
                 "They realised it was too odd to notice. "
                 + " ".join(["word"] * 60) + ". A tribunal issued a writ."}
    r = critic.score(d, {"years_from_now": 3000, "engine": "logistics"},
                     quality_cfg)
    assert r["score"] == 0.0
    assert r["rejected"] is True


def test_score_runs_against_the_REAL_settings_config():
    """Guards a whole class of silent failure: every other test here uses the
    hardcoded quality_cfg fixture, so renaming a key in config/settings.yaml
    would leave the suite green while production raised KeyError inside
    choose_draft and the site went stale."""
    import yaml
    with open(rel("config/settings.yaml"), encoding="utf-8") as fh:
        real = yaml.safe_load(fh)["quality"]
    d = _clean_dispatch()
    d["dateline"] = {"place": "Oronko"}
    r = critic.score(d, {"years_from_now": 300, "engine": "logistics"}, real)
    assert r["rejected"] is False
    assert r["score"] == 1.0


def test_structure_catches_a_missing_headline(quality_cfg):
    d = _clean_dispatch()
    d["dateline"] = {"place": "Oronko"}
    d["headline"] = ""
    r = critic.score(d, {"years_from_now": 300, "engine": "logistics"},
                     quality_cfg)
    assert r["rejected"] is True
    assert any(v["rule"] == "structure" and "no headline" in v["detail"]
               for v in r["violations"])


def test_structure_catches_a_missing_dateline_place_and_a_stub_body(quality_cfg):
    r = critic.score({"headline": "Fine", "body": "Three words only.",
                      "dateline": {"place": ""}},
                     {"years_from_now": 300, "engine": "logistics"}, quality_cfg)
    details = " ".join(v["detail"] for v in r["violations"]
                       if v["rule"] == "structure")
    assert "no dateline place" in details
    assert "absolute floor" in details
    assert r["rejected"] is True


def test_legal_regex_does_not_fire_on_ordinary_english():
    # "a fine morning" and "would not permit entry" used to trip a HARD REJECT.
    for innocent in ("It was a fine morning on the ridge.",
                     "The doors would not permit entry.",
                     "She paid a fine for it.",
                     "He held a licence to fish.",
                     "The insurance of continuity mattered."):
        assert critic.check_register(innocent, "logistics") == [], innocent
    # genuinely legal language still fires
    assert critic.check_register("The tribunal issued a writ.", "logistics")


def test_headline_length_is_flagged_but_never_hard_rejects():
    """Verbose headlines were Charlie's first complaint on 10/08/2026, but a
    long headline is a style miss, not a broken dispatch - it must not share the
    `structure` rule name, which IS a hard reject."""
    import critic
    from common import load_settings
    cfg = load_settings()["quality"]
    d = {"headline": "Grandmother Banished To In-Law Shade At Luminary Glades",
         "dateline": {"place": "Somewhere"},
         "body": " ".join(["word"] * 260) + "."}
    v = critic.check_structure(d, cfg)
    rules = [x["rule"] for x in v]
    assert "headline_length" in rules
    assert "structure" not in rules
    assert "headline_length" not in cfg["hard_reject"]


def test_short_headline_passes():
    import critic
    from common import load_settings
    cfg = load_settings()["quality"]
    d = {"headline": "Council Rules Snow Is Trespassing",
         "dateline": {"place": "Somewhere"},
         "body": " ".join(["word"] * 260) + "."}
    assert [x["rule"] for x in critic.check_structure(d, cfg)] == []


def test_funny_block_shows_setup_not_orphaned_lines():
    """Charlie, 10/08/2026: "the lines are funny in the context they're in, not
    just by themself". A pool of bare one-liners teaches the model that flat
    sentences are inherently funny - the opposite of the lesson."""
    import write
    pool = [{"line": "Most messages address minor domestic disputes.",
             "setup": ["Teenagers cracked the magnetosphere grid.",
                       "The graffiti spans five hundred miles."],
             "source": "t002"}]
    b = write.funny_block(pool)
    assert ">>>Most messages address minor domestic disputes.<<<" in b
    assert "Teenagers cracked the magnetosphere grid." in b
    assert "the SET-UP" in b and "SEQUENCE" in b


def test_funny_block_merges_marks_from_one_source():
    """Four marks from one paragraph must not repeat their shared setup four
    times - that bloats the prompt and over-weights one dispatch's wording."""
    import write
    setup = ["Teenagers cracked the magnetosphere grid."]
    pool = [{"line": "It spans five hundred miles.", "setup": setup, "source": "t002"},
            {"line": "Most messages are petty.",
             "setup": setup + ["It spans five hundred miles."], "source": "t002"}]
    b = write.funny_block(pool)
    assert b.count("Teenagers cracked the magnetosphere grid.") == 1
    assert ">>>It spans five hundred miles.<<<" in b
    assert ">>>Most messages are petty.<<<" in b


def test_funny_block_keeps_separate_sources_apart():
    import write
    pool = [{"line": "A landed here.", "setup": ["Setup A."], "source": "t002"},
            {"line": "B landed here.", "setup": ["Setup B."], "source": "t007"}]
    b = write.funny_block(pool)
    assert len([ln for ln in b.splitlines() if ln.startswith("  ...")]) == 2


def test_funny_block_empty_pool_is_silent():
    import write
    assert write.funny_block([]) == ""


# --- plainness: the vocabulary a reader has to decode -----------------------
# Added 17/08/2026 after Charlie said the dispatches were hard to read and used
# archaic words. He was right, and the cause was that plainness was the only
# quality dimension the critic did not measure, so it lost to every rule that
# was measured.

def _plain_cfg():
    return {"plainness": {"rate_max": 5.0, "rate_major": 7.0}}


def test_rare_words_ignores_invented_proper_nouns():
    """The paper is built on invented names; they are supposed to be unfamiliar.
    Only the ordinary vocabulary AROUND them is the readability problem."""
    import critic
    common = frozenset({"walked", "into", "the", "shaft", "with", "her", "crew"})
    hits = critic.rare_words("Amara Osei walked into Lock Four with her crew.",
                             common)
    assert hits == []


def test_rare_words_splits_hyphenated_coinages():
    """A coinage built from plain words is free; one built from archaic words is
    still caught. This is the whole point - keep the world strange, the language
    plain."""
    import critic
    common = frozenset({"seal", "brusher", "held", "spit", "tray", "and", "the"})
    assert critic.rare_words("The seal-brusher held a spit-tray.", common) == []
    assert critic.rare_words("The juris-cartographer held a spit-tray.",
                             common) == ["juris", "cartographer"]


def test_check_plainness_is_silent_on_plain_prose():
    import critic
    common = frozenset("the vault door opened and forty gold bars went down "
                       "chute he waited on railing ate a bar".split())
    body = ("The vault door opened and forty gold bars went down the chute. "
            "He waited on the railing and ate a bar.")
    assert critic.check_plainness(body, common, _plain_cfg()) == []


def test_check_plainness_flags_archaic_prose_and_names_the_words():
    """The offending words must appear in the detail line, because that string is
    what revise.py shows the model - a bare rate would be unactionable."""
    import critic
    common = frozenset("the walked past and to buy from with a of".split())
    body = " ".join(["The apothecary walked past the cobblestone hermitage to "
                     "buy lard and chrism from a gravedigger."] * 2)
    out = critic.check_plainness(body, common, _plain_cfg())
    assert len(out) == 1 and out[0]["rule"] == "plainness"
    for word in ("apothecary", "cobblestone", "hermitage", "chrism"):
        assert word in out[0]["detail"]


def test_check_plainness_escalates_to_major_past_the_upper_rate():
    """6% of the body is a minor fault, 8% a major one - the thresholds bracket
    the range the real archive actually ran at."""
    import critic
    common = frozenset({"the", "and"})
    filler = "the and " * 47                       # 94 plain words
    minor = critic.check_plainness(filler + "apothecary " * 6, common,
                                   _plain_cfg())    # 6 of 100 = 6.0%
    major = critic.check_plainness(filler + "apothecary " * 8, common,
                                   _plain_cfg())    # 8 of 102 = 7.8%
    assert minor and minor[0]["severity"] == "minor"
    assert major and major[0]["severity"] == "major"


def test_check_plainness_skipped_without_a_word_list():
    """critic.py does no file IO, so the caller supplies the vocabulary. Absent
    it the check must no-op rather than guess."""
    import critic
    assert critic.check_plainness("apothecary chrism lard", None,
                                  _plain_cfg()) == []


def test_plainness_is_never_a_hard_reject():
    """Sometimes the unfamiliar word is the right word. A taste threshold must
    cost points, never refuse to publish."""
    from common import load_settings
    assert "plainness" not in load_settings()["quality"]["hard_reject"]


def test_score_applies_plainness_when_the_caller_supplies_the_words(quality_cfg):
    import critic
    body = " ".join(["The apothecary sealed the hermitage on the Tuesday."] * 8)
    dispatch = {"headline": "Vault Door Shut", "body": body,
                "dateline": {"place": "Lock Four"}}
    common = frozenset("the sealed on tuesday".split())
    with_words = critic.score(dispatch, {"years_from_now": 200, "engine": "x",
                                         "common_words": common}, quality_cfg)
    without = critic.score(dispatch, {"years_from_now": 200, "engine": "x"},
                           quality_cfg)
    rules = [v["rule"] for v in with_words["violations"]]
    assert "plainness" in rules
    assert "plainness" not in [v["rule"] for v in without["violations"]]
    assert with_words["score"] < without["score"]


def test_a_sporting_court_is_not_the_legal_register():
    """25/08/2026: "Sentries Turn Missile Silo Into Pickleball Court" was HARD
    rejected for legal register and never reached the judge. A word-list that
    cannot tell a sport from a lawsuit should not be able to delete a draft."""
    import critic
    assert critic.check_register("They built a pickleball court.", "") == []
    assert critic.check_register("Play resumed on the indoor courts.", "") == []


def test_a_real_court_still_flags_even_beside_a_sporting_one():
    """One legal mention is enough - a piece that plays pickleball AND sues
    somebody is still leaning on the register."""
    import critic
    out = critic.check_register(
        "The pickleball court hosted a hearing after the court fined them.", "")
    assert out and "court" in out[0]["detail"]


def test_the_rest_of_the_legal_list_is_untouched():
    import critic
    out = critic.check_register("The magistrate raised a levy on the debt.", "")
    assert out and {"magistrate", "levy", "debt"} <= set(
        out[0]["detail"].split(": ")[1].split(", "))
