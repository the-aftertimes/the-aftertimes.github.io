import json
import random

import gemini
import ideate
import selection as select_stage
import write as write_stage


SETTINGS = {
    "ideate": {"n_premises": 8, "bible_slice_size": 2, "recent_premise_window": 20},
    "novelty": {"match_threshold": 0.45, "recent_window": 30},
    "gemini": {"model": "gemini-2.5-flash", "endpoint": "x", "timeout_seconds": 1,
               "max_retries": 0, "temperature_ideate": 1.1, "temperature_write": 0.9},
}


def test_ideate_prompt_mentions_date_domain_and_avoids(rng):
    prompt = ideate.build_prompt(
        dateline={"year": 2391, "years_from_now": 365, "month": 9, "day": 4},
        domain="crime", bible_motifs=[{"term": "Nordwire", "gloss": "wire"}],
        seed_premises=["a clone sues itself"], avoid_headlines=["old headline"],
        n=8, style_guidance="A straight wire report.")
    assert "2391" in prompt and "crime" in prompt
    assert "Nordwire" in prompt
    assert "old headline" in prompt
    assert "8" in prompt
    assert "A straight wire report." in prompt


def test_ideate_returns_premise_list(monkeypatch, rng):
    monkeypatch.setattr(gemini, "generate",
                        lambda *a, **k: json.dumps({"premises": ["a", "b", "c"]}))
    out = ideate.ideate(
        dateline={"year": 2391, "years_from_now": 365, "month": 9, "day": 4},
        domain="crime", bible_motifs=[], seed_premises=[], avoid_headlines=[],
        settings=SETTINGS, style_guidance="A straight wire report.")
    assert out == ["a", "b", "c"]


def test_select_skips_non_novel(monkeypatch):
    ledger = [{"headline": "a nation abolishes money on a tuesday",
               "domain": "money", "era_bucket": 1}]
    premises = ["A nation abolishes money on a Tuesday",   # dup -> reject
                "Saturn's moon secedes over time zones"]   # novel -> keep
    chosen = select_stage.select(premises, ledger, SETTINGS)
    assert chosen == "Saturn's moon secedes over time zones"


def test_select_falls_back_to_first_when_all_stale(monkeypatch):
    monkeypatch.setattr(select_stage, "is_novel", lambda *a, **k: False)
    premises = ["one", "two"]
    assert select_stage.select(premises, [], SETTINGS) == "one"


def test_write_parses_and_hyphenates(monkeypatch):
    payload = {
        "headline": "Floating Capital Sues the Sea",
        "dateline_place": "Port Kobenhavn-2",
        "body": "An em dash sneaks in \u2014 like this.",
        "wire_name": "Nordwire", "wire_gloss": "pan-Baltic newswire",
        "domain": "law",
        "glossary": [{"term": "Tide & Wren", "gloss": "non-human law firm"}],
    }
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: json.dumps(payload))
    dispatch = write_stage.write(
        premise="a city sues the sea",
        dateline={"place": "", "year": 2391, "years_from_now": 365, "month": 9, "day": 4},
        domain="law", settings=SETTINGS, style_guidance="A straight wire report.")
    assert dispatch["dateline"]["place"] == "Port Kobenhavn-2"
    assert "\u2014" not in dispatch["body"]      # hyphenated
    assert dispatch["headline"] == "Floating Capital Sues the Sea"
    assert dispatch["glossary"][0]["term"] == "Tide & Wren"
    assert "wire" not in dispatch
