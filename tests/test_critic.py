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
