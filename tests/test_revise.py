import json

import gemini
import revise

SETTINGS = {"gemini": {"model": "gemini-3.6-flash", "endpoint": "x",
                       "timeout_seconds": 1, "max_retries": 0,
                       "temperature_ideate": 1.1, "temperature_write": 0.9}}

DISPATCH = {
    "headline": "Shaft Sealed Quietly",
    "body": "Original body text.",
    "scene": "workers stand at a sealed airlock",
    "dateline": {"place": "Oronko", "year": 2600, "years_from_now": 574,
                 "month": 4, "day": 9},
    "domain": "death and mourning",
    "glossary": [],
    "premise": "a colony hides a disaster",
}

VIOLATIONS = [
    {"rule": "rhythm_mean", "detail": "mean sentence is 29 words, wanted 14-20",
     "severity": "major"},
    {"rule": "machine_phrases", "detail": "stock machine phrasing: took an "
     "unexpected turn", "severity": "major"},
]


def test_violations_render_as_plain_instructions():
    text = revise.render_violations(VIOLATIONS)
    assert "mean sentence is 29 words" in text
    assert "took an unexpected turn" in text


def test_prompt_carries_the_draft_and_the_faults():
    p = revise.build_prompt(DISPATCH, VIOLATIONS)
    assert "Original body text." in p
    assert "Shaft Sealed Quietly" in p
    assert "mean sentence is 29 words" in p
    assert "critique" in p


def test_revise_returns_a_normalised_dispatch(monkeypatch):
    payload = {"critique": "too long", "revised": {
        "headline": "Neighbor Sealed" + chr(0x2014) + "Quietly",
        "dateline_place": "Oronko", "body": "Tighter body.",
        "scene": "a sealed airlock", "domain": "death and mourning",
        "glossary": []}}
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: json.dumps(payload))
    out = revise.revise(DISPATCH, VIOLATIONS, SETTINGS)
    assert out["critique"] == "too long"
    d = out["dispatch"]
    # the same normalisation as a fresh write: AU spelling and no em dashes
    assert "Neighbour" in d["headline"]
    assert chr(0x2014) not in d["headline"]
    assert d["body"] == "Tighter body."
    assert d["premise"] == DISPATCH["premise"]
    assert d["dateline"]["year"] == 2600


def test_revise_raises_on_a_missing_revised_object(monkeypatch):
    monkeypatch.setattr(gemini, "generate",
                        lambda *a, **k: json.dumps({"critique": "fine"}))
    try:
        revise.revise(DISPATCH, VIOLATIONS, SETTINGS)
    except gemini.GeminiError:
        return
    raise AssertionError("expected GeminiError when revised is missing")
