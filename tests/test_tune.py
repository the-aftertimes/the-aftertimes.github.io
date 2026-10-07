"""The self-improvement loop. See tune.py."""
import json

import yaml

import run as run_mod
import tune
import write
import write as write_stage
from tests.test_resume import _mock_stages, repo  # noqa: F401 - fixture

CFG = {"trials": 10, "promote_at": 7, "max_lines": 8, "max_line_chars": 220}
DATELINE = {"year": 2300, "years_from_now": 274}


def _state(champion=("A",), challenger=("A", "B")):
    s = tune.empty_state()
    s["champion"] = list(champion)
    s["challenger"] = list(challenger) if challenger is not None else None
    return s


# --- which notes write which draft ---

def test_drafts_alternate_only_while_there_is_a_challenger():
    assert [tune.variant_for(_state(), i) for i in range(4)] == [
        "champion", "challenger", "champion", "challenger"]
    assert {tune.variant_for(_state(challenger=None), i) for i in range(4)} == {"champion"}
    assert tune.notes_for(_state(), "challenger") == ["A", "B"]
    assert tune.notes_for(_state(challenger=None), "challenger") == ["A"]


def test_no_notes_leaves_the_prompt_exactly_as_it_was():
    plain = write.build_prompt("p", DATELINE, "transport", "news")
    assert write.build_prompt("p", DATELINE, "transport", "news", house_notes=[]) == plain
    noted = write.build_prompt("p", DATELINE, "transport", "news",
                               house_notes=["Quotes are flat and procedural."])
    # Last before the output spec: what a model reads last weighs most.
    assert noted.index("Quotes are flat and procedural.") < noted.index("Return JSON only")
    assert noted.index("House notes") > noted.index("Australian English")


# --- what counts as a result ---

def test_a_day_counts_only_when_both_sides_were_in_a_real_contest():
    both = {"contest_variants": ["champion", "challenger"], "panel": {"points": [1, 2]}}
    assert tune.outcome(both, "challenger") == "win"
    assert tune.outcome(both, "champion") == "loss"
    judge_only = {"contest_variants": ["challenger", "champion"], "judge_pick": 1}
    assert tune.outcome(judge_only, "champion") == "loss"
    # A walkover: only one side's drafts survived to the contest.
    assert tune.outcome({"contest_variants": ["champion", "champion"],
                         "panel": {}}, "champion") is None
    # Chosen by the critic's score alone, which measures rule-keeping.
    assert tune.outcome({"contest_variants": ["champion", "challenger"],
                         "judge_pick": None}, "challenger") is None


def test_a_day_is_never_counted_twice():
    s = _state()
    tune.record(s, "2026-10-08", "win")
    tune.record(s, "2026-10-08", "win")
    assert s["results"] == {"2026-10-08": "win"}
    s2 = _state(challenger=None)
    tune.record(s2, "2026-10-08", "win")
    assert s2["results"] == {}


# --- promotion ---

def _with_results(wins, losses):
    s = _state()
    s["results"] = {f"d{i}": "win" for i in range(wins)}
    s["results"].update({f"e{i}": "loss" for i in range(losses)})
    return s


def test_nothing_is_decided_before_enough_days():
    s = _with_results(6, 3)
    assert tune.decide(s, CFG, "2026-10-20") is None
    assert s["challenger"] == ["A", "B"]


def test_seven_of_ten_promotes_and_keeps_the_history():
    s = _with_results(7, 3)
    assert tune.decide(s, CFG, "2026-10-20") == "promoted"
    assert s["champion"] == ["A", "B"] and s["challenger"] is None
    assert s["results"] == {}
    h = s["history"][-1]
    assert (h["verdict"], h["wins"], h["of"]) == ("promoted", 7, 10)
    assert h["champion_before"] == ["A"]


def test_six_of_ten_retires_and_the_champion_stands():
    s = _with_results(6, 4)
    assert tune.decide(s, CFG, "2026-10-20") == "retired"
    assert s["champion"] == ["A"] and s["challenger"] is None


# --- what a proposal may be ---

def test_a_proposal_is_exactly_one_edit():
    champ = ["One.", "Two."]
    assert tune.valid(["One.", "Two.", "Three."], champ, CFG)        # add
    assert tune.valid(["Two."], champ, CFG)                          # delete
    assert tune.valid(["One.", "Two, reworded."], champ, CFG)        # reword
    assert not tune.valid(["Uno.", "Dos."], champ, CFG)              # two edits
    assert not tune.valid(champ, champ, CFG)                         # no edit
    assert not tune.valid(["One.", "Two.", "x", "y"], champ, CFG)    # two adds
    assert tune.valid(["First note."], [], CFG)                      # from nothing


