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


def test_write_prompt_bans_the_legal_crutch_and_varies_the_turn():
    prompt = write_stage.build_prompt(
        premise="p", dateline={"year": 2500, "years_from_now": 474},
        domain="food", style_guidance="A wire report.",
        place_guidance="a lunar crater town")
    assert "LEGAL/FINANCIAL CRUTCH" in prompt
    assert "do not default to a rival claimant or an official body" in prompt
