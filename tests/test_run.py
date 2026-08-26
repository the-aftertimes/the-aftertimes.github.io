import os

import run as run_mod


def test_inject_stale_banner_returns_false_when_no_page(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    assert run_mod.inject_stale_banner("index.html") is False


def test_inject_stale_banner_marks_existing_page(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    page = tmp_path / "index.html"
    page.write_text("<body><div class=\"wrap\">hi</div></body>", encoding="utf-8")
    assert run_mod.inject_stale_banner("index.html") is True
    assert "Showing yesterday" in page.read_text(encoding="utf-8")


def test_inject_stale_banner_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    page = tmp_path / "index.html"
    page.write_text("<body><div class=\"wrap\">hi</div></body>", encoding="utf-8")
    run_mod.inject_stale_banner("index.html")
    run_mod.inject_stale_banner("index.html")
    assert page.read_text(encoding="utf-8").count("Showing yesterday") == 1


def _stub_dispatch(tmp_path, run_date):
    d = tmp_path / "data" / "dispatches"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{run_date}.json").write_text("{}", encoding="utf-8")


def test_already_filed_is_false_when_no_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    assert run_mod.already_filed("2026-08-06") is False


def test_already_filed_is_true_once_the_day_is_filed(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    _stub_dispatch(tmp_path, "2026-08-06")
    assert run_mod.already_filed("2026-08-06") is True
    assert run_mod.already_filed("2026-08-07") is False


def test_main_skips_when_the_day_is_already_filed(tmp_path, monkeypatch, capsys):
    """The backup cron must NEVER republish over an edition already emailed."""
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(run_mod, "_load_dotenv", lambda: None)
    today = run_mod.datetime.now(run_mod.timezone.utc).date().isoformat()
    _stub_dispatch(tmp_path, today)

    def _boom():
        raise AssertionError("run_pipeline must not be called on an already-filed day")

    monkeypatch.setattr(run_mod, "run_pipeline", _boom)
    assert run_mod.main([]) == 0
    assert "already filed" in capsys.readouterr().out


def test_main_force_regenerates_an_already_filed_day(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(run_mod, "_load_dotenv", lambda: None)
    today = run_mod.datetime.now(run_mod.timezone.utc).date().isoformat()
    _stub_dispatch(tmp_path, today)
    calls = []
    monkeypatch.setattr(run_mod, "run_pipeline", lambda: calls.append(1))
    assert run_mod.main(["--force"]) == 0
    assert calls == [1]


def test_main_runs_the_pipeline_when_the_day_is_unfiled(tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "rel", lambda p: str(tmp_path / p))
    monkeypatch.setattr(run_mod, "_load_dotenv", lambda: None)
    calls = []
    monkeypatch.setattr(run_mod, "run_pipeline", lambda: calls.append(1))
    assert run_mod.main([]) == 0
    assert calls == [1]


def test_trial_sentences_split_across_paragraph_breaks():
    """Bodies carry paragraph breaks; splitting on spaces alone merged the last
    sentence of a paragraph with the first of the next, which would misalign the
    numbering Charlie marks funny sentences against."""
    import trial
    body = 'He denied it. I missed the marker.\n\nThe staff refused.'
    assert trial.split_sentences(body) == [
        "He denied it.", "I missed the marker.", "The staff refused."]


def test_trial_sentences_keep_quoted_endings_separate():
    import trial
    body = '"Your grandmother glows," she said. The staff refused to move her.'
    assert trial.split_sentences(body) == [
        '"Your grandmother glows," she said.', "The staff refused to move her."]


# --- the revise gate --------------------------------------------------------
# 22/08/2026: all three drafts scored a perfect 1.0, the critique correctly said
# the final line restated the setup, the rewrite fixed it and scored 0.92 on one
# minor violation, and the gate threw it away. From a 1.0 draft the old gate
# could only accept a score-NEUTRAL rewrite, so the revise pass was structurally
# incapable of improving comedy on exactly the days the prose was already clean.

def _qcfg(**over):
    from common import load_settings
    cfg = dict(load_settings()["quality"])
    cfg.update(over)
    return cfg


def _dispatch(tag):
    return {"headline": f"Head {tag}", "body": "A body. " * 30,
            "dateline": {"place": "P"}}


def _patch(monkeypatch, after_score, pick, before_score=1.0):
    import run as run_mod
    scores = iter([before_score, after_score])
    monkeypatch.setattr(run_mod.critic, "score",
                        lambda d, c, q: {"score": next(scores), "rejected": False,
                                         "violations": [], "metrics": {}})
    monkeypatch.setattr(run_mod.revise_mod, "revise",
                        lambda d, v, s: {"critique": "weak kicker",
                                         "dispatch": _dispatch("revised")})
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda drafts, s: {"pick": pick, "reason": "funnier"})


def test_a_slightly_worse_revision_goes_to_the_judge_and_can_win(monkeypatch):
    import run as run_mod
    _patch(monkeypatch, after_score=0.92, pick=1)
    out, info = run_mod.maybe_revise(_dispatch("draft"), {}, _qcfg(), {})
    assert info["revision_accepted"] is True
    assert out["headline"] == "Head revised"


def test_the_judge_can_still_keep_the_draft(monkeypatch):
    import run as run_mod
    _patch(monkeypatch, after_score=0.92, pick=0)
    out, info = run_mod.maybe_revise(_dispatch("draft"), {}, _qcfg(), {})
    assert info["revision_accepted"] is False
    assert out["headline"] == "Head draft"


def test_a_big_score_drop_is_never_put_to_the_judge(monkeypatch):
    """The tolerance buys one minor violation for a better joke. It must not let
    a majorly-flawed rewrite through on a model's say-so."""
    import run as run_mod
    called = []
    _patch(monkeypatch, after_score=0.5, pick=1)
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda d, s: called.append(1) or {"pick": 1, "reason": ""})
    out, info = run_mod.maybe_revise(_dispatch("draft"), {}, _qcfg(), {})
    assert info["revision_accepted"] is False and called == []


def test_a_judge_failure_keeps_the_draft(monkeypatch):
    import run as run_mod
    _patch(monkeypatch, after_score=0.92, pick=1)
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda d, s: (_ for _ in ()).throw(RuntimeError("429")))
    out, info = run_mod.maybe_revise(_dispatch("draft"), {}, _qcfg(), {})
    assert info["revision_accepted"] is False
    assert out["headline"] == "Head draft"


def test_the_judge_cannot_excuse_a_house_rule(monkeypatch):
    """Some minors are taste; the seven-word headline cap is not. The first
    reedit dry run offered a nine-word headline and the tolerance alone would
    have let it through."""
    import run as run_mod
    called = []
    scores = iter([1.0, 0.92])
    monkeypatch.setattr(run_mod.critic, "score", lambda d, c, q: {
        "score": next(scores), "rejected": False, "metrics": {},
        "violations": ([] if not called.append(0) else [])
        or ([{"rule": "headline_length", "severity": "minor", "detail": "9 words"}]
            if len(called) > 1 else [])})
    monkeypatch.setattr(run_mod.revise_mod, "revise",
                        lambda d, v, s: {"critique": "c",
                                         "dispatch": _dispatch("revised")})
    judged = []
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda d, s: judged.append(1) or {"pick": 1, "reason": ""})
    out, info = run_mod.maybe_revise(_dispatch("draft"), {}, _qcfg(), {})
    assert info["revision_accepted"] is False
    assert judged == [], "a house-rule breach must not even reach the judge"
    assert out["headline"] == "Head draft"


