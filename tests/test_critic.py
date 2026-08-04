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
        "machine_phrases", "legal_register", "dash_residue", "us_spelling"}
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
