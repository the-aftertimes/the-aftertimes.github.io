import json
import random

import gemini
import ideate
import selection as select_stage
import write as write_stage


SETTINGS = {
    "ideate": {"n_premises": 8, "bible_slice_size": 2, "recent_premise_window": 20},
    "novelty": {"match_threshold": 0.45, "recent_window": 30},
    "gemini": {"model": "gemini-3.6-flash", "write_model": "gemini-3.1-pro-preview",
               "endpoint": "x", "timeout_seconds": 1, "max_retries": 0,
               "temperature_ideate": 1.1, "temperature_write": 0.9},
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
        "scene": "a couple hides under a dining table as an armoured unit arrives",
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
    assert dispatch["scene"] == ("a couple hides under a dining table as an "
                                 "armoured unit arrives")
    assert "\u2014" not in dispatch["scene"]     # hyphenated
    assert "wire" not in dispatch


def test_write_falls_back_to_flash_when_pro_fails(monkeypatch):
    # Pro model errors (a 404/429/bad-JSON stand-in); the write stage must
    # retry on the flash default and still file a dispatch.
    flash_payload = {"headline": "Filed On Flash", "dateline_place": "Backup Bay",
                     "body": "text", "scene": "a scene", "domain": "law",
                     "glossary": []}
    calls = []

    def fake_generate(prompt, settings, temperature, model=None, retries=None):
        calls.append((model, retries))
        if model == SETTINGS["gemini"]["write_model"]:
            assert retries == 0            # Pro attempt fast-fails (no backoff)
            raise gemini.GeminiError("HTTP 429: quota")
        return json.dumps(flash_payload)

    monkeypatch.setattr(gemini, "generate", fake_generate)
    dispatch = write_stage.write(
        premise="p", dateline={"place": "", "year": 3000, "years_from_now": 974,
                               "month": 9, "day": 4},
        domain="law", settings=SETTINGS, style_guidance="A straight wire report.")
    assert dispatch["headline"] == "Filed On Flash"
    assert [c[0] for c in calls] == [SETTINGS["gemini"]["write_model"],
                                     SETTINGS["gemini"]["model"]]


def test_au_spelling_normalised_preserving_case():
    # 31/07/2026 shipped a headline reading "Neighbor's" despite the prompt.
    f = write_stage._fix_slips
    assert f("Neighbor's garden") == "Neighbour's garden"
    assert f("the neighbors complained") == "the neighbours complained"
    assert f("NEIGHBOR DISPUTE") == "NEIGHBOUR DISPUTE"
    assert f("a localized squall") == "a localised squall"
    assert f("two meters of gray snow") == "two metres of grey snow"
    assert f("the defense center") == "the defence centre"


def test_prose_report_counts_sentences_ending_inside_quotes():
    # The first version split only on (?<=[.!?])\s+, so a sentence ending
    # '...storage."' merged with the next one - inflating the mean and hiding
    # short sentences, which fired false "reads long/uniform" warnings.
    body = '"Sector 12 was mostly storage." Sector 12 remains submerged.'
    r = write_stage.prose_report(body)
    assert r["sentences"] == 2
    assert r["short_sentences"] == 2
    assert r["mean_sentence"] < 6


def test_prose_report_flags_machine_phrases_and_long_uniform_prose():
    long_body = ("The proceedings took an unexpected turn when the assembled "
                 "delegates, who had gathered under conditions of considerable "
                 "procedural formality, discovered that the entire arrangement "
                 "had been predicated upon a misapprehension of the schedule.")
    r = write_stage.prose_report(long_body)
    assert "took an unexpected turn" in r["machine_phrases"]
    assert r["mean_sentence"] > 22
    assert r["short_sentences"] == 0


def test_ise_suffix_rule_generalises_beyond_the_word_list():
    # 04/08/2026 shipped "civilization"; enumerating words one at a time does not
    # scale, so there is a general -ize/-ization -> -ise/-isation rule.
    f = write_stage._fix_slips
    assert f("Polite civilization was built") == "Polite civilisation was built"
    assert f("CIVILIZATION ENDS") == "CIVILISATION ENDS"
    assert f("they memorized it") == "they memorised it"
    assert f("sterilizing the bay") == "sterilising the bay"
    assert f("Baptized in orbit") == "Baptised in orbit"


def test_ise_rule_skips_the_size_and_prize_family():
    f = write_stage._fix_slips
    for phrase in ("the ship capsized", "downsized the crew", "a prize",
                   "the size of it", "seize the day", "resize the hull"):
        assert f(phrase) == phrase, phrase


def test_au_spelling_leaves_ambiguous_and_unrelated_words_alone():
    f = write_stage._fix_slips
    # deliberately not in the map (noun/verb or software/non-software split)
    assert "program" in f("the program ran")
    assert "license" in f("license the software")
    # word-boundary safety: no mangling inside longer words
    assert f("programmer") == "programmer"
    assert f("colorectal") == "colorectal"


def test_write_prompt_includes_place_guidance_and_bans_new_earth_cities():
    prompt = write_stage.build_prompt(
        premise="p", dateline={"year": 2914, "years_from_now": 888},
        domain="weather", style_guidance="A wire report.",
        place_guidance="a floating platform in a gas giant's atmosphere")
    assert "gas giant's atmosphere" in prompt
    assert "New Wollongong" in prompt      # named as a banned example
    assert "HEADLINE MUST CARRY THE JOKE" in prompt


def test_fix_slips_corrects_common_idioms():
    assert write_stage._fix_slips("done for all intent and purpose") == \
        "done for all intents and purposes"
    assert write_stage._fix_slips("that peaked my interest") == "that piqued my interest"
    assert write_stage._fix_slips("nothing to fix here") == "nothing to fix here"


def test_select_many_returns_n_distinct_premises():
    premises = ["a city sues the sea", "a moon secedes over time zones",
                "a fern is mourned by a whole colony",
                "an orbital cricket league refuses zero gravity"]
    out = select_stage.select_many(premises, [], SETTINGS, 3)
    assert len(out) == 3
    assert len(set(out)) == 3
    assert out[0] == premises[0]      # ideate orders strongest first


def test_select_many_drops_near_duplicate_candidates():
    premises = ["a fern is mourned by a whole colony",
                "a fern is mourned by an entire colony",
                "an orbital cricket league refuses zero gravity"]
    out = select_stage.select_many(premises, [], SETTINGS, 3)
    assert len(out) == 2
    assert "cricket" in out[1]


def test_select_many_falls_back_when_too_few_survive():
    premises = ["a fern is mourned by a whole colony",
                "a fern is mourned by an entire colony"]
    out = select_stage.select_many(premises, [], SETTINGS, 3)
    assert len(out) >= 1
    assert out[0] == premises[0]
