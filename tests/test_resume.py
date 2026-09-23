"""The prose edition must be buyable ACROSS the day's cron runs.

23/09/2026: 55 hours stale. Google 503'd the first call of every run for two
days; the pipeline needs about fourteen consecutive successes and never got
them, while Photocopy - same key, same models - published every day because it
needs one and any run can supply it. These tests run the REAL run_pipeline
twice: the first attempt dies after the drafts are written, and the second must
publish without re-buying anything the first one already paid for.
"""
import json
import os

import pytest

import depict
import illustrate as illustrate_mod
import judge as judge_mod
import revise as revise_mod
import run as run_mod
import selection as select_stage
import write as write_stage

_BODY = ("The clerk sealed the shaft on Tuesday and nobody filed a query about "
         "the missing crew that week. ") * 9 + "Nobody asked. Nobody wrote it down. It held."


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway repo root. Patches `common._path`, the one true seam - see
    tests/test_haiku_pipeline.py for the day this was learned the hard way."""
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


def _mock_stages(monkeypatch, calls):
    def ideate(*a, **k):
        calls.append("ideate")
        return [f"premise {i}" for i in range(6)]

    def rank(premises, settings):
        calls.append("rank")
        return premises

    def select_many(premises, ledger, settings, n):
        calls.append("select")
        return premises[:n]

    def write(premise, dateline, domain, settings, *a, **k):
        calls.append(f"write:{premise}")
        return {"headline": f"H {premise}", "body": _BODY, "scene": "a scene",
                "domain": domain, "dateline": dateline, "glossary": [],
                "premise": premise}

    monkeypatch.setattr(run_mod.ideate_stage, "ideate", ideate)
    monkeypatch.setattr(run_mod, "rank_premises", rank)
    monkeypatch.setattr(select_stage, "select_many", select_many)
    monkeypatch.setattr(write_stage, "write", write)
    monkeypatch.setattr(run_mod, "maybe_revise",
                        lambda d, *a, **k: (d, {"revision_accepted": False}))
    monkeypatch.setattr(judge_mod, "judge",
                        lambda *a, **k: {"pick": 0, "score": 8, "reason": "ok"})
    monkeypatch.setattr(depict, "depict", lambda *a, **k: None)
    monkeypatch.setattr(illustrate_mod, "_cf_image", lambda *a, **k: None)
    monkeypatch.setattr(run_mod, "build_avoid_block", lambda *a, **k: "")
    monkeypatch.setattr(run_mod, "maybe_write_proposals", lambda *a, **k: None)
    return calls


def test_a_second_run_does_not_re_buy_what_the_first_one_paid_for(repo, monkeypatch):
    calls = _mock_stages(monkeypatch, [])
    run_date = run_mod.publication_date()

    # RUN ONE dies after the drafts land - the shape of a 503 outage that lets
    # the early calls through and then refuses. The failure is armed with a flag
    # rather than monkeypatch.undo(), which would also undo the repo fixture and
    # send run two at the live site.
    real_choose = run_mod.choose_draft
    outage = {"on": True}

    def choose(*a, **k):
        if outage["on"]:
            raise RuntimeError("503 high demand")
        return real_choose(*a, **k)

    monkeypatch.setattr(run_mod, "choose_draft", choose)
    with pytest.raises(RuntimeError):
        run_mod.run_pipeline()
    first = list(calls)
    assert "ideate" in first
    written = [c for c in first if c.startswith("write:")]
    assert written, "the first run must have bought some drafts"
    wip = run_mod.load_wip(run_date)
    assert wip["chosen_premises"] and len(wip["drafts"]) == len(written)

    # RUN TWO, later the same evening, on an edition date that has not filed.
    calls.clear()
    outage["on"] = False
    record = run_mod.run_pipeline()

    assert "ideate" not in calls, "the premises were already bought"
    assert "select" not in calls, "the selection was already made"
    assert not [c for c in calls if c.startswith("write:")], \
        "every draft was already written; the second run must buy none of them"
    assert record["quality"]["n_drafts"] == len(written)
    assert (repo / "index.html").exists()
    assert json.loads((repo / "data" / "dispatches" / f"{run_date}.json")
                      .read_text(encoding="utf-8"))["dispatch"]["headline"]
    assert run_mod.load_wip(run_date) == {}, "filing must clear the cache"


def test_a_resumed_run_keeps_the_datelines_it_wrote_for(repo, monkeypatch):
    """The context is sampled randomly per run. A draft written for 2183 on
    Silt-Reach must not be published under a dateline drawn fresh tonight."""
    calls = _mock_stages(monkeypatch, [])
    real_choose = run_mod.choose_draft
    outage = {"on": True}

    def choose(*a, **k):
        if outage["on"]:
            raise RuntimeError("503 high demand")
        return real_choose(*a, **k)

    monkeypatch.setattr(run_mod, "choose_draft", choose)
    with pytest.raises(RuntimeError):
        run_mod.run_pipeline()
    saved = run_mod.load_wip(run_mod.publication_date())
    ctx = saved["context"]

    calls.clear()
    outage["on"] = False
    record = run_mod.run_pipeline()
    assert record["dispatch"]["dateline"]["year"] == ctx["dateline"]["year"]
    assert record["meta"]["domain"] == ctx["domain"] if "domain" in record["meta"] \
        else record["dispatch"]["domain"] == ctx["domain"]
