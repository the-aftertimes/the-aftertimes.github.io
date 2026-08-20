"""The structured visual brief, ported from photocopy 17/08/2026."""
import depict
import illustrate


def _brief(**over):
    b = {"subject": "a brass mannequin", "action": "kneeling, facing left",
         "setting": "a flooded parade hall", "light": "hard, from a high window",
         "materials": "brass, wet stone, canvas", "anomaly": "one hand replaced by a ladle"}
    b.update(over)
    return b


def test_prompt_puts_the_negative_last():
    """flux weights the tail hardest, and the slots are exactly what tempts it to
    render lettering - a no-text clause in front of them loses the argument."""
    p = illustrate.build_prompt({}, _brief())
    assert p.rstrip().endswith("purely pictorial.")
    assert p.index("Materials:") < p.index("purely pictorial")


def test_prompt_skips_empty_slots_rather_than_emitting_them_blank():
    """A dangling 'Light: .' is read by flux as an instruction about punctuation."""
    p = illustrate.build_prompt({}, _brief(light="", materials=""))
    assert "Light:" not in p
    assert "Materials:" not in p
    assert ". ." not in p


def test_prompt_assembles_slots_in_schema_order():
    p = illustrate.build_prompt({}, _brief())
    order = [p.index(s) for s in ("brass mannequin", "kneeling", "parade hall",
                                  "high window", "wet stone", "ladle")]
    assert order == sorted(order)


def test_falls_back_to_the_scene_line_without_a_brief():
    p = illustrate.build_prompt({"scene": "a whale on a gantry", "headline": "H"}, None)
    assert 'depicts this scene: "a whale on a gantry"' in p
    assert p.rstrip().endswith("purely pictorial.")


def test_fallback_uses_the_headline_when_there_is_no_scene():
    p = illustrate.build_prompt({"scene": "", "headline": "Mine Denies Grief"}, None)
    assert "Mine Denies Grief" in p


def test_text_artefacts_are_stripped_from_a_brief():
    """A brief naming a sign hands flux the instruction the prompt spends a whole
    sentence forbidding."""
    out = depict.parse({"subject": "a kiosk", "anomaly": "a sign reading CLOSED.",
                        "setting": "a tiled arcade"})
    assert out["anomaly"] == ""
    assert out["subject"] == "a kiosk"


def test_text_artefact_strip_keeps_the_clean_clause_of_a_mixed_value():
    out = depict.parse({"subject": "a brass valve; a label reading 40 PSI"})
    assert out["subject"] == "a brass valve"


def test_is_usable_needs_a_subject_and_three_slots():
    assert depict.is_usable(_brief()) is True
    assert depict.is_usable({"subject": "", "action": "a", "setting": "b",
                             "light": "c"}) is False
    assert depict.is_usable({"subject": "a", "action": "b"}) is False


def test_parse_tolerates_missing_keys():
    out = depict.parse({"subject": "a mannequin"})
    assert set(out) == set(depict.FIELDS)
    assert out["materials"] == ""


def test_parse_rejects_a_non_object():
    import pytest
    with pytest.raises(ValueError):
        depict.parse(["not", "an", "object"])


def test_depict_returns_none_when_gemini_fails(monkeypatch):
    """A missing brief must cost a better picture, never the picture."""
    monkeypatch.setattr(depict.gemini, "generate",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("429")))
    from common import load_settings
    assert depict.depict({"headline": "H", "body": "B"}, load_settings()) is None


def test_depict_returns_none_on_a_thin_brief(monkeypatch):
    monkeypatch.setattr(depict.gemini, "generate", lambda *a, **k: '{"subject": "x"}')
    from common import load_settings
    assert depict.depict({"headline": "H", "body": "B"}, load_settings()) is None


def test_brief_must_centre_the_person_the_headline_is_about():
    """18/08/2026: a dispatch about six nuns guarding a burst pipe was
    illustrated as a lone station fitter at a cart. The brief was plain, real and
    faithful to a moment in the story - and unrecognisable as that story. The
    one-or-two-figures rule is settled house style, so the fix is WHICH figure,
    not how many."""
    prompt = depict.build_prompt({"headline": "Nuns Block Pipe Repair",
                                  "scene": "six nuns with wrenches",
                                  "body": "A fitter waited, bored."})
    # Reworded 19/08 when this stage stopped choosing at all: the subject is no
    # longer something depict picks correctly, it is something it copies.
    assert "The `subject` is the scene's subject" in prompt
    assert "bystanding fitter" in prompt          # the failure kept as evidence
    # the focal-subject rule must survive the fix, not be traded away for it
    assert "THE SUBJECT IS ONE PERSON, or at most two" in prompt


def test_brief_must_dress_the_whole_person():
    """19/08/2026: a brief named a jumper and boots and nothing between them, and
    flux filled the gap with bare legs and a reclining pose. Charlie: "today's
    image was a bit lewd." Any body part the brief leaves unspecified is one the
    renderer decides about."""
    prompt = depict.build_prompt({"headline": "H", "scene": "s", "body": "b"})
    assert "DESCRIBE THE WHOLE OF WHAT THE SUBJECT IS WEARING" in prompt
    assert "dressed for work" in prompt


def test_depict_specifies_the_given_scene_and_never_rechooses():
    """19/08/2026, third wrong picture running. Every previous fix tried to make
    this stage choose BETTER; the fix is that it does not choose at all. The
    writer already picked the moment, knowing the whole story, and the figure cap
    means a plural scene gets cut down to one - so the writer does the cutting,
    where the judgement is, rather than the picture editor guessing.

    The label matters as much as the instruction: it used to read SUGGESTED
    SCENE, and a suggestion is a thing you may decline."""
    prompt = depict.build_prompt({"headline": "H", "scene": "s", "body": "b"})
    assert "SUGGESTED SCENE" not in prompt
    assert "THE SCENE TO DRAW (not a suggestion - draw this)" in prompt
    assert "not to pick a different" in prompt
    assert "do not pick a moment from it" in prompt
    # the cap must survive the rewrite - though 20/08 moved it from the FRAME to
    # the subject, once Charlie saw a background group and liked it
    assert "THE SUBJECT IS ONE PERSON, or at most two" in prompt
    assert "not on the picture" in prompt


def test_flux_prompt_dresses_everyone_and_bans_posing():
    """The brief is one guard; the image prompt is the other. flux weights the
    tail of a prompt most heavily, so this lives in the negative block."""
    import illustrate
    out = illustrate.build_prompt({"headline": "H", "scene": "s"},
                                  {"subject": "a woman in a jumper"})
    for clause in ("fully and modestly clothed", "No nudity", "no bare legs",
                   "posed suggestively"):
        assert clause in out, clause
    # and it must still come after the slots, or it loses the argument
    assert out.index("a woman in a jumper") < out.index("No nudity")
