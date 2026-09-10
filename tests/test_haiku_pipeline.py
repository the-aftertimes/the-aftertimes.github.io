"""End-to-end proof of the haiku edition, with every model call mocked.

This is the test that had to exist before `form: haiku` could be switched on,
because the alternative verification was letting the live cron publish and
reading the result - and a daily publisher that breaks does not break quietly,
it breaks in front of the only reader. It runs the REAL run_haiku_pipeline
against a temp repo root and asserts what actually lands on disk.
"""
import json
import os

import pytest

import gemini
import illustrate as illustrate_mod
import run as run_mod

#: Forty candidates the way the model returns them. Deliberately a MIX: 3 of
#: these do not scan, so the sieve has something to remove and the test proves
#: the denominator is reported rather than assumed.
_GOOD = [
    ["the cloud licence clerk", "stamps the thunderstorm for noon",
     "dry rain takes two weeks"],
    ["four soft velvet hounds", "queued to have their barking trimmed",
     "now they hum in C"],
    ["hall sixteen was sold", "to a soap firm for nine months",
     "walls smell like fresh foam"],
]
_BAD = [["far too many syllables in this line", "short", "also wrong"]]


def _batch_json():
    items = [{"lines": l, "title": f"T{i}"} for i, l in enumerate(_GOOD)]
    items += [{"lines": l, "title": "bad"} for l in _BAD]
    return json.dumps({"place": "Carrow Shelf", "haiku": items})


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway repo root, so the test cannot touch the real site.

    PATCH `common._path`, WHICH IS THE ONE TRUE SEAM. The first version of this
    fixture patched `common.rel` plus `rel` on eight importing modules, and it
    leaked: `read_json` and `write_json` call `_path` directly, so the test
    overwrote the real 2026-09-09 dispatch and ledger with its own fixture
    haiku. It was caught by the pipeline printing `ledger=49` - a real number
    where the temp repo should have said 1 - and by `git status` immediately
    after. Everything else, `rel` included, routes through `_path`, so this one
    line is both necessary and sufficient. Never add a second patch here: a
    second one means a seam has been missed."""
    import common
    for sub in ("data/dispatches", "d", "assets/img", "config"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    real_config = common._path("config")
    for name in os.listdir(real_config):
        src = os.path.join(real_config, name)
        if os.path.isfile(src):
            (tmp_path / "config" / name).write_bytes(open(src, "rb").read())
    monkeypatch.setattr(common, "_path",
                        lambda *parts: os.path.join(str(tmp_path), *parts))
    return tmp_path


def test_the_fixture_actually_isolates_the_repo(repo):
    """The guard on the guard. If this fails, every test in this file is writing
    to the live site - which is exactly what happened on the first run."""
    import common
    assert common._path("x").startswith(str(repo))
    assert common.rel("x").startswith(str(repo)), "rel must route through _path"
    from common import write_json
    write_json("data/probe.json", {"ok": True})
    assert (repo / "data" / "probe.json").exists(), "write_json escaped the temp root"


def _mock_calls(monkeypatch, batch=None, judge_pick=1):
    """Return the raw text for each Gemini call in order: batch, judge, depict."""
    calls = []

    def fake(prompt, settings, temperature, model=None, retries=None):
        calls.append({"model": model, "prompt": prompt})
        if "Write 40 haiku" in prompt or "haiku from that place" in prompt:
            return batch if batch is not None else _batch_json()
        if "Exactly" in prompt or "haiku written for today" in prompt:
            return json.dumps({"pick": judge_pick, "score": 7,
                               "reason": "the turn lands"})
        return json.dumps({"focus": "a squat alloy weather stamp",
                           "material": "dull alloy", "surface": "a bare counter",
                           "light": "flat overhead", "wear": "a chipped edge"})

    monkeypatch.setattr(gemini, "generate", fake)
    monkeypatch.setattr(illustrate_mod, "_cf_image", lambda *a, **k: None)
    return calls


def test_a_haiku_edition_publishes_end_to_end(repo, monkeypatch):
    calls = _mock_calls(monkeypatch)
    record = run_mod.run_haiku_pipeline()

    # THE RECORD
    assert record["quality"]["form"] == "haiku"
    assert record["quality"]["asked"] == run_mod.HAIKU_BATCH
    assert record["quality"]["scanned"] == 3, "the sieve kept the wrong number"
    assert record["quality"]["failed_scan"] == 1, "the denominator must be recorded"
    assert record["quality"]["judge_score"] == 7
    assert len(record["quality"]["candidates"]) == 3, "losing haiku must be kept"

    d = record["dispatch"]
    assert d["lines"] == _GOOD[0], "the judge's pick must be what publishes"
    assert d["body"].splitlines() == _GOOD[0]
    assert d["headline"] == "T0"
    assert d["dateline"]["place"] == "Carrow Shelf", "the invented place must land"

    # THE FILES
    index = (repo / "index.html").read_text(encoding="utf-8")
    assert 'class="body poem"' in index, "the poem layout must be used"
    assert "dry rain takes two weeks" in index
    perma = repo / "d" / f"{record['run_date']}.html"
    assert perma.exists(), "the permalink must be written"
    saved = json.loads((repo / "data" / "dispatches" /
                        f"{record['run_date']}.json").read_text(encoding="utf-8"))
    assert saved["dispatch"]["lines"] == _GOOD[0]
    assert (repo / "archive.html").exists(), "the archive must be rebuilt"

    # THE CALL BUDGET. Three a day is the whole economic case for the pivot
    # against the prose pipeline's 8-13, and the free tier allows 20 per model
    # per day. A regression here is the thing that quietly breaks the paper.
    assert len(calls) == 3, f"expected 3 Gemini calls, made {len(calls)}: {calls}"


def test_the_picture_brief_has_no_people_in_it(repo, monkeypatch):
    """Every illustration Charlie called weird was a figure fault. The haiku
    brief must not carry a subject, and the flux prompt must not invent one."""
    calls = _mock_calls(monkeypatch)
    drawn = {}
    monkeypatch.setattr(illustrate_mod, "_cf_image",
                        lambda prompt, settings: drawn.setdefault("prompt", prompt))
    run_mod.run_haiku_pipeline()
    assert "a figure" not in drawn["prompt"], "an object brief invented a figure"
    assert "a squat alloy weather stamp" in drawn["prompt"]
    assert drawn["prompt"].rstrip().endswith("empty margins."), \
        "the no-caption rule must be the last thing flux reads"
    assert len(drawn["prompt"]) <= illustrate_mod.MAX_PROMPT


def test_a_judge_outage_still_publishes(repo, monkeypatch):
    """A judge failure must cost the BEST haiku, never the day."""
    def fake(prompt, settings, temperature, model=None, retries=None):
        if "haiku from that place" in prompt:
            return _batch_json()
        if "haiku written for today" in prompt:
            raise gemini.GeminiError("judge is down")
        return json.dumps({"focus": "a stamp", "material": "alloy",
                           "surface": "a counter", "light": "flat", "wear": "chip"})
    monkeypatch.setattr(gemini, "generate", fake)
    monkeypatch.setattr(illustrate_mod, "_cf_image", lambda *a, **k: None)
    record = run_mod.run_haiku_pipeline()
    assert record["dispatch"]["lines"] == _GOOD[0], "must fall back to a survivor"
    assert record["quality"]["judge_pick"] is None


def test_a_batch_where_nothing_scans_raises_rather_than_publishing(repo, monkeypatch):
    """Better to fail into the stale-banner fallback than to publish something
    that is not a haiku. main()'s guard turns this into 'keep yesterday'."""
    _mock_calls(monkeypatch,
                batch=json.dumps({"place": "X", "haiku":
                                  [{"lines": l, "title": "b"} for l in _BAD]}))
    with pytest.raises(RuntimeError, match="no haiku batch survived"):
        run_mod.run_haiku_pipeline()
    assert not (repo / "index.html").exists(), "nothing must be written"