def test_a_pre_existing_house_rule_breach_is_not_held_against_the_revision():
    """If the DRAFT already broke the cap, the revision is not punished for
    inheriting it - only newly-introduced breaches block."""
    from common import load_settings
    assert "headline_length" in load_settings()["quality"]["revise_judge_never"]


# --- the backup cron fills a missing picture ---------------------------------

def test_a_filed_day_with_no_picture_is_retried(monkeypatch, tmp_path):
    """25/08/2026 published with no engraving. The 22:13 backup cron exists to
    catch a dropped primary, saw the day was filed, printed "nothing to do" and
    left it pictureless. "Filed" is not "complete"."""
    import run as run_mod
    called = []
    monkeypatch.setattr(run_mod, "read_json", lambda p, default=None: {
        "dispatch": {"headline": "H", "image": None}})
    import reillustrate
    monkeypatch.setattr(reillustrate, "reillustrate",
                        lambda d, scene="": called.append(d) or 0)
    assert run_mod.fill_missing_image("2026-08-25") is True
    assert called == ["2026-08-25"]


def test_a_filed_day_with_a_picture_is_left_alone(monkeypatch):
    """The backup must never redraw a good picture - that would burn a
    Cloudflare call every night and could replace a hand-corrected engraving."""
    import run as run_mod
    called = []
    monkeypatch.setattr(run_mod, "read_json", lambda p, default=None: {
        "dispatch": {"headline": "H", "image": "assets/img/x.jpg"}})
    import reillustrate
    monkeypatch.setattr(reillustrate, "reillustrate",
                        lambda d, scene="": called.append(d) or 0)
    assert run_mod.fill_missing_image("2026-08-25") is False
    assert called == []


