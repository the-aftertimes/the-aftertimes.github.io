"""Guards against the paper collapsing into one comic register.

31/07/2026: every dispatch was becoming a debt/tax/lien/injunction story
("why is it always unpaid debts"). Root cause was the few-shot seeds - 8 of 12
were sue/contract/money/paperwork - since few-shots steer a model harder than
instructions. These tests keep the balance from drifting back.
"""
import re

import yaml

import ideate
import write as write_stage
from common import rel

_LEGAL = re.compile(
    r"\b(sue[sd]?|suing|lawsuit|court|contract|money|budget|tax|taxes|debt|debts"
    r"|lien|fine[sd]?|permit|licence|license|paperwork|accountant|loyalty-points"
    r"|injunction|repossess\w*|insurance|bailiff)\b", re.I)


def _load(name):
    with open(rel(f"config/{name}"), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_seed_premises_are_register_balanced():
    seeds = _load("seed_premises.yaml")["seed_premises"]
    legal = [p for p in seeds if _LEGAL.search(p)]
    # At most two, per the rule documented in seed_premises.yaml. Keep this
    # tight: few-shot examples dominate the model's output.
    assert len(legal) <= 3, f"too many legal/financial seeds: {legal}"
    assert len(legal) / len(seeds) < 0.25, "legal/financial seeds over 25%"


def test_seed_premises_cover_many_engines():
    seeds = _load("seed_premises.yaml")["seed_premises"]
    assert len(seeds) >= 15, "need a broad few-shot set to spread the register"


def test_engines_config_is_broad_and_flags_the_crutch():
    engines = _load("engines.yaml")["engines"]
    keys = {e["key"] for e in engines}
    assert len(engines) >= 10
    # the over-used register must exist but be explicitly marked as such
    assert "bureaucratic" in keys
    bureau = next(e for e in engines if e["key"] == "bureaucratic")
    assert "sparingly" in bureau["guidance"].lower()
    # and the alternatives must actually be non-legal
    for k in ("logistics", "etiquette", "sentiment", "nature", "leisure"):
        assert k in keys


def test_ideate_prompt_carries_engine_and_bans_the_crutch():
    prompt = ideate.build_prompt(
        dateline={"year": 2500, "years_from_now": 474}, domain="food",
        bible_motifs=[], seed_premises=[], avoid_headlines=[], n=8,
        style_guidance="A wire report.",
        engine_guidance="social manners, status and awkwardness")
    assert "social manners, status and awkwardness" in prompt
    assert "crutch" in prompt
    assert "repossession" in prompt


def test_no_ruling_shaped_styles():
    # 04/08/2026: style=court overrode engine=logistics and still produced
    # "High Court Orders Street Greasing For Mobile Whale Liver". A style that
    # forces a ruling shape defeats the whole engine rotation.
    styles = _load("styles.yaml")["styles"]
    keys = {s["key"] for s in styles}
    assert "court" not in keys and "notice" not in keys
    assert {"investigation", "trend", "discovery"} <= keys
    for s in styles:
        g = s["guidance"].lower()
        # a style may BAN the ruling shape ("not a ruling or a verdict"); none may
        # prescribe one
        assert "is a ruling shape" not in g, f"{s['key']} prescribes a ruling"
        assert "judicial" not in g, f"{s['key']} prescribes judicial language"
        assert "handing down" not in g, f"{s['key']} prescribes a ruling"


def test_dates_are_far_enough_out_to_feel_futuristic():
    # A 33-years-hence dispatch read as near-present. Nothing nearer than 60.
    d = _load("settings.yaml")["dates"]
    assert d["min_years"] >= 60
    assert d["bands"]["near"][0] >= 60
    # the near band must not dominate the way it did (was 0.70)
    assert d["band_weights"][0] <= 0.5


def test_prompts_require_a_satirical_target():
    ip = ideate.build_prompt(
        dateline={"year": 2500, "years_from_now": 474}, domain="food",
        bible_motifs=[], seed_premises=[], avoid_headlines=[], n=8,
        style_guidance="A wire report.", engine_guidance="etiquette")
    assert "SATIRISE SOMETHING REAL" in ip
    wp = write_stage.build_prompt(
        premise="p", dateline={"year": 2500, "years_from_now": 474},
        domain="food", style_guidance="A wire report.",
        place_guidance="a lunar crater town")
    assert "MUST BE ABOUT SOMETHING" in wp
    assert "IT MUST FEEL LIKE THE FUTURE" in wp
    assert "cobblestones" in wp        # the named anti-pattern


def test_era_rule_scales_strangeness_with_distance():
    near = write_stage._era_rule(120)
    mid = write_stage._era_rule(1500)
    deep = write_stage._era_rule(37536)
    assert "recognisable" in near
    assert "UNFAMILIAR" in mid
    assert "NOTHING of the present survives" in deep
    assert near != mid != deep


def test_prompt_bans_present_day_props_in_the_far_future():
    # 37562 AD came back with a Boston fern, candles and a bronze plaque.
    wp = write_stage.build_prompt(
        premise="p", dateline={"year": 37562, "years_from_now": 35536},
        domain="death and mourning", style_guidance="An expose.",
        place_guidance="an under-ice settlement")
    assert "35536" in wp                      # the distance is stated explicitly
    assert "Boston fern" in wp
    assert "bronze plaques" in wp
    assert "NOTHING of the present survives" in wp


def test_prompt_forbids_stating_the_joke():
    wp = write_stage.build_prompt(
        premise="p", dateline={"year": 2500, "years_from_now": 474},
        domain="food", style_guidance="A wire report.", place_guidance="a moon")
    assert "NEVER STATE THE JOKE" in wp
    assert "cannot see the joke" in wp or "cannot\nsee the joke" in wp


def test_scene_guidance_protects_the_illustrator():
    wp = write_stage.build_prompt(
        premise="p", dateline={"year": 2500, "years_from_now": 474},
        domain="food", style_guidance="A wire report.", place_guidance="a moon")
    assert "CENTRE IT ON PEOPLE" in wp
    assert "blob" in wp


def test_write_prompt_bans_the_legal_crutch_and_varies_the_turn():
    prompt = write_stage.build_prompt(
        premise="p", dateline={"year": 2500, "years_from_now": 474},
        domain="food", style_guidance="A wire report.",
        place_guidance="a lunar crater town")
    assert "LEGAL/FINANCIAL CRUTCH" in prompt
    assert "do not default to a rival claimant or an official body" in prompt


def test_hyphenate_strips_the_whole_dash_family():
    # 04/08/2026: gpt-oss-120b emits U+2011 non-breaking hyphens
    # ("grief-counselling") and nine survived the old two-character version.
    from common import hyphenate
    for cp in (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2043,
               0x2212, 0xFE58, 0xFE63, 0xFF0D):
        assert hyphenate("a" + chr(cp) + "b") == "a-b", hex(cp)


def test_prompt_forbids_copying_its_own_examples():
    # llama-3.3-70b lifted the rhythm example verbatim into a story.
    wp = write_stage.build_prompt(
        premise="p", dateline={"year": 2500, "years_from_now": 474},
        domain="food", style_guidance="A wire report.", place_guidance="a moon")
    assert "Never copy an example's words" in wp