def test_a_dead_first_model_falls_through_to_the_next(repo, monkeypatch):
    """20 calls per day PER MODEL, so the second model is the day's insurance."""
    used = []

    def fake(prompt, settings, temperature, model=None, retries=None):
        if "haiku from that place" in prompt:
            used.append(model)
            if model == run_mod.HAIKU_MODELS[0]:
                raise gemini.GeminiError("quota gone for this model")
            return _batch_json()
        if "haiku written for today" in prompt:
            return json.dumps({"pick": 1, "score": 6, "reason": "ok"})
        return json.dumps({"focus": "a stamp", "material": "alloy",
                           "surface": "a counter", "light": "flat", "wear": "chip"})
    monkeypatch.setattr(gemini, "generate", fake)
    monkeypatch.setattr(illustrate_mod, "_cf_image", lambda *a, **k: None)
    record = run_mod.run_haiku_pipeline()
    assert used[:2] == list(run_mod.HAIKU_MODELS[:2])
    assert record["dispatch"]["lines"] == _GOOD[0]


def test_settings_select_a_form_that_has_a_pipeline():
    """The switch itself.

    This pinned `== "haiku"` until 10/09/2026 and failed the moment Charlie asked
    to go back to prose - the third time a test in this repo has asserted the
    CURRENT SETTING instead of the invariant (see n_drafts and the rhythm floor
    in test_critic). A reversible switch whose test only passes in one position
    is not reversible; it just makes the way back look like a regression.

    What actually matters is that whatever is selected resolves to a pipeline."""
    import run
    from common import load_settings
    form = load_settings().get("form", "prose")
    assert form in {"prose", "haiku"}
    assert callable(run.run_haiku_pipeline if form == "haiku" else run.run_pipeline)


