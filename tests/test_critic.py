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
    assert r["mean_min"] == 14 and r["mean_max"] == 20
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
