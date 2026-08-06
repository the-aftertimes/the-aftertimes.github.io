import ideate
import write as write_stage

BLOCK = 'RECENTLY OVER-USED - the paper has leaned on these lately:\n- name: "Kaelen Varma"'


def test_ideate_prompt_carries_the_block_when_given_one():
    p = ideate.build_prompt(
        dateline={"year": 2500, "years_from_now": 474}, domain="food",
        bible_motifs=[], seed_premises=[], avoid_headlines=[], n=8,
        style_guidance="A wire report.", engine_guidance="etiquette",
        place_guidance="a moon", avoid_block=BLOCK)
    assert "Kaelen Varma" in p


def test_write_prompt_carries_the_block_when_given_one():
    p = write_stage.build_prompt(
        premise="p", dateline={"year": 2500, "years_from_now": 474},
        domain="food", style_guidance="A wire report.",
        place_guidance="a moon", avoid_block=BLOCK)
    assert "Kaelen Varma" in p


def test_prompts_are_byte_identical_without_a_block():
    """The kill switch must restore the previous prompts EXACTLY, so turning the
    feature off is a genuine rollback rather than a different prompt."""
    args = dict(premise="p", dateline={"year": 2500, "years_from_now": 474},
                domain="food", style_guidance="A wire report.",
                place_guidance="a moon")
    assert write_stage.build_prompt(**args) == write_stage.build_prompt(
        **args, avoid_block="")
