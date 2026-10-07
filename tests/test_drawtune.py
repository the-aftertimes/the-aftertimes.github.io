"""Two pictures a day and drawing notes that learn. See drawtune.py."""
import io
import json

import yaml
from PIL import Image

import drawtune
import gemini
import illustrate
import run as run_mod
import tune
from tests.test_resume import _mock_stages, repo  # noqa: F401 - fixture

CFG = {"trials": 10, "promote_at": 7, "max_lines": 4, "max_line_chars": 120}
DISPATCH = {"headline": "Surgeons Herd Loose Blood",
            "scene": "A surgeon nudges a dark pool toward a lift shaft with a foam noodle."}


def _jpeg(grey: int) -> bytes:
    """A flat image of one grey level: 128 is all mush, 0 or 255 none."""
    out = io.BytesIO()
    Image.new("L", (64, 64), grey).save(out, format="JPEG")
    return out.getvalue()


def _settings(tmp_path=None):
    s = run_mod.load_settings()
    return {**s, "image": {**s["image"], "dir": "assets/img"}}


def _state(challenger=("Seen whole from a few paces.",)):
    st = tune.empty_state()
    st["champion"] = []
    st["challenger"] = list(challenger) if challenger is not None else None
    return st


# --- the measure and the judge ---

def test_mush_reads_the_mid_grey_band():
    assert drawtune.mush(_jpeg(128)) == 100.0
    assert drawtune.mush(_jpeg(0)) == 0.0
    assert drawtune.mush(_jpeg(255)) == 0.0


def test_the_judge_is_actually_shown_both_pictures(monkeypatch):
    seen = {}

    def fake(prompt, settings, temp, model=None, retries=None, images=None):
        seen.update(prompt=prompt, images=images)
        return '{"pick": 2, "reason": "the first crops the surgeon"}'
    monkeypatch.setattr(gemini, "generate", fake)
    got = drawtune.judge(DISPATCH, b"A", b"B", _settings())
    assert seen["images"] == [b"A", b"B"]
    assert DISPATCH["scene"] in seen["prompt"]
    assert got == {"pick": 1, "reason": "the first crops the surgeon"}


def test_a_judge_that_answers_nonsense_is_no_answer(monkeypatch):
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: '{"pick": 3}')
    assert drawtune.judge(DISPATCH, b"A", b"B", _settings()) is None


# --- drawing two and choosing ---

def _draws(monkeypatch, shots, prompts=None):
    it = iter(shots)

    def cf(prompt, settings):
        if prompts is not None:
            prompts.append(prompt)
        return next(it)
    monkeypatch.setattr(illustrate, "_cf_image", cf)
    monkeypatch.setattr(illustrate, "_crop", lambda raw, frac: raw)


def test_the_judges_pick_is_published(repo, monkeypatch):  # noqa: F811
    _draws(monkeypatch, [_jpeg(0), _jpeg(128)])
    monkeypatch.setattr(drawtune, "judge",
                        lambda *a, **k: {"pick": 1, "reason": "clearer"})
    path, info = drawtune.draw(DISPATCH, "2026-10-08", _settings(), None, _state())
    assert path == "assets/img/2026-10-08.jpg"
    assert (repo / path).read_bytes() == _jpeg(128)
    assert (info["pick"], info["decided_by"]) == (1, "judge")


def test_without_a_judge_the_crisper_picture_wins(repo, monkeypatch):  # noqa: F811
    _draws(monkeypatch, [_jpeg(128), _jpeg(0)])
    monkeypatch.setattr(drawtune, "judge", lambda *a, **k: None)
    path, info = drawtune.draw(DISPATCH, "2026-10-08", _settings(), None, _state())
    assert (info["pick"], info["decided_by"]) == (1, "mush")
    assert (repo / path).read_bytes() == _jpeg(0)


def test_one_failed_draw_still_publishes_the_other(repo, monkeypatch):  # noqa: F811
    _draws(monkeypatch, [None, _jpeg(0)])
    path, info = drawtune.draw(DISPATCH, "2026-10-08", _settings(), None, _state())
    assert path and (info["pick"], info["decided_by"]) == (1, "walkover")