def test_a_failed_fill_in_never_fails_the_job(monkeypatch):
    import run as run_mod
    monkeypatch.setattr(run_mod, "read_json", lambda p, default=None: {
        "dispatch": {"headline": "H", "image": None}})
    import reillustrate
    monkeypatch.setattr(reillustrate, "reillustrate",
                        lambda d, scene="": (_ for _ in ()).throw(RuntimeError("cf")))
    assert run_mod.fill_missing_image("2026-08-25") is False


# --- a pool of one is not a choice ------------------------------------------

def _scored(monkeypatch, specs):
    """specs: list of (score, rejected, rules) in draft order."""
    import run as run_mod
    it = iter(specs)
    monkeypatch.setattr(run_mod.critic, "score", lambda d, c, q: (
        lambda sc: {"score": sc[0], "rejected": sc[1], "metrics": {},
                    "violations": [{"rule": r, "severity": "major",
                                    "detail": r} for r in sc[2]]})(next(it)))


def test_a_draft_rejected_only_for_register_is_put_back_to_the_judge(monkeypatch):
    """25/08/2026: two of three drafts were hard rejected on legal_register, so
    the judge was never asked and the day was decided by elimination."""
    import run as run_mod
    _scored(monkeypatch, [(0.75, True, ["legal_register"]),
                          (0.67, True, ["legal_register"]),
                          (0.92, False, [])])
    seen = []
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda drafts, s: seen.append(len(drafts))
                        or {"pick": 0, "reason": "funnier"})
    drafts = [_dispatch("a"), _dispatch("b"), _dispatch("c")]
    out, info = run_mod.choose_draft(drafts, {}, _qcfg(), {})
    assert seen == [3], "all three should reach the judge, not just the survivor"
    assert info["judge_reason"] == "funnier"


def test_a_structurally_broken_draft_is_never_rescued(monkeypatch):
    """The rescue list is register TASTE. A missing headline is not an opinion."""
    import run as run_mod
    _scored(monkeypatch, [(0.75, True, ["structure"]),
                          (0.67, True, ["structure"]),
                          (0.92, False, [])])
    seen = []
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda drafts, s: seen.append(len(drafts))
                        or {"pick": 0, "reason": ""})
    drafts = [_dispatch("a"), _dispatch("b"), _dispatch("c")]
    run_mod.choose_draft(drafts, {}, _qcfg(), {})
    assert seen == [], "one survivor and nothing rescuable means no judge call"


def test_two_clean_drafts_are_judged_without_rescuing_anything(monkeypatch):
    import run as run_mod
    _scored(monkeypatch, [(0.75, True, ["legal_register"]),
                          (0.9, False, []), (0.92, False, [])])
    seen = []
    monkeypatch.setattr(run_mod.judge_mod, "judge",
                        lambda drafts, s: seen.append(len(drafts))
                        or {"pick": 0, "reason": ""})
    drafts = [_dispatch("a"), _dispatch("b"), _dispatch("c")]
    run_mod.choose_draft(drafts, {}, _qcfg(), {})
    assert seen == [2], "a healthy pool must not drag rejected drafts back in"