def test_a_proposal_cannot_ask_for_what_the_house_has_ruled_out():
    for bad in ("Escalate each paragraph further.", "Make it more absurd.",
                "Write in the first person.", "Lean into surreal imagery.",
                "Use an em dash for timing.", "Pause — then land it."):
        assert not tune.valid([bad], [], CFG), bad
    assert not tune.valid(["x" * 221], [], CFG)
    assert not tune.valid([f"n{i}" for i in range(9)], [f"n{i}" for i in range(8)], CFG)
    assert not tune.valid("not a list", [], CFG)


def test_a_failed_proposal_changes_nothing(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("503")
    monkeypatch.setattr(write_stage, "_generate_json", boom)
    s = _state(challenger=None)
    assert tune.propose(s, [], {"gemini": {"models": ["m"]}, "tune": CFG}, "d") is False
    assert s["challenger"] is None


def test_an_invalid_proposal_is_not_taken(monkeypatch):
    monkeypatch.setattr(write_stage, "_generate_json",
                        lambda *a, **k: {"notes": ["Be much more absurd."], "why": "w"})
    s = _state(challenger=None)
    assert tune.propose(s, [], {"gemini": {"models": ["m"]}, "tune": CFG}, "d") is False
    assert s["challenger"] is None


def test_a_valid_proposal_becomes_the_challenger(monkeypatch):
    monkeypatch.setattr(write_stage, "_generate_json", lambda *a, **k: {
        "notes": ["A", "Quotes are dull and procedural."], "why": "flat quotes"})
    s = _state(challenger=None)
    assert tune.propose(s, [], {"gemini": {"models": ["m"]}, "tune": CFG}, "2026-10-08")
    assert s["challenger"] == ["A", "Quotes are dull and procedural."]
    assert (s["why"], s["since"], s["results"]) == ("flat quotes", "2026-10-08", {})


# --- the real pipeline ---

def test_the_pipeline_splits_drafts_and_scores_the_day(repo, monkeypatch):  # noqa: F811
    _mock_stages(monkeypatch, [])
    seen = {}

    def write_(premise, dateline, domain, settings, *a, **k):
        seen[premise] = k.get("house_notes")
        return {"headline": f"H {premise}", "body": "x", "scene": "s",
                "domain": domain, "dateline": dateline, "glossary": [],
                "premise": premise}
    # Same body as the shared mock so the critic treats every draft alike.
    from tests.test_resume import _BODY
    monkeypatch.setattr(write_stage, "write", lambda p, dl, dom, st, *a, **k: {
        **write_(p, dl, dom, st, *a, **k), "body": _BODY})
    # Every draft clean, so the judge (mocked to pick the top) really chooses.
    monkeypatch.setattr(run_mod.critic, "score", lambda *a, **k: {
        "score": 1.0, "violations": [], "rejected": False})
    monkeypatch.setattr(run_mod.panel, "convene", lambda *a, **k: None)
    proposed = []
    monkeypatch.setattr(tune, "propose",
                        lambda *a, **k: proposed.append(1) or False)
    (repo / "config" / "house_notes.yaml").write_text(
        yaml.safe_dump(_state()), encoding="utf-8")

    record = run_mod.run_pipeline()

    notes = list(seen.values())
    assert notes[0] == ["A"] and notes[1] == ["A", "B"], notes
    t = record["quality"]["tune"]
    # The mocked judge picks the top of a tied pool, which is the first draft:
    # the champion's. So the challenger lost the day.
    assert record["quality"]["judge_pick"] == 0
    assert t["result"] == "loss" and t["variant"] == "champion"
    stored = yaml.safe_load((repo / "config" / "house_notes.yaml").read_text(
        encoding="utf-8"))
    assert list(stored["results"].values()) == [t["result"]]
    on_disk = json.loads((repo / "data" / "dispatches" /
                          f"{record['run_date']}.json").read_text(encoding="utf-8"))
    assert on_disk["quality"]["tune"] == t
    assert proposed == []                        # a challenger is still running


def test_a_broken_tune_step_never_costs_the_edition(repo, monkeypatch):  # noqa: F811
    _mock_stages(monkeypatch, [])
    monkeypatch.setattr(tune, "after_edition",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("bad yaml")))
    record = run_mod.run_pipeline()
    assert (repo / "index.html").exists()
    assert "tune" not in record["quality"]


def test_switched_off_the_prompt_carries_no_notes(repo, monkeypatch):  # noqa: F811
    _mock_stages(monkeypatch, [])
    seen = []
    real = write_stage.write
    monkeypatch.setattr(write_stage, "write",
                        lambda *a, **k: seen.append(k.get("house_notes")) or real(*a, **k))
    settings = run_mod.load_settings()
    monkeypatch.setattr(run_mod, "load_settings",
                        lambda: {**settings, "tune": {"enabled": False}})
    (repo / "config" / "house_notes.yaml").write_text(
        yaml.safe_dump(_state()), encoding="utf-8")
    record = run_mod.run_pipeline()
    assert seen and all(n == [] for n in seen)
    assert "tune" not in record["quality"]
