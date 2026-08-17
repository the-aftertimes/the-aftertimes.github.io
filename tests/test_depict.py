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