def test_two_failed_draws_publish_no_picture(repo, monkeypatch):  # noqa: F811
    _draws(monkeypatch, [None, None])
    path, info = drawtune.draw(DISPATCH, "2026-10-08", _settings(), None, _state())
    assert path is None and not (repo / "assets/img/2026-10-08.jpg").exists()


def test_the_challengers_notes_reach_only_the_second_draw(repo, monkeypatch):  # noqa: F811
    prompts = []
    _draws(monkeypatch, [_jpeg(0), _jpeg(0)], prompts)
    monkeypatch.setattr(drawtune, "judge", lambda *a, **k: None)
    drawtune.draw(DISPATCH, "2026-10-08", _settings(), None, _state())
    assert "Seen whole from a few paces." not in prompts[0]
    assert "Seen whole from a few paces." in prompts[1]
    # Without a challenger the day is plain best of two.
    prompts.clear()
    _draws(monkeypatch, [_jpeg(0), _jpeg(0)], prompts)
    _, info = drawtune.draw(DISPATCH, "2026-10-08", _settings(), None,
                            _state(challenger=None))
    assert info["variants"] == ["champion", "champion"] and prompts[0] == prompts[1]


# --- the notes in the prompt ---

def test_notes_are_the_first_thing_dropped_for_length():
    noted = illustrate.build_prompt(DISPATCH, None, ["Seen whole from a few paces."])
    assert "Seen whole from a few paces." in noted
    assert illustrate.build_prompt(DISPATCH, None, []) == illustrate.build_prompt(DISPATCH)
    # Sized so the scene fits the 2020 budget on its own and not with the notes.
    long_scene = {**DISPATCH, "scene": "word " * 148}
    squeezed = illustrate.build_prompt(long_scene, None, ["Seen whole from a few paces."])
    assert len(squeezed) <= illustrate.MAX_PROMPT
    assert "Seen whole" not in squeezed and "word word" in squeezed


# --- what counts, and what a note may say ---

def test_only_a_judged_day_between_different_notes_counts():
    base = {"variants": ["champion", "challenger"], "pick": 1}
    assert drawtune.outcome({**base, "decided_by": "judge"}) == "win"
    assert drawtune.outcome({**base, "pick": 0, "decided_by": "judge"}) == "loss"
    assert drawtune.outcome({**base, "decided_by": "mush"}) is None
    assert drawtune.outcome({**base, "decided_by": "walkover"}) is None
    assert drawtune.outcome({"variants": ["champion", "champion"], "pick": 0,
                             "decided_by": "judge"}) is None


def test_a_note_may_frame_the_picture_but_not_change_its_style():
    ok = "Show the subject whole from a few paces, nothing cut off."
    assert tune.valid([ok], [], CFG, drawtune._FORBIDDEN)
    for bad in ("Render it as a photograph.", "Add a red accent to the pool.",
                "Make it dreamlike.", "Draw it as a cartoon.", "Use a watercolour wash."):
        assert not tune.valid([bad], [], CFG, drawtune._FORBIDDEN), bad
    assert not tune.valid(["x" * 121], [], CFG, drawtune._FORBIDDEN)


# --- the real pipeline ---

def test_the_pipeline_draws_two_and_scores_the_day(repo, monkeypatch):  # noqa: F811
    _mock_stages(monkeypatch, [])
    _draws(monkeypatch, [_jpeg(128), _jpeg(0)])
    monkeypatch.setattr(drawtune, "judge",
                        lambda *a, **k: {"pick": 1, "reason": "the first is mush"})
    (repo / "config" / "drawing_notes.yaml").write_text(
        yaml.safe_dump(_state()), encoding="utf-8")

    record = run_mod.run_pipeline()

    pic = record["quality"]["picture"]
    assert pic["variants"] == ["champion", "challenger"]
    assert pic["decided_by"] == "judge" and pic["mush"] == [100.0, 0.0]
    assert record["quality"]["draw_tune"]["result"] == "win"
    stored = yaml.safe_load((repo / "config" / "drawing_notes.yaml")
                            .read_text(encoding="utf-8"))
    assert list(stored["results"].values()) == ["win"]
    on_disk = json.loads((repo / "data" / "dispatches" /
                          f"{record['run_date']}.json").read_text(encoding="utf-8"))
    assert on_disk["quality"]["draw_tune"]["result"] == "win"
    assert (repo / record["dispatch"]["image"]).read_bytes() == _jpeg(0)