def test_no_brief_publishes_no_picture_rather_than_a_wrong_one(repo, monkeypatch):
    """The illustrate fallback builds its prompt from the scene line using the
    style and negative blocks that ASK for "figures in a believable environment"
    and compose "one or two clear focal figures". For a haiku that is the exact
    failure being designed out - a crowd of invented faces round the poem's
    object - so a failed brief must cost the picture, not replace it."""
    drawn = []

    def fake(prompt, settings, temperature, model=None, retries=None):
        if "haiku from that place" in prompt:
            return _batch_json()
        if "haiku written for today" in prompt:
            return json.dumps({"pick": 1, "score": 7, "reason": "ok"})
        raise gemini.GeminiError("depict is down on every model")

    monkeypatch.setattr(gemini, "generate", fake)
    monkeypatch.setattr(illustrate_mod, "_cf_image",
                        lambda *a, **k: drawn.append(1))
    record = run_mod.run_haiku_pipeline()
    assert record["dispatch"]["image"] is None
    assert record["dispatch"]["brief"] is None
    assert drawn == [], "nothing may be drawn without an object brief"
    # The edition still publishes - a pictureless day has rendered correctly
    # since August and is far better than a wrong picture.
    assert (repo / "index.html").exists()
    assert "dry rain takes two weeks" in (repo / "index.html").read_text(encoding="utf-8")


def test_the_judge_and_the_brief_walk_the_same_model_list(repo, monkeypatch):
    """20 calls a day PER MODEL. A run that got its poems from a spare model and
    then spent the judge and the brief on the exhausted one would degrade twice
    for no reason - which is what would have happened on 09/09/2026."""
    seen = []

    def fake(prompt, settings, temperature, model=None, retries=None):
        seen.append(model)
        if model == run_mod.HAIKU_MODELS[0]:
            raise gemini.GeminiError("this model's daily allowance is gone")
        if "haiku from that place" in prompt:
            return _batch_json()
        if "haiku written for today" in prompt:
            return json.dumps({"pick": 1, "score": 7, "reason": "ok"})
        return json.dumps({"focus": "a stamp", "material": "alloy",
                           "surface": "a counter", "light": "flat", "wear": "chip"})

    monkeypatch.setattr(gemini, "generate", fake)
    monkeypatch.setattr(illustrate_mod, "_cf_image", lambda *a, **k: None)
    record = run_mod.run_haiku_pipeline()
    # Every stage tried the dead model and then moved on, so all three
    # succeeded on a sibling rather than only the batch.
    assert seen.count(run_mod.HAIKU_MODELS[0]) == 3, seen
    assert record["quality"]["judge_score"] == 7, "the judge must have run"
    assert record["dispatch"]["brief"] is not None, "the brief must have run"
